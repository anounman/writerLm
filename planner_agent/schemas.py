from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


BEGINNER_SIGNALS = (
    "beginner",
    "beginners",
    "intro",
    "introduction",
    "introductory",
    "getting started",
    "new to",
    "novice",
    "first project",
    "first-time",
)

PRACTICAL_SIGNALS = (
    "practical",
    "hands-on",
    "implementation",
    "implement",
    "build",
    "building",
    "code",
    "coding",
    "project",
    "prototype",
    "walkthrough",
    "tutorial",
)

COMPREHENSIVE_SIGNALS = (
    "comprehensive",
    "complete guide",
    "complete handbook",
    "exhaustive",
    "deep dive",
    "reference",
    "survey",
    "state of the art",
    "research frontier",
)


class RequestConstraints(BaseModel):
    model_config = ConfigDict(extra="ignore")

    max_section_words: Optional[int] = Field(default=None, ge=150, le=2000)


class ContentDensityTargets(BaseModel):
    """Density targets that control how code-heavy, example-rich, and visual the book should be."""

    model_config = ConfigDict(extra="ignore")

    code_density: Literal["high", "medium", "low"] = Field(
        default="high",
        description="How much code should appear. 'high' = code in every section, 'medium' = most sections, 'low' = selective.",
    )
    example_density: Literal["high", "medium", "low"] = Field(
        default="high",
        description="How many concrete examples per section.",
    )
    diagram_density: Literal["high", "medium", "low"] = Field(
        default="medium",
        description="How many diagrams/visuals. 'high' = every section, 'medium' = per chapter, 'low' = key concepts only.",
    )


class UserBookRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    topic: str = Field(..., min_length=3)
    audience: str = Field(..., min_length=3)
    tone: str = "clear, practical, project-based"
    depth: Literal["introductory", "intermediate", "advanced"] = "intermediate"
    goals: List[str] = Field(default_factory=list)
    chapter_count: Optional[int] = Field(default=None, ge=3, le=20)
    max_section_words: Optional[int] = Field(default=None, ge=150, le=2000)
    constraints: Optional[RequestConstraints] = None

    # --- New fields for practical book generation ---
    project_based: bool = Field(
        default=True,
        description="If true, the book teaches through a single evolving project across chapters.",
    )
    running_project_description: Optional[str] = Field(
        default=None,
        description="Optional description of the running project (e.g., 'Build a RAG chatbot from scratch').",
    )
    content_density: ContentDensityTargets = Field(
        default_factory=ContentDensityTargets,
        description="Controls code, example, and diagram density throughout the book.",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_request_payload(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        constraints = normalized.get("constraints")
        nested_max = None

        if isinstance(constraints, dict):
            nested_max = constraints.get("max_section_words")
        elif isinstance(constraints, RequestConstraints):
            nested_max = constraints.max_section_words

        top_level_max = normalized.get("max_section_words")
        if (
            top_level_max is not None
            and nested_max is not None
            and int(top_level_max) != int(nested_max)
        ):
            raise ValueError(
                "Conflicting max_section_words values were provided at the top level "
                "and inside constraints."
            )

        if top_level_max is None and nested_max is not None:
            normalized["max_section_words"] = nested_max

        goals = normalized.get("goals")
        if isinstance(goals, str):
            stripped = goals.strip()
            normalized["goals"] = [stripped] if stripped else []

        if normalized.get("depth") in (None, ""):
            normalized["depth"] = cls._infer_depth_from_payload(normalized)

        return normalized

    @classmethod
    def _infer_depth_from_payload(cls, payload: dict[str, object]) -> str:
        text_fragments = [
            str(payload.get("topic", "")),
            str(payload.get("audience", "")),
            str(payload.get("tone", "")),
        ]

        goals = payload.get("goals")
        if isinstance(goals, list):
            text_fragments.extend(str(goal) for goal in goals)

        combined = " ".join(fragment.lower() for fragment in text_fragments if fragment)

        if any(signal in combined for signal in BEGINNER_SIGNALS):
            return "introductory"

        return "intermediate"

    @property
    def normalized_goals(self) -> list[str]:
        return [goal.strip() for goal in self.goals if goal and goal.strip()]

    @property
    def combined_intent_text(self) -> str:
        parts = [
            self.topic,
            self.audience,
            self.tone,
            *self.normalized_goals,
        ]
        return " ".join(part.lower() for part in parts if part)

    def has_any_signal(self, signals: tuple[str, ...]) -> bool:
        combined = self.combined_intent_text
        return any(signal in combined for signal in signals)

    @property
    def is_beginner_focused(self) -> bool:
        return self.depth == "introductory" or self.has_any_signal(BEGINNER_SIGNALS)

    @property
    def is_practical_focused(self) -> bool:
        return self.has_any_signal(PRACTICAL_SIGNALS)

    @property
    def wants_comprehensive_coverage(self) -> bool:
        return self.has_any_signal(COMPREHENSIVE_SIGNALS)

    @property
    def is_focused_beginner_guide(self) -> bool:
        return (
            self.is_beginner_focused
            and self.is_practical_focused
            and not self.wants_comprehensive_coverage
        )

    @property
    def preferred_chapter_range(self) -> tuple[int, int]:
        if self.is_focused_beginner_guide:
            return (5, 7)
        if self.depth == "introductory":
            return (4, 7)
        if self.depth == "advanced":
            return (8, 12)
        return (6, 10)

    @property
    def preferred_sections_per_chapter_range(self) -> tuple[int, int]:
        if self.is_focused_beginner_guide:
            return (3, 5)
        return (3, 6)

    @property
    def preferred_max_total_sections(self) -> Optional[int]:
        if self.is_focused_beginner_guide:
            return 35
        return None

    @property
    def preferred_practical_payoff_latest_chapter(self) -> Optional[int]:
        if self.is_focused_beginner_guide:
            return 4
        return None


class SectionContentRequirements(BaseModel):
    """Hard content requirements for a single section, set by the planner."""

    model_config = ConfigDict(extra="ignore")

    must_include_code: bool = Field(
        default=False,
        description="Section MUST contain at least one code example.",
    )
    must_include_example: bool = Field(
        default=True,
        description="Section MUST contain at least one concrete example or analogy.",
    )
    must_include_diagram: bool = Field(
        default=False,
        description="Section MUST contain a diagram or visualization hint.",
    )
    suggested_diagram_type: Optional[str] = Field(
        default=None,
        description="Hint for diagram type, e.g., 'flowchart', 'architecture', 'comparison table', 'sequence diagram'.",
    )


class SectionPlan(BaseModel):
    title: str
    goal: str
    key_questions: List[str] = Field(default_factory=list)
    estimated_words: int = Field(..., ge=150, le=2000)
    content_requirements: SectionContentRequirements = Field(
        default_factory=SectionContentRequirements,
        description="Hard content requirements (code, examples, diagrams) for this section.",
    )
    builds_on: Optional[str] = Field(
        default=None,
        description="Title of a previous section this one builds upon (project continuity).",
    )


class ChapterPlan(BaseModel):
    chapter_number: int = Field(..., ge=1)
    title: str
    chapter_goal: str
    sections: List[SectionPlan] = Field(default_factory=list)
    project_milestone: Optional[str] = Field(
        default=None,
        description="What the reader has built/achieved by the end of this chapter.",
    )


class BookPlan(BaseModel):
    title: str
    audience: str
    tone: str
    depth: str
    chapters: List[ChapterPlan] = Field(default_factory=list)
    running_project: Optional[str] = Field(
        default=None,
        description="Description of the evolving project that runs across all chapters.",
    )

    def get_chapter_count(self) -> int:
        return len(self.chapters)


class PlanningContext(BaseModel):
    book_purpose: str = ""
    audience_needs: List[str] = Field(default_factory=list)
    core_idea: str = ""
    main_questions: List[str] = Field(default_factory=list)
    scope_includes: List[str] = Field(default_factory=list)
    scope_excludes: List[str] = Field(default_factory=list)
    key_themes: List[str] = Field(default_factory=list)
    sequence_logic: List[str] = Field(default_factory=list)
    structure_options: List[str] = Field(default_factory=list)
    evidence_examples: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
