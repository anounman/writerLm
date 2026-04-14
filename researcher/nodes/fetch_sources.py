from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
from urllib.parse import urlparse

from researcher.constants import (
    ALLOW_PARTIAL_SOURCE_FAILURE,
    BLOCKED_SOURCE_DOMAINS,
    DOMAIN_TRUST_OVERRIDES,
    ENABLE_FIRECRAWL_FALLBACK,
    FIRECRAWL_FALLBACK_MIN_TEXT_CHARS,
    MAX_FETCHED_SOURCES_PER_SECTION,
)
from researcher.registry.source_registry import SourceRegistry
from researcher.schemas import DiscoveredSource, ExtractionMethod, SourceDocument, SourceType
from researcher.services.firecrawl_client import (
    FirecrawlClient,
    FirecrawlExtractionError,
)
from researcher.services.pdf_extractor import PDFExtractionError, PDFExtractor
from researcher.services.web_extractor import WebExtractionError, WebExtractor
from researcher.state import ResearcherState
from researcher.utils.hashing import stable_url_hash


class FetchSourcesNode:
    """
    Fetch and extract discovered sources into normalized SourceDocument objects.

    Responsibilities:
    - read discovered sources from state
    - select which sources to fetch
    - route extraction by source type
    - use Firecrawl only as fallback for weak/failed webpage extraction
    - update source registry with extracted source metadata
    - write fetched documents back into state
    """

    def __init__(
        self,
        web_extractor: WebExtractor,
        pdf_extractor: PDFExtractor,
        firecrawl_client: FirecrawlClient | None = None,
        max_fetched_sources: int = MAX_FETCHED_SOURCES_PER_SECTION,
        allow_partial_failures: bool = ALLOW_PARTIAL_SOURCE_FAILURE,
        enable_firecrawl_fallback: bool = ENABLE_FIRECRAWL_FALLBACK,
    ) -> None:
        self.web_extractor = web_extractor
        self.pdf_extractor = pdf_extractor
        self.firecrawl_client = firecrawl_client
        self.max_fetched_sources = max_fetched_sources
        self.allow_partial_failures = allow_partial_failures
        self.enable_firecrawl_fallback = enable_firecrawl_fallback
        self.blocked_domains = BLOCKED_SOURCE_DOMAINS
        self.domain_trust_overrides = DOMAIN_TRUST_OVERRIDES
        self.max_fetch_workers = 3
        self.cache_dir = Path(__file__).resolve().parents[2] / ".cache" / "fetched_sources"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def run(self, state: ResearcherState) -> ResearcherState:
        """
        Fetch and extract a bounded set of discovered sources.
        """
        if state.fetched_documents:
            return state

        if not state.discovered_sources:
            state.add_error("Cannot fetch sources because discovered_sources is empty.")
            return state

        registry = self._build_registry_from_state(state)
        fetched_documents: list[SourceDocument] = []

        selected_sources = self._select_sources_to_fetch(state)

        fetch_results = self._fetch_sources_with_cache(selected_sources)

        for source, document, error in fetch_results:
            if error is not None:
                message = (
                    f"Failed to fetch source '{source.source_id}' ({source.url}): {error}"
                )
                if self.allow_partial_failures:
                    state.add_warning(message)
                    registry.add_reliability_note(
                        source_id=source.source_id,
                        note=f"fetch_failed: {error}",
                    )
                    continue

                state.add_error(message)
                return state

            assert document is not None
            fetched_documents.append(document)
            registry.register_source_document(
                source_document=document,
                discovery_query_id=source.query_id,
            )

        if not fetched_documents:
            state.add_error(
                f"No sources were successfully fetched for section '{state.section_id}'."
            )
            return state

        state.fetched_documents = fetched_documents
        state.source_registry = registry.list_entries()
        return state

    def _select_sources_to_fetch(self, state: ResearcherState):
        """
        Select a bounded subset of discovered sources for extraction.

        Policy:
        - filter blocked domains
        - sort by trust score
        - respect the fetch cap
        """
        filtered_sources = [
            source
            for source in state.discovered_sources
            if not self._is_blocked_domain_for_url(str(source.url))
        ]

        return sorted(
            filtered_sources,
            key=self._source_sort_key,
            reverse=True,
        )[: self.max_fetched_sources]

    def _fetch_sources_with_cache(
        self,
        sources: list[DiscoveredSource],
    ) -> list[tuple[DiscoveredSource, SourceDocument | None, Exception | None]]:
        """
        Fetch selected sources with URL cache and a small worker pool.
        Results are returned in the original source order for easier debugging.
        """
        ordered_results: list[tuple[DiscoveredSource, SourceDocument | None, Exception | None]] = [
            (source, None, None) for source in sources
        ]
        pending_items: list[tuple[int, DiscoveredSource]] = []

        for index, source in enumerate(sources):
            cached_document = self._load_cached_document(source)
            if cached_document is not None:
                ordered_results[index] = (source, cached_document, None)
            else:
                pending_items.append((index, source))

        if not pending_items:
            return ordered_results

        with ThreadPoolExecutor(max_workers=self.max_fetch_workers) as executor:
            futures = {
                executor.submit(self._fetch_one_source, source): (index, source)
                for index, source in pending_items
            }

            completed_results: dict[int, tuple[SourceDocument | None, Exception | None]] = {}
            for future in as_completed(futures):
                index, source = futures[future]
                try:
                    document = future.result()
                except Exception as exc:
                    completed_results[index] = (None, exc)
                else:
                    self._save_cached_document(source=source, document=document)
                    completed_results[index] = (document, None)

        for index, source in pending_items:
            document, error = completed_results[index]
            ordered_results[index] = (source, document, error)

        return ordered_results

    def _fetch_one_source(self, source: DiscoveredSource) -> SourceDocument:
        """
        Fetch and normalize one discovered source.
        """
        if source.source_type == SourceType.PDF or str(source.url).lower().endswith(
            ".pdf"
        ):
            return self._fetch_pdf_source(source)

        return self._fetch_web_source(source)

    def _fetch_pdf_source(self, source: DiscoveredSource) -> SourceDocument:
        """
        Extract one PDF source using PyMuPDF.
        """
        result = self.pdf_extractor.extract(str(source.url))

        metadata: dict[str, object] = dict(result.metadata)
        metadata["final_url"] = result.final_url
        metadata["page_count"] = result.page_count

        if result.pages:
            metadata["pages"] = [
                {
                    "page_number": page.page_number,
                    "text": page.text,
                }
                for page in result.pages
            ]

        return SourceDocument(
            source_id=source.source_id,
            url=result.final_url,
            title=result.title or source.title,
            source_type=SourceType.PDF,
            extraction_method=ExtractionMethod.PYMUPDF,
            text=result.text,
            metadata=metadata,
            extraction_success=True,
            extraction_error=None,
        )

    def _fetch_web_source(self, source: DiscoveredSource) -> SourceDocument:
        """
        Extract one webpage source using trafilatura first,
        then Firecrawl fallback when enabled and necessary.
        """
        try:
            result = self.web_extractor.extract(str(source.url))
            return SourceDocument(
                source_id=source.source_id,
                url=result.final_url,
                title=result.title or source.title,
                source_type=(
                    source.source_type
                    if source.source_type != SourceType.UNKNOWN
                    else SourceType.WEBPAGE
                ),
                extraction_method=ExtractionMethod.TRAFILATURA,
                text=result.text,
                metadata={
                    "final_url": result.final_url,
                },
                extraction_success=True,
                extraction_error=None,
            )
        except WebExtractionError as web_exc:
            if not self._should_try_firecrawl_fallback():
                raise web_exc

            fallback_document = self._try_firecrawl_fallback(source)
            if fallback_document is not None:
                return fallback_document

            raise web_exc

    def _try_firecrawl_fallback(self, source: DiscoveredSource) -> SourceDocument | None:
        """
        Try Firecrawl fallback for webpages when configured.
        """
        if self.firecrawl_client is None:
            return None

        try:
            result = self.firecrawl_client.extract(str(source.url))
        except FirecrawlExtractionError:
            return None

        if len(result.text.strip()) < FIRECRAWL_FALLBACK_MIN_TEXT_CHARS:
            return None

        return SourceDocument(
            source_id=source.source_id,
            url=result.final_url,
            title=result.title or source.title,
            source_type=(
                source.source_type
                if source.source_type != SourceType.UNKNOWN
                else SourceType.WEBPAGE
            ),
            extraction_method=ExtractionMethod.FIRECRAWL,
            text=result.text,
            metadata=result.metadata,
            extraction_success=True,
            extraction_error=None,
        )

    def _should_try_firecrawl_fallback(self) -> bool:
        """
        Whether fallback extraction is allowed.
        """
        return self.enable_firecrawl_fallback and self.firecrawl_client is not None

    def _build_registry_from_state(self, state: ResearcherState) -> SourceRegistry:
        """
        Rebuild an in-memory registry object from current state entries.
        """
        registry = SourceRegistry()
        for entry in state.source_registry:
            registry._entries[entry.source_id] = entry
        return registry

    def _cache_path_for_source(self, source: DiscoveredSource) -> Path:
        return self.cache_dir / f"{stable_url_hash(self._normalized_url_for_cache(str(source.url)))}.json"

    def _normalized_url_for_cache(self, url: str) -> str:
        return url.strip()

    def _load_cached_document(self, source: DiscoveredSource) -> SourceDocument | None:
        cache_path = self._cache_path_for_source(source)
        if not cache_path.exists():
            return None

        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            cached_document = SourceDocument.model_validate(payload)
        except Exception:
            return None

        return cached_document.model_copy(update={"source_id": source.source_id})

    def _save_cached_document(
        self,
        *,
        source: DiscoveredSource,
        document: SourceDocument,
    ) -> None:
        cache_path = self._cache_path_for_source(source)
        try:
            cache_path.write_text(
                json.dumps(
                    document.model_dump(mode="json"),
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except Exception:
            return

    def _source_sort_key(self, source: DiscoveredSource) -> tuple[float, float, float]:
        return (
            self._compute_trust_score(source),
            float(source.discovery_score or 0.0),
            -float(source.rank),
        )

    def _compute_trust_score(self, source: DiscoveredSource) -> float:
        domain = self._extract_domain(str(source.url))
        if domain is not None:
            for trusted_domain, score in self.domain_trust_overrides.items():
                if domain == trusted_domain or domain.endswith(f".{trusted_domain}"):
                    return score

        if source.source_type == SourceType.DOCS:
            return 0.94
        if source.source_type == SourceType.RESEARCH_PAPER:
            return 0.93
        if source.source_type == SourceType.REPORT:
            return 0.88
        if source.source_type == SourceType.PDF:
            return 0.84
        if source.source_type == SourceType.NEWS:
            return 0.62
        if source.source_type == SourceType.BLOG:
            return 0.42
        return 0.5

    def _is_blocked_domain_for_url(self, url: str) -> bool:
        domain = self._extract_domain(url)
        if domain is None:
            return False
        return any(
            domain == blocked_domain or domain.endswith(f".{blocked_domain}")
            for blocked_domain in self.blocked_domains
        )

    def _extract_domain(self, url: str) -> str | None:
        parsed = urlparse(url)
        host = parsed.netloc.lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host or None
