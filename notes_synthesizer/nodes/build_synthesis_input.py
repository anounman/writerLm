from __future__ import annotations

from typing import Any, Dict

from ..state import NotesSynthesizerState, NotesSynthesizerSectionTask
from ..selectors import build_section_synthesis_input


def _resolve_planner_section(task: NotesSynthesizerSectionTask) -> Dict[str, Any]:
    """
    Resolve planner section data.

    Assumes planner_section_ref already contains the actual dict
    OR is directly passed as a dict by the caller.
    """
    if isinstance(task.planner_section_ref, dict):
        return task.planner_section_ref

    raise ValueError(
        f"Planner section not resolved for section_id={task.section_id}"
    )


def _resolve_research_section(task: NotesSynthesizerSectionTask) -> Dict[str, Any]:
    """
    Resolve researcher section data.

    Assumes research_section_ref already contains the actual dict
    OR is directly passed as a dict by the caller.
    """
    if isinstance(task.research_section_ref, dict):
        return task.research_section_ref

    raise ValueError(
        f"Research section not resolved for section_id={task.section_id}"
    )


def build_synthesis_input_node(state: NotesSynthesizerState) -> NotesSynthesizerState:
    """
    Node:
    - Pops next pending task
    - Builds SectionSynthesisInput
    - Attaches it to active_task
    """

    if state.active_task is not None:
        return state

    if not state.pending_tasks:
        return state

    task = state.pending_tasks.pop(0)

    try:
        planner_section = _resolve_planner_section(task)
        research_section = _resolve_research_section(task)

        synthesis_input = build_section_synthesis_input(
            planner_section=planner_section,
            research_section=research_section,
        )

        task.synthesis_input = synthesis_input
        state.active_task = task

    except Exception as e:
        task.errors.append(str(e))
        state.failed_tasks.append(task)

        if state.runtime.fail_fast:
            raise

    return state