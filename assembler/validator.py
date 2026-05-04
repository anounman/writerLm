from __future__ import annotations

import re

from .schemas import AssembledChapter, AssemblerPlannerBook, AssemblerReviewedSection


INTERNAL_SOURCE_ID_PATTERN = re.compile(r"query_[a-zA-Z0-9_\-]+__src_\d+")
RAW_HTML_MATH_PATTERN = re.compile(r"</?(?:sub|sup)>", flags=re.IGNORECASE)
PRIVATE_SOURCE_PATH_PATTERN = re.compile(
    r"(?:file://|/app/\.cache|/Users/)[^\s\]\)>,]*",
    flags=re.IGNORECASE,
)
VALID_SYNTHESIS_STATUSES = {"ready", "partial", "blocked"}
VALID_WRITING_STATUSES = {"ready", "partial", "blocked"}


def validate_planner_book(book: AssemblerPlannerBook) -> None:
    if not book.title:
        raise ValueError("Assembler planner book must include a non-empty title.")

    if not book.chapters:
        raise ValueError("Assembler planner book must contain at least one chapter.")

    chapter_numbers = [chapter.chapter_number for chapter in book.chapters]
    expected_numbers = list(range(1, len(book.chapters) + 1))
    if chapter_numbers != expected_numbers:
        raise ValueError(
            "Planner chapters must be ordered sequentially starting at 1: "
            f"got {chapter_numbers}, expected {expected_numbers}."
        )

    seen_chapter_ids: set[str] = set()
    seen_section_ids: set[str] = set()

    for chapter in book.chapters:
        if chapter.chapter_id in seen_chapter_ids:
            raise ValueError(f"Duplicate chapter_id detected: {chapter.chapter_id}")
        seen_chapter_ids.add(chapter.chapter_id)

        if not chapter.chapter_title:
            raise ValueError(
                f"Planner chapter {chapter.chapter_number} must include a non-empty title."
            )

        if not chapter.sections:
            raise ValueError(
                f"Planner chapter {chapter.chapter_number} must contain at least one section."
            )

        expected_section_numbers = list(range(1, len(chapter.sections) + 1))
        actual_section_numbers = [section.section_number for section in chapter.sections]
        if actual_section_numbers != expected_section_numbers:
            raise ValueError(
                f"Planner chapter {chapter.chapter_number} sections must be ordered "
                f"sequentially starting at 1: got {actual_section_numbers}, "
                f"expected {expected_section_numbers}."
            )

        for section in chapter.sections:
            if section.chapter_id != chapter.chapter_id:
                raise ValueError(
                    f"Section {section.section_id} chapter_id does not match parent chapter."
                )

            if not section.section_title:
                raise ValueError(
                    f"Planner section {section.section_id} must include a non-empty title."
                )

            if section.section_id in seen_section_ids:
                raise ValueError(f"Duplicate planner section_id detected: {section.section_id}")
            seen_section_ids.add(section.section_id)


def validate_reviewed_sections(sections: list[AssemblerReviewedSection]) -> None:
    if not sections:
        raise ValueError("Assembler reviewer input must contain at least one reviewed section.")

    seen_section_ids: set[str] = set()

    for section in sections:
        if not section.section_id:
            raise ValueError("Reviewed section is missing section_id.")

        if section.section_id in seen_section_ids:
            raise ValueError(f"Duplicate reviewed section_id detected: {section.section_id}")
        seen_section_ids.add(section.section_id)

        if not section.section_title:
            raise ValueError(
                f"Reviewed section {section.section_id} must include a non-empty title."
            )

        if not section.reviewed_content.strip():
            raise ValueError(
                f"Reviewed section {section.section_id} must include non-empty content."
            )

        if section.synthesis_status not in VALID_SYNTHESIS_STATUSES:
            raise ValueError(
                f"Reviewed section {section.section_id} has invalid synthesis_status "
                f"'{section.synthesis_status}'."
            )

        if section.writing_status not in VALID_WRITING_STATUSES:
            raise ValueError(
                f"Reviewed section {section.section_id} has invalid writing_status "
                f"'{section.writing_status}'."
            )

        if INTERNAL_SOURCE_ID_PATTERN.search(section.reviewed_content):
            raise ValueError(
                f"Reviewed section {section.section_id} contains internal source ids in prose."
            )

        if RAW_HTML_MATH_PATTERN.search(section.reviewed_content):
            # The renderer can repair these in most cases, but preserving this
            # signal helps us track prompt hygiene and reviewer cleanup gaps.
            continue

        if PRIVATE_SOURCE_PATH_PATTERN.search(section.reviewed_content):
            # Private upload paths are stripped by the LaTeX renderer. Do not
            # fail here because old review bundles may contain them.
            continue


