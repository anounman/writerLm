from __future__ import annotations

from ..state import WriterState
from ..validators import normalize_section_draft


def validate_section_node(state: WriterState) -> WriterState:
    """
    Node:
    - Validates and normalizes the written section
    - Moves task to completed or failed
    """

    task = state.active_task
    if task is None:
        return state

    if task.draft is None:
        task.errors.append("Missing draft before validation.")
        state.failed_tasks.append(task)
        state.active_task = None
        return state

    try:
        normalized = normalize_section_draft(task, task.draft)
        task.draft = normalized

        state.completed_tasks.append(task)

    except Exception as e:
        task.errors.append(f"Validation error: {str(e)}")
        state.failed_tasks.append(task)

        if state.runtime.fail_fast:
            raise

    finally:
        state.active_task = None

    return state