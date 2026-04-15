from __future__ import annotations

from .node import LLMClientProtocol, review_section_safe
from .schemas import (
    ReviewBundle,
    ReviewBundleMetadata,
    ReviewStatus,
    ReviewerSectionResult,
)
from .state import ReviewerSectionTask


def run_reviewer(
    tasks: list[ReviewerSectionTask],
    llm_client: LLMClientProtocol,
) -> ReviewBundle:
    completed_sections: list[ReviewerSectionResult] = []

    approved_count = 0
    revised_count = 0
    flagged_count = 0

    for task in tasks:
        reviewed_task = review_section_safe(task=task, llm_client=llm_client)

        if reviewed_task.section_output is None:
            raise ValueError(
                f"Reviewer failed for section {reviewed_task.section_input.section_id}: "
                f"{reviewed_task.error_message}"
            )

        review_status = reviewed_task.section_output.review_status

        if review_status == ReviewStatus.APPROVED:
            approved_count += 1
        elif review_status == ReviewStatus.REVISED:
            revised_count += 1
        elif review_status == ReviewStatus.FLAGGED:
            flagged_count += 1

        completed_sections.append(
            ReviewerSectionResult(
                section_input=reviewed_task.section_input,
                section_output=reviewed_task.section_output,
            )
        )

    metadata = ReviewBundleMetadata(
        total_sections=len(completed_sections),
        approved_sections=approved_count,
        revised_sections=revised_count,
        flagged_sections=flagged_count,
    )

    return ReviewBundle(
        metadata=metadata,
        sections=completed_sections,
    )
