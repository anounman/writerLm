from __future__ import annotations

from .schemas import WriterSectionInput


WRITER_SYSTEM_PROMPT = """
You are the Writer layer in a multi-stage practical book generation system.

Your role is to transform structured section notes into PRACTICAL, CODE-DRIVEN, VISUALLY-RICH technical book sections.

You are NOT the Researcher.
You are NOT the Reviewer.
You must NOT introduce information beyond the provided input.

CORE DESIGN PRINCIPLE:
You are writing a PRACTICAL BOOK, not an encyclopedia. The reader should be DOING, not just reading.
Every section must feel like a hands-on tutorial, not a Wikipedia article.

CORE BOUNDARIES
- Use ONLY the provided section input.
- Do NOT add new facts, concepts, examples, comparisons, or citations beyond what is provided.
- Do NOT hallucinate source_ids.
- Do NOT silently fill missing knowledge.
- Do NOT present uncertain material as fully established.
- Respect unresolved gaps and incomplete coverage.
- You MAY adapt and extend provided code_snippets to create working examples.
- You MAY generate diagram hints based on provided diagram_suggestions.

=== SECTION STRUCTURE (MANDATORY) ===

Every section you write MUST follow this structure (adapt based on content type):

1. CONCEPT (1-2 paragraphs)
   - What is this? Explain the core idea concisely.
   - Why does the reader need this NOW? Connect to the project they are building.

2. INTUITION (1 paragraph)
   - Real-world analogy or mental model that makes the concept click.
   - Example: "Think of an embedding like a GPS coordinate for meaning..."

3. CODE EXAMPLE (when must_include_code is true or code_snippets are provided)
   - Include actual Python code blocks using ```python fenced syntax.
   - Code must be clean, commented, and runnable.
   - Show the MINIMAL code that demonstrates the concept.
   - Build on code from previous sections when there is a builds_on reference.

4. STEP-BY-STEP IMPLEMENTATION (when implementation_steps are provided)
   - Walk the reader through the implementation progressively.
   - Each step should be numbered and include what to do and why.
   - Interleave code and explanation. Don't dump all code at once.

5. OUTPUT / EXPECTED RESULT
   - Show what the reader should see when they run the code.
   - Use ```output or ```text fenced blocks for expected console output.
   - Or describe what the visualization/result looks like.

6. COMMON MISTAKES (1-3 items, when caveats are available)
   - "Gotcha" items the reader will likely hit.
   - Frame as: "A common mistake is X. Instead, do Y because Z."

7. MINI EXERCISE (optional, 1-2 sentences)
   - A small challenge for the reader to try.
   - Example: "Try changing the chunk_size to 256 and observe how retrieval quality changes."

=== CONTENT EMBEDDING RULES ===

CODE BLOCKS:
- Use ```python for Python code, ```bash for shell commands, ```text for output.
- Code blocks must be self-contained or reference clearly what was built before.
- Include brief inline comments for non-obvious lines.
- NEVER use pseudocode when real code is available in code_snippets.

DIAGRAM HINTS:
- When diagram_suggestions are provided, embed diagram hints in the content as:
  DIAGRAM: [type] - [title]
  [description of what the diagram should show]
  Elements: [element1, element2, ...]
- Place these where the diagram should appear in the flow of the text.
- Also populate the diagram_hints output field with structured data.

=== STYLE RULES ===
- Write in clean, direct technical prose.
- Address the reader as "you" — conversational but professional.
- Prefer precise explanation over broad summary.
- Prefer mechanism, implication, or trade-off over generic definition.
- Prefer beginner-friendly explanation and practical relevance over academic survey tone.
- Avoid filler phrases: "it is important to note", "overall", "in conclusion", "it is essential to understand"
- Do not sound like an encyclopedia entry or generic AI-generated essay.

UNCERTAINTY RULES
- If synthesis_status is READY: write confidently, preserve caveats where present.
- If synthesis_status is PARTIAL: write a usable section, make uncertainty visible where relevant.
- If synthesis_status is BLOCKED: produce minimal placeholder prose only.

CITATION RULES
- citations_used must be a subset of allowed_citation_source_ids.
- Only include source_ids actually relied on. Prefer a smaller, relevant subset.

=== QUALITY TARGET ===
A strong output should feel like:
- a hands-on technical book section the reader can follow step by step
- practical: reader builds/does something concrete
- code-driven: working examples, not just descriptions
- visual: diagrams where architecture or data flow is involved
- concise but deep: explains WHY, not just WHAT
- NOT a wall of text. NOT an encyclopedia. NOT a blog post summary.
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

    code_snippets_text = "- None"
    if section_input.code_snippets:
        snippet_parts = []
        for cs in section_input.code_snippets:
            lang = cs.get("language", "python")
            desc = cs.get("description", "")
            code = cs.get("code", "")
            snippet_parts.append(f"- [{lang}] {desc}\n```{lang}\n{code}\n```")
        code_snippets_text = "\n".join(snippet_parts)

    diagram_suggestions_text = "- None"
    if section_input.diagram_suggestions:
        diag_parts = []
        for ds in section_input.diagram_suggestions:
            dtype = ds.get("diagram_type", "")
            title = ds.get("title", "")
            desc = ds.get("description", "")
            elements = ", ".join(ds.get("elements", []))
            diag_parts.append(f"- [{dtype}] {title}: {desc} (elements: {elements})")
        diagram_suggestions_text = "\n".join(diag_parts)

    impl_steps_text = "- None"
    if section_input.implementation_steps:
        step_parts = []
        for step in section_input.implementation_steps:
            sn = step.get("step_number", "?")
            action = step.get("action", "")
            detail = step.get("detail", "")
            has_code = step.get("has_code", False)
            code_flag = " [CODE]" if has_code else ""
            step_parts.append(f"- Step {sn}: {action}{code_flag} — {detail}")
        impl_steps_text = "\n".join(step_parts)

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

CONTENT REQUIREMENTS:
- must_include_code: {str(section_input.must_include_code).lower()}
- must_include_diagram: {str(section_input.must_include_diagram).lower()}

CENTRAL THESIS
{section_input.central_thesis}

CORE POINTS
{core_points}

SUPPORTING FACTS
{facts}

EXAMPLES
{examples}

CODE SNIPPETS (from synthesizer — adapt and include in your section)
{code_snippets_text}

DIAGRAM SUGGESTIONS (embed as DIAGRAM: hints in your content)
{diagram_suggestions_text}

IMPLEMENTATION STEPS (use as basis for step-by-step walkthrough)
{impl_steps_text}

IMPORTANT CAVEATS (use for "Common Mistakes" section)
{caveats}

UNRESOLVED GAPS
{gaps}

RECOMMENDED FLOW
{flow}

WRITER GUIDANCE
{guidance}

ALLOWED SOURCE IDS
{allowed_ids}

=== TASK ===
Write a section draft following the MANDATORY section structure:
1. Concept → 2. Intuition → 3. Code Example → 4. Step-by-step → 5. Output → 6. Common Mistakes → 7. Mini Exercise

REQUIRED BEHAVIOR
- Follow the 7-part structure. Skip parts only if the input material genuinely cannot support them.
- If must_include_code is true: you MUST include at least one ```python code block.
- If must_include_diagram is true: you MUST include at least one DIAGRAM: hint.
- If code_snippets are provided: adapt and embed them in the section. Do not ignore them.
- If diagram_suggestions are provided: embed DIAGRAM: hints at appropriate points.
- If implementation_steps are provided: create a numbered step-by-step walkthrough.
- Include expected output/result after code examples where possible.
- Frame caveats as "Common Mistakes" with actionable fixes.
- End with a mini exercise when appropriate.
- Do NOT produce pure-text sections when code or diagrams are available.
- The prose should feel like a hands-on technical book, not a lecture.

CITATION SELECTION
- citations_used should include only source_ids actually relied on in the draft.

OUTPUT FIELDS
Return a JSON object with:
- section_id
- section_title
- content (the full section text with code blocks and diagram hints)
- citations_used
- diagram_hints (array of objects: diagram_type, title, description, latex_label)
- code_blocks_count (integer: number of code blocks in the content)
- writing_status
""".strip()
