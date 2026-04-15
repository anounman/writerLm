from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Set

from .schemas import ReviewStatus, ReviewerSectionOutput, ReviewWarning
from .state import ReviewerSectionTask


MIN_REVIEWED_CONTENT_LENGTH = 120
VALID_SYNTHESIS_STATUSES = {"ready", "partial", "blocked"}
VALID_WRITING_STATUSES = {"ready", "partial", "blocked"}

INLINE_CITATION_PATTERNS = [
    r"query_[a-zA-Z0-9_\-]+__src_\d+",
    r"\[\d+(?:\]\[\d+)*\]",
    r"\[[^\[\]]*__src_\d+\]",
]
RISK_WARNINGS = {
    ReviewWarning.POSSIBLE_TOPIC_DRIFT,
    ReviewWarning.UNSUPPORTED_CLAIM_RISK,
    ReviewWarning.MISSING_CAVEAT,
}


def normalize_reviewer_task(task: ReviewerSectionTask) -> ReviewerSectionTask:
    task.section_input.section_id = task.section_input.section_id.strip()
    task.section_input.section_title = task.section_input.section_title.strip()
    task.section_input.synthesis_status = task.section_input.synthesis_status.lower().strip()
    task.section_input.writing_status = task.section_input.writing_status.lower().strip()
    task.section_input.central_thesis = task.section_input.central_thesis.strip()
    task.section_input.writer_content = task.section_input.writer_content.strip()

    task.section_input.core_points = _normalize_str_list(task.section_input.core_points)
    task.section_input.supporting_facts = _normalize_str_list(task.section_input.supporting_facts)
    task.section_input.examples = _normalize_str_list(task.section_input.examples)
    task.section_input.important_caveats = _normalize_str_list(task.section_input.important_caveats)
    task.section_input.unresolved_gaps = _normalize_str_list(task.section_input.unresolved_gaps)
    task.section_input.recommended_flow = _normalize_str_list(task.section_input.recommended_flow)
    task.section_input.writer_guidance = _normalize_str_list(task.section_input.writer_guidance)
    task.section_input.allowed_citation_source_ids = _normalize_str_list(
        task.section_input.allowed_citation_source_ids
    )
    task.section_input.writer_citations_used = _dedupe_keep_order(
        _normalize_str_list(task.section_input.writer_citations_used)
    )

    return task


def validate_reviewer_task(task: ReviewerSectionTask) -> None:
    if not task.section_input.section_id:
        raise ValueError("Reviewer section input must include a non-empty section_id.")

    if not task.section_input.section_title:
        raise ValueError("Reviewer section input must include a non-empty section_title.")

    if task.section_input.synthesis_status not in VALID_SYNTHESIS_STATUSES:
        raise ValueError(
            f"Invalid synthesis_status '{task.section_input.synthesis_status}' for "
            f"section {task.section_input.section_id}."
        )

    if task.section_input.writing_status not in VALID_WRITING_STATUSES:
        raise ValueError(
            f"Invalid writing_status '{task.section_input.writing_status}' for "
            f"section {task.section_input.section_id}."
        )

    if not task.section_input.central_thesis:
        raise ValueError(
            f"Reviewer section input for {task.section_input.section_id} must include "
            "a non-empty central_thesis."
        )

    if not task.section_input.writer_content:
        raise ValueError(
            f"Reviewer section input for {task.section_input.section_id} must include "
            "non-empty writer_content."
        )

    allowed_ids: Set[str] = set(task.section_input.allowed_citation_source_ids)
    invalid_writer_citations = [
        cid for cid in task.section_input.writer_citations_used if cid not in allowed_ids
    ]
    if invalid_writer_citations:
        raise ValueError(
            f"Writer citations contain ids not allowed for section "
            f"{task.section_input.section_id}: {invalid_writer_citations}"
        )


