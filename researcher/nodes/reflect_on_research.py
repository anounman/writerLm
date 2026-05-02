from __future__ import annotations

from pydantic import BaseModel, Field

from researcher.constants import (
    MAX_FOLLOWUP_SOURCES_PER_ROUND,
    MAX_REFLEXION_ROUNDS,
    MIN_DISTINCT_EVIDENCE_TYPES_FOR_SUFFICIENT_COVERAGE,
    MIN_EVIDENCE_ITEMS_PER_SECTION,
    MIN_SOURCE_COUNT_FOR_SUFFICIENT_COVERAGE,
    USE_LLM_REFLEXION,
)
from researcher.schemas import (
    CoverageReport,
    CoverageStatus,
    EvidenceItem,
    EvidenceType,
    QueryKind,
    ReflexionAction,
    ReflexionDecision,
    ResearchQuery,
)
from researcher.services.llm_structured import GroqStructuredLLM
from researcher.state import ResearcherState
from researcher.utils.ids import make_query_id


class FollowupQueryCandidate(BaseModel):
    kind: QueryKind = Field(..., description="Why this follow-up query exists.")
    query_text: str = Field(..., description="Targeted follow-up query text.")
    rationale: str = Field(..., description="Why this follow-up query is needed.")
    priority: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Relative importance. 1 = highest priority, 5 = lowest.",
    )


class ReflectOnResearchOutput(BaseModel):
    covered_topics: list[str] = Field(
        default_factory=list,
        description="Topics or sub-questions already covered well enough.",
    )
    missing_topics: list[str] = Field(
        default_factory=list,
        description="Topics or sub-questions that remain missing or weak.",
    )
    weak_evidence_types: list[EvidenceType] = Field(
        default_factory=list,
        description="Evidence types that are still weak or underrepresented.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Short diagnostic notes about research quality or gaps.",
    )
    action: ReflexionAction = Field(
        ...,
        description="Whether to finalize or continue with follow-up research.",
    )
    reasoning: str = Field(
        ...,
        description="Why this reflexion decision was made.",
    )
    followup_queries: list[FollowupQueryCandidate] = Field(
        default_factory=list,
        description="Targeted follow-up queries for the next research pass.",
    )


REFLECT_ON_RESEARCH_SYSTEM_PROMPT = """
You are a research critic inside a multi-stage book generation system.

Your job is to evaluate the current evidence collected for one section and decide whether:
- the section research is already sufficient, or
- a bounded follow-up research pass is needed.

You are NOT writing the section.
You are NOT summarizing sources in prose.
You are diagnosing research completeness and weakness.

Guidelines:
- Judge coverage relative to the section objective, not in general.
- Prefer practical completeness over perfectionism.
- Identify missing topics only when they are genuinely important to the section.
- Identify weak evidence types when the section would clearly benefit from them.
- Suggest follow-up queries only when additional research is actually needed.
- Keep follow-up queries targeted and non-redundant.
- Do not include markdown.
"""


def build_reflect_on_research_user_prompt(
    *,
    section_id: str,
    chapter_title: str,
    section_title: str,
    section_goal: str,
    objective: str,
    scope_inclusions: list[str],
    scope_exclusions: list[str],
    research_questions: list[str],
    required_evidence_types: list[EvidenceType],
    evidence_items: list[EvidenceItem],
    source_count: int,
    reflexion_round: int,
    max_reflexion_rounds: int,
) -> str:
    inclusions_text = (
        "\n".join(f"- {item}" for item in scope_inclusions)
        if scope_inclusions
        else "- None"
    )
    exclusions_text = (
        "\n".join(f"- {item}" for item in scope_exclusions)
        if scope_exclusions
        else "- None"
    )
    questions_text = (
        "\n".join(f"- {item}" for item in research_questions)
        if research_questions
        else "- None"
    )
    required_types_text = (
        "\n".join(f"- {item.value}" for item in required_evidence_types)
        if required_evidence_types
        else "- None"
    )
    evidence_text = _format_evidence_items_for_prompt(evidence_items)

    return f"""
Reflect on the current research coverage for this section.

Section ID: {section_id}
Chapter Title: {chapter_title}
Section Title: {section_title}
Section Goal: {section_goal}
Research Objective: {objective}

Scope Inclusions:
{inclusions_text}

Scope Exclusions:
{exclusions_text}

Research Questions:
{questions_text}

Required Evidence Types:
{required_types_text}

Current Source Count: {source_count}
Current Reflexion Round: {reflexion_round}
Maximum Reflexion Rounds: {max_reflexion_rounds}

Current Evidence Items:
{evidence_text}

Return structured reflexion output only.
""".strip()


def _format_evidence_items_for_prompt(evidence_items: list[EvidenceItem]) -> str:
    if not evidence_items:
        return "- None"

    lines: list[str] = []
    for item in evidence_items:
        lines.append(f"- Evidence ID: {item.evidence_id}")
        lines.append(f"  Type: {item.evidence_type.value}")
        lines.append(f"  Source ID: {item.source_id}")
        lines.append(f"  Content: {item.content}")
        if item.summary:
            lines.append(f"  Summary: {item.summary}")
        if item.relevance_note:
            lines.append(f"  Relevance: {item.relevance_note}")
        if item.tags:
            lines.append(f"  Tags: {', '.join(item.tags)}")
    return "\n".join(lines)


