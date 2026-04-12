from __future__ import annotations

from pydantic import BaseModel, Field

from researcher.constants import (
    ALLOW_PARTIAL_SOURCE_FAILURE,
    ENABLE_FIRECRAWL_FALLBACK,
    FIRECRAWL_FALLBACK_MIN_TEXT_CHARS,
)
from researcher.registry.source_registry import SourceRegistry, SourceRegistryError
from researcher.schemas import (
    DiscoveredSource,
    EvidenceItem,
    EvidenceType,
    ExtractionMethod,
    ReflexionAction,
    SourceDocument,
    SourceType,
)
from researcher.services.firecrawl_client import (
    FirecrawlClient,
    FirecrawlExtractionError,
)
from researcher.services.llm_structured import GroqStructuredLLM
from researcher.services.pdf_extractor import PDFExtractor
from researcher.services.tavily_client import TavilySearchClient, TavilySearchError
from researcher.services.web_extractor import WebExtractionError, WebExtractor
from researcher.state import ResearcherState
from researcher.utils.ids import make_evidence_id


class FollowupResearchNode:
    """
    Run one bounded follow-up research pass after reflexion.

    Responsibilities:
    - read follow-up queries from state
    - discover additional sources
    - fetch and extract them
    - extract additional evidence
    - merge new artifacts into existing state
    - increment the reflexion round
    """

    def __init__(
        self,
        *,
        llm: GroqStructuredLLM,
        tavily_client: TavilySearchClient,
        web_extractor: WebExtractor,
        pdf_extractor: PDFExtractor,
        firecrawl_client: FirecrawlClient | None = None,
        allow_partial_failures: bool = ALLOW_PARTIAL_SOURCE_FAILURE,
        enable_firecrawl_fallback: bool = ENABLE_FIRECRAWL_FALLBACK,
    ) -> None:
        self.llm = llm
        self.tavily_client = tavily_client
        self.web_extractor = web_extractor
        self.pdf_extractor = pdf_extractor
        self.firecrawl_client = firecrawl_client
        self.allow_partial_failures = allow_partial_failures
        self.enable_firecrawl_fallback = enable_firecrawl_fallback

    def run(self, state: ResearcherState) -> ResearcherState:
        """
        Execute one bounded follow-up research pass.
        """
        if state.reflexion_decision is None:
            state.add_error(
                "Cannot run follow-up research because reflexion_decision is missing."
            )
            return state

        if state.reflexion_decision.action != ReflexionAction.FOLLOW_UP:
            return state

        if not state.followup_queries:
            state.add_warning(
                "Reflexion requested follow-up research, but no followup_queries were available."
            )
            state.reflexion_round += 1
            return state

        registry = self._build_registry_from_state(state)
        seen_urls = {
            str(source.url).strip().lower() for source in state.discovered_sources
        }
        seen_evidence_keys = {
            self._evidence_dedupe_key(item.content) for item in state.evidence_items
        }

        newly_discovered: list[DiscoveredSource] = []
        newly_fetched: list[SourceDocument] = []
        newly_extracted_evidence: list[EvidenceItem] = []

        max_additional_sources = state.reflexion_decision.max_additional_sources
        discovered_count = 0

        sorted_queries = sorted(
            state.followup_queries,
            key=lambda query: (query.priority, query.query_id),
        )

        for query in sorted_queries:
            if discovered_count >= max_additional_sources:
                break

            remaining_capacity = max_additional_sources - discovered_count
            if remaining_capacity <= 0:
                break

            try:
                discovered_sources = self.tavily_client.search(
                    query_text=query.query_text,
                    query_id=query.query_id,
                    max_results=remaining_capacity,
                )
            except TavilySearchError as exc:
                state.add_warning(
                    f"Follow-up discovery failed for query '{query.query_id}' "
                    f"({query.query_text}): {exc}"
                )
                continue

            for source in discovered_sources:
                normalized_url = str(source.url).strip().lower()
                if not normalized_url or normalized_url in seen_urls:
                    continue

                seen_urls.add(normalized_url)
                newly_discovered.append(source)
                registry.register_discovered_source(source)
                discovered_count += 1

                try:
                    document = self._fetch_one_source(source)
                except Exception as exc:
                    message = (
                        f"Failed to fetch follow-up source '{source.source_id}' "
                        f"({source.url}): {exc}"
                    )
                    if self.allow_partial_failures:
                        state.add_warning(message)
                        registry.add_reliability_note(
                            source_id=source.source_id,
                            note=f"followup_fetch_failed: {exc}",
                        )
                        if discovered_count >= max_additional_sources:
                            break
                        continue

                    state.add_error(message)
                    return state

                newly_fetched.append(document)
                registry.register_source_document(
                    source_document=document,
                    discovery_query_id=source.query_id,
                )

                try:
                    evidence_items = self._extract_evidence_from_one_document(
                        document=document,
                        state=state,
                    )
                except Exception as exc:
                    state.add_warning(
                        f"Follow-up evidence extraction failed for source '{document.source_id}': {exc}"
                    )
                    try:
                        registry.add_reliability_note(
                            source_id=document.source_id,
                            note=f"followup_evidence_extraction_failed: {exc}",
                        )
                    except SourceRegistryError:
                        pass

                    if discovered_count >= max_additional_sources:
                        break
                    continue

                for item in evidence_items:
                    dedupe_key = self._evidence_dedupe_key(item.content)
                    if dedupe_key in seen_evidence_keys:
                        continue

                    seen_evidence_keys.add(dedupe_key)
                    newly_extracted_evidence.append(item)

                    try:
                        registry.attach_evidence(
                            source_id=item.source_id,
                            evidence_id=item.evidence_id,
                        )
                    except SourceRegistryError as exc:
                        state.add_warning(
                            f"Could not attach follow-up evidence '{item.evidence_id}' "
                            f"to source '{item.source_id}': {exc}"
                        )

                if discovered_count >= max_additional_sources:
                    break

        state.discovered_sources = [*state.discovered_sources, *newly_discovered]
        state.fetched_documents = [*state.fetched_documents, *newly_fetched]
        state.evidence_items = [*state.evidence_items, *newly_extracted_evidence]
        state.source_registry = registry.list_entries()
        state.reflexion_round += 1

        return state

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

    def _try_firecrawl_fallback(
        self, source: DiscoveredSource
    ) -> SourceDocument | None:
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

    def _extract_evidence_from_one_document(
        self,
        *,
        document: SourceDocument,
        state: ResearcherState,
    ) -> list[EvidenceItem]:
        """
        Extract evidence items from one follow-up source document.
        """
        assert state.research_task is not None

        user_prompt = self._build_extract_evidence_user_prompt(
            section_id=state.research_task.section.section_id,
            section_title=state.research_task.section.section_title,
            section_goal=state.research_task.section.section_goal,
            task_objective=state.research_task.objective,
            required_evidence_types=state.research_task.required_evidence_types,
            source_title=document.title,
            source_url=str(document.url),
            source_type=document.source_type.value,
            source_text=document.text,
        )

        llm_output = self.llm.generate_structured(
            system_prompt=EXTRACT_EVIDENCE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=ExtractEvidenceOutput,
        )

        return self._normalize_evidence_items(
            document=document,
            section_id=state.research_task.section.section_id,
            candidates=llm_output.evidence_items,
        )

    def _normalize_evidence_items(
        self,
        *,
        document: SourceDocument,
        section_id: str,
        candidates: list["ExtractedEvidenceCandidate"],
    ) -> list[EvidenceItem]:
        """
        Convert candidate evidence items into final EvidenceItem objects.
        """
        normalized_items: list[EvidenceItem] = []
        seen_contents: set[str] = set()

        for index, candidate in enumerate(candidates, start=1):
            cleaned_content = self._clean_text(candidate.content)
            if not cleaned_content:
                continue

            dedupe_key = cleaned_content.casefold()
            if dedupe_key in seen_contents:
                continue
            seen_contents.add(dedupe_key)

            normalized_items.append(
                EvidenceItem(
                    evidence_id=make_evidence_id(
                        document.source_id,
                        candidate.evidence_type.value,
                        index,
                    ),
                    source_id=document.source_id,
                    section_id=section_id,
                    evidence_type=candidate.evidence_type,
                    content=cleaned_content,
                    summary=self._clean_optional_text(candidate.summary),
                    relevance_note=self._clean_optional_text(candidate.relevance_note),
                    confidence=candidate.confidence,
                    tags=self._clean_tags(candidate.tags),
                )
            )

        return normalized_items

    def _evidence_dedupe_key(self, content: str) -> str:
        """
        Simple text-based dedupe key for evidence merging.
        """
        return self._clean_text(content).casefold()

    def _clean_text(self, value: str) -> str:
        """
        Normalize required text fields.
        """
        return " ".join(value.split()).strip()

    def _clean_optional_text(self, value: str | None) -> str | None:
        """
        Normalize optional text fields.
        """
        if value is None:
            return None
        cleaned = " ".join(value.split()).strip()
        return cleaned or None

    def _clean_tags(self, tags: list[str]) -> list[str]:
        """
        Normalize and deduplicate tag strings.
        """
        cleaned_tags: list[str] = []
        seen: set[str] = set()

        for tag in tags:
            cleaned = " ".join(tag.split()).strip()
            if not cleaned:
                continue

            key = cleaned.casefold()
            if key in seen:
                continue

            seen.add(key)
            cleaned_tags.append(cleaned)

        return cleaned_tags

    def _build_registry_from_state(self, state: ResearcherState) -> SourceRegistry:
        """
        Rebuild an in-memory registry object from current state entries.
        """
        registry = SourceRegistry()
        for entry in state.source_registry:
            registry._entries[entry.source_id] = entry
        return registry

    def _build_extract_evidence_user_prompt(
        self,
        *,
        section_id: str,
        section_title: str,
        section_goal: str,
        task_objective: str,
        required_evidence_types: list[EvidenceType],
        source_title: str,
        source_url: str,
        source_type: str,
        source_text: str,
    ) -> str:
        required_types_text = (
            "\n".join(f"- {item.value}" for item in required_evidence_types)
            if required_evidence_types
            else "- None"
        )

        return f"""
Extract evidence for this research task.

Target Section ID: {section_id}
Target Section Title: {section_title}
Target Section Goal: {section_goal}
Research Objective: {task_objective}

Required Evidence Types:
{required_types_text}

Source Title: {source_title}
Source URL: {source_url}
Source Type: {source_type}

Source Text:
{source_text}

Return only structured evidence extraction output for this source.
""".strip()


class ExtractedEvidenceCandidate(BaseModel):
    evidence_type: EvidenceType
    content: str
    summary: str | None = None
    relevance_note: str | None = None
    confidence: float = 0.7
    tags: list[str] = Field(default_factory=list)


class ExtractEvidenceOutput(BaseModel):
    evidence_items: list[ExtractedEvidenceCandidate] = Field(default_factory=list)


EXTRACT_EVIDENCE_SYSTEM_PROMPT = """
You are an evidence extraction specialist inside a multi-stage research pipeline for book generation.

Your job is to read one extracted source document and pull out useful research evidence for one specific book section.

You are NOT writing the section.
You are NOT summarizing the whole source.
You are extracting evidence that can support later synthesis and writing.

Only extract evidence that is clearly relevant to the target section objective.

Good evidence may include:
- definitions
- facts
- examples
- case studies
- statistics
- references
- claims
- insights
- warnings

Guidelines:
- Stay tightly scoped to the section objective.
- Prefer concrete and useful evidence over generic statements.
- Avoid duplicate evidence.
- Keep evidence items atomic when possible.
- Do not invent facts not supported by the source text.
- Do not include markdown.
"""
