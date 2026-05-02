from __future__ import annotations

import os

from ..deterministic import build_deterministic_section_draft
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
        if _deterministic_writer_enabled():
            result = build_deterministic_section_draft(task.section_input)
        else:
            result = llm.generate_structured(
                system_prompt=WRITER_SYSTEM_PROMPT,
                user_prompt=build_writer_user_prompt(task.section_input),
                response_model=SectionDraft,
            )
        task.draft = result

    except StructuredLLMError as e:
        task.warnings.append(f"Writer deterministic fallback used after LLM error: {str(e)}")
        task.draft = build_deterministic_section_draft(task.section_input)

    except Exception as e:
        task.warnings.append(f"Writer deterministic fallback used after unexpected error: {str(e)}")
        task.draft = build_deterministic_section_draft(task.section_input)

    return state


def _deterministic_writer_enabled() -> bool:
    value = os.getenv("WRITERLM_DETERMINISTIC_WRITER", "").strip().lower()
    return value in {"1", "true", "yes", "on"}
