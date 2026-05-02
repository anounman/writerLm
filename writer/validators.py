from __future__ import annotations

import re
from typing import Set

from .schemas import DiagramHint, SectionDraft, WritingStatus
from .state import WriterSectionTask


MIN_CONTENT_LENGTH = 180
SOURCE_ID_PATTERN = re.compile(r"query_[a-zA-Z0-9\-_]+__src_\d+")
CODE_FENCE_PATTERN = re.compile(r"```[a-zA-Z0-9_-]*\n")


def normalize_section_draft(
    task: WriterSectionTask,
    draft: SectionDraft,
) -> SectionDraft:
    """
    Normalize and validate a section draft against its writer input.
    """

    allowed_ids: Set[str] = set(task.section_input.allowed_citation_source_ids)
    synthesis_status = task.section_input.synthesis_status.lower().strip()

    # Keep only allowed citation ids
    draft.citations_used = [cid for cid in draft.citations_used if cid in allowed_ids]

    # Ensure IDs/titles stay aligned to task input
    draft.section_id = task.section_id
    draft.section_title = task.section_title

    # Strip content
    draft.content = draft.content.strip()

    # Remove leaked raw source ids from prose, but preserve code blocks
    # Split on code fences, only clean non-code parts
    draft.content = _clean_prose_preserve_code(draft.content)

    _ensure_required_code(task, draft)
    _ensure_required_diagram(task, draft)
    _ensure_reference_links(task, draft)
    draft.code_blocks_count = _count_code_blocks(draft.content)

    # BLOCKED upstream stays BLOCKED
    if synthesis_status == "blocked":
        draft.writing_status = WritingStatus.BLOCKED
        return draft

    # Very short content is weak
    if len(draft.content) < MIN_CONTENT_LENGTH:
        if draft.writing_status == WritingStatus.READY:
            draft.writing_status = WritingStatus.PARTIAL

    # If content still contains obvious citation leakage, downgrade
    if SOURCE_ID_PATTERN.search(draft.content):
        if draft.writing_status == WritingStatus.READY:
            draft.writing_status = WritingStatus.PARTIAL

    if draft.writing_status == WritingStatus.PARTIAL and _draft_is_assembly_ready(task, draft):
        draft.writing_status = WritingStatus.READY

    return draft


def _count_code_blocks(content: str) -> int:
    return len(CODE_FENCE_PATTERN.findall(content))


def _ensure_required_code(task: WriterSectionTask, draft: SectionDraft) -> None:
    if not task.section_input.must_include_code:
        return
    if _count_code_blocks(draft.content) > 0:
        return

    snippet = next(
        (
            item
            for item in task.section_input.code_snippets
            if item.get("code")
        ),
        None,
    )
    if snippet is None:
        return

    language = (snippet.get("language") or "python").strip() or "python"
    description = (snippet.get("description") or "Try the smallest working version:").strip()
    code = str(snippet.get("code", "")).strip()
    if not code:
        return

    draft.content = (
        f"{draft.content.rstrip()}\n\n"
        "### Code Example\n"
        f"{description}\n\n"
        f"```{language}\n{code}\n```"
    )


def _ensure_required_diagram(task: WriterSectionTask, draft: SectionDraft) -> None:
    if not task.section_input.must_include_diagram:
        return
    if "DIAGRAM:" in draft.content:
        return

    suggestion = (task.section_input.diagram_suggestions or [{}])[0]
    diagram_type = suggestion.get("diagram_type") or "flowchart"
    title = suggestion.get("title") or f"{task.section_title}: visual map"
    description = suggestion.get("description") or (
        "A compact visual map connecting the idea, the action, and the result."
    )
    elements = suggestion.get("elements") or [
        task.section_title,
        "Example",
        "Implementation",
        "Result",
    ]
    element_text = ", ".join(str(item) for item in elements if item)

    draft.content = (
        f"{draft.content.rstrip()}\n\n"
        f"DIAGRAM: [{diagram_type}] - {title}\n"
        f"{description}\n"
        f"Elements: {element_text}"
    )

    if not draft.diagram_hints:
        draft.diagram_hints.append(
            DiagramHint(
                diagram_type=str(diagram_type),
                title=str(title),
                description=str(description),
                latex_label=None,
            )
        )


def _ensure_reference_links(task: WriterSectionTask, draft: SectionDraft) -> None:
    if "Further Reading" in draft.content:
        return

    links = [
        item
        for item in task.section_input.reference_links
        if item.get("url")
    ]
    if not links:
        return

    rendered = []
    for item in links[:5]:
        title = item.get("title") or item.get("source_id") or "Reference"
        rendered.append(f"- {title}: {item.get('url')}")

    if rendered:
        draft.content = (
            f"{draft.content.rstrip()}\n\n"
            "### Further Reading\n"
            + "\n".join(rendered)
        )


def _draft_is_assembly_ready(task: WriterSectionTask, draft: SectionDraft) -> bool:
    if len(draft.content) < 700:
        return False
    if SOURCE_ID_PATTERN.search(draft.content):
        return False
    if task.section_input.must_include_code and draft.code_blocks_count <= 0:
        return False
    if task.section_input.must_include_diagram and "DIAGRAM:" not in draft.content and not draft.diagram_hints:
        return False
    return True


def _clean_prose_preserve_code(content: str) -> str:
    """Remove leaked source IDs and collapse whitespace in prose, but leave code blocks intact."""
    parts = re.split(r"(```[\s\S]*?```)", content)
    cleaned_parts = []
    for i, part in enumerate(parts):
        if part.startswith("```"):
            # Code block — leave untouched
            cleaned_parts.append(part)
        else:
            # Prose — clean up
            cleaned = SOURCE_ID_PATTERN.sub("", part)
            cleaned = re.sub(r"\(\s*\)", "", cleaned)
            cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
            cleaned_parts.append(cleaned)
    return "".join(cleaned_parts).strip()
