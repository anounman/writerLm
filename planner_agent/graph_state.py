from typing import Optional, TypedDict

from schemas import UserBookRequest, PlanningContext, BookPlan
from outline_schemas import ChapterOutlinePlan
from section_schemas import ChapterSectionPlan


class PlannerState(TypedDict):
    request: UserBookRequest
    planning_context: Optional[PlanningContext]
    chapter_outline: Optional[ChapterOutlinePlan]
    chapter_section_plans: Optional[list[ChapterSectionPlan]]
    final_book_plan: Optional[BookPlan]
    validation_issues: list[str]