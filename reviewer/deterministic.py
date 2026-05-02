from __future__ import annotations

from .schemas import QualityScores, ReviewerSectionInput, ReviewerSectionOutput, ReviewStatus, ReviewWarning


def build_deterministic_reviewer_output(
    section: ReviewerSectionInput,
    *,
    error_message: str | None = None,
) -> ReviewerSectionOutput:
    warnings: list[ReviewWarning] = []

    if section.must_include_code and section.writer_code_blocks_count <= 0:
        warnings.append(ReviewWarning.MISSING_CODE_EXAMPLE)
    if section.must_include_diagram and section.writer_diagram_hints_count <= 0:
        warnings.append(ReviewWarning.MISSING_DIAGRAM)
    if section.writer_code_blocks_count <= 0 and section.writer_diagram_hints_count <= 0:
        warnings.append(ReviewWarning.PURE_TEXT_SECTION)
    if len(section.writer_content) < 700:
        warnings.append(ReviewWarning.SHALLOW_EXPLANATION)
    if error_message:
        warnings.append(ReviewWarning.CLEANUP_ARTIFACT_FIXED)

    practicality = 8 if section.writer_code_blocks_count > 0 else 5
    code_coverage = 8 if section.writer_code_blocks_count > 0 else 3
    learning_depth = 7 if len(section.writer_content) >= 900 else 5
    visual = 8 if section.writer_diagram_hints_count > 0 else 4

    status = ReviewStatus.REVISED if warnings else ReviewStatus.APPROVED
    if any(
        warning in warnings
        for warning in (
            ReviewWarning.MISSING_CODE_EXAMPLE,
            ReviewWarning.MISSING_DIAGRAM,
            ReviewWarning.PURE_TEXT_SECTION,
        )
    ):
        status = ReviewStatus.FLAGGED

    summary = ["Deterministic review preserved writer content."]
    if error_message:
        summary.append("LLM review was unavailable, so rule-based review was used.")

    return ReviewerSectionOutput(
        section_id=section.section_id,
        section_title=section.section_title,
        reviewed_content=section.writer_content.strip(),
        review_status=status,
        citations_used=[
            source_id
            for source_id in section.writer_citations_used
            if source_id in section.allowed_citation_source_ids
        ],
        applied_changes_summary=summary,
        reviewer_warnings=warnings,
        quality_scores=QualityScores(
            practicality_score=practicality,
            code_coverage_score=code_coverage,
            learning_depth_score=learning_depth,
            visual_richness_score=visual,
        ),
    )
