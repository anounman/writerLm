from __future__ import annotations

from researcher.utils.urls import canonicalize_url


def test_canonicalize_url_removes_tracking_noise() -> None:
    url = "HTTPS://www.Example.com:443/a/b/?utm_source=newsletter&b=2&a=1#section"

    assert canonicalize_url(url) == "https://example.com/a/b?a=1&b=2"


def test_canonicalize_url_preserves_meaningful_query_params() -> None:
    url = "https://docs.example.com/search/?q=rag&page=2"

    assert canonicalize_url(url) == "https://docs.example.com/search?page=2&q=rag"


def test_canonicalize_url_adds_missing_scheme() -> None:
    assert canonicalize_url("www.example.com/docs/") == "https://example.com/docs"
