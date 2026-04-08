from pydantic import ValidationError

from config import get_client, get_model_name
from schemas import UserBookRequest, PlanningContext
from outline_schemas import ChapterOutlineItem
from section_schemas import ChapterSectionPlan
from section_prompt import (
    SECTION_PLANNER_SYSTEM_PROMPT,
    build_section_planner_prompt,
)
from utils import load_json_safe


class SectionPlannerNode:
    def __init__(self) -> None:
        self.client = get_client()
        self.model_name = get_model_name()

    def _generate_raw(
        self,
        request: UserBookRequest,
        context: PlanningContext,
        chapter: ChapterOutlineItem,
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SECTION_PLANNER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_section_planner_prompt(
                        request=request,
                        context=context,
                        chapter=chapter,
                    ),
                },
            ],
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("No content returned from the section planner model.")

        return content

    def run(
        self,
        request: UserBookRequest,
        context: PlanningContext,
        chapter: ChapterOutlineItem,
    ) -> ChapterSectionPlan:
        raw_output = self._generate_raw(
            request=request,
            context=context,
            chapter=chapter,
        )

        try:
            data = load_json_safe(raw_output)
            section_plan = ChapterSectionPlan.model_validate(data)
            return section_plan
        except (ValueError, ValidationError) as e:
            raise ValueError(f"Failed to create section plan: {str(e)}") from e