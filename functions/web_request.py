import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

_CA_BUNDLE_PATHS = [
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/etc/ssl/ca-bundle.pem",
    "/etc/ssl/cert.pem",
    "/usr/local/etc/openssl/cert.pem",
]


def _make_ssl_context(verify: bool = True) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    for path in _CA_BUNDLE_PATHS:
        if os.path.isfile(path):
            try:
                ctx.load_verify_locations(cafile=path)
            except ssl.SSLError:
                continue
            return ctx
    return ctx


def web_request(working_directory: str, url: str, method: str = "GET", headers: dict | None = None, data: dict | str | None = None, cookies: dict | None = None, verify_ssl: bool = True) -> str:
    try:
        method = method.upper().strip()
        if method not in ("GET", "POST"):
            return f"Error: Unsupported method '{method}'. Use GET or POST."

        body: bytes | None = None
        if method == "POST" and data is not None:
            if isinstance(data, dict):
                body = urllib.parse.urlencode(data).encode("utf-8")
                if headers is None:
                    headers = {}
                headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
            elif isinstance(data, str):
                body = data.encode("utf-8")

        req_headers: dict[str, str] = headers or {}
        if cookies:
            req_headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())

        req = urllib.request.Request(url, data=body, headers=req_headers, method=method)

        cj = CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cj),
            urllib.request.HTTPSHandler(context=_make_ssl_context(verify=verify_ssl)),
        )

        try:
            with opener.open(req, timeout=15) as resp:
                body_text = resp.read(65536).decode("utf-8", errors="replace")
                output = {
                    "status_code": resp.status,
                    "headers": dict(resp.headers),
                    "cookies": {c.name: c.value for c in cj},
                    "body": body_text[:4096],
                    "body_truncated": len(body_text) > 4096,
                }
                return json.dumps(output, indent=2)

        except urllib.error.HTTPError as e:
            output = {
                "status_code": e.code,
                "headers": dict(e.headers),
                "cookies": {},
                "body": e.read(4096).decode("utf-8", errors="replace"),
                "error": str(e.reason),
            }
            return json.dumps(output, indent=2)

    except Exception as e:
        return f"Error in web_request: {e}"


schema_web_request = {
    "type": "function",
    "function": {
        "name": "web_request",
        "description": "Perform an HTTP GET or POST request to a URL. Returns the HTTP status code, response headers, cookies, and body content. Set verify_ssl=false for challenges that use self-signed certificates.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The full URL to request."},
                "method": {"type": "string", "enum": ["GET", "POST"], "description": "HTTP method. Defaults to GET."},
                "headers": {"type": "object", "description": "Optional dictionary of additional HTTP request headers."},
                "data": {"type": "string", "description": "Request body for POST. URL-encoded string or JSON string."},
                "cookies": {"type": "object", "description": "Optional dictionary of cookies to send with the request."},
                "verify_ssl": {"type": "boolean", "description": "Whether to verify the server's SSL certificate. Defaults to true."},
            },
            "required": ["url"],
        },
    },
}
