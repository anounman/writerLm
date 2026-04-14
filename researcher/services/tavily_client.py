from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, List, Optional

from pydantic import HttpUrl, TypeAdapter
from tavily import TavilyClient

from researcher.constants import DEFAULT_TAVILY_RESULTS_PER_QUERY
from researcher.schemas import DiscoveredSource, SourceType

HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)
CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "tavily"


class TavilySearchError(Exception):
    """Raised when Tavily discovery fails."""


class TavilySearchClient:
    """
    Small wrapper around Tavily search.

    Responsibilities:
    - execute search queries
    - normalize result payloads
    - convert Tavily results into DiscoveredSource objects
    - isolate provider-specific response handling from workflow nodes
    """

    def __init__(
        self,
        api_key: str,
        default_max_results: int = DEFAULT_TAVILY_RESULTS_PER_QUERY,
        topic: str = "general",
        search_depth: str = "advanced",
        include_answer: bool = False,
        include_raw_content: bool = False,
    ) -> None:
        self.client = TavilyClient(api_key=api_key)
        self.default_max_results = default_max_results
        self.topic = topic
        self.search_depth = search_depth
        self.include_answer = include_answer
        self.include_raw_content = include_raw_content
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _normalize_result(
        self,
        *,
        result: Any,
        query_id: str,
        rank: int,
    ) -> Optional[DiscoveredSource]:
        """
        Convert one Tavily result item into a DiscoveredSource.
        Returns None when the result is too malformed to use safely.
        """
        if not isinstance(result, dict):
            return None

        raw_url = result.get("url")
        title = result.get("title") or "Untitled source"

        if not raw_url or not isinstance(raw_url, str):
            return None

        try:
            url = HTTP_URL_ADAPTER.validate_python(raw_url)
        except Exception:
            return None

        snippet = self._extract_snippet(result)
        source_type = self._infer_source_type(url=url, title=title)
        source_id = self._build_source_id(query_id=query_id, rank=rank)
        discovery_score = self._coerce_score(result.get("score"))

        try:
            return DiscoveredSource(
                source_id=source_id,
                query_id=query_id,
                title=title,
                url=str(url),
                snippet=snippet,
                source_type=source_type,
                rank=rank,
                discovery_score=discovery_score,
            )
        except Exception:
            return None

    def _extract_snippet(self, result: dict[str, Any]) -> Optional[str]:
        """
        Extract a useful short snippet from Tavily response fields.
        """
        for key in ("content", "snippet", "raw_content"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _infer_source_type(self, *, url: HttpUrl, title: str) -> SourceType:

        lowered_url = str(url).lower()
        lowered_title = title.lower()

        if lowered_url.endswith(".pdf") or "/pdf" in lowered_url:
            return SourceType.PDF

        if any(token in lowered_url for token in ["/docs/", "docs.", "documentation"]):
            return SourceType.DOCS

        if any(
            token in lowered_url
            for token in ["/news/", "news.", "/article/", "/articles/"]
        ):
            return SourceType.NEWS

        if any(token in lowered_url for token in ["/blog/", "blog."]):
            return SourceType.BLOG

        if any(
            token in lowered_title for token in ["paper", "study", "arxiv", "research"]
        ):
            return SourceType.RESEARCH_PAPER

        if any(token in lowered_title for token in ["report", "whitepaper"]):
            return SourceType.REPORT

        return SourceType.WEBPAGE

    def _build_source_id(self, *, query_id: str, rank: int) -> str:
        """
        Build a stable-enough source id within the context of one discovery pass.
        """
        return f"{query_id}__src_{rank}"

    def _coerce_score(self, value: Any) -> Optional[float]:
        """
        Convert Tavily score into float when possible.
        """
        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def search(
        self,
        *,
        query_text: str,
        query_id: str,
        max_results: Optional[int] = None,
    ) -> List[DiscoveredSource]:
        requested_max_results = max_results or self.default_max_results
        cache_path = self._cache_path(
            query_text=query_text,
            max_results=requested_max_results,
        )

        if cache_path.exists():
            try:
                cached_payload = json.loads(cache_path.read_text(encoding="utf-8"))
                return [
                    DiscoveredSource.model_validate(
                        {
                            **item,
                            "query_id": query_id,
                            "source_id": self._build_source_id(
                                query_id=query_id,
                                rank=index,
                            ),
                        }
                    )
                    for index, item in enumerate(cached_payload, start=1)
                ]
            except Exception:
                pass

        try:
            response = self.client.search(
                query=query_text,
                max_results=requested_max_results,
                topic=self.topic,
                search_depth=self.search_depth,
                include_answer=self.include_answer,
                include_raw_content=self.include_raw_content,
            )
        except Exception as exc:
            raise TavilySearchError(f"Tavily search failed: {str(exc)}") from exc

        results = response.get("results", [])
        if not isinstance(results, list):
            raise TavilySearchError("Tavily returned an invalid 'results' payload.")

        discovered_sources: List[DiscoveredSource] = []
        for index, result in enumerate(results, start=1):
            normalized = self._normalize_result(
                result=result,
                query_id=query_id,
                rank=index,
            )
            if normalized is not None:
                discovered_sources.append(normalized)

        try:
            cache_path.write_text(
                json.dumps(
                    [item.model_dump(mode="json") for item in discovered_sources],
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

        return discovered_sources

    def _cache_path(self, *, query_text: str, max_results: int) -> Path:
        raw_key = "|".join(
            [
                query_text,
                str(max_results),
                self.topic,
                self.search_depth,
                str(self.include_answer),
                str(self.include_raw_content),
            ]
        )
        digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        return CACHE_DIR / f"{digest}.json"
