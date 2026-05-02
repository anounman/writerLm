from planner_agent.schemas import (
    BookPlan,
    ChapterPlan,
    SectionContentRequirements,
    SectionPlan,
    UserBookRequest,
)
from planner_agent.section_schemas import ChapterSectionPlan


class BookPlanAssembler:
    def assemble(
        self,
        request: UserBookRequest,
        chapter_section_plans: list[ChapterSectionPlan],
        title: str,
        running_project: str | None = None,
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
                    content_requirements=SectionContentRequirements(
                        must_include_code=section.content_requirements.must_include_code,
                        must_include_example=section.content_requirements.must_include_example,
                        must_include_diagram=section.content_requirements.must_include_diagram,
                        suggested_diagram_type=section.content_requirements.suggested_diagram_type,
                    ),
                    builds_on=section.builds_on,
                )
                for section in chapter_plan.sections
            ]

            chapters.append(
                ChapterPlan(
                    chapter_number=chapter_plan.chapter_number,
                    title=chapter_plan.chapter_title,
                    chapter_goal=chapter_plan.chapter_goal,
                    sections=sections,
                    project_milestone=chapter_plan.project_milestone,
                )
            )

        return BookPlan(
            title=title,
            audience=request.audience,
            tone=request.tone,
            depth=request.depth,
            chapters=chapters,
            running_project=running_project,
        )
