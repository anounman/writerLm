from __future__ import annotations

from researcher.constants import (
    ALLOW_PARTIAL_SOURCE_FAILURE,
    ENABLE_FIRECRAWL_FALLBACK,
    FIRECRAWL_FALLBACK_MIN_TEXT_CHARS,
    MAX_FETCHED_SOURCES_PER_SECTION,
)
from researcher.registry.source_registry import SourceRegistry
from researcher.schemas import ExtractionMethod, SourceDocument, SourceType
from researcher.services.firecrawl_client import (
    FirecrawlClient,
    FirecrawlExtractionError,
)
from researcher.services.pdf_extractor import PDFExtractionError, PDFExtractor
from researcher.services.web_extractor import WebExtractionError, WebExtractor
from researcher.state import ResearcherState


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

        for source in selected_sources:
            try:
                document = self._fetch_one_source(source)
            except Exception as exc:
                message = (
                    f"Failed to fetch source '{source.source_id}' ({source.url}): {exc}"
                )
                if self.allow_partial_failures:
                    state.add_warning(message)
                    registry.add_reliability_note(
                        source_id=source.source_id,
                        note=f"fetch_failed: {exc}",
                    )
                    continue

                state.add_error(message)
                return state

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

        Right now the selection policy is simple:
        - keep discovery order
        - respect the fetch cap
        """
        return state.discovered_sources[: self.max_fetched_sources]

    def _fetch_one_source(self, source) -> SourceDocument:
        """
        Fetch and normalize one discovered source.
        """
        if source.source_type == SourceType.PDF or str(source.url).lower().endswith(
            ".pdf"
        ):
            return self._fetch_pdf_source(source)

        return self._fetch_web_source(source)

    def _fetch_pdf_source(self, source) -> SourceDocument:
        """
        Extract one PDF source using PyMuPDF.
        """
        result = self.pdf_extractor.extract(str(source.url))

        metadata: dict[str, object] = dict(result.metadata)
        metadata["final_url"] = result.final_url
        metadata["page_count"] = str(result.page_count)

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

    def _fetch_web_source(self, source) -> SourceDocument:
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

    def _try_firecrawl_fallback(self, source) -> SourceDocument | None:
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
