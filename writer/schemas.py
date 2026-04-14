from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel, Field, ConfigDict


# -----------------------------
# Enums
# -----------------------------

class WritingStatus(str, Enum):
    """
    Final writing status for a section.

    Mirrors Synthesizer status but from a writing perspective.
    """

    READY = "ready"
    PARTIAL = "partial"
    BLOCKED = "blocked"


# -----------------------------
# Core Input (from Synthesizer)
# -----------------------------

class WriterSectionInput(BaseModel):
    """
    Input to the Writer layer for a single section.

    This is derived directly from SectionNoteArtifact.
    Keep it explicit to avoid hidden coupling with previous layers.
    """

    model_config = ConfigDict(extra="forbid")

    section_id: str
    section_title: str

    synthesis_status: str  # keep flexible to match upstream enum

    central_thesis: str
    core_points: List[str]

    supporting_facts: List[dict] = Field(
        default_factory=list,
        description="Each item should include fact text + source_ids.",
    )

    examples: List[dict] = Field(
        default_factory=list,
        description="Each item should include example text + source_ids.",
    )

    important_caveats: List[str] = Field(default_factory=list)
    unresolved_gaps: List[str] = Field(default_factory=list)

    recommended_flow: List[dict] = Field(
        default_factory=list,
        description="Ordered steps describing how to structure the section.",
    )

    writer_guidance: List[str] = Field(default_factory=list)

    allowed_citation_source_ids: List[str] = Field(default_factory=list)


# -----------------------------
# Output Per Section
# -----------------------------

class SectionDraft(BaseModel):
    """
    Final written output for one section.

    This is what Reviewer and Assembler will consume.
    """

    model_config = ConfigDict(extra="forbid")

    section_id: str
    section_title: str

    content: str = Field(
        ...,
        description="Final written section text in clean, natural language.",
    )

    citations_used: List[str] = Field(
        default_factory=list,
        description="Subset of allowed source_ids actually used in writing.",
    )

    writing_status: WritingStatus


# -----------------------------
# Bundle Output
# -----------------------------

class WriterOutputBundle(BaseModel):
    """
    Final output of the Writer layer.

    Contains all section drafts.
    """

    model_config = ConfigDict(extra="forbid")

    section_drafts: List[SectionDraft]

    total_sections: int
    ready_sections: int
    partial_sections: int
    blocked_sections: int