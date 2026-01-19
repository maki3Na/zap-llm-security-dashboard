# secdemo/url_reconstruct.py
import re
from urllib.parse import urljoin

REQ_LINE = re.compile(r"^(?P<method>[A-Z]+)\s+(?P<target>\S+)\s+HTTP/\d\.\d$", re.M)
HOST_LINE = re.compile(r"^Host:\s*(?P<host>.+)$", re.M | re.I)

def reconstruct_url(request_header: str, fallback_base: str = "http://localhost") -> tuple[str, str]:
    request_header = request_header or ""

    method = "GET"
    target = "/"

    m = REQ_LINE.search(request_header)
    if m:
        method = m.group("method") or "GET"
        target = m.group("target") or "/"

    if target.startswith("http://") or target.startswith("https://"):
        return method, target

    h = HOST_LINE.search(request_header)
    host = h.group("host").strip() if h else None

    base = f"http://{host}" if host else fallback_base
    full_url = urljoin(base, target)
    return method, full_url
