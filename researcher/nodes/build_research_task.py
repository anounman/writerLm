from __future__ import annotations

from pydantic import BaseModel, Field

from researcher.constants import (
    DEFAULT_REQUIRED_EVIDENCE_TYPES,
    DEEP_RESEARCH_REQUIRED_EVIDENCE_TYPES,
)
from researcher.schemas import EvidenceType, ResearchDepth, ResearchTask
from researcher.services.llm_structured import GroqStructuredLLM
from researcher.state import ResearcherState
from researcher.utils.ids import make_research_task_id


class BuildResearchTaskOutput(BaseModel):
    objective: str = Field(..., description="Clear research objective for the section.")
    scope_inclusions: list[str] = Field(
        default_factory=list,
        description="Topics or angles that must be covered.",
    )
    scope_exclusions: list[str] = Field(
        default_factory=list,
        description="Topics or angles intentionally excluded.",
    )
    research_questions: list[str] = Field(
        default_factory=list,
        description="Guiding research questions for this section.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Useful assumptions or framing constraints.",
    )


BUILD_RESEARCH_TASK_SYSTEM_PROMPT = """
You are a research-planning specialist inside a multi-stage book generation system.

Your job is to convert planner output for a single book section into a precise research brief.

You are NOT writing the section.
You are NOT producing prose.
You are preparing a research task for downstream discovery, source collection, and evidence extraction.

Your output must be practical, scoped, and useful for structured research.

Guidelines:
- Keep the objective specific and actionable.
- Scope inclusions should capture the key ideas that must be researched.
- Scope exclusions should prevent topic drift and premature expansion.
- Research questions should help downstream search and evidence gathering.
- Assumptions should be minimal and useful.
- Do not invent unnecessary complexity.
- Do not include markdown.
"""


def build_research_task_user_prompt(
    *,
    section_id: str,
    chapter_title: str,
    section_title: str,
    section_goal: str,
    section_summary: str | None,
    key_points: list[str],
    depth: ResearchDepth,
) -> str:
    summary_text = section_summary or "None"
    key_points_text = (
        "\n".join(f"- {point}" for point in key_points) if key_points else "- None"
    )
    schema_hint = """
{
  "objective": "string",
  "scope_inclusions": ["string"],
  "scope_exclusions": ["string"],
  "research_questions": ["string"],
  "assumptions": ["string"]
}
""".strip()

    return f"""
Build a research task for this book section.

Section ID: {section_id}
Chapter Title: {chapter_title}
Section Title: {section_title}
Desired Research Depth: {depth.value}

Section Goal:
{section_goal}

Section Summary:
{summary_text}

Planner Key Points:
{key_points_text}

Return one JSON object with exactly these keys:
{schema_hint}

Rules:
- `objective` is required and must be a single clear sentence.
- `scope_inclusions`, `scope_exclusions`, `research_questions`, and `assumptions` must all be arrays.
- Do not include `section_id`, `section_title`, `chapter_title`, or `research_depth` in the output.
- Do not add extra keys.
""".strip()


class BuildResearchTaskNode:

    def __init__(
        self,
        llm: GroqStructuredLLM,
        default_depth: ResearchDepth = ResearchDepth.STANDARD,
    ) -> None:
        self.llm = llm
        self.default_depth = default_depth

    def _required_evidence_types_for_depth(
        self,
        depth: ResearchDepth,
    ) -> list[EvidenceType]:
        """
        Select evidence expectations based on requested research depth.
        """
        if depth == ResearchDepth.DEEP:
            return list(DEEP_RESEARCH_REQUIRED_EVIDENCE_TYPES)

        return list(DEFAULT_REQUIRED_EVIDENCE_TYPES)

    def run(
        self,
        state: ResearcherState,
    ) -> ResearcherState:
        if state.research_task is not None:
            return state

        section = state.planner_section
        depth = self.default_depth

        user_prompt = build_research_task_user_prompt(
            section_id=section.section_id,
            chapter_title=section.chapter_title,
            section_title=section.section_title,
            section_goal=section.section_goal,
            section_summary=section.section_summary,
            key_points=section.key_points,
            depth=depth,
        )

        try:
            output = self.llm.generate_structured(
                system_prompt=BUILD_RESEARCH_TASK_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=BuildResearchTaskOutput,
            )
        except Exception as e:
            state.add_error(
                f"Failed to build research task for section '{section.section_id}': {e}"
            )
            return state
        required_evidence_types = self._required_evidence_types_for_depth(depth)
        state.research_task = ResearchTask(
            task_id=make_research_task_id(section.section_id),
            section=section,
            objective=output.objective,
            depth=depth,
            scope_inclusions=output.scope_inclusions,
            scope_exclusions=output.scope_exclusions,
            required_evidence_types=required_evidence_types,
            research_questions=output.research_questions,
            assumptions=output.assumptions,
        )

        return state
