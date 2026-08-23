import json
from collections.abc import Callable

from config import MAX_TOOL_OUTPUT_CHARS, WORKING_DIR
from functions.decode_data import decode_data, schema_decode_data
from functions.get_file_content import get_file_content, schema_get_file_content
from functions.get_files_info import get_files_info, schema_get_files_info
from functions.inspect_file import inspect_file, schema_inspect_file
from functions.netcat_connect import netcat_connect, schema_netcat_connect
from functions.run_command import run_command, schema_run_command
from functions.run_python_file import run_python_file, schema_run_python_file
from functions.web_request import web_request, schema_web_request
from functions.write_file import schema_write_file, write_file

available_functions: list = [
    schema_get_files_info,
    schema_get_file_content,
    schema_run_python_file,
    schema_write_file,
    schema_decode_data,
    schema_inspect_file,
    schema_web_request,
    schema_netcat_connect,
    schema_run_command,
]

function_map: dict[str, Callable[..., str]] = {
    "get_files_info": get_files_info,
    "get_file_content": get_file_content,
    "run_python_file": run_python_file,
    "write_file": write_file,
    "decode_data": decode_data,
    "inspect_file": inspect_file,
    "web_request": web_request,
    "netcat_connect": netcat_connect,
    "run_command": run_command,
}


def call_function(tool_call, verbose: bool = False) -> dict:
    function_name = tool_call.function.name
    try:
        function_args = json.loads(tool_call.function.arguments or "{}")
    except Exception:
        function_args = {}

    if verbose:
        print(f"[Action] Calling function: {function_name}")
        print(f"  Arguments:\n{json.dumps(function_args, indent=4)}")
    else:
        args_str = ", ".join(f"{k}={v!r}" for k, v in function_args.items() if k != "working_directory")
        if args_str:
            print(f"[Action] Calling function: {function_name}({args_str})")
        else:
            print(f"[Action] Calling function: {function_name}")

    if function_name not in function_map:
        err_msg = f"Error: Unknown function: {function_name}"
        print(f"  Result: {err_msg}")
        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": err_msg,
        }

    function_args["working_directory"] = WORKING_DIR

    try:
        result = function_map[function_name](**function_args)
    except Exception as e:
        result = f"Error executing {function_name}: {e}"

    if len(result) > MAX_TOOL_OUTPUT_CHARS:
        result = result[:MAX_TOOL_OUTPUT_CHARS] + f"\n[... Output truncated at {MAX_TOOL_OUTPUT_CHARS} characters ...]"

    if verbose:
        print(f"  Tool Output ({len(result)} chars):")
        for line in result.splitlines():
            print(f"    {line}")
    else:
        lines = [line.strip() for line in result.splitlines() if line.strip()]
        if not lines:
            snippet = "(empty output)"
        elif len(lines) == 1 and len(lines[0]) <= 100:
            snippet = lines[0]
        else:
            snippet = lines[0][:80] + f"... (+{len(lines)-1} more lines, {len(result)} chars total)"
        print(f"  Output: {snippet}")

    return {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": result,
    }


