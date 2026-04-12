from typing import Optional, TypedDict

from planner_agent.outline_schemas import ChapterOutlinePlan
from planner_agent.schemas import BookPlan, PlanningContext, UserBookRequest
from planner_agent.section_schemas import ChapterSectionPlan


class PlannerState(TypedDict):
    request: UserBookRequest
    planning_context: Optional[PlanningContext]
    chapter_outline: Optional[ChapterOutlinePlan]
    chapter_section_plans: Optional[list[ChapterSectionPlan]]
    final_book_plan: Optional[BookPlan]
    validation_issues: list[str]
