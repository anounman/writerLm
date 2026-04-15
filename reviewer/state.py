from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

from .schemas import ReviewerSectionInput, ReviewerSectionOutput


class ReviewerSectionTask(BaseModel):
    """
    Runtime state for reviewing a single section.

    This object moves through the Reviewer workflow and carries:
    - normalized section input
    - the reviewer result once produced
    - optional error/debug fields for orchestration
    """

    model_config = ConfigDict(extra="forbid")

    section_input: ReviewerSectionInput
    section_output: Optional[ReviewerSectionOutput] = None

    error_message: Optional[str] = None