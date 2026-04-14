from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict

from .schemas import (
    WriterSectionInput,
    SectionDraft,
    WriterOutputBundle,
)


class WriterSectionTask(BaseModel):
    """
    One unit of work for the Writer layer.

    Holds:
    - input from Synthesizer
    - final written draft
    - warnings/errors
    """

    model_config = ConfigDict(extra="forbid")

    section_id: str
    section_title: str

    section_input: WriterSectionInput

    draft: Optional[SectionDraft] = None

    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class WriterRuntimeConfig(BaseModel):
    """
    Runtime config for Writer layer.

    Keep this lightweight — no heavy operations.
    """

    model_config = ConfigDict(extra="forbid")

    debug: bool = Field(default=False)
    fail_fast: bool = Field(default=False)


class WriterInput(BaseModel):
    """
    Entry input for Writer layer.
    """

    model_config = ConfigDict(extra="forbid")

    book_id: Optional[str] = None
    book_title: Optional[str] = None

    tasks: List[WriterSectionTask] = Field(default_factory=list)

    runtime: WriterRuntimeConfig = Field(default_factory=WriterRuntimeConfig)


class WriterState(BaseModel):
    """
    Mutable state used in graph execution.
    """

    model_config = ConfigDict(extra="forbid")

    book_id: Optional[str] = None
    book_title: Optional[str] = None

    runtime: WriterRuntimeConfig = Field(default_factory=WriterRuntimeConfig)

    pending_tasks: List[WriterSectionTask] = Field(default_factory=list)
    completed_tasks: List[WriterSectionTask] = Field(default_factory=list)
    failed_tasks: List[WriterSectionTask] = Field(default_factory=list)

    active_task: Optional[WriterSectionTask] = None

    output_bundle: Optional[WriterOutputBundle] = None

    run_warnings: List[str] = Field(default_factory=list)
    run_errors: List[str] = Field(default_factory=list)

    @property
    def total_sections(self) -> int:
        return (
            len(self.pending_tasks)
            + len(self.completed_tasks)
            + len(self.failed_tasks)
            + (1 if self.active_task else 0)
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