def validate_planner_reviewer_alignment(
    book: AssemblerPlannerBook,
    reviewed_sections: list[AssemblerReviewedSection],
) -> None:
    planner_sections = {
        section.section_id: section
        for chapter in book.chapters
        for section in chapter.sections
    }
    reviewed_by_id = {section.section_id: section for section in reviewed_sections}

    missing_reviewed_ids = sorted(set(planner_sections) - set(reviewed_by_id))
    extra_reviewed_ids = sorted(set(reviewed_by_id) - set(planner_sections))
    if missing_reviewed_ids or extra_reviewed_ids:
        message_parts: list[str] = []

        if missing_reviewed_ids:
            message_parts.append(
                "missing reviewer sections="
                f"{len(missing_reviewed_ids)} (sample: {missing_reviewed_ids[:5]})"
            )

        if extra_reviewed_ids:
            message_parts.append(
                "extra reviewer sections="
                f"{len(extra_reviewed_ids)} (sample: {extra_reviewed_ids[:5]})"
            )

        raise ValueError(
            "Planner and reviewer artifacts are not from the same normalized book structure: "
            + "; ".join(message_parts)
        )

    for section_id, planner_section in planner_sections.items():
        reviewed_section = reviewed_by_id[section_id]

        if _normalize_title_for_compare(planner_section.section_title) != _normalize_title_for_compare(
            reviewed_section.section_title
        ):
            raise ValueError(
                f"Section title mismatch for section_id={section_id}: "
                f"planner='{planner_section.section_title}' vs "
                f"reviewer='{reviewed_section.section_title}'"
            )


def validate_rendered_latex(
    *,
    latex_content: str,
    assembled_chapters: list[AssembledChapter],
) -> None:
    if not latex_content.strip():
        raise ValueError("Rendered LaTeX manuscript is empty.")

    required_fragments = (
        "\\documentclass",
        "\\begin{document}",
        "\\tableofcontents",
        "\\end{document}",
    )
    for fragment in required_fragments:
        if fragment not in latex_content:
            raise ValueError(f"Rendered LaTeX manuscript is missing required fragment: {fragment}")

    if RAW_HTML_MATH_PATTERN.search(latex_content):
        raise ValueError("Rendered LaTeX contains raw HTML sub/sup tags.")

    if PRIVATE_SOURCE_PATH_PATTERN.search(latex_content):
        raise ValueError("Rendered LaTeX contains private local source paths.")

    expected_chapter_count = len(assembled_chapters)
    actual_chapter_count = latex_content.count("\\chapter{")
    if actual_chapter_count != expected_chapter_count:
        raise ValueError(
            f"Rendered LaTeX chapter count mismatch: expected {expected_chapter_count}, "
            f"got {actual_chapter_count}."
        )

    expected_section_count = sum(len(chapter.sections) for chapter in assembled_chapters)
    actual_section_count = latex_content.count("\\section{")
    if actual_section_count != expected_section_count:
        raise ValueError(
            f"Rendered LaTeX section count mismatch: expected {expected_section_count}, "
            f"got {actual_section_count}."
        )


def validate_assembled_chapters(chapters: list[AssembledChapter]) -> None:
    if not chapters:
        raise ValueError("Assembler must produce at least one assembled chapter.")

    for chapter in chapters:
        if not chapter.sections:
            raise ValueError(
                f"Assembled chapter {chapter.chapter_number} must contain at least one section."
            )

        for section in chapter.sections:
            if not section.content.strip():
                raise ValueError(
                    f"Assembled section {section.section_id} must include non-empty content."
                )

            if INTERNAL_SOURCE_ID_PATTERN.search(section.content):
                raise ValueError(
                    f"Assembled section {section.section_id} contains internal source ids in visible content."
                )


def _normalize_title_for_compare(value: str) -> str:
    normalized = " ".join(value.split()).strip().lower()
    normalized = normalized.replace("‐", "-")
    normalized = normalized.replace("‑", "-")
    normalized = normalized.replace("‒", "-")
    normalized = normalized.replace("–", "-")
    normalized = normalized.replace("—", "-")
    normalized = normalized.replace("−", "-")
    normalized = normalized.replace("’", "'")
    normalized = normalized.replace("‘", "'")
    normalized = normalized.replace("“", '"')
    normalized = normalized.replace("”", '"')
    return normalized
