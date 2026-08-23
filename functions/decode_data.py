import base64
import urllib.parse


def decode_data(working_directory: str, data: str, operation: str, encoding_type: str, key: str = "") -> str:
    try:
        op = operation.lower().strip()
        enc = encoding_type.lower().strip()

        if enc == "hex":
            if op == "encode":
                return data.encode().hex()
            else:
                return bytes.fromhex(data.replace(" ", "").replace("0x", "")).decode("utf-8", errors="replace")

        elif enc == "base64":
            if op == "encode":
                return base64.b64encode(data.encode()).decode()
            else:
                padded = data + "=" * (-len(data) % 4)
                return base64.b64decode(padded).decode("utf-8", errors="replace")

        elif enc == "binary":
            if op == "encode":
                return " ".join(format(b, "08b") for b in data.encode())
            else:
                bits = data.replace(" ", "")
                if len(bits) % 8 != 0:
                    return "Error: Binary string length must be a multiple of 8"
                return "".join(chr(int(bits[i:i+8], 2)) for i in range(0, len(bits), 8))

        elif enc == "url":
            if op == "encode":
                return urllib.parse.quote(data, safe="")
            else:
                return urllib.parse.unquote(data)

        elif enc in ("rot13", "caesar"):
            shift = 13
            if enc == "caesar" and key:
                try:
                    shift = int(key) % 26
                except ValueError:
                    return "Error: Caesar key must be an integer shift value"
            result = []
            for ch in data:
                if ch.isalpha():
                    base = ord("A") if ch.isupper() else ord("a")
                    offset = shift if op == "encode" else -shift
                    result.append(chr((ord(ch) - base + offset) % 26 + base))
                else:
                    result.append(ch)
            return "".join(result)

        elif enc == "xor":
            if not key:
                return "Error: XOR requires a 'key' parameter (hex string or plain text)"
            k = key.strip()
            if k.startswith("0x"):
                key_bytes = bytes.fromhex(k[2:])
            else:
                try:
                    key_bytes = bytes.fromhex(k)
                except ValueError:
                    key_bytes = k.encode()
            try:
                data_bytes = bytes.fromhex(data.replace(" ", "").replace("0x", ""))
            except ValueError:
                data_bytes = data.encode()
            return bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(data_bytes)).decode("utf-8", errors="replace")

        else:
            return f"Error: Unsupported encoding_type '{encoding_type}'. Choose from: hex, base64, binary, url, rot13, caesar, xor"

    except Exception as e:
        return f"Error in decode_data: {e}"


schema_decode_data = {
    "type": "function",
    "function": {
        "name": "decode_data",
        "description": "Encode or decode data using common CTF encoding/cryptography schemes. Supports: hex, base64, binary, url, rot13, caesar (with shift key), and xor (with a hex or text key).",
        "parameters": {
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "The input string to encode or decode."},
                "operation": {"type": "string", "enum": ["encode", "decode"], "description": "Whether to encode or decode the data."},
                "encoding_type": {"type": "string", "enum": ["hex", "base64", "binary", "url", "rot13", "caesar", "xor"], "description": "The encoding/cipher scheme to apply."},
                "key": {"type": "string", "description": "Optional key for XOR (hex bytes or plain text) or Caesar cipher (integer shift as string)."},
            },
            "required": ["data", "operation", "encoding_type"],
        },
    },
}
