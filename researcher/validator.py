from __future__ import annotations

from researcher.constants import (
    MIN_EVIDENCE_ITEMS_PER_SECTION,
    MIN_SOURCE_COUNT_FOR_SUFFICIENT_COVERAGE,
)
from researcher.schemas import (
    CoverageStatus,
    SectionResearchPacket,
    ValidationIssue,
    ValidationReport,
)
from researcher.state import ResearcherState


class ResearchPacketValidator:
    """
    Validate the final SectionResearchPacket before handoff to the next layer.

    Responsibilities:
    - check required packet structure
    - verify evidence/source linkage
    - check minimum research sufficiency signals
    - return a structured ValidationReport
    """

    def validate_state(self, state: ResearcherState) -> ValidationReport:
        """
        Validate the research packet currently stored in state.
        """
        if state.research_packet is None:
            return ValidationReport(
                ok=False,
                issues=[
                    ValidationIssue(
                        code="missing_research_packet",
                        message="Research packet is missing from state.",
                        severity="error",
                    )
                ],
            )

        report = self.validate_packet(state.research_packet)
        state.validation_report = report
        return report

    def validate_packet(self, packet: SectionResearchPacket) -> ValidationReport:
        """
        Validate one assembled SectionResearchPacket.
        """
        issues: list[ValidationIssue] = []

        self._validate_identity_fields(packet, issues)
        self._validate_objective(packet, issues)
        self._validate_evidence(packet, issues)
        self._validate_sources(packet, issues)
        self._validate_evidence_source_linkage(packet, issues)
        self._validate_required_evidence_diversity(packet, issues)
        self._validate_coverage(packet, issues)
        self._validate_writing_guidance(packet, issues)

        ok = not any(issue.severity == "error" for issue in issues)
        return ValidationReport(ok=ok, issues=issues)

    def _validate_identity_fields(
        self,
        packet: SectionResearchPacket,
        issues: list[ValidationIssue],
    ) -> None:
        """
        Ensure core packet identity fields are present.
        """
        if not packet.packet_id.strip():
            issues.append(
                ValidationIssue(
                    code="missing_packet_id",
                    message="Research packet is missing packet_id.",
                    severity="error",
                )
            )

        if not packet.task_id.strip():
            issues.append(
                ValidationIssue(
                    code="missing_task_id",
                    message="Research packet is missing task_id.",
                    severity="error",
                )
            )

        if not packet.section_id.strip():
            issues.append(
                ValidationIssue(
                    code="missing_section_id",
                    message="Research packet is missing section_id.",
                    severity="error",
                )
            )

        if not packet.chapter_id.strip():
            issues.append(
                ValidationIssue(
                    code="missing_chapter_id",
                    message="Research packet is missing chapter_id.",
                    severity="error",
                )
            )

        if not packet.section_title.strip():
            issues.append(
                ValidationIssue(
                    code="missing_section_title",
                    message="Research packet is missing section_title.",
                    severity="error",
                )
            )

    def _validate_objective(
        self,
        packet: SectionResearchPacket,
        issues: list[ValidationIssue],
    ) -> None:
        """
        Ensure the packet has a usable objective.
        """
        if not packet.objective.strip():
            issues.append(
                ValidationIssue(
                    code="missing_objective",
                    message="Research packet is missing objective.",
                    severity="error",
                )
            )
            return

        if len(packet.objective.split()) < 3:
            issues.append(
                ValidationIssue(
                    code="weak_objective",
                    message="Research packet objective looks unusually short.",
                    severity="warning",
                )
            )

    def _validate_evidence(
        self,
        packet: SectionResearchPacket,
        issues: list[ValidationIssue],
    ) -> None:
        """
        Check evidence presence and basic quality floor.
        """
        if not packet.evidence_items:
            issues.append(
                ValidationIssue(
                    code="missing_evidence",
                    message="Research packet contains no evidence items.",
                    severity="error",
                )
            )
            return

        if len(packet.evidence_items) < MIN_EVIDENCE_ITEMS_PER_SECTION:
            issues.append(
                ValidationIssue(
                    code="low_evidence_count",
                    message=(
                        f"Research packet has only {len(packet.evidence_items)} evidence items; "
                        f"recommended minimum is {MIN_EVIDENCE_ITEMS_PER_SECTION}."
                    ),
                    severity="warning",
                )
            )

        empty_content_count = sum(
            1 for item in packet.evidence_items if not item.content.strip()
        )
        if empty_content_count > 0:
            issues.append(
                ValidationIssue(
                    code="empty_evidence_content",
                    message=f"{empty_content_count} evidence items have empty content.",
                    severity="error",
                )
            )

    def _validate_sources(
        self,
        packet: SectionResearchPacket,
        issues: list[ValidationIssue],
    ) -> None:
        """
        Check source presence and basic sufficiency.
        """
        if not packet.sources:
            issues.append(
                ValidationIssue(
                    code="missing_sources",
                    message="Research packet contains no sources.",
                    severity="error",
                )
            )
            return

        if len(packet.sources) < MIN_SOURCE_COUNT_FOR_SUFFICIENT_COVERAGE:
            issues.append(
                ValidationIssue(
                    code="low_source_count",
                    message=(
                        f"Research packet has only {len(packet.sources)} sources; "
                        f"recommended minimum is {MIN_SOURCE_COUNT_FOR_SUFFICIENT_COVERAGE}."
                    ),
                    severity="warning",
                )
            )

        missing_title_count = sum(
            1 for source in packet.sources if not source.title.strip()
        )
        if missing_title_count > 0:
            issues.append(
                ValidationIssue(
                    code="sources_missing_title",
                    message=f"{missing_title_count} sources are missing a title.",
                    severity="warning",
                )
            )

    def _validate_evidence_source_linkage(
        self,
        packet: SectionResearchPacket,
        issues: list[ValidationIssue],
    ) -> None:
        """
        Ensure all evidence items point to known sources and section ids are consistent.
        """
        source_ids = {source.source_id for source in packet.sources}
        reverse_link_map = {
            source.source_id: set(source.evidence_ids) for source in packet.sources
        }

        missing_source_links = []
        inconsistent_section_ids = []
        missing_reverse_links = []

        for evidence in packet.evidence_items:
            if evidence.source_id not in source_ids:
                missing_source_links.append(evidence.evidence_id)

            if evidence.section_id != packet.section_id:
                inconsistent_section_ids.append(evidence.evidence_id)

            if evidence.source_id in reverse_link_map:
                if evidence.evidence_id not in reverse_link_map[evidence.source_id]:
                    missing_reverse_links.append(evidence.evidence_id)

        if missing_source_links:
            issues.append(
                ValidationIssue(
                    code="evidence_missing_source_link",
                    message=(
                        "Some evidence items point to unknown sources: "
                        + ", ".join(missing_source_links[:5])
                    ),
                    severity="error",
                )
            )

        if inconsistent_section_ids:
            issues.append(
                ValidationIssue(
                    code="evidence_section_mismatch",
                    message=(
                        "Some evidence items have section_id different from the packet section: "
                        + ", ".join(inconsistent_section_ids[:5])
                    ),
                    severity="error",
                )
            )

        if missing_reverse_links:
            issues.append(
                ValidationIssue(
                    code="missing_reverse_evidence_links",
                    message=(
                        "Some evidence items are not attached back to their source registry entry: "
                        + ", ".join(missing_reverse_links[:5])
                    ),
                    severity="warning",
                )
            )

    def _validate_required_evidence_diversity(
        self,
        packet: SectionResearchPacket,
        issues: list[ValidationIssue],
    ) -> None:
        """
        Check whether the packet contains a healthy spread of evidence types.
        """
        if not packet.evidence_items:
            return

        distinct_types = {item.evidence_type.value for item in packet.evidence_items}
        if len(distinct_types) < 2:
            issues.append(
                ValidationIssue(
                    code="low_evidence_type_diversity",
                    message="Research packet has very low evidence type diversity.",
                    severity="warning",
                )
            )

        if not any(
            item.evidence_type.value == "definition" for item in packet.evidence_items
        ):
            issues.append(
                ValidationIssue(
                    code="missing_definition_evidence",
                    message="Research packet contains no definition evidence.",
                    severity="warning",
                )
            )

        if not any(
            item.evidence_type.value == "fact" for item in packet.evidence_items
        ):
            issues.append(
                ValidationIssue(
                    code="missing_fact_evidence",
                    message="Research packet contains no fact evidence.",
                    severity="warning",
                )
            )

    def _validate_coverage(
        self,
        packet: SectionResearchPacket,
        issues: list[ValidationIssue],
    ) -> None:
        """
        Validate coverage report consistency and usefulness.
        """
        if packet.coverage_report is None:
            issues.append(
                ValidationIssue(
                    code="missing_coverage_report",
                    message="Research packet is missing coverage_report.",
                    severity="warning",
                )
            )
            return

        if packet.coverage_report.section_id != packet.section_id:
            issues.append(
                ValidationIssue(
                    code="coverage_section_mismatch",
                    message="Coverage report section_id does not match packet section_id.",
                    severity="error",
                )
            )

        if (
            packet.coverage_report.status == CoverageStatus.INSUFFICIENT
            and len(packet.evidence_items) >= MIN_EVIDENCE_ITEMS_PER_SECTION
        ):
            issues.append(
                ValidationIssue(
                    code="coverage_evidence_tension",
                    message=(
                        "Coverage report says insufficient despite a non-trivial amount of evidence. "
                        "Review reflexion outcome."
                    ),
                    severity="warning",
                )
            )

        if (
            packet.coverage_report.status == CoverageStatus.SUFFICIENT
            and packet.coverage_report.missing_topics
        ):
            issues.append(
                ValidationIssue(
                    code="coverage_missing_topics_tension",
                    message=(
                        "Coverage report is marked sufficient but still contains missing topics."
                    ),
                    severity="warning",
                )
            )

    def _validate_writing_guidance(
        self,
        packet: SectionResearchPacket,
        issues: list[ValidationIssue],
    ) -> None:
        """
        Check that the packet gives at least minimal handoff guidance.
        """
        if not packet.writing_guidance:
            issues.append(
                ValidationIssue(
                    code="missing_writing_guidance",
                    message="Research packet contains no writing guidance for the next layer.",
                    severity="warning",
                )
            )

        if not packet.key_concepts:
            issues.append(
                ValidationIssue(
                    code="missing_key_concepts",
                    message="Research packet contains no derived key concepts.",
                    severity="warning",
                )
            )
