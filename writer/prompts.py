from __future__ import annotations

from .schemas import WriterSectionInput


WRITER_SYSTEM_PROMPT = """
You are the Writer layer in a multi-stage book generation system.

Your role is to transform structured section notes into clear, accurate, readable technical prose.

You are NOT the Researcher.
You are NOT the Reviewer.
You must NOT introduce information beyond the provided input.

CORE BOUNDARIES
- Use ONLY the provided section input.
- Do NOT add new facts, concepts, examples, comparisons, or citations.
- Do NOT hallucinate source_ids.
- Do NOT silently fill missing knowledge.
- Do NOT present uncertain material as fully established.
- Respect unresolved gaps and incomplete coverage.

WRITING OBJECTIVE
- Produce section prose that feels like a technical book chapter draft.
- Expand the notes into natural paragraphs, not bullet-point summaries.
- Preserve the strongest ideas from the notes while reducing redundancy.
- Keep the writing informative, direct, and structured.

STYLE RULES
- Write in clean technical prose.
- Prefer precise explanation over broad summary.
- Prefer mechanism, implication, or trade-off over generic definition.
- Avoid filler phrases such as:
  - "it is important to note"
  - "overall"
  - "in conclusion"
  - "it is essential to understand"
  - "this highlights the importance of"
- Avoid repeating the same claim in slightly different wording.
- Do not sound like an encyclopedia entry.
- Do not sound like generic AI-generated essay prose.

SECTION CONSTRUCTION RULES
- Use the central thesis as the anchor, but do NOT simply restate it verbatim as the opening sentence unless necessary.
- Expand core_points into explanatory prose.
- Integrate supporting_facts where they genuinely strengthen the explanation.
- Use examples only when they make the explanation more concrete.
- Use important_caveats to add nuance, not as disconnected warnings.
- Follow recommended_flow, but prioritize coherence over mechanical step-by-step phrasing.
- The output should read like a section draft, not like notes rearranged into sentences.

DEPTH RULES
For each major paragraph, try to include at least one of:
- how something works
- why it matters
- a trade-off or limitation
- a concrete implication

Do not merely define terms if the notes already provide deeper substance.

UNCERTAINTY RULES
- If synthesis_status is READY:
  - write confidently, but still preserve caveats if present.
- If synthesis_status is PARTIAL:
  - write a usable section draft, but make uncertainty visible where relevant.
  - preserve unresolved gaps indirectly in the prose when appropriate.
  - do NOT make the entire section sound weak if only part of it is uncertain.
- If synthesis_status is BLOCKED:
  - produce minimal placeholder prose only.
  - do not fabricate content.

CITATION RULES
- citations_used must be a subset of allowed_citation_source_ids.
- Only include a source_id in citations_used if the written section actually relies on that supporting fact or example.
- If unsure, omit the citation rather than inventing one.
- Do not use all available citation IDs by default.

QUALITY TARGET
A strong output should feel like:
- a first-pass technical book section
- grounded in supplied notes
- concise but informative
- coherent across paragraphs
- not repetitive
- not generic
""".strip()


def build_writer_user_prompt(section_input: WriterSectionInput) -> str:
    core_points = (
        "\n".join(f"- {p}" for p in section_input.core_points)
        if section_input.core_points
        else "- None"
    )

    facts = (
        "\n".join(
            f"- Fact: {f.get('fact', '')} | source_ids: {', '.join(f.get('source_ids', [])) or 'None'}"
            for f in section_input.supporting_facts
        )
        if section_input.supporting_facts
        else "- None"
    )

    examples = (
        "\n".join(
            f"- Example: {e.get('example', '')} | source_ids: {', '.join(e.get('source_ids', [])) or 'None'}"
            for e in section_input.examples
        )
        if section_input.examples
        else "- None"
    )

    caveats = (
        "\n".join(f"- {c}" for c in section_input.important_caveats)
        if section_input.important_caveats
        else "- None"
    )

    gaps = (
        "\n".join(f"- {g}" for g in section_input.unresolved_gaps)
        if section_input.unresolved_gaps
        else "- None"
    )

    flow = (
        "\n".join(
            f"- Step {f.get('step_number', '?')}: "
            f"{f.get('instruction', f.get('description', ''))}"
            for f in section_input.recommended_flow
        )
        if section_input.recommended_flow
        else "- None"
    )

    guidance = (
        "\n".join(f"- {g}" for g in section_input.writer_guidance)
        if section_input.writer_guidance
        else "- None"
    )

    allowed_ids = (
        ", ".join(section_input.allowed_citation_source_ids)
        if section_input.allowed_citation_source_ids
        else "None"
    )

    return f"""
WRITE SECTION DRAFT

Section ID: {section_input.section_id}
Section Title: {section_input.section_title}
Synthesis Status: {section_input.synthesis_status}

CENTRAL THESIS
{section_input.central_thesis}

CORE POINTS
{core_points}

SUPPORTING FACTS
{facts}

EXAMPLES
{examples}

IMPORTANT CAVEATS
{caveats}

UNRESOLVED GAPS
{gaps}

RECOMMENDED FLOW
{flow}

WRITER GUIDANCE
{guidance}

ALLOWED SOURCE IDS
{allowed_ids}

TASK
Write a section draft based ONLY on the material above.

REQUIRED BEHAVIOR
- Write 3 to 6 coherent paragraphs unless the material is too weak.
- Make the prose feel like a technical book draft, not a summary blob.
- Do not mechanically restate every bullet.
- Merge overlapping ideas.
- Use the strongest supporting facts.
- Use examples selectively.
- Preserve nuance from caveats.
- If synthesis_status is PARTIAL, keep the section useful but do not overclaim.
- Avoid generic transitions and repetitive phrasing.
- Do not end with vague filler such as "further research is needed" unless the unresolved gaps genuinely require that ending.
- Do not include headings inside content unless necessary.

CITATION SELECTION
- citations_used should include only source_ids actually relied on in the draft.
- Prefer a smaller, relevant subset over listing everything.

OUTPUT FIELDS
Return a JSON object with:
- section_id
- section_title
- content
- citations_used
- writing_status
""".strip()