def normalize_reviewer_output(
    task: ReviewerSectionTask,
    output: ReviewerSectionOutput,
) -> ReviewerSectionOutput:
    output.section_id = task.section_input.section_id
    output.section_title = task.section_input.section_title
    output.reviewed_content = _clean_reviewed_content(output.reviewed_content)
    output.citations_used = _dedupe_keep_order(_normalize_str_list(output.citations_used))
    output.applied_changes_summary = _normalize_str_list(output.applied_changes_summary)
    output.reviewer_warnings = _dedupe_keep_order(output.reviewer_warnings)

    allowed_ids: Set[str] = set(task.section_input.allowed_citation_source_ids)
    filtered_citations = [cid for cid in output.citations_used if cid in allowed_ids]
    removed_any_invalid = len(filtered_citations) != len(output.citations_used)
    output.citations_used = filtered_citations

    if removed_any_invalid and ReviewWarning.INVALID_CITATION_REMOVED not in output.reviewer_warnings:
        output.reviewer_warnings.append(ReviewWarning.INVALID_CITATION_REMOVED)

    if _looks_like_cleanup_happened(task.section_input.writer_content, output.reviewed_content):
        if ReviewWarning.CLEANUP_ARTIFACT_FIXED not in output.reviewer_warnings:
            output.reviewer_warnings.append(ReviewWarning.CLEANUP_ARTIFACT_FIXED)

    if _partial_uncertainty_weakened(task, output.reviewed_content):
        if ReviewWarning.PARTIAL_UNCERTAINTY_WEAKENED not in output.reviewer_warnings:
            output.reviewer_warnings.append(ReviewWarning.PARTIAL_UNCERTAINTY_WEAKENED)

    output.review_status = _normalize_review_status(task, output)

    if output.review_status == ReviewStatus.APPROVED and not output.applied_changes_summary:
        output.applied_changes_summary = ["Approved with minimal or no edits."]

    if output.review_status == ReviewStatus.FLAGGED and not output.applied_changes_summary:
        output.applied_changes_summary = ["Flagged for manual review."]

    return output


def validate_reviewer_output(
    task: ReviewerSectionTask,
    output: ReviewerSectionOutput,
) -> None:
    if output.section_id != task.section_input.section_id:
        raise ValueError(
            f"Reviewer output section_id mismatch for section {task.section_input.section_id}."
        )

    if output.section_title != task.section_input.section_title:
        raise ValueError(
            f"Reviewer output section_title mismatch for section {task.section_input.section_id}."
        )

    if output.review_status != ReviewStatus.FLAGGED:
        if not output.reviewed_content:
            raise ValueError(
                f"Reviewer output for section {task.section_input.section_id} must include "
                "non-empty reviewed_content unless flagged."
            )

        if len(output.reviewed_content) < MIN_REVIEWED_CONTENT_LENGTH:
            raise ValueError(
                f"Reviewer output for section {task.section_input.section_id} is too short "
                f"({len(output.reviewed_content)} chars)."
            )

    if _contains_inline_citation_artifact(output.reviewed_content):
        raise ValueError(
            f"Reviewer output for section {task.section_input.section_id} contains "
            "inline citation artifacts inside reviewed_content."
        )

    allowed_ids: Set[str] = set(task.section_input.allowed_citation_source_ids)
    invalid_citations = [cid for cid in output.citations_used if cid not in allowed_ids]
    if invalid_citations:
        raise ValueError(
            f"Reviewer output contains invalid citations for section "
            f"{task.section_input.section_id}: {invalid_citations}"
        )

    if output.review_status == ReviewStatus.FLAGGED and not output.applied_changes_summary:
        raise ValueError(
            f"Flagged reviewer output for section {task.section_input.section_id} must include "
            "an applied_changes_summary explaining the flag."
        )

