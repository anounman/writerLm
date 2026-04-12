from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from firecrawl import FirecrawlApp


class FirecrawlExtractionError(Exception):
    """Raised when Firecrawl extraction fails."""


@dataclass
class FirecrawlExtractionResult:
    url: str
    final_url: str
    title: Optional[str]
    text: str
    metadata: dict[str, Any]
    extraction_method: str = "firecrawl"


class FirecrawlClient:
    """
    Fallback extractor using Firecrawl.

    Responsibilities:
    - call Firecrawl on difficult webpages
    - normalize extracted content
    - return a predictable result shape for downstream nodes
    """

    def __init__(
        self,
        api_key: str,
        timeout_ms: int = 30_000,
        only_main_content: bool = True,
    ) -> None:
        self.app = FirecrawlApp(api_key=api_key)
        self.timeout_ms = timeout_ms
        self.only_main_content = only_main_content

    def extract(self, url: str) -> FirecrawlExtractionResult:
        """
        Scrape a webpage through Firecrawl and normalize the result.
        """
        try:
            response = self.app.scrape(
                url,
                formats=["markdown"],
                only_main_content=self.only_main_content,
                timeout=self.timeout_ms,
            )
        except Exception as exc:
            raise FirecrawlExtractionError(
                f"Firecrawl extraction failed for url='{url}': {exc}"
            ) from exc

        if not isinstance(response, dict):
            raise FirecrawlExtractionError("Firecrawl returned a non-dict response.")

        data = response.get("data")
        if not isinstance(data, dict):
            raise FirecrawlExtractionError("Firecrawl response missing 'data' object.")

        text = self._extract_text(data)
        if not text:
            raise FirecrawlExtractionError(
                f"Firecrawl returned empty extracted text for url='{url}'."
            )

        metadata = data.get("metadata")
        normalized_metadata = metadata if isinstance(metadata, dict) else {}

        title = self._extract_title(normalized_metadata)
        final_url = self._extract_final_url(normalized_metadata, fallback=url)

        return FirecrawlExtractionResult(
            url=url,
            final_url=final_url,
            title=title,
            text=text,
            metadata=normalized_metadata,
        )

    def _extract_text(self, data: dict[str, Any]) -> str:
        """
        Prefer markdown output because it usually preserves readable structure
        while still being easy for downstream processing.
        """
        markdown = data.get("markdown")
        if isinstance(markdown, str) and markdown.strip():
            return markdown.strip()

        content = data.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()

        return ""

    def _extract_title(self, metadata: dict[str, Any]) -> Optional[str]:
        """
        Best-effort title extraction from Firecrawl metadata.
        """
        for key in ("title", "ogTitle"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _extract_final_url(self, metadata: dict[str, Any], *, fallback: str) -> str:
        """
        Best-effort final URL extraction from metadata.
        """
        for key in ("sourceURL", "url"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return fallback
