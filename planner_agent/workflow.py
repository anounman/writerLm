from __future__ import annotations

from typing import Any

from planner_agent.graph_state import PlannerState
from planner_agent.planner_graph import build_planner_graph
from planner_agent.schemas import BookPlan, UserBookRequest


class PlannerWorkflow:
    """
    Thin adapter around the planner graph so orchestration layers can treat the
    planner as a reusable workflow with a stable `run(...)` entrypoint.
    """

    def __init__(self, llm: Any | None = None) -> None:
        self.llm = llm
        self.graph = build_planner_graph()

    def run(self, planner_input: UserBookRequest | dict[str, Any]) -> BookPlan:
        request = self._coerce_request(planner_input)
        initial_state: PlannerState = {
            "request": request,
            "planning_context": None,
            "chapter_outline": None,
            "chapter_section_plans": None,
            "final_book_plan": None,
            "validation_issues": [],
        }

        result = self.graph.invoke(initial_state)
        final_book_plan = result.get("final_book_plan")

        if final_book_plan is None:
            raise ValueError("Planner workflow finished without producing a final_book_plan.")

        validation_issues = result.get("validation_issues", [])
        if validation_issues:
            issue_text = "; ".join(validation_issues)
            raise ValueError(f"Planner workflow produced validation issues: {issue_text}")

        return final_book_plan

    def _coerce_request(
        self,
        planner_input: UserBookRequest | dict[str, Any],
    ) -> UserBookRequest:
        if isinstance(planner_input, UserBookRequest):
            return planner_input

        if isinstance(planner_input, dict):
            return UserBookRequest.model_validate(planner_input)

        raise TypeError(
            "PlannerWorkflow.run expects planner_input to be a UserBookRequest or dict."
        )
