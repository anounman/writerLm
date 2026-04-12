from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests
import trafilatura

from researcher.constants import MIN_WEBPAGE_TEXT_CHARS


class WebExtractionError(Exception):
    """Raised when webpage fetching or extraction fails."""


@dataclass
class WebExtractionResult:
    url: str
    final_url: str
    title: Optional[str]
    text: str
    raw_html: Optional[str]
    extraction_method: str = "trafilatura"


class WebExtractor:
    """
    Primary webpage extractor using requests + trafilatura.

    Responsibilities:
    - download webpage HTML
    - extract readable main content
    - return normalized extraction output
    - surface weak/failed extraction clearly
    """

    def __init__(
        self,
        timeout_seconds: int = 20,
        user_agent: Optional[str] = None,
        mix_text_chars: int = MIN_WEBPAGE_TEXT_CHARS,
        include_raw_html: bool = False,
    ) -> None:

        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
        self.mix_text_chars = mix_text_chars
        self.include_raw_html = include_raw_html

    def _download_html(self, url: str) -> tuple[str, str]:
        try:
            response = requests.get(
                url,
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout_seconds,
                allow_redirects=True,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise WebExtractionError(
                f"Failed to fetch webpage url='{url}': {exc}"
            ) from exc
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type:
            raise WebExtractionError(
                f"URL did not return HTML content: url='{url}', content_type='{content_type}'"
            )

        html = response.text
        if not html or not html.strip():
            raise WebExtractionError(f"Empty HTML content fetched from url='{url}'")
        return html, str(response.url)

    def _extract_main_text(self, html: str) -> str:
        """
        Extract main readable article/page text from HTML.
        """
        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            include_links=False,
            output_format="txt",
            favor_precision=True,
            deduplicate=True,
        )

        if not extracted or not extracted.strip():
            raise WebExtractionError("Trafilatura returned empty extracted text.")

        return extracted

    def _extract_title(self, html: str) -> Optional[str]:
        """
        Best-effort title extraction using trafilatura metadata.
        """
        metadata = trafilatura.extract_metadata(html)
        if metadata is None:
            return None

        title = getattr(metadata, "title", None)
        if isinstance(title, str) and title.strip():
            return title.strip()

        return None

    def extract(self, url: str) -> WebExtractionResult:
        """
        Fetch a webpage and extract main readable content with trafilatura.
        """
        html, final_url = self._download_html(url)
        extracted_text = self._extract_main_text(html)
        title = self._extract_title(html)

        if len(extracted_text.strip()) < self.mix_text_chars:
            raise WebExtractionError(
                f"Extracted text is too short: url='{url}', chars='{len(extracted_text.strip())}'"
            )
        return WebExtractionResult(
            url=url,
            final_url=final_url,
            title=title,
            text=extracted_text.strip(),
            raw_html=html if self.include_raw_html else None,
        )
