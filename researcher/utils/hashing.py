from __future__ import annotations
import hashlib
from urllib.parse import urlsplit, urlunsplit


def stable_text_hash(text: str) -> str:
    """
    Generate a stable hash for a given text string.
    Uses SHA-256 and returns the first 16 characters for brevity.
    """
    normalized_text = " ".join(text.split()).strip()
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


def stable_url_hash(url: str) -> str:
    """
    Generate a stable hash for a URL after light normalization.
    """
    stripped_url = url.strip()
    parts = urlsplit(stripped_url)
    normalized_scheme = parts.scheme.lower()
    normalized_netloc = parts.netloc.lower()
    normalized_path = parts.path or "/"
    normalized_query = parts.query
    normalized_url = urlunsplit(
        (
            normalized_scheme,
            normalized_netloc,
            normalized_path,
            normalized_query,
            "",
        )
    )
    return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()
