from __future__ import annotations

import re
from typing import Set

from .schemas import SectionDraft, WritingStatus
from .state import WriterSectionTask


MIN_CONTENT_LENGTH = 180
SOURCE_ID_PATTERN = re.compile(r"query_[a-zA-Z0-9\-_]+__src_\d+")


def normalize_section_draft(
    task: WriterSectionTask,
    draft: SectionDraft,
) -> SectionDraft:
    """
    Normalize and validate a section draft against its writer input.
    """

    allowed_ids: Set[str] = set(task.section_input.allowed_citation_source_ids)
    synthesis_status = task.section_input.synthesis_status.lower().strip()

    # Keep only allowed citation ids
    draft.citations_used = [cid for cid in draft.citations_used if cid in allowed_ids]

    # Ensure IDs/titles stay aligned to task input
    draft.section_id = task.section_id
    draft.section_title = task.section_title

    # Strip content
    draft.content = draft.content.strip()

    # Remove leaked raw source ids from prose
    draft.content = SOURCE_ID_PATTERN.sub("", draft.content)
    draft.content = re.sub(r"\(\s*\)", "", draft.content)
    draft.content = re.sub(r"\s{2,}", " ", draft.content).strip()

    # BLOCKED upstream stays BLOCKED
    if synthesis_status == "blocked":
        draft.writing_status = WritingStatus.BLOCKED
        return draft

    # PARTIAL upstream should not become READY
    if synthesis_status == "partial" and draft.writing_status == WritingStatus.READY:
        draft.writing_status = WritingStatus.PARTIAL

    # Very short content is weak
    if len(draft.content) < MIN_CONTENT_LENGTH:
        if draft.writing_status == WritingStatus.READY:
            draft.writing_status = WritingStatus.PARTIAL

    # If content still contains obvious citation leakage, downgrade
    if SOURCE_ID_PATTERN.search(draft.content):
        if draft.writing_status == WritingStatus.READY:
            draft.writing_status = WritingStatus.PARTIAL

    return draft