from __future__ import annotations

import os

from ..deterministic import build_deterministic_section_note
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
        if _deterministic_notes_enabled():
            result = build_deterministic_section_note(task.synthesis_input)
        else:
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
        task.warnings.append(f"Notes LLM fallback used after error: {str(e)}")
        task.synthesized_note = build_deterministic_section_note(task.synthesis_input)

        if not task.synthesized_note.synthesis_status:
            task.synthesized_note.synthesis_status = SynthesisStatus.READY

    except Exception as e:
        task.warnings.append(f"Notes deterministic fallback used after unexpected error: {str(e)}")
        task.synthesized_note = build_deterministic_section_note(task.synthesis_input)

        if not task.synthesized_note.synthesis_status:
            task.synthesized_note.synthesis_status = SynthesisStatus.READY

    return state


def _deterministic_notes_enabled() -> bool:
    value = os.getenv("WRITERLM_DETERMINISTIC_NOTES", "").strip().lower()
    return value in {"1", "true", "yes", "on"}
