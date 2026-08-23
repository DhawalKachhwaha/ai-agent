import socket


def netcat_connect(working_directory: str, host: str, port: int, send_data: str = "", timeout: int = 5) -> str:
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            initial_data = b""
            try:
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    initial_data += chunk
                    sock.settimeout(0.5)
            except (socket.timeout, BlockingIOError):
                pass

            response_data = b""
            if send_data:
                payload = send_data if send_data.endswith("\n") else send_data + "\n"
                sock.sendall(payload.encode("utf-8"))
                sock.settimeout(timeout)
                try:
                    while True:
                        chunk = sock.recv(4096)
                        if not chunk:
                            break
                        response_data += chunk
                        sock.settimeout(0.5)
                except (socket.timeout, BlockingIOError):
                    pass

        parts = []
        if initial_data:
            parts.append("=== Banner / Initial Response ===\n" + initial_data.decode("utf-8", errors="replace"))
        if response_data:
            parts.append("=== Response to Sent Data ===\n" + response_data.decode("utf-8", errors="replace"))
        if not parts:
            return f"Connected to {host}:{port} — no data received."
        return "\n".join(parts)

    except ConnectionRefusedError:
        return f"Error: Connection refused to {host}:{port}"
    except socket.timeout:
        return f"Error: Connection to {host}:{port} timed out after {timeout}s"
    except OSError as e:
        return f"Error connecting to {host}:{port}: {e}"
    except Exception as e:
        return f"Error in netcat_connect: {e}"


schema_netcat_connect = {
    "type": "function",
    "function": {
        "name": "netcat_connect",
        "description": "Connect to a remote TCP server (like `nc host port`), read any banner or initial prompt, optionally send a line of data, and return the response.",
        "parameters": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Hostname or IP address of the target server."},
                "port": {"type": "integer", "description": "TCP port number to connect to."},
                "send_data": {"type": "string", "description": "Optional string to send after connecting. A newline is appended automatically if not present."},
                "timeout": {"type": "integer", "description": "Connection and read timeout in seconds. Defaults to 5."},
            },
            "required": ["host", "port"],
        },
    },
}
