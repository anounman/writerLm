from __future__ import annotations

from ..state import WriterState, WriterSectionTask
from ..schemas import WriterSectionInput


def build_writing_input_node(state: WriterState) -> WriterState:
    """
    Node:
    - Pops next pending task
    - Prepares WriterSectionInput (already mostly present)
    - Sets active_task
    """

    if state.active_task is not None:
        return state

    if not state.pending_tasks:
        return state

    task = state.pending_tasks.pop(0)

    try:
        section_input = task.section_input

        if section_input is None:
            raise ValueError("Missing section_input for Writer task.")

        # Minimal sanity checks (cheap, no heavy validation)
        if not section_input.central_thesis:
            task.warnings.append("Missing central_thesis.")

        if not section_input.core_points:
            task.warnings.append("No core_points provided.")

        state.active_task = task

    except Exception as e:
        task.errors.append(str(e))
        state.failed_tasks.append(task)

        if state.runtime.fail_fast:
            raise

    return state