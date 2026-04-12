from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from researcher.schemas import (
    CoverageReport,
    DiscoveredSource,
    PlannerSectionRef,
    ReflexionDecision,
    ResearchQuery,
    ResearchTask,
    SearchPlan,
    SectionResearchPacket,
    SourceDocument,
    SourceRegistryEntry,
    ValidationReport,
    EvidenceItem,
)


class ResearcherState(BaseModel):
    """
    Shared workflow state for the Researcher layer.

    Each node reads from and writes to this object.
    The goal is to keep every intermediate artifact visible,
    typed, and easy to debug.
    """

    # ---------------------------------------------------------
    # Input / target
    # ---------------------------------------------------------
    planner_section: PlannerSectionRef = Field(
        ...,
        description="The specific planner section currently being researched.",
    )

    # ---------------------------------------------------------
    # Core research artifacts
    # ---------------------------------------------------------
    research_task: Optional[ResearchTask] = Field(
        default=None,
        description="Research brief built from the planner section.",
    )

    search_plan: Optional[SearchPlan] = Field(
        default=None,
        description="Structured search/query plan for the current section.",
    )

    discovered_sources: List[DiscoveredSource] = Field(
        default_factory=list,
        description="Sources returned by discovery/search before fetching.",
    )

    fetched_documents: List[SourceDocument] = Field(
        default_factory=list,
        description="Normalized extracted source documents after fetch/parsing.",
    )

    source_registry: List[SourceRegistryEntry] = Field(
        default_factory=list,
        description="Tracked provenance entries for all accepted sources.",
    )

    evidence_items: List[EvidenceItem] = Field(
        default_factory=list,
        description="Structured evidence extracted from fetched sources.",
    )

    # ---------------------------------------------------------
    # Reflexion / coverage
    # ---------------------------------------------------------
    coverage_report: Optional[CoverageReport] = Field(
        default=None,
        description="Coverage assessment of the current research state.",
    )

    reflexion_decision: Optional[ReflexionDecision] = Field(
        default=None,
        description="Decision to finalize or continue with follow-up research.",
    )

    followup_queries: List[ResearchQuery] = Field(
        default_factory=list,
        description="Additional targeted queries proposed after reflexion.",
    )

    reflexion_round: int = Field(
        default=0,
        ge=0,
        description="Current reflexion loop round.",
    )

    # ---------------------------------------------------------
    # Final output
    # ---------------------------------------------------------
    research_packet: Optional[SectionResearchPacket] = Field(
        default=None,
        description="Final structured research artifact for the section.",
    )

    validation_report: Optional[ValidationReport] = Field(
        default=None,
        description="Validation result for the final research packet.",
    )

    # ---------------------------------------------------------
    # Runtime diagnostics
    # ---------------------------------------------------------
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-fatal issues collected during workflow execution.",
    )

    errors: List[str] = Field(
        default_factory=list,
        description="Fatal or blocking issues collected during workflow execution.",
    )

    # ---------------------------------------------------------
    # Convenience helpers
    # ---------------------------------------------------------
    def add_warning(self, message: str) -> None:
        """Append a non-fatal warning to the state."""
        self.warnings.append(message)

    def add_error(self, message: str) -> None:
        """Append a blocking error to the state."""
        self.errors.append(message)

    @property
    def section_id(self) -> str:
        """Shortcut access to the current planner section id."""
        return self.planner_section.section_id

    @property
    def chapter_id(self) -> str:
        """Shortcut access to the current planner chapter id."""
        return self.planner_section.chapter_id

    @property
    def has_blocking_errors(self) -> bool:
        """Whether the state has accumulated any blocking errors."""
        return len(self.errors) > 0

    @property
    def should_continue_research(self) -> bool:
        """
        True when reflexion decided the workflow should run
        another bounded research pass.
        """
        if self.reflexion_decision is None:
            return False
        return self.reflexion_decision.action.value == "follow_up"