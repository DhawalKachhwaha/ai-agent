import argparse
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

from call_function import available_functions, call_function
from config import MAX_HISTORY_TURNS, MAX_ITERS, MAX_OLD_TOOL_OUTPUT_CHARS
from prompts import system_prompt


def _get_role(msg) -> str | None:
    if isinstance(msg, dict):
        return msg.get("role")
    return getattr(msg, "role", None)


def _get_content(msg) -> str:
    if isinstance(msg, dict):
        return msg.get("content") or ""
    return getattr(msg, "content", "") or ""


def trim_messages(
    messages: list,
    max_turns: int = MAX_HISTORY_TURNS,
    max_old_tool_chars: int = MAX_OLD_TOOL_OUTPUT_CHARS,
    verbose: bool = False,
) -> list:
    if len(messages) <= 1:
        return messages

    header = messages[:1]
    history = messages[1:]

    turns = []
    current_turn = []
    for msg in history:
        role = _get_role(msg)
        if role == "user" and current_turn:
            turns.append(current_turn)
            current_turn = []
        current_turn.append(msg)
    if current_turn:
        turns.append(current_turn)

    if len(turns) > max_turns:
        if verbose:
            print(f"[Verbose] History trim: keeping last {max_turns} turns out of {len(turns)} turns.")
        turns = turns[-max_turns:]

    trimmed = []
    for i, turn in enumerate(turns):
        is_latest = (i == len(turns) - 1)
        for msg in turn:
            role = _get_role(msg)
            if role == "tool" and not is_latest:
                content = _get_content(msg)
                if len(content) > max_old_tool_chars:
                    if verbose:
                        print(f"[Verbose] Truncating old tool output from {len(content)} to {max_old_tool_chars} chars.")
                    tool_id = msg.get("tool_call_id") if isinstance(msg, dict) else getattr(msg, "tool_call_id", "")
                    msg = {
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": content[:max_old_tool_chars] + f"\n[... Output truncated to {max_old_tool_chars} chars ...]",
                    }
            trimmed.append(msg)

    return header + trimmed


def generate_content(client: OpenAI, messages: list, verbose: bool) -> str | None:
    model = os.environ.get("MODEL")
    if not model:
        raise RuntimeError("MODEL environment variable not set")

    max_attempts = 3
    response = None

    for attempt in range(max_attempts):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=available_functions,
            )
            break
        except Exception as e:
            err_msg = str(e).lower()
            if any(term in err_msg for term in ("context", "token", "length", "too long", "exceed")):
                if verbose:
                    print("\n[Verbose] Context window limit hit, aggressively pruning history and retrying...")
                messages[:] = trim_messages(messages, max_turns=2, max_old_tool_chars=200, verbose=verbose)
            elif any(term in err_msg for term in ("parse", "tool call", "500", "syntax error", "invalid string")):
                if verbose:
                    print(f"\n[Verbose] Tool call JSON parse error from provider (Attempt {attempt + 1}/{max_attempts}). Retrying with prompt guidance...")
                messages.append({
                    "role": "user",
                    "content": "Notice: The previous tool call failed because the generated JSON arguments contained unescaped quotes or invalid string syntax. Please retry calling the tool with simpler string formatting.",
                })
            else:
                if attempt == max_attempts - 1:
                    raise
                if verbose:
                    print(f"\n[Verbose] API error encountered (Attempt {attempt + 1}/{max_attempts}): {e}. Retrying...")

    if not response or not response.usage:
        raise RuntimeError("API response appears to be malformed or empty after retries")


    if verbose:
        prompt_tokens = response.usage.prompt_tokens or 0
        completion_tokens = response.usage.completion_tokens or 0
        print(f"[Verbose] Tokens - Prompt: {prompt_tokens} | Completion: {completion_tokens} | Total: {prompt_tokens + completion_tokens}")

    message = response.choices[0].message
    messages.append(message)

    content = message.content or ""

    if content.strip():
        if message.tool_calls:
            print(f"\n[Thought]\n{content.strip()}\n")
        else:
            print(f"\nAgent:\n{content.strip()}\n")

    if not message.tool_calls:
        return content

    for tool_call in message.tool_calls:
        if tool_call.type != "function":
            continue
        result_message = call_function(tool_call, verbose)
        if not result_message.get("content"):
            raise RuntimeError(f"Empty function response for {tool_call.function.name}")
        messages.append(result_message)

    return None


def process_user_prompt(client: OpenAI, messages: list, user_input: str, verbose: bool) -> None:
    messages.append({"role": "user", "content": user_input})

    for iteration in range(1, MAX_ITERS + 1):
        if verbose:
            print(f"\n[Verbose] --- Iteration {iteration}/{MAX_ITERS} ---")

        messages[:] = trim_messages(messages, verbose=verbose)

        try:
            final_response = generate_content(client, messages, verbose)
            if final_response is not None:
                return
        except KeyboardInterrupt:
            print("\n[Execution interrupted by user.]")
            return
        except RuntimeError as e:
            print(f"\n[Error] Agent execution error: {e}")
            return
        except Exception as e:
            print(f"\n[Error] Agent execution error: {e}")
            return

    print(f"\n[Warning] Maximum iterations ({MAX_ITERS}) reached for this turn.")



def run_chat_loop(client: OpenAI, initial_prompt: str | None = None, verbose: bool = False) -> None:
    print("-" * 50)
    print("AI Agent Chat Interface")
    print("Commands: 'exit', 'quit', 'q' to end | '/clear' to reset history | '/help' for commands")
    if verbose:
        print("Mode: VERBOSE")
    print("-" * 50 + "\n")

    messages = [{"role": "system", "content": system_prompt}]

    if initial_prompt:
        print(f"You: {initial_prompt}")
        process_user_prompt(client, messages, initial_prompt, verbose)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting chat session.")
            break

        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in ("exit", "quit", "q"):
            print("\nExiting chat session.")
            break

        if cmd == "/clear":
            messages = [{"role": "system", "content": system_prompt}]
            print("\nConversation history cleared.")
            continue

        if cmd == "/help":
            print("\nAvailable commands:")
            print("  /clear  - Clear conversation history")
            print("  /help   - Show this help message")
            print("  exit    - End chat session")
            continue

        process_user_prompt(client, messages, user_input, verbose)



def main() -> None:
    parser = argparse.ArgumentParser(description="AI Code Assistant Chat Interface")
    parser.add_argument("user_prompt", type=str, nargs="?", default=None, help="Optional initial prompt to send to the LLM")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    api = os.environ.get("API")

    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY environment variable not set")
    if not api:
        raise RuntimeError("API environment variable not set")

    client = OpenAI(base_url=api, api_key=api_key)

    run_chat_loop(client, initial_prompt=args.user_prompt, verbose=args.verbose)


if __name__ == "__main__":
    main()

