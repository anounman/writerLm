from __future__ import annotations

from pydantic import BaseModel, Field

from researcher.constants import DEPTH_TO_QUERY_COUNT, USE_LLM_QUERY_PLANNING
from researcher.schemas import QueryKind, ResearchQuery, ResearchTask, SearchPlan
from researcher.services.llm_structured import GroqStructuredLLM
from researcher.state import ResearcherState
from researcher.utils.ids import make_query_id


class QueryPlanItem(BaseModel):
    kind: QueryKind = Field(..., description="Why this query exists.")
    query_text: str = Field(..., description="Search query text.")
    rationale: str = Field(..., description="Why this query is useful.")
    priority: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Relative importance. 1 = highest priority, 5 = lowest.",
    )


class PlanQueriesOutput(BaseModel):
    queries: list[QueryPlanItem] = Field(
        default_factory=list,
        description="Structured research queries for discovery.",
    )


PLAN_QUERIES_SYSTEM_PROMPT = """
You are a query-planning specialist inside a research pipeline for a multi-stage book generation system.

Your job is to convert a structured research task into a small, high-quality set of search queries.

You are NOT doing the search.
You are NOT summarizing sources.
You are only planning search queries.

Guidelines:
- Each query should serve a distinct research purpose.
- Prefer concrete and searchable phrasing.
- Avoid redundant queries that would return nearly identical results.
- Cover the section objective with complementary search angles.
- Include foundational queries first, then examples, case studies, statistics, or follow-up depth where useful.
- Keep the number of queries aligned with the requested target count.
- Do not produce generic filler queries.
- Do not include markdown.
"""


def build_plan_queries_user_prompt(
    *,
    research_task: ResearchTask,
    target_query_count: int,
) -> str:
    inclusions_text = (
        "\n".join(f"- {item}" for item in research_task.scope_inclusions)
        if research_task.scope_inclusions
        else "- None"
    )
    exclusions_text = (
        "\n".join(f"- {item}" for item in research_task.scope_exclusions)
        if research_task.scope_exclusions
        else "- None"
    )
    questions_text = (
        "\n".join(f"- {item}" for item in research_task.research_questions)
        if research_task.research_questions
        else "- None"
    )
    assumptions_text = (
        "\n".join(f"- {item}" for item in research_task.assumptions)
        if research_task.assumptions
        else "- None"
    )
    required_evidence_text = (
        "\n".join(f"- {item.value}" for item in research_task.required_evidence_types)
        if research_task.required_evidence_types
        else "- None"
    )
    schema_hint = """
{
  "queries": [
    {
      "kind": "core_concept",
      "query_text": "string",
      "rationale": "string",
      "priority": 1
    }
  ]
}
""".strip()
    valid_kinds = ", ".join(kind.value for kind in QueryKind)

    return f"""
Plan search queries for this research task.

Task ID: {research_task.task_id}
Section ID: {research_task.section.section_id}
Chapter Title: {research_task.section.chapter_title}
Section Title: {research_task.section.section_title}
Research Depth: {research_task.depth.value}
Target Query Count: {target_query_count}

Objective:
{research_task.objective}

Scope Inclusions:
{inclusions_text}

Scope Exclusions:
{exclusions_text}

Research Questions:
{questions_text}

Assumptions:
{assumptions_text}

Required Evidence Types:
{required_evidence_text}

Return one JSON object with exactly this structure:
{schema_hint}

Rules:
- `queries` must be an array of objects, not strings.
- Every query object must include `kind`, `query_text`, `rationale`, and `priority`.
- Valid `kind` values are: {valid_kinds}
- `priority` must be an integer between 1 and 5.
- Generate exactly {target_query_count} query objects unless fewer truly distinct queries are possible.
- Do not add extra top-level keys.
""".strip()


