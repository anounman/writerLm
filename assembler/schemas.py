from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from reviewer.schemas import ReviewStatus, ReviewWarning


class AssemblyStatus(str, Enum):
    READY = "ready"
    READY_WITH_FLAGS = "ready_with_flags"


class AssemblyFrontMatter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    audience: str
    tone: str
    depth: str
    include_title_page: bool = True
    include_toc: bool = True


class AssemblySourceArtifacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    book_plan_path: str
    review_bundle_path: str


class AssemblerPlannerSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    chapter_id: str
    chapter_number: int = Field(..., ge=1)
    section_number: int = Field(..., ge=1)
    chapter_title: str
    section_title: str
    section_goal: str
    estimated_words: int = Field(..., ge=0)
    key_questions: list[str] = Field(default_factory=list)


class AssemblerPlannerChapter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_id: str
    chapter_number: int = Field(..., ge=1)
    chapter_title: str
    chapter_goal: str
    sections: list[AssemblerPlannerSection] = Field(default_factory=list)


class AssemblerPlannerBook(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    audience: str
    tone: str
    depth: str
    chapters: list[AssemblerPlannerChapter] = Field(default_factory=list)


class AssemblerReviewedSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    section_title: str
    reviewed_content: str
    review_status: ReviewStatus

    citations_used: list[str] = Field(default_factory=list)
    applied_changes_summary: list[str] = Field(default_factory=list)
    reviewer_warnings: list[ReviewWarning] = Field(default_factory=list)

    synthesis_status: str
    writing_status: str
    central_thesis: str


class AssemblySectionRegistryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    chapter_id: str
    chapter_number: int = Field(..., ge=1)
    section_number: int = Field(..., ge=1)
    chapter_title: str
    section_title: str
    review_status: ReviewStatus
    flagged: bool = False
    latex_label: str
    content_hash: str


class AssembledSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    chapter_id: str
    chapter_number: int = Field(..., ge=1)
    section_number: int = Field(..., ge=1)
    chapter_title: str
    section_title: str
    planner_goal: str
    estimated_words: int = Field(..., ge=0)

    review_status: ReviewStatus
    synthesis_status: str
    writing_status: str

    reviewer_warnings: list[ReviewWarning] = Field(default_factory=list)
    citations_used: list[str] = Field(default_factory=list)
    applied_changes_summary: list[str] = Field(default_factory=list)

    content: str
    content_hash: str
    latex_label: str


class AssembledChapter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_id: str
    chapter_number: int = Field(..., ge=1)
    chapter_title: str
    chapter_goal: str
    sections: list[AssembledSection] = Field(default_factory=list)


class LatexManuscript(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_filename: str = "book.tex"
    compiler: str = "pdflatex"
    document_class: str = "scrbook"
    content: str


class AssemblyBundleMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_name: str = "book_generation"
    layer_name: str = "assembler"
    assembly_status: AssemblyStatus
    book_title: str
    chapter_count: int = Field(..., ge=0)
    planned_section_count: int = Field(..., ge=0)
    assembled_section_count: int = Field(..., ge=0)
    approved_sections: int = Field(..., ge=0)
    revised_sections: int = Field(..., ge=0)
    flagged_sections: int = Field(..., ge=0)
    generated_at: datetime
    latex_output_path: str


class AssemblyBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: AssemblyBundleMetadata
    source_artifacts: AssemblySourceArtifacts
    front_matter: AssemblyFrontMatter
    chapters: list[AssembledChapter] = Field(default_factory=list)
    section_registry: list[AssemblySectionRegistryEntry] = Field(default_factory=list)
    flagged_section_ids: list[str] = Field(default_factory=list)
    full_book_text: str
    assembly_notes: list[str] = Field(default_factory=list)


class AssemblyArtifacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assembly_bundle: AssemblyBundle
    latex_manuscript: LatexManuscript
