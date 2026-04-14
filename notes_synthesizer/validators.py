from __future__ import annotations

from typing import List, Set

from .schemas import (
    SectionNoteArtifact,
    SynthesisStatus,
    CoverageSignal,
)


MAX_CORE_POINTS = 8
MAX_FACTS = 15
MAX_EXAMPLES = 8
MAX_CAVEATS = 10
MAX_GAPS = 10
MAX_FLOW_STEPS = 10
MAX_WRITER_GUIDANCE = 10


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen: Set[str] = set()
    output: List[str] = []
    for item in items:
        if not item:
            continue
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        output.append(cleaned)
    return output


def _filter_allowed_source_ids(
    source_ids: List[str],
    allowed: Set[str],
) -> List[str]:
    return [sid for sid in source_ids if sid in allowed]


def normalize_section_note(
    note: SectionNoteArtifact,
) -> SectionNoteArtifact:
    """
    Normalize + enforce constraints on a synthesized section note.
    """

    allowed_ids = set(note.allowed_citation_source_ids or [])

    # --- core text fields ---
    note.core_points = _dedupe_preserve_order(note.core_points)[:MAX_CORE_POINTS]
    note.important_caveats = _dedupe_preserve_order(note.important_caveats)[
        :MAX_CAVEATS
    ]
    note.unresolved_gaps = _dedupe_preserve_order(note.unresolved_gaps)[
        :MAX_GAPS
    ]
    note.writer_guidance = _dedupe_preserve_order(note.writer_guidance)[
        :MAX_WRITER_GUIDANCE
    ]

    # --- supporting facts ---
    for fact in note.supporting_facts:
        fact.source_ids = _filter_allowed_source_ids(
            fact.source_ids, allowed_ids
        )
    note.supporting_facts = note.supporting_facts[:MAX_FACTS]

    # --- examples ---
    for ex in note.examples:
        ex.source_ids = _filter_allowed_source_ids(
            ex.source_ids, allowed_ids
        )
    note.examples = note.examples[:MAX_EXAMPLES]

    # --- flow steps ---
    note.recommended_flow = note.recommended_flow[:MAX_FLOW_STEPS]
    for i, step in enumerate(note.recommended_flow, start=1):
        step.step_number = i

    # --- source trace ---
    for trace in note.source_trace:
        trace.source_ids = _filter_allowed_source_ids(
            trace.source_ids, allowed_ids
        )

    # --- synthesis status correction ---
    if note.coverage_signal == CoverageSignal.WEAK:
        note.synthesis_status = SynthesisStatus.PARTIAL

    if note.coverage_signal == CoverageSignal.PARTIAL:
        if not note.unresolved_gaps:
            note.unresolved_gaps.append(
                "Some aspects of this section may be under-supported based on available research."
            )
        if note.synthesis_status == SynthesisStatus.READY:
            note.synthesis_status = SynthesisStatus.PARTIAL

    return note