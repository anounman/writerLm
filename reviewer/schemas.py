from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel, Field, ConfigDict


class ReviewStatus(str, Enum):
    APPROVED = "approved"
    REVISED = "revised"
    FLAGGED = "flagged"


class ReviewWarning(str, Enum):
    POSSIBLE_TOPIC_DRIFT = "possible_topic_drift"
    UNSUPPORTED_CLAIM_RISK = "unsupported_claim_risk"
    MISSING_CAVEAT = "missing_caveat"
    PARTIAL_UNCERTAINTY_WEAKENED = "partial_uncertainty_weakened"
    INVALID_CITATION_REMOVED = "invalid_citation_removed"
    CLEANUP_ARTIFACT_FIXED = "cleanup_artifact_fixed"


class ReviewerSectionInput(BaseModel):
    """
    Reviewer-facing section input assembled from Notes + Writer artifacts.
    """

    model_config = ConfigDict(extra="forbid")

    section_id: str
    section_title: str

    synthesis_status: str
    central_thesis: str
    core_points: List[str] = Field(default_factory=list)
    supporting_facts: List[str] = Field(default_factory=list)
    examples: List[str] = Field(default_factory=list)
    important_caveats: List[str] = Field(default_factory=list)
    unresolved_gaps: List[str] = Field(default_factory=list)
    recommended_flow: List[str] = Field(default_factory=list)
    writer_guidance: List[str] = Field(default_factory=list)
    allowed_citation_source_ids: List[str] = Field(default_factory=list)

    writer_content: str
    writer_citations_used: List[str] = Field(default_factory=list)
    writing_status: str


class ReviewerSectionOutput(BaseModel):
    """
    Final normalized reviewer result for one section.
    """

    model_config = ConfigDict(extra="forbid")

    section_id: str
    section_title: str
    reviewed_content: str
    review_status: ReviewStatus

    citations_used: List[str] = Field(default_factory=list)
    applied_changes_summary: List[str] = Field(default_factory=list)
    reviewer_warnings: List[ReviewWarning] = Field(default_factory=list)


class ReviewerSectionResult(BaseModel):
    """
    Stored per-section artifact in the final review bundle.
    Includes both the structured input snapshot and the reviewer output.
    """

    model_config = ConfigDict(extra="forbid")

    section_input: ReviewerSectionInput
    section_output: ReviewerSectionOutput


class ReviewBundleMetadata(BaseModel):
    """
    Run-level metadata for the review bundle.
    """

    model_config = ConfigDict(extra="forbid")

    project_name: str = "book_generation"
    layer_name: str = "reviewer"
    total_sections: int
    approved_sections: int
    revised_sections: int
    flagged_sections: int


class ReviewBundle(BaseModel):
    """
    Final persisted artifact produced by the Reviewer layer.
    """

    model_config = ConfigDict(extra="forbid")

    metadata: ReviewBundleMetadata
    sections: List[ReviewerSectionResult] = Field(default_factory=list)