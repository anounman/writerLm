from __future__ import annotations

from ..state import WriterState
from ..schemas import WriterOutputBundle, WritingStatus


def assemble_writer_bundle_node(state: WriterState) -> WriterState:
    """
    Node:
    - Collect all completed section drafts
    - Build final WriterOutputBundle
    """

    drafts = []
    ready = 0
    partial = 0
    blocked = 0

    for task in state.completed_tasks:
        draft = task.draft
        if draft is None:
            continue

        drafts.append(draft)

        if draft.writing_status == WritingStatus.READY:
            ready += 1
        elif draft.writing_status == WritingStatus.PARTIAL:
            partial += 1
        else:
            blocked += 1

    bundle = WriterOutputBundle(
        section_drafts=drafts,
        total_sections=len(drafts),
        ready_sections=ready,
        partial_sections=partial,
        blocked_sections=blocked,
    )

    state.output_bundle = bundle
    return state