class PlanQueriesNode:
    """
    Build a structured SearchPlan from a ResearchTask.

    Responsibilities:
    - read the research task from state
    - ask the LLM for targeted search queries
    - normalize them into ResearchQuery objects
    - write SearchPlan back into state
    """

    def __init__(self, llm: GroqStructuredLLM) -> None:
        self.llm = llm

    def run(self, state: ResearcherState) -> ResearcherState:
        """
        Create a SearchPlan from the current ResearchTask and store it in state.
        """
        if state.search_plan is not None:
            return state

        if state.research_task is None:
            state.add_error("Cannot plan queries because research_task is missing.")
            return state

        research_task = state.research_task
        target_query_count = self._target_query_count_for_task(research_task)

        if not USE_LLM_QUERY_PLANNING:
            queries = self._build_fallback_queries(research_task=research_task)
            state.search_plan = SearchPlan(
                task_id=research_task.task_id,
                queries=queries,
            )
            return state

        user_prompt = build_plan_queries_user_prompt(
            research_task=research_task,
            target_query_count=target_query_count,
        )

        try:
            llm_output = self.llm.generate_structured(
                system_prompt=PLAN_QUERIES_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=PlanQueriesOutput,
            )
        except Exception as exc:
            state.add_error(
                f"Failed to plan queries for section '{research_task.section.section_id}': {exc}"
            )
            return state

        queries = self._build_research_queries(
            research_task=research_task,
            planned_queries=llm_output.queries,
        )

        if not queries:
            state.add_error(
                f"Query planning produced no usable queries for section '{research_task.section.section_id}'."
            )
            return state

        state.search_plan = SearchPlan(
            task_id=research_task.task_id,
            queries=queries,
        )
        return state

    def _target_query_count_for_task(self, research_task: ResearchTask) -> int:
        """
        Determine how many queries to request based on research depth.
        """
        return DEPTH_TO_QUERY_COUNT[research_task.depth]

    def _build_research_queries(
        self,
        *,
        research_task: ResearchTask,
        planned_queries: list[QueryPlanItem],
    ) -> list[ResearchQuery]:
        """
        Convert LLM query plan items into final ResearchQuery objects.
        """
        normalized_queries: list[ResearchQuery] = []
        seen_query_texts: set[str] = set()

        for index, item in enumerate(planned_queries, start=1):
            cleaned_query_text = self._clean_query_text(item.query_text)
            if not cleaned_query_text:
                continue

            dedupe_key = cleaned_query_text.casefold()
            if dedupe_key in seen_query_texts:
                continue
            seen_query_texts.add(dedupe_key)

            normalized_queries.append(
                ResearchQuery(
                    query_id=make_query_id(
                        research_task.section.section_id,
                        cleaned_query_text,
                        index,
                    ),
                    kind=item.kind,
                    query_text=cleaned_query_text,
                    rationale=item.rationale.strip(),
                    priority=item.priority,
                )
            )

        return normalized_queries

    def _clean_query_text(self, query_text: str) -> str:
        """
        Normalize query text before storing it.
        """
        return " ".join(query_text.split()).strip()

    def _build_fallback_queries(
        self,
        *,
        research_task: ResearchTask,
    ) -> list[ResearchQuery]:
        section_title = research_task.section.section_title
        chapter_title = research_task.section.chapter_title
        task_text = f"{research_task.objective} {section_title} {chapter_title}".lower()
        if any(signal in task_text for signal in ("build", "implement", "code", "python", "api", "software", "pipeline")):
            candidates = [
                (
                    QueryKind.TECHNICAL,
                    f"{section_title} practical implementation tutorial",
                    "Find implementation-focused guidance for the section.",
                ),
                (
                    QueryKind.EXAMPLE,
                    f"{section_title} code example",
                    "Find concrete implementation examples readers can learn from.",
                ),
                (
                    QueryKind.CORE_CONCEPT,
                    f"{chapter_title} {section_title} best practices",
                    "Find reliable conceptual and best-practice coverage.",
                ),
            ]
        else:
            candidates = [
                (
                    QueryKind.CORE_CONCEPT,
                    f"{chapter_title} {section_title} explanation",
                    "Find reliable conceptual coverage.",
                ),
                (
                    QueryKind.EXAMPLE,
                    f"{section_title} worked examples exercises",
                    "Find concrete examples or problem patterns readers can learn from.",
                ),
                (
                    QueryKind.COUNTERPOINT,
                    f"{section_title} common mistakes misconceptions",
                    "Find common learner mistakes and misconceptions.",
                ),
            ]

        queries: list[ResearchQuery] = []
        seen_query_texts: set[str] = set()
        for index, (kind, query_text, rationale) in enumerate(candidates, start=1):
            cleaned_query_text = self._clean_query_text(query_text)
            dedupe_key = cleaned_query_text.casefold()
            if dedupe_key in seen_query_texts:
                continue
            seen_query_texts.add(dedupe_key)
            queries.append(
                ResearchQuery(
                    query_id=make_query_id(
                        research_task.section.section_id,
                        cleaned_query_text,
                        index,
                    ),
                    kind=kind,
                    query_text=cleaned_query_text,
                    rationale=rationale,
                    priority=index,
                )
            )

        return queries
