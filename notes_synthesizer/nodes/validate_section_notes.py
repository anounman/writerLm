from __future__ import annotations

from ..state import NotesSynthesizerState
from ..validators import normalize_section_note


def validate_section_notes_node(
    state: NotesSynthesizerState,
) -> NotesSynthesizerState:
    """
    Node:
    - Takes active_task with synthesized_note
    - Runs normalization + validation
    - Moves task to completed or failed
    """

    task = state.active_task
    if task is None:
        return state

    if task.synthesized_note is None:
        task.errors.append("Missing synthesized_note before validation step.")
        state.failed_tasks.append(task)
        state.active_task = None
        return state

    try:
        normalized = normalize_section_note(task.synthesized_note)
        task.synthesized_note = normalized

        state.completed_tasks.append(task)

    except Exception as e:
        task.errors.append(f"Validation error: {str(e)}")
        state.failed_tasks.append(task)

        if state.runtime.fail_fast:
            raise

    finally:
        state.active_task = None

    return state