from planner_agent.schemas import BookPlan, UserBookRequest


def validate_book_plan(plan: BookPlan, request: UserBookRequest) -> list[str]:
    issues: list[str] = []

    if not plan.title.strip():
        issues.append("Book title is empty.")

    if not plan.chapters:
        issues.append("No chapters defined.")
        return issues
    if plan.get_chapter_count() < 3:
        issues.append("Book must have at least 3 chapters.")

    if request.chapter_count is not None and plan.get_chapter_count() != request.chapter_count:
        issues.append(
            f"Expected {request.chapter_count} chapters, but got {plan.get_chapter_count()}."
        )

    seen_chapter_titles = set()

    for chapter in plan.chapters:
        normalized_chapter_title = chapter.title.strip().lower()

        if not chapter.title.strip():
            issues.append(f"Chapter {chapter.chapter_number} has an empty title.")

        if normalized_chapter_title in seen_chapter_titles:
            issues.append(f"Duplicate chapter title: '{chapter.title}'.")
        seen_chapter_titles.add(normalized_chapter_title)

        if not chapter.chapter_goal.strip():
            issues.append(f"Chapter '{chapter.title}' has an empty goal.")

        if not chapter.sections:
            issues.append(f"Chapter {chapter.chapter_number} has no sections.")

        seen_section_titles = set()

        for section in chapter.sections:
            normalized_section_title = section.title.strip().lower()

            if not section.title.strip():
                issues.append(
                    f"Section in Chapter {chapter.chapter_number} has an empty title."
                )

            if normalized_section_title in seen_section_titles:
                issues.append(
                    f"Duplicate section title '{section.title}' in Chapter {chapter.chapter_number}."
                )
            seen_section_titles.add(normalized_section_title)

            if not section.goal.strip():
                issues.append(
                    f"Section '{section.title}' in Chapter {chapter.chapter_number} has an empty goal."
                )

            if len(section.key_questions) == 0:
                issues.append(
                    f"Section '{section.title}' in Chapter {chapter.chapter_number} has no key questions."
                )

            if section.estimated_words <= 0:
                issues.append(
                    f"Section '{section.title}' in Chapter {chapter.chapter_number} has non-positive estimated words."
                )

            if (
                request.max_section_words is not None
                and section.estimated_words > request.max_section_words
            ):
                issues.append(
                    f"Section '{section.title}' in Chapter {chapter.chapter_number} exceeds max_section_words={request.max_section_words}."
                )

    return issues