class ReflectOnResearchNode:
    """
    Critique current research coverage and decide whether follow-up research is needed.

    Responsibilities:
    - read current research artifacts from state
    - evaluate evidence coverage against the section objective
    - produce a CoverageReport
    - produce a ReflexionDecision
    - generate targeted follow-up queries when needed
    """

    def __init__(
        self,
        llm: GroqStructuredLLM,
        max_reflexion_rounds: int = MAX_REFLEXION_ROUNDS,
        max_followup_sources: int = MAX_FOLLOWUP_SOURCES_PER_ROUND,
    ) -> None:
        self.llm = llm
        self.max_reflexion_rounds = max_reflexion_rounds
        self.max_followup_sources = max_followup_sources

    def run(self, state: ResearcherState) -> ResearcherState:
        """
        Evaluate current research coverage and decide whether to continue.
        """
        if state.research_task is None:
            state.add_error(
                "Cannot reflect on research because research_task is missing."
            )
            return state

        if not state.evidence_items:
            state.add_error(
                "Cannot reflect on research because evidence_items is empty."
            )
            return state

        if state.reflexion_round >= self.max_reflexion_rounds:
            coverage_report = self._build_max_rounds_coverage_report(state)
            decision = ReflexionDecision(
                section_id=state.section_id,
                action=ReflexionAction.FINALIZE,
                reasoning=(
                    f"Reached maximum reflexion rounds ({self.max_reflexion_rounds}). "
                    "Finalizing with current research coverage."
                ),
                followup_queries=[],
                max_additional_sources=0,
            )
            state.coverage_report = coverage_report
            state.reflexion_decision = decision
            return state

        heuristic_coverage_status = self._heuristic_coverage_status(state)
        if not USE_LLM_REFLEXION:
            state.coverage_report = self._build_fallback_coverage_report(
                state,
                heuristic_coverage_status=heuristic_coverage_status,
            )
            state.reflexion_decision = self._build_fallback_decision(
                state,
                heuristic_coverage_status=heuristic_coverage_status,
            )
            return state

        user_prompt = build_reflect_on_research_user_prompt(
            section_id=state.research_task.section.section_id,
            chapter_title=state.research_task.section.chapter_title,
            section_title=state.research_task.section.section_title,
            section_goal=state.research_task.section.section_goal,
            objective=state.research_task.objective,
            scope_inclusions=state.research_task.scope_inclusions,
            scope_exclusions=state.research_task.scope_exclusions,
            research_questions=state.research_task.research_questions,
            required_evidence_types=state.research_task.required_evidence_types,
            evidence_items=state.evidence_items,
            source_count=len(state.fetched_documents),
            reflexion_round=state.reflexion_round,
            max_reflexion_rounds=self.max_reflexion_rounds,
        )

        try:
            llm_output = self.llm.generate_structured(
                system_prompt=REFLECT_ON_RESEARCH_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=ReflectOnResearchOutput,
            )
        except Exception as exc:
            state.add_warning(
                f"Reflexion model call failed for section '{state.section_id}': {exc}"
            )
            state.coverage_report = self._build_fallback_coverage_report(
                state,
                heuristic_coverage_status=heuristic_coverage_status,
            )
            state.reflexion_decision = self._build_fallback_decision(
                state,
                heuristic_coverage_status=heuristic_coverage_status,
            )
            return state

        normalized_followup_queries = self._normalize_followup_queries(
            state=state,
            candidates=llm_output.followup_queries,
        )

        final_action = llm_output.action
        if (
            final_action == ReflexionAction.FOLLOW_UP
            and not normalized_followup_queries
        ):
            final_action = ReflexionAction.FINALIZE

        state.coverage_report = CoverageReport(
            section_id=state.section_id,
            status=self._resolve_coverage_status(
                llm_action=final_action,
                heuristic_status=heuristic_coverage_status,
                missing_topics=llm_output.missing_topics,
                weak_evidence_types=llm_output.weak_evidence_types,
            ),
            covered_topics=self._clean_list(llm_output.covered_topics),
            missing_topics=self._clean_list(llm_output.missing_topics),
            weak_evidence_types=llm_output.weak_evidence_types,
            notes=self._clean_list(llm_output.notes),
        )

        state.followup_queries = normalized_followup_queries
        state.reflexion_decision = ReflexionDecision(
            section_id=state.section_id,
            action=final_action,
            reasoning=self._clean_text(llm_output.reasoning),
            followup_queries=normalized_followup_queries,
            max_additional_sources=self.max_followup_sources,
        )
        return state

    def _normalize_followup_queries(
        self,
        *,
        state: ResearcherState,
        candidates: list[FollowupQueryCandidate],
    ) -> list[ResearchQuery]:
        """
        Convert follow-up query candidates into final ResearchQuery objects.
        """
        normalized_queries: list[ResearchQuery] = []
        seen_query_texts: set[str] = set()

        for index, candidate in enumerate(candidates, start=1):
            cleaned_query_text = self._clean_text(candidate.query_text)
            if not cleaned_query_text:
                continue

            dedupe_key = cleaned_query_text.casefold()
            if dedupe_key in seen_query_texts:
                continue
            seen_query_texts.add(dedupe_key)

            normalized_queries.append(
                ResearchQuery(
                    query_id=make_query_id(
                        state.section_id,
                        cleaned_query_text,
                        index,
                    ),
                    kind=candidate.kind,
                    query_text=cleaned_query_text,
                    rationale=self._clean_text(candidate.rationale),
                    priority=candidate.priority,
                )
            )

        return normalized_queries

    def _heuristic_coverage_status(self, state: ResearcherState) -> CoverageStatus:
        """
        Cheap deterministic baseline before LLM judgment.
        """
        evidence_count = len(state.evidence_items)
        source_count = len({item.source_id for item in state.evidence_items})
        evidence_type_count = len({item.evidence_type for item in state.evidence_items})

        if (
            evidence_count >= MIN_EVIDENCE_ITEMS_PER_SECTION
            and source_count >= MIN_SOURCE_COUNT_FOR_SUFFICIENT_COVERAGE
            and evidence_type_count
            >= MIN_DISTINCT_EVIDENCE_TYPES_FOR_SUFFICIENT_COVERAGE
        ):
            return CoverageStatus.SUFFICIENT

        if evidence_count > 0:
            return CoverageStatus.PARTIAL

        return CoverageStatus.INSUFFICIENT

    def _resolve_coverage_status(
        self,
        *,
        llm_action: ReflexionAction,
        heuristic_status: CoverageStatus,
        missing_topics: list[str],
        weak_evidence_types: list[EvidenceType],
    ) -> CoverageStatus:
        """
        Merge deterministic and model-guided signals into final status.
        """
        if llm_action == ReflexionAction.FOLLOW_UP:
            if heuristic_status == CoverageStatus.INSUFFICIENT:
                return CoverageStatus.INSUFFICIENT
            return CoverageStatus.PARTIAL

        if missing_topics or weak_evidence_types:
            if heuristic_status == CoverageStatus.INSUFFICIENT:
                return CoverageStatus.INSUFFICIENT
            return CoverageStatus.PARTIAL

        return heuristic_status

    def _build_fallback_coverage_report(
        self,
        state: ResearcherState,
        *,
        heuristic_coverage_status: CoverageStatus,
    ) -> CoverageReport:
        """
        Build a deterministic fallback coverage report when the LLM call fails.
        """
        covered_topics = (
            self._clean_list(state.research_task.scope_inclusions[:3])
            if state.research_task
            else []
        )
        notes = [
            "Coverage report generated from deterministic heuristics because reflexion failed."
        ]

        return CoverageReport(
            section_id=state.section_id,
            status=heuristic_coverage_status,
            covered_topics=covered_topics,
            missing_topics=[],
            weak_evidence_types=[],
            notes=notes,
        )

    def _build_fallback_decision(
        self,
        state: ResearcherState,
        *,
        heuristic_coverage_status: CoverageStatus,
    ) -> ReflexionDecision:
        """
        Build a deterministic fallback decision when the LLM call fails.
        """
        if heuristic_coverage_status == CoverageStatus.SUFFICIENT:
            return ReflexionDecision(
                section_id=state.section_id,
                action=ReflexionAction.FINALIZE,
                reasoning=(
                    "Reflexion model failed, but heuristic coverage appears sufficient. "
                    "Finalizing current research."
                ),
                followup_queries=[],
                max_additional_sources=0,
            )

        return ReflexionDecision(
            section_id=state.section_id,
            action=ReflexionAction.FINALIZE,
            reasoning=(
                "Reflexion model failed, so follow-up planning could not be generated safely. "
                "Finalizing with current research and warnings."
            ),
            followup_queries=[],
            max_additional_sources=0,
        )

    def _build_max_rounds_coverage_report(
        self, state: ResearcherState
    ) -> CoverageReport:
        """
        Build a final coverage report when the loop budget is exhausted.
        """
        heuristic_status = self._heuristic_coverage_status(state)
        notes = [f"Reached maximum reflexion rounds ({self.max_reflexion_rounds})."]
        return CoverageReport(
            section_id=state.section_id,
            status=heuristic_status,
            covered_topics=[],
            missing_topics=[],
            weak_evidence_types=[],
            notes=notes,
        )

    def _clean_text(self, value: str) -> str:
        """
        Normalize required text fields.
        """
        return " ".join(value.split()).strip()

    def _clean_list(self, values: list[str]) -> list[str]:
        """
        Normalize, drop empties, and deduplicate list items.
        """
        cleaned_values: list[str] = []
        seen: set[str] = set()

        for value in values:
            cleaned = " ".join(value.split()).strip()
            if not cleaned:
                continue

            key = cleaned.casefold()
            if key in seen:
                continue

            seen.add(key)
            cleaned_values.append(cleaned)

        return cleaned_values
