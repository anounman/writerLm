from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator


class CoverageSignal(str, Enum):
    SUFFICIENT = "sufficient"
    PARTIAL = "partial"
    WEAK = "weak"


class SynthesisStatus(str, Enum):
    READY = "ready"
    PARTIAL = "partial"
    BLOCKED = "blocked"


class SourceTraceItem(BaseModel):
    """
    Lightweight traceability record showing which existing source IDs
    support a synthesized note element.
    """

    model_config = ConfigDict(extra="forbid")

    note_element: str = Field(
        ...,
        description="Name of the synthesized element being supported, e.g. 'core_point_1'.",
    )
    source_ids: List[str] = Field(
        default_factory=list,
        description="Subset of source IDs already present in the research packet.",
    )

    @field_validator("source_ids")
    @classmethod
    def dedupe_source_ids(cls, value: List[str]) -> List[str]:
        seen = set()
        deduped = []
        for item in value:
            if item and item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped


class SupportingFact(BaseModel):
    """
    Compact factual statement the writer may use as grounded support.
    """

    model_config = ConfigDict(extra="forbid")

    fact: str = Field(
        ...,
        min_length=1,
        description="Concise factual support statement.",
    )
    source_ids: List[str] = Field(
        default_factory=list,
        description="Allowed supporting source IDs from the research artifact only.",
    )

    @field_validator("source_ids")
    @classmethod
    def dedupe_source_ids(cls, value: List[str]) -> List[str]:
        seen = set()
        deduped = []
        for item in value:
            if item and item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped


class ExampleNote(BaseModel):
    """
    Strong example or illustration that helps the writer explain the section.
    """

    model_config = ConfigDict(extra="forbid")

    example: str = Field(
        ...,
        min_length=1,
        description="Compact example or illustrative case.",
    )
    source_ids: List[str] = Field(
        default_factory=list,
        description="Allowed supporting source IDs from the research artifact only.",
    )

    @field_validator("source_ids")
    @classmethod
    def dedupe_source_ids(cls, value: List[str]) -> List[str]:
        seen = set()
        deduped = []
        for item in value:
            if item and item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped


class FlowStep(BaseModel):
    """
    Recommended local writing flow for the section.
    """

    model_config = ConfigDict(extra="forbid")

    step_number: int = Field(
        ...,
        ge=1,
        description="Ordered flow step.",
    )
    instruction: str = Field(
        ...,
        min_length=1,
        description="What the writer should do in this step.",
    )


class SectionSynthesisInput(BaseModel):
    """
    Compact, token-efficient input created from planner metadata and
    researcher artifacts. This is the object sent to the synthesizer LLM call.
    """

    model_config = ConfigDict(extra="forbid")

    section_id: str = Field(..., min_length=1)
    section_title: str = Field(..., min_length=1)
    section_objective: str = Field(..., min_length=1)

    planner_context: Optional[str] = Field(
        default=None,
        description="Optional short planner-derived context for this section.",
    )

    key_concepts: List[str] = Field(default_factory=list)
    evidence_items: List[str] = Field(
        default_factory=list,
        description="Compressed evidence statements, not raw source text.",
    )
    writing_guidance: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)

    coverage_signal: CoverageSignal = Field(
        ...,
        description="Normalized research coverage strength.",
    )

    available_source_ids: List[str] = Field(
        default_factory=list,
        description="All source IDs allowed for downstream citation usage.",
    )

    @field_validator("key_concepts", "evidence_items", "writing_guidance", "open_questions", "available_source_ids")
    @classmethod
    def strip_and_remove_empty(cls, value: List[str]) -> List[str]:
        cleaned = []
        seen = set()
        for item in value:
            if not item:
                continue
            normalized = item.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                cleaned.append(normalized)
        return cleaned


class SectionNoteArtifact(BaseModel):
    """
    Final compact, writer-ready note object for one section.
    """

    model_config = ConfigDict(extra="forbid")

    section_id: str = Field(..., min_length=1)
    section_title: str = Field(..., min_length=1)
    section_objective: str = Field(..., min_length=1)

    synthesis_status: SynthesisStatus = Field(...)
    coverage_signal: CoverageSignal = Field(...)

    central_thesis: str = Field(
        ...,
        min_length=1,
        description="The main claim or framing for the section.",
    )

    core_points: List[str] = Field(
        default_factory=list,
        description="Primary points the writer should cover.",
    )

    supporting_facts: List[SupportingFact] = Field(default_factory=list)
    examples: List[ExampleNote] = Field(default_factory=list)

    important_caveats: List[str] = Field(
        default_factory=list,
        description="Nuances, limits, and warnings that must be preserved.",
    )
    unresolved_gaps: List[str] = Field(
        default_factory=list,
        description="What remains uncertain or under-supported.",
    )

    recommended_flow: List[FlowStep] = Field(default_factory=list)
    writer_guidance: List[str] = Field(default_factory=list)

    allowed_citation_source_ids: List[str] = Field(
        default_factory=list,
        description="Whitelisted source IDs the writer may cite from this section note.",
    )

    source_trace: List[SourceTraceItem] = Field(
        default_factory=list,
        description="Minimal traceability from note elements to source IDs.",
    )

    @field_validator(
        "core_points",
        "important_caveats",
        "unresolved_gaps",
        "writer_guidance",
        "allowed_citation_source_ids",
    )
    @classmethod
    def strip_and_remove_empty(cls, value: List[str]) -> List[str]:
        cleaned = []
        seen = set()
        for item in value:
            if not item:
                continue
            normalized = item.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                cleaned.append(normalized)
        return cleaned


class NotesSynthesisBundle(BaseModel):
    """
    Final bundle emitted by the Notes Synthesizer layer and consumed by the Writer.
    """

    model_config = ConfigDict(extra="forbid")

    section_notes: List[SectionNoteArtifact] = Field(default_factory=list)
    total_sections: int = Field(..., ge=0)
    ready_sections: int = Field(..., ge=0)
    partial_sections: int = Field(..., ge=0)
    blocked_sections: int = Field(..., ge=0)