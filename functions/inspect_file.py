import os
import struct

_MAGIC_SIGNATURES = [
    (b"\x89PNG\r\n\x1a\n", "PNG image"),
    (b"\xff\xd8\xff", "JPEG image"),
    (b"GIF87a", "GIF image (87a)"),
    (b"GIF89a", "GIF image (89a)"),
    (b"%PDF-", "PDF document"),
    (b"PK\x03\x04", "ZIP archive (or docx/xlsx/jar)"),
    (b"PK\x05\x06", "ZIP archive (empty)"),
    (b"PK\x07\x08", "ZIP archive (spanned)"),
    (b"\x1f\x8b", "GZIP compressed data"),
    (b"BZh", "BZIP2 compressed data"),
    (b"\xfd7zXZ\x00", "XZ compressed data"),
    (b"7z\xbc\xaf'\x1c", "7-Zip archive"),
    (b"Rar!\x1a\x07\x00", "RAR archive (v4)"),
    (b"Rar!\x1a\x07\x01\x00", "RAR archive (v5)"),
    (b"\x7fELF", "ELF executable"),
    (b"MZ", "Windows PE/MZ executable"),
    (b"\xca\xfe\xba\xbe", "Java class file / Mach-O FAT binary"),
    (b"\xfe\xed\xfa\xce", "Mach-O 32-bit"),
    (b"\xce\xfa\xed\xfe", "Mach-O 32-bit (reversed)"),
    (b"\xfe\xed\xfa\xcf", "Mach-O 64-bit"),
    (b"\xcf\xfa\xed\xfe", "Mach-O 64-bit (reversed)"),
    (b"OggS", "Ogg container"),
    (b"fLaC", "FLAC audio"),
    (b"ID3", "MP3 audio (ID3 tag)"),
    (b"RIFF", "RIFF container (WAV/AVI)"),
    (b"\x00\x00\x00\x18ftypmp42", "MP4 video"),
    (b"\x00\x00\x00\x20ftyp", "MP4/M4A video"),
    (b"BM", "BMP image"),
    (b"\x00\x00\x01\x00", "ICO icon"),
    (b"<!DOCTYPE html", "HTML document"),
    (b"<html", "HTML document"),
    (b"<?xml", "XML document"),
    (b"SQLite format 3", "SQLite database"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "Microsoft Office legacy (DOC/XLS/PPT)"),
]


def _identify_magic(data: bytes) -> str:
    for magic, description in _MAGIC_SIGNATURES:
        if data.startswith(magic):
            return description
    hex_preview = data[:16].hex()
    if all(32 <= b < 127 for b in data[:512]):
        return f"Plain text / ASCII data (first 16 bytes hex: {hex_preview})"
    return f"Unknown binary format (first 16 bytes hex: {hex_preview})"


def _extract_metadata(file_path: str, data: bytes) -> str:
    lines = [f"File size : {len(data)} bytes"]

    if data[:8] == b"\x89PNG\r\n\x1a\n":
        if len(data) >= 24:
            width = struct.unpack(">I", data[16:20])[0]
            height = struct.unpack(">I", data[20:24])[0]
            lines.append("Image type: PNG")
            lines.append(f"Dimensions: {width} x {height} px")
            lines.append(f"Bit depth : {data[24] if len(data) > 24 else '?'}, Color type: {data[25] if len(data) > 25 else '?'}")

    elif data[:3] == b"\xff\xd8\xff":
        lines.append("Image type: JPEG")
        i = 2
        while i < len(data) - 4:
            if data[i] != 0xFF:
                break
            marker = data[i+1]
            length = struct.unpack(">H", data[i+2:i+4])[0]
            if marker == 0xE0 and data[i+4:i+8] == b"JFIF":
                lines.append("Contains: JFIF APP0 segment")
            elif marker == 0xE1 and data[i+4:i+8] == b"Exif":
                lines.append("Contains: EXIF APP1 segment")
            i += 2 + length

    elif data[:4] == b"\x7fELF":
        arch = {1: "32-bit", 2: "64-bit"}.get(data[4] if len(data) > 4 else 0, "unknown")
        endian = {1: "little-endian", 2: "big-endian"}.get(data[5] if len(data) > 5 else 0, "unknown")
        lines.append(f"ELF arch  : {arch} ({endian})")

    elif data[:4] == b"PK\x03\x04":
        lines.append("Archive type: ZIP")

    elif data[:4] == b"%PDF":
        lines.append(f"PDF header: {data[:20].decode('ascii', errors='replace').strip()}")

    return "\n".join(lines)


def _extract_strings(data: bytes, min_len: int = 4) -> str:
    results = []
    current: list[int] = []
    for byte in data:
        if 0x20 <= byte < 0x7F:
            current.append(byte)
        else:
            if len(current) >= min_len:
                results.append(bytes(current).decode("ascii"))
            current = []
    if len(current) >= min_len:
        results.append(bytes(current).decode("ascii"))
    if not results:
        return f"No printable strings of length >= {min_len} found."
    return f"Found {len(results)} strings (min length {min_len}):\n" + "\n".join(results)


def inspect_file(working_directory: str, file_path: str, extraction_type: str, min_string_len: int = 4) -> str:
    try:
        abs_working_dir = os.path.abspath(working_directory)
        abs_file_path = os.path.normpath(os.path.join(abs_working_dir, file_path))
        if os.path.commonpath([abs_working_dir, abs_file_path]) != abs_working_dir:
            return f'Error: Cannot access "{file_path}" as it is outside the working directory'
        if not os.path.isfile(abs_file_path):
            return f'Error: File not found: "{file_path}"'

        with open(abs_file_path, "rb") as f:
            data = f.read()

        ext = extraction_type.lower().strip()

        if ext == "magic_bytes":
            return f"File: {file_path}\nType: {_identify_magic(data)}"
        elif ext == "metadata":
            return f"File: {file_path}\n{_extract_metadata(abs_file_path, data)}"
        elif ext == "strings":
            return _extract_strings(data, min_len=min_string_len)
        else:
            return f"Error: Unknown extraction_type '{extraction_type}'. Choose from: magic_bytes, metadata, strings"

    except Exception as e:
        return f"Error inspecting file: {e}"


schema_inspect_file = {
    "type": "function",
    "function": {
        "name": "inspect_file",
        "description": "Forensically inspect a file for CTF challenges. Can identify the file type from magic bytes, extract basic metadata (dimensions, architecture, etc.), or dump printable ASCII strings embedded in the file (like the `strings` utility).",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to inspect, relative to the working directory."},
                "extraction_type": {"type": "string", "enum": ["magic_bytes", "metadata", "strings"], "description": "What to extract: 'magic_bytes' to identify the file type, 'metadata' for structural info, 'strings' to extract embedded printable ASCII strings."},
                "min_string_len": {"type": "integer", "description": "Minimum string length for the 'strings' extraction_type. Defaults to 4."},
            },
            "required": ["file_path", "extraction_type"],
        },
    },
}