def _normalize_review_status(
    task: ReviewerSectionTask,
    output: ReviewerSectionOutput,
) -> ReviewStatus:
    warning_set = set(output.reviewer_warnings)

    if warning_set & RISK_WARNINGS:
        return ReviewStatus.FLAGGED

    if (
        task.section_input.synthesis_status == "partial"
        and ReviewWarning.PARTIAL_UNCERTAINTY_WEAKENED in warning_set
    ):
        return ReviewStatus.FLAGGED

    similarity = _normalized_similarity(
        task.section_input.writer_content,
        output.reviewed_content,
    )

    # READY sections should often be assembly-ready even after moderate polish.
    if task.section_input.synthesis_status == "ready":
        if similarity >= 0.90:
            return ReviewStatus.APPROVED
        if warning_set <= {ReviewWarning.CLEANUP_ARTIFACT_FIXED}:
            return ReviewStatus.APPROVED

    # PARTIAL sections can still be revised safely if uncertainty is preserved.
    if task.section_input.synthesis_status == "partial":
        return ReviewStatus.REVISED

    return ReviewStatus.REVISED
def _normalize_str_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = value.strip()
        if text:
            cleaned.append(text)
    return cleaned


def _dedupe_keep_order(values: list) -> list:
    seen = set()
    deduped = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _contains_uncertainty_signal(text: str) -> bool:
    lowered = text.lower()
    signals = (
        "may",
        "might",
        "remains unclear",
        "is not fully clear",
        "not enough evidence",
        "incomplete",
        "uncertain",
        "open question",
        "open questions",
        "based on the available evidence",
        "the available evidence",
        "further research is needed",
        "is not yet clear",
        "not fully established",
        "still unclear",
        "currently unclear",
        "at this stage",
        "require further study",
        "requires further study",
        "require further research",
        "requires further research",
        "not yet well characterized",
        "not yet well documented",
        "remain open",
        "remain uncertain",
        "several aspects remain uncertain",
        "details remain incomplete",
        "remain incomplete",
        "beyond the scope",
    )
    return any(signal in lowered for signal in signals)


def _contains_inline_citation_artifact(text: str) -> bool:
    return any(re.search(pattern, text) for pattern in INLINE_CITATION_PATTERNS)


def _clean_reviewed_content(text: str) -> str:
    cleaned = text.strip()

    for pattern in INLINE_CITATION_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned)

    cleaned = re.sub(r"\(\s*,?\s*\)", "", cleaned)
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    cleaned = re.sub(r"([(\[])\s+", r"\1", cleaned)
    cleaned = re.sub(r"\s+([)\]])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


def _normalized_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _collapse_ws(a), _collapse_ws(b)).ratio()


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _looks_like_cleanup_happened(before: str, after: str) -> bool:
    before_has_artifact = (
        _contains_inline_citation_artifact(before)
        or "(, )" in before
        or "  " in before
    )
    after_has_artifact = _contains_inline_citation_artifact(after)
    return before_has_artifact and not after_has_artifact

def _partial_uncertainty_weakened(
    task: ReviewerSectionTask,
    reviewed_content: str,
) -> bool:
    if task.section_input.synthesis_status != "partial":
        return False

    if not task.section_input.unresolved_gaps and not task.section_input.important_caveats:
        return False

    lowered = reviewed_content.lower()

    strong_uncertainty_signals = (
        "remains unclear",
        "still unclear",
        "currently unclear",
        "not enough evidence",
        "incomplete",
        "uncertain",
        "open question",
        "open questions",
        "further research is needed",
        "requires further research",
        "requires further study",
        "remain open",
        "remain uncertain",
        "not yet well documented",
        "not yet well characterized",
    )
    if any(signal in lowered for signal in strong_uncertainty_signals):
        return False

    soft_limit_signals = (
        "depends on",
        "limitation",
        "limitations",
        "not covered here",
        "outside the scope",
        "beyond the scope",
        "not fully specified",
        "not specified",
        "further investigation",
        "details remain",
        "details are not provided",
        "the literature does not specify",
        "the evidence does not address",
        "remain incomplete",
        "remain unresolved",
    )
    if any(signal in lowered for signal in soft_limit_signals):
        return False

    return True