from __future__ import annotations

from ..state import NotesSynthesizerState
from ..schemas import NotesSynthesisBundle, SynthesisStatus


def assemble_notes_bundle_node(
    state: NotesSynthesizerState,
) -> NotesSynthesizerState:
    """
    Node:
    - Collects all completed section notes
    - Builds final NotesSynthesisBundle
    """

    section_notes = []
    ready = 0
    partial = 0
    blocked = 0

    for task in state.completed_tasks:
        note = task.synthesized_note
        if note is None:
            continue

        section_notes.append(note)

        if note.synthesis_status == SynthesisStatus.READY:
            ready += 1
        elif note.synthesis_status == SynthesisStatus.PARTIAL:
            partial += 1
        else:
            blocked += 1

    bundle = NotesSynthesisBundle(
        section_notes=section_notes,
        total_sections=len(section_notes),
        ready_sections=ready,
        partial_sections=partial,
        blocked_sections=blocked,
    )

    state.output_bundle = bundle
    return state