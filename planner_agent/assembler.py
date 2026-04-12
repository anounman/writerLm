from planner_agent.schemas import BookPlan, ChapterPlan, SectionPlan, UserBookRequest
from planner_agent.section_schemas import ChapterSectionPlan


class BookPlanAssembler:
    def assemble(
        self,
        request: UserBookRequest,
        chapter_section_plans: list[ChapterSectionPlan],
        title: str,
    ) -> BookPlan:
        sorted_chapters = sorted(
            chapter_section_plans,
            key=lambda chapter: chapter.chapter_number,
        )

        chapters: list[ChapterPlan] = []

        for chapter_plan in sorted_chapters:
            sections = [
                SectionPlan(
                    title=section.title,
                    goal=section.goal,
                    key_questions=section.key_questions,
                    estimated_words=section.estimated_words,
                )
                for section in chapter_plan.sections
            ]

            chapters.append(
                ChapterPlan(
                    chapter_number=chapter_plan.chapter_number,
                    title=chapter_plan.chapter_title,
                    chapter_goal=chapter_plan.chapter_goal,
                    sections=sections,
                )
            )

        return BookPlan(
            title=title,
            audience=request.audience,
            tone=request.tone,
            depth=request.depth,
            chapters=chapters,
        )
