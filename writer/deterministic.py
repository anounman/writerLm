from __future__ import annotations

from .schemas import DiagramHint, SectionDraft, WriterSectionInput, WritingStatus


def build_deterministic_section_draft(section_input: WriterSectionInput) -> SectionDraft:
    core_points = _render_core_points(section_input)
    build_goal = _build_goal_sentence(section_input)
    subject = _subject_label(section_input)

    content_parts = [
        "### Concept",
        (
            f"{section_input.section_title} is a focused checkpoint in the book's learning path. "
            f"{section_input.central_thesis} {build_goal}"
        ),
        core_points,
        "### Checkpoint",
        (
            "Before moving on, you should be able to explain what input this step receives, "
            f"what it produces, and how you would know it worked. That habit keeps {subject} "
            "clear as the material becomes more complex."
        ),
        "### Intuition",
        (
            f"Think of {subject} as a chain of connected ideas. Each step should make the "
            "next step easier to understand, apply, or verify. If one step is vague, the "
            "reader loses the thread, so this section makes the important moving parts "
            "visible and testable."
        ),
    ]

    diagram_hints: list[DiagramHint] = []
    if section_input.diagram_suggestions:
        suggestion = section_input.diagram_suggestions[0]
        content_parts.append(_render_diagram_hint(suggestion, section_input))
        diagram_hints.append(
            DiagramHint(
                diagram_type=str(suggestion.get("diagram_type") or "flowchart"),
                title=str(suggestion.get("title") or f"{section_input.section_title}: visual map"),
                description=str(suggestion.get("description") or "Visual map for the section."),
                latex_label=None,
            )
        )

    if section_input.code_snippets:
        content_parts.extend(
            [
                "### Code Example",
                _render_code_snippet(section_input.code_snippets[0]),
                _expected_output_for_snippet(section_input.code_snippets[0]),
            ]
        )

    if section_input.implementation_steps:
        content_parts.extend(
            [
                "### Step-by-step Implementation",
                _render_steps(section_input),
            ]
        )

    content_parts.extend(
        [
            "### Output / Expected Result",
            (
                "The expected result is not just that the code runs. You should see a concrete "
                "artifact: a solved example, a derived formula, a diagram, a short explanation, "
                "a working code result, or a visible project outcome. Save that artifact or write "
                "a small summary so the next section has something real to build on."
            ),
            "### Common Mistakes",
            _render_common_mistakes(section_input),
            "### Mini Exercise",
            (
                "Change one input, parameter, or file. Run the code again and write down what "
                "changed. If nothing changed, add one print statement or assertion that makes "
                "the hidden state visible."
            ),
        ]
    )

    if section_input.reference_links:
        content_parts.extend(
            [
                "### Further Reading",
                "\n".join(
                    f"- {item.get('title') or item.get('source_id')}: {item.get('url')}"
                    for item in section_input.reference_links[:5]
                    if item.get("url")
                ),
            ]
        )

    content = "\n\n".join(part for part in content_parts if part)
    return SectionDraft(
        section_id=section_input.section_id,
        section_title=section_input.section_title,
        content=content,
        citations_used=list(section_input.allowed_citation_source_ids[:3]),
        diagram_hints=diagram_hints,
        code_blocks_count=content.count("```"),
        writing_status=(
            WritingStatus.PARTIAL
            if section_input.synthesis_status.lower() == "partial"
            else WritingStatus.READY
        ),
    )


def _build_goal_sentence(section_input: WriterSectionInput) -> str:
    if section_input.implementation_steps:
        first = section_input.implementation_steps[0].get("action", "build the next step")
        return f"In practice, you will {first.lower()} and verify it before continuing."
    return "In practice, you will connect the idea to the next measurable project step."


def _render_core_points(section_input: WriterSectionInput) -> str:
    points = section_input.core_points[:4]
    if not points:
        points = [
            "Keep the step small enough to test.",
            "Connect the output to the next idea, example, or implementation step.",
        ]
    rendered = "\n".join(f"- {point}" for point in points)
    return "### Key Idea\n" + rendered


def _subject_label(section_input: WriterSectionInput) -> str:
    text = " ".join(
        part
        for part in (
            section_input.section_title,
            section_input.chapter_title,
            section_input.central_thesis,
        )
        if part
    ).lower()
    if any(signal in text for signal in ("rag", "retrieval", "embedding", "vector")):
        return "the RAG system"
    if any(signal in text for signal in ("transformer", "attention", "model", "neural")):
        return "the model architecture"
    if any(signal in text for signal in ("equation", "matrix", "calculus", "probability", "proof")):
        return "the mathematical argument"
    return "the subject"


def _render_diagram_hint(suggestion: dict, section_input: WriterSectionInput) -> str:
    diagram_type = suggestion.get("diagram_type") or "flowchart"
    title = suggestion.get("title") or f"{section_input.section_title}: visual map"
    description = suggestion.get("description") or (
        "A visual map from concept to implementation to expected result."
    )
    elements = suggestion.get("elements") or [
        "Concept",
        "Code",
        "Output",
        "Improve",
    ]
    return "\n".join(
        [
            f"DIAGRAM: [{diagram_type}] - {title}",
            str(description),
            "Elements: " + ", ".join(str(item) for item in elements),
        ]
    )


def _render_code_snippet(snippet: dict) -> str:
    language = snippet.get("language") or "python"
    description = snippet.get("description") or "Run the smallest working example first."
    code = snippet.get("code") or "print('hello from the project step')"
    return f"{description}\n\n```{language}\n{code}\n```"


def _expected_output_for_snippet(snippet: dict) -> str:
    language = (snippet.get("language") or "python").lower()
    if language in {"bash", "sh", "shell"}:
        return (
            "If the command succeeds, your terminal should either return to the prompt "
            "without errors or print a short confirmation message. Treat any import error "
            "as a dependency problem to fix before writing more code."
        )
    return (
        "The printed output is your first test. It should be small, boring, and easy to "
        "inspect. In a RAG project, boring output is good: it means the pipeline stage is "
        "predictable enough to connect to the next stage."
    )


def _render_steps(section_input: WriterSectionInput) -> str:
    lines = []
    for index, step in enumerate(section_input.implementation_steps, start=1):
        action = step.get("action", "Do the next step")
        detail = step.get("detail", "")
        why = " This matters because each RAG component should fail loudly and locally."
        lines.append(f"{step.get('step_number', index)}. {action}: {detail}{why}".strip())
    return "\n".join(lines)


def _render_common_mistakes(section_input: WriterSectionInput) -> str:
    caveats = section_input.important_caveats[:3] or [
        "Trying to build the final version before the small version works.",
        "Changing several things at once, which makes debugging harder.",
    ]
    return "\n".join(
        f"- Watch for this: {item} Fix it by testing the smallest visible behavior before moving on."
        for item in caveats
    )
