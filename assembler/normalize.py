from __future__ import annotations

from planner_agent.schemas import BookPlan
from reviewer.schemas import ReviewBundle

from .ids import build_chapter_id, build_section_id
from .schemas import (
    AssemblerPlannerBook,
    AssemblerPlannerChapter,
    AssemblerPlannerSection,
    AssemblerReviewedSection,
    AssemblyFrontMatter,
)


def normalize_book_plan(book_plan: BookPlan) -> AssemblerPlannerBook:
    normalized_chapters: list[AssemblerPlannerChapter] = []

    sorted_chapters = sorted(book_plan.chapters, key=lambda chapter: chapter.chapter_number)

    for chapter in sorted_chapters:
        chapter_title = _clean_text(chapter.title)
        chapter_goal = _clean_text(chapter.chapter_goal)
        chapter_id = build_chapter_id(
            chapter_number=chapter.chapter_number,
            chapter_title=chapter_title,
        )

        normalized_sections: list[AssemblerPlannerSection] = []

        for section_number, section in enumerate(chapter.sections, start=1):
            section_title = _clean_text(section.title)
            section_goal = _clean_text(section.goal)

            normalized_sections.append(
                AssemblerPlannerSection(
                    section_id=build_section_id(
                        chapter_number=chapter.chapter_number,
                        section_title=section_title,
                    ),
                    chapter_id=chapter_id,
                    chapter_number=chapter.chapter_number,
                    section_number=section_number,
                    chapter_title=chapter_title,
                    section_title=section_title,
                    section_goal=section_goal,
                    estimated_words=section.estimated_words,
                    key_questions=_normalize_str_list(section.key_questions),
                )
            )

        normalized_chapters.append(
            AssemblerPlannerChapter(
                chapter_id=chapter_id,
                chapter_number=chapter.chapter_number,
                chapter_title=chapter_title,
                chapter_goal=chapter_goal,
                sections=normalized_sections,
            )
        )

    return AssemblerPlannerBook(
        title=_clean_text(book_plan.title),
        audience=_clean_text(book_plan.audience),
        tone=_clean_text(book_plan.tone),
        depth=_clean_text(book_plan.depth),
        chapters=normalized_chapters,
    )


def build_front_matter(book: AssemblerPlannerBook) -> AssemblyFrontMatter:
    return AssemblyFrontMatter(
        title=book.title,
        audience=book.audience,
        tone=book.tone,
        depth=book.depth,
    )


def normalize_review_bundle(review_bundle: ReviewBundle) -> list[AssemblerReviewedSection]:
    normalized_sections: list[AssemblerReviewedSection] = []

    for result in review_bundle.sections:
        section_input = result.section_input
        section_output = result.section_output

        normalized_sections.append(
            AssemblerReviewedSection(
                section_id=_clean_text(section_output.section_id),
                section_title=_clean_text(section_output.section_title),
                reviewed_content=_normalize_prose(section_output.reviewed_content),
                review_status=section_output.review_status,
                citations_used=_normalize_str_list(section_output.citations_used),
                applied_changes_summary=_normalize_str_list(
                    section_output.applied_changes_summary
                ),
                reviewer_warnings=list(section_output.reviewer_warnings),
                synthesis_status=_clean_text(section_input.synthesis_status).lower(),
                writing_status=_clean_text(section_input.writing_status).lower(),
                central_thesis=_clean_text(section_input.central_thesis),
            )
        )

    return normalized_sections


def build_reviewed_section_map(
    sections: list[AssemblerReviewedSection],
) -> dict[str, AssemblerReviewedSection]:
    return {section.section_id: section for section in sections}


def _normalize_prose(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    normalized = "\n".join(lines).strip()
    return normalized


def _normalize_str_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized = _clean_text(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            cleaned.append(normalized)

    return cleaned


def _clean_text(value: str) -> str:
    return " ".join(str(value).split()).strip()
