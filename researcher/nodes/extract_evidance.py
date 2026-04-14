from __future__ import annotations

from pydantic import BaseModel, Field

from researcher.constants import MAX_SOURCE_TEXT_CHARS_FOR_SINGLE_PASS
from researcher.schemas import (
    EvidenceItem,
    EvidenceType,
    SourceDocument,
)
from researcher.registry.source_registry import SourceRegistry, SourceRegistryError
from researcher.services.llm_structured import GroqStructuredLLM
from researcher.state import ResearcherState
from researcher.utils.ids import make_evidence_id


class ExtractedEvidenceCandidate(BaseModel):
    evidence_type: EvidenceType = Field(..., description="Type of extracted evidence.")
    content: str = Field(..., description="The extracted evidence content.")
    summary: str | None = Field(
        default=None,
        description="Short explanation of why this evidence matters.",
    )
    relevance_note: str | None = Field(
        default=None,
        description="Why this evidence is relevant to the section objective.",
    )
    confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Confidence in this extracted evidence item.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Optional concept tags for grouping or later synthesis.",
    )


class ExtractEvidenceOutput(BaseModel):
    evidence_items: list[ExtractedEvidenceCandidate] = Field(
        default_factory=list,
        description="Structured evidence items extracted from one source document.",
    )


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


def build_extract_evidence_user_prompt(
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


class ExtractEvidenceNode:
    """
    Extract structured EvidenceItem objects from fetched source documents.

    Responsibilities:
    - read fetched documents from state
    - ask the LLM to extract relevant evidence per source
    - normalize evidence into final EvidenceItem objects
    - attach evidence ids back to the source registry
    - write evidence items back into state
    """

    def __init__(self, llm: GroqStructuredLLM) -> None:
        self.llm = llm

    def run(self, state: ResearcherState) -> ResearcherState:
        """
        Extract evidence from all fetched documents for the current section.
        """
        if state.evidence_items:
            return state

        if state.research_task is None:
            state.add_error("Cannot extract evidence because research_task is missing.")
            return state

        if not state.fetched_documents:
            state.add_error(
                "Cannot extract evidence because fetched_documents is empty."
            )
            return state

        registry = self._build_registry_from_state(state)
        all_evidence_items: list[EvidenceItem] = []

        for document in state.fetched_documents:
            try:
                extracted_items = self._extract_from_one_document(
                    document=document,
                    state=state,
                )
            except Exception as exc:
                state.add_warning(
                    f"Evidence extraction failed for source '{document.source_id}': {exc}"
                )
                try:
                    registry.add_reliability_note(
                        source_id=document.source_id,
                        note=f"evidence_extraction_failed: {exc}",
                    )
                except SourceRegistryError:
                    pass
                continue

            for item in extracted_items:
                all_evidence_items.append(item)
                try:
                    registry.attach_evidence(
                        source_id=item.source_id,
                        evidence_id=item.evidence_id,
                    )
                except SourceRegistryError as exc:
                    state.add_warning(
                        f"Could not attach evidence '{item.evidence_id}' to source "
                        f"'{item.source_id}': {exc}"
                    )

        if not all_evidence_items:
            state.add_error(
                f"No evidence was extracted for section '{state.section_id}'."
            )
            return state

        state.evidence_items = all_evidence_items
        state.source_registry = registry.list_entries()
        return state

    def _extract_from_one_document(
        self,
        *,
        document: SourceDocument,
        state: ResearcherState,
    ) -> list[EvidenceItem]:
        """
        Extract evidence items from one fetched source document.
        """
        assert state.research_task is not None

        user_prompt = build_extract_evidence_user_prompt(
            section_id=state.research_task.section.section_id,
            section_title=state.research_task.section.section_title,
            section_goal=state.research_task.section.section_goal,
            task_objective=state.research_task.objective,
            required_evidence_types=state.research_task.required_evidence_types,
            source_title=document.title,
            source_url=str(document.url),
            source_type=document.source_type.value,
            source_text=self._truncate_source_text(document.text),
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
        candidates: list[ExtractedEvidenceCandidate],
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

            cleaned_summary = self._clean_optional_text(candidate.summary)
            cleaned_relevance_note = self._clean_optional_text(candidate.relevance_note)
            cleaned_tags = self._clean_tags(candidate.tags)

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
                    summary=cleaned_summary,
                    relevance_note=cleaned_relevance_note,
                    confidence=candidate.confidence,
                    tags=cleaned_tags,
                )
            )

        return normalized_items

    def _truncate_source_text(self, text: str) -> str:
        """
        Bound prompt size to keep evidence extraction fast and predictable.
        """
        return text[:MAX_SOURCE_TEXT_CHARS_FOR_SINGLE_PASS].strip()

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
