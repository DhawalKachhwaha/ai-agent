import subprocess

_BLOCKED = frozenset({
    "rm", "rmdir", "mkfs", "dd", "shred",
    "shutdown", "reboot", "halt", "poweroff",
    "chmod", "chown", "sudo", "su",
    "wget", "curl",
})

def run_command(working_directory: str, command: list[str], timeout: int = 10) -> str:
    try:
        if not command:
            return "Error: command list is empty."
        if command[0].strip() in _BLOCKED:
            return f"Error: Execution of '{command[0]}' is not permitted. Blocked commands: {sorted(_BLOCKED)}"
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, cwd=working_directory)
        parts = []
        if result.stdout:
            parts.append(f"=== STDOUT ===\n{result.stdout}")
        if result.stderr:
            parts.append(f"=== STDERR ===\n{result.stderr}")
        parts.append(f"=== Exit Code: {result.returncode} ===")
        combined = "\n".join(parts)
        if len(combined) > 8192:
            combined = combined[:8192] + "\n[... output truncated at 8192 characters ...]"
        return combined
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds: {command}"
    except FileNotFoundError:
        return f"Error: Executable not found: '{command[0]}'. Is it installed?"
    except PermissionError:
        return f"Error: Permission denied running: {command}"
    except Exception as e:
        return f"Error running command {command}: {e}"

schema_run_command = {
    "type": "function",
    "function": {
        "name": "run_command",
        "description": "Execute a CLI command as a subprocess and return its stdout, stderr, and exit code. Use for standard UNIX forensics/CTF tools such as: file, strings, binwalk, xxd, exiftool, zipinfo, objdump, grep, hexdump, etc. Destructive commands and network downloaders are blocked.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "array", "items": {"type": "string"}, "description": "Command to run as a list of strings, e.g. ['binwalk', '-e', 'image.png']."},
                "timeout": {"type": "integer", "description": "Maximum runtime in seconds. Defaults to 10."},
            },
            "required": ["command"],
        },
    },
}
