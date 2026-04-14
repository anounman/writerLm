from __future__ import annotations

from typing import List, Optional , Dict, Any

from pydantic import BaseModel, Field, ConfigDict

from .schemas import (
    NotesSynthesisBundle,
    SectionNoteArtifact,
    SectionSynthesisInput,
)


class NotesSynthesizerSectionTask(BaseModel):
    """
    One unit of work for the Notes Synthesizer layer.

    This is the stable per-section task record that moves through the graph.
    It starts with raw upstream references, later receives a compact
    SectionSynthesisInput, and finally receives the synthesized note artifact.
    """

    model_config = ConfigDict(extra="forbid")

    section_id: str = Field(..., min_length=1)
    section_title: str = Field(..., min_length=1)

    planner_section_ref: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Planner section data (resolved, not just a reference).",
    )

    research_section_ref: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Researcher section packet (resolved, structured data).",
    )

    synthesis_input: Optional[SectionSynthesisInput] = Field(
        default=None,
        description="Compact, token-efficient synthesis input built for this section.",
    )
    synthesized_note: Optional[SectionNoteArtifact] = Field(
        default=None,
        description="Final validated writer-ready note artifact for this section.",
    )

    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class NotesSynthesizerRuntimeConfig(BaseModel):
    """
    Runtime controls for this layer.

    Keep this layer cheap by default. These settings should mainly affect
    logging/debugging and small operational behavior, not trigger any new
    research or network activity.
    """

    model_config = ConfigDict(extra="forbid")

    debug: bool = Field(
        default=False,
        description="Enable extra debug visibility for this run.",
    )
    fail_fast: bool = Field(
        default=False,
        description="Stop the run immediately on the first hard section failure.",
    )
    max_warnings_per_section: int = Field(
        default=10,
        ge=0,
        description="Soft cap for warnings retained per section task.",
    )
    keep_source_trace: bool = Field(
        default=True,
        description="Whether synthesized notes should preserve lightweight source trace info.",
    )


class NotesSynthesizerInput(BaseModel):
    """
    Top-level input payload for the Notes Synthesizer layer.

    This should be created by the caller/orchestrator from the already-produced
    planner and researcher artifacts. The graph should not discover data on its own.
    """

    model_config = ConfigDict(extra="forbid")

    book_id: Optional[str] = Field(
        default=None,
        description="Optional book/project identifier for tracing.",
    )
    book_title: Optional[str] = Field(
        default=None,
        description="Optional book title for logging and diagnostics.",
    )

    tasks: List[NotesSynthesizerSectionTask] = Field(
        default_factory=list,
        description="All section tasks to process in this layer.",
    )
    runtime: NotesSynthesizerRuntimeConfig = Field(
        default_factory=NotesSynthesizerRuntimeConfig,
    )


class NotesSynthesizerState(BaseModel):
    """
    Mutable graph state for the Notes Synthesizer workflow.

    The graph operates over section tasks, progressively filling:
    - synthesis_input
    - synthesized_note
    - warnings/errors

    At the end, the bundle is assembled for downstream Writer consumption.
    """

    model_config = ConfigDict(extra="forbid")

    book_id: Optional[str] = Field(default=None)
    book_title: Optional[str] = Field(default=None)

    runtime: NotesSynthesizerRuntimeConfig = Field(
        default_factory=NotesSynthesizerRuntimeConfig,
    )

    pending_tasks: List[NotesSynthesizerSectionTask] = Field(default_factory=list)
    completed_tasks: List[NotesSynthesizerSectionTask] = Field(default_factory=list)
    failed_tasks: List[NotesSynthesizerSectionTask] = Field(default_factory=list)

    active_task: Optional[NotesSynthesizerSectionTask] = Field(
        default=None,
        description="The section task currently being processed by a node.",
    )

    output_bundle: Optional[NotesSynthesisBundle] = Field(
        default=None,
        description="Final assembled Notes Synthesizer output bundle.",
    )

    run_warnings: List[str] = Field(default_factory=list)
    run_errors: List[str] = Field(default_factory=list)

    @property
    def total_sections(self) -> int:
        return (
            len(self.pending_tasks)
            + len(self.completed_tasks)
            + len(self.failed_tasks)
            + (1 if self.active_task is not None else 0)
        )

    @property
    def completed_sections(self) -> int:
        return len(self.completed_tasks)

    @property
    def failed_sections(self) -> int:
        return len(self.failed_tasks)

    @property
    def has_pending_work(self) -> bool:
        return bool(self.pending_tasks) or self.active_task is not None