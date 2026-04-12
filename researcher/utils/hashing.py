from __future__ import annotations
import hashlib


def stable_text_hash(text: str) -> str:
    """
    Generate a stable hash for a given text string.
    Uses SHA-256 and returns the first 16 characters for brevity.
    """
    normalized_text = " ".join(text.split()).strip()
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
