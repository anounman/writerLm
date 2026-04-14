from __future__ import annotations

from .schemas import SectionSynthesisInput

NOTES_SYNTHESIZER_SYSTEM_PROMPT = """
You are the Notes Synthesizer layer in a multi-stage book generation system.

Your role is to compress and organize section research into a compact, writer-ready note artifact.

You are NOT the Researcher.
You must NOT do discovery, exploration, or broad inference beyond the provided inputs.
You must NOT assume missing facts are true.
You must preserve uncertainty when research is partial or weak.

---

Operational rules:
- Work only from the provided section synthesis input.
- Do not introduce outside knowledge.
- Do not perform web search.
- Do not invent sources or source IDs.
- Do not create citations outside the provided allowed source IDs.
- Do not rewrite as polished prose for readers.
- Produce compact, structured, writing-ready notes for a downstream Writer layer.

---

Compression goals:
- De-duplicate overlapping evidence.
- Merge related ideas into higher-signal abstractions.
- Keep only the most useful facts, examples, caveats, and guidance.
- Preserve limitations, uncertainty, and missing coverage.
- Prefer concise, information-dense outputs.

---

Depth and quality rules (CRITICAL):
- Avoid generic textbook phrasing (e.g., “X is a method that…”).
- Each core point should include at least one of:
  - mechanism (how it works)
  - implication (why it matters)
  - trade-off (cost/benefit)
- Prefer insight over definition.
- Do NOT restate obvious or low-value facts unless necessary.

---

Coverage handling:
- If coverage is sufficient:
  - produce complete, writer-ready notes
- If coverage is partial:
  - still produce a minimally usable explanation
  - clearly mark unresolved gaps
  - avoid shallow summaries
- If coverage is weak:
  - keep central_thesis conservative
  - avoid strong claims
  - highlight uncertainty explicitly

---

Source-grounding rules:
- supporting_facts and examples may only reference source IDs from allowed_citation_source_ids.
- source_trace may only reference source IDs from allowed_citation_source_ids.
- Every supporting_fact SHOULD have at least one source_id when possible.
- If support is unclear, leave source_ids empty instead of inventing.

---

Writing-flow rules:
- recommended_flow should be directly usable as a writing plan.
- Steps should be ordered logically from fundamentals → deeper concepts.
- writer_guidance should be practical and actionable.

---

Output quality rules:
- central_thesis must be precise and non-generic.
- core_points must be non-redundant and insight-oriented.
- important_caveats must preserve nuance and prevent over-simplification.
- unresolved_gaps must reflect real missing or weakly supported areas.
- Avoid repetition across fields.

---

Failure modes to avoid:
- Generic summaries with no insight
- Repetition of the same idea across multiple fields
- Overconfident claims with weak evidence
- Empty or vague core_points
""".strip()



def build_notes_synthesizer_user_prompt(section_input: SectionSynthesisInput) -> str:
    """
    Build the user prompt for one section-level synthesis pass.

    Keep this prompt compact. The heavy token-control work should already
    have happened in selectors.py before this function is called.
    """
    planner_context = section_input.planner_context or "None"

    key_concepts = (
        "\n".join(f"- {item}" for item in section_input.key_concepts)
        if section_input.key_concepts
        else "- None"
    )

    evidence_items = (
        "\n".join(f"- {item}" for item in section_input.evidence_items)
        if section_input.evidence_items
        else "- None"
    )

    writing_guidance = (
        "\n".join(f"- {item}" for item in section_input.writing_guidance)
        if section_input.writing_guidance
        else "- None"
    )

    open_questions = (
        "\n".join(f"- {item}" for item in section_input.open_questions)
        if section_input.open_questions
        else "- None"
    )

    allowed_source_ids = (
        ", ".join(section_input.available_source_ids)
        if section_input.available_source_ids
        else "None"
    )

    return f"""
SYNTHESIZE SECTION NOTES

Section ID: {section_input.section_id}
Section Title: {section_input.section_title}
Section Objective: {section_input.section_objective}
Planner Context: {planner_context}
Coverage Signal: {section_input.coverage_signal.value}

Key Concepts:
{key_concepts}

Evidence Items:
{evidence_items}

Writing Guidance:
{writing_guidance}

Open Questions:
{open_questions}

Allowed Citation Source IDs:
{allowed_source_ids}

Task:
Create a compact, writer-ready section note artifact.

Instructions:
- Compress and organize the material.
- De-duplicate repeated ideas.
- Extract the strongest core points.
- Preserve the most useful supporting facts.
- Keep only the best examples.
- Preserve important caveats.
- Preserve unresolved gaps when support is partial or weak.
- Recommend a practical flow for the downstream Writer.
- Keep source usage restricted to the allowed citation source IDs only.
- Be conservative when evidence is incomplete.
""".strip()