from pydantic import ValidationError
from planner_agent.config import get_client, get_model_name
from planner_agent.outline_prompt import (
    CHAPTER_OUTLINE_SYSTEM_PROMPT,
    build_chapter_outline_prompt,
)

from planner_agent.outline_schemas import ChapterOutlinePlan
from planner_agent.schemas import PlanningContext, UserBookRequest
from planner_agent.utils import load_json_safe

class ChapterOutlineNode:
    def __init__(self) -> None:
        self.client = get_client()
        self.model_name = get_model_name()

    def _generate_raw(self, request: UserBookRequest, context: PlanningContext) -> str:
        prompt = build_chapter_outline_prompt(request, context)
        response = self.client.chat.completions.create(
            model=self.model_name,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": CHAPTER_OUTLINE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("No content returned from the model.")
        return content
    def run(
        self,
        request: UserBookRequest,
        context: PlanningContext,
    ) -> ChapterOutlinePlan:
        raw_output = self._generate_raw(request, context)
        try:
            data = load_json_safe(raw_output)
            chapter_outline = ChapterOutlinePlan.model_validate(data)
            return chapter_outline
        except (ValueError, ValidationError) as e:
            raise ValueError(f"Failed to create chapter outline: {str(e)}") from e
