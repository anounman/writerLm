from __future__ import annotations

from ..state import NotesSynthesizerState
from ..schemas import SectionNoteArtifact, SynthesisStatus
from ..llm import GroqStructuredLLM, StructuredLLMError
from ..prompt import (
    NOTES_SYNTHESIZER_SYSTEM_PROMPT,
    build_notes_synthesizer_user_prompt,
)


def synthesize_section_notes_node(
    state: NotesSynthesizerState,
    llm: GroqStructuredLLM,
) -> NotesSynthesizerState:
    """
    Node:
    - Takes active_task with synthesis_input
    - Calls LLM once
    - Produces SectionNoteArtifact
    - Attaches to active_task
    """

    task = state.active_task
    if task is None:
        return state

    if task.synthesis_input is None:
        task.errors.append("Missing synthesis_input before synthesis step.")
        state.failed_tasks.append(task)
        state.active_task = None
        return state

    try:
        system_prompt = NOTES_SYNTHESIZER_SYSTEM_PROMPT
        user_prompt = build_notes_synthesizer_user_prompt(task.synthesis_input)

        result = llm.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=SectionNoteArtifact,
        )

        # attach result
        task.synthesized_note = result

        # basic status fallback if model forgot
        if not result.synthesis_status:
            result.synthesis_status = SynthesisStatus.READY

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
