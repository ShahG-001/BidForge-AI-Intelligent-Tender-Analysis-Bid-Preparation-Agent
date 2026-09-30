"""Fetch small amounts of text from public tender/company web pages safely."""
import ipaddress
import socket
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

MAX_BYTES = 5 * 1024 * 1024


def _validate_public_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise ValueError("Enter a complete public http:// or https:// URL.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing embedded usernames/passwords are not allowed.")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise ValueError("The URL host could not be resolved.") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("Private or local network URLs are not allowed.")
    return url.strip()


def fetch_public_text(url: str) -> tuple[str, str]:
    """Fetch a public web page or directly linked PDF; redirects are disabled."""
    safe_url = _validate_public_url(url)
    response = requests.get(
        safe_url,
        timeout=(5, 20),
        allow_redirects=False,
        stream=True,
        headers={"User-Agent": "BidForgeAI/1.0 (public document text extraction)"},
    )
    if response.is_redirect:
        response.close()
        return "", "The link redirects. Open its final public URL and paste that URL instead."
    response.raise_for_status()
    length = int(response.headers.get("Content-Length", "0") or 0)
    if length > MAX_BYTES:
        response.close()
        return "", "The linked file exceeds the 5 MB link-import limit. Download and upload a smaller document."
    data = response.raw.read(MAX_BYTES + 1, decode_content=True)
    content_type = response.headers.get("Content-Type", "").lower()
    if len(data) > MAX_BYTES:
        return "", "The linked file exceeds the 5 MB link-import limit."
    if "pdf" in content_type or safe_url.lower().split("?")[0].endswith(".pdf"):
        from io import BytesIO
        from pypdf import PdfReader

        text = "\n\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages)
        return text, "" if text.strip() else "No selectable PDF text was found; upload a searchable PDF instead."
    if "html" not in content_type and "text/" not in content_type:
        return "", f"Unsupported link content type: {content_type or 'unknown'}. Use a public webpage or PDF link."
    soup = BeautifulSoup(data, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        tag.decompose()
    text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
    title = soup.title.get_text(" ", strip=True) if soup.title else safe_url
    return f"Source title: {title}\nSource URL: {safe_url}\n\n{text[:100000]}", "" if text.strip() else "No readable page text was found."
