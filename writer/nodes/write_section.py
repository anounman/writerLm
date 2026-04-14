from __future__ import annotations

from ..llm import GroqStructuredLLM, StructuredLLMError
from ..prompts import WRITER_SYSTEM_PROMPT, build_writer_user_prompt
from ..schemas import SectionDraft
from ..state import WriterState


def write_section_node(
    state: WriterState,
    llm: GroqStructuredLLM,
) -> WriterState:
    """
    Node:
    - Writes one section draft from the active task
    - Stores the structured draft on the task
    """

    task = state.active_task
    if task is None:
        return state

    try:
        result = llm.generate_structured(
            system_prompt=WRITER_SYSTEM_PROMPT,
            user_prompt=build_writer_user_prompt(task.section_input),
            response_model=SectionDraft,
        )
        task.draft = result

    except StructuredLLMError as e:
        task.errors.append(f"LLM error: {str(e)}")
        state.failed_tasks.append(task)
        state.active_task = None

        if state.runtime.fail_fast:
            raise

    except Exception as e:
        task.errors.append(f"Unexpected error: {str(e)}")
        state.failed_tasks.append(task)
        state.active_task = None

        if state.runtime.fail_fast:
            raise

    return state