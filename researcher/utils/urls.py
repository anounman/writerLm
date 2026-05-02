from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_PARAMS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "msclkid",
    "ref",
    "source",
}


def canonicalize_url(url: str) -> str:
    """
    Normalize URLs for dedupe and cache keys.

    This intentionally keeps meaningful query parameters while dropping fragments,
    common tracking parameters, host case, default ports, and trailing slash noise.
    """
    raw_url = url.strip()
    if not raw_url:
        return ""

    parsed = urlparse(raw_url)
    if not parsed.scheme and not parsed.netloc:
        parsed = urlparse(f"https://{raw_url}")
    scheme = (parsed.scheme or "https").lower()
    host = parsed.hostname.lower() if parsed.hostname else parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    port = parsed.port
    include_port = port is not None and not (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    )
    netloc = f"{host}:{port}" if include_port else host

    path = parsed.path or "/"
    while "//" in path:
        path = path.replace("//", "/")
    if path != "/":
        path = path.rstrip("/")

    query_items = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        normalized_key = key.strip()
        lowered_key = normalized_key.lower()
        if not normalized_key:
            continue
        if lowered_key in TRACKING_QUERY_PARAMS:
            continue
        if any(lowered_key.startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES):
            continue
        query_items.append((normalized_key, value))

    query = urlencode(sorted(query_items), doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))
