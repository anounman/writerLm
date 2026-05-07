from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


ApiKeyProvider = Literal["google", "groq", "tavily", "firecrawl"]
Provider = Literal["google", "groq"]
Density = Literal["high", "medium", "low"]
LatexEngine = Literal["pdflatex", "xelatex", "lualatex"]
BookType = Literal[
    "auto",
    "textbook",
    "practice_workbook",
    "course_companion",
    "implementation_guide",
    "reference_handbook",
    "conceptual_guide",
    "exam_prep",
]
TheoryPracticeBalance = Literal["auto", "theory_heavy", "balanced", "practice_heavy", "implementation_heavy"]
PedagogyStyle = Literal[
    "auto",
    "german_theoretical",
    "indian_theory_then_examples",
    "socratic",
    "exam_oriented",
    "project_based",
]
SourceUsage = Literal["auto", "primary_curriculum", "supplemental", "example_inspiration"]
ExerciseStrategy = Literal["auto", "none", "extract_patterns", "worked_examples", "practice_sets"]


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # Use plain `str` instead of `EmailStr` because Clerk generates synthetic
    # placeholder addresses (e.g. user-xxx@clerk-user.local) for OAuth users
    # who have no verified primary email.  Those fail Pydantic's strict RFC
    # 5322 domain validation even though they are perfectly valid DB values.
    email: str
    created_at: datetime


class ApiKeyUpsert(BaseModel):
    provider: ApiKeyProvider
    value: str = Field(..., min_length=3)


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: ApiKeyProvider
    key_hint: str
    created_at: datetime
    updated_at: datetime


class PipelineConfig(BaseModel):
    llm_provider: Provider = "google"
    planner_google_model: str = "gemini-2.5-flash-lite"
    researcher_google_model: str = "gemini-2.5-flash-lite"
    notes_google_model: str = "gemini-2.5-flash-lite"
    writer_google_model: str = "gemini-2.5-flash-lite"
    reviewer_google_model: str = "gemini-2.5-flash-lite"
    planner_groq_model: str = "openai/gpt-oss-120b"
    researcher_groq_model: str = "openai/gpt-oss-120b"
    notes_groq_model: str = "llama-3.3-70b-versatile"
    writer_groq_model: str = "llama-3.3-70b-versatile"
    reviewer_groq_model: str = "openai/gpt-oss-120b"
    parallel_section_pipeline: bool = True
    section_pipeline_concurrency: int = Field(default=2, ge=1, le=12)
    compile_latex: bool = True
    strict_latex_compile: bool = False
    latex_engine: LatexEngine = "pdflatex"
    research_execution_profile: Literal["budget", "debug", "full"] = "budget"
    token_budget: int | None = Field(default=None, ge=1000)
    max_completion_tokens: int | None = Field(default=None, ge=256)


class BookRequest(BaseModel):
    topic: str = Field(..., min_length=3)
    audience: str = Field(..., min_length=3)
    tone: str = "clear and supportive"
    book_type: BookType = "auto"
    theory_practice_balance: TheoryPracticeBalance = "balanced"
    pedagogy_style: PedagogyStyle = "auto"
    source_usage: SourceUsage = "auto"
    exercise_strategy: ExerciseStrategy = "auto"
    goals: list[str] = Field(default_factory=list)
    project_based: bool = False
    running_project_description: str | None = None
    code_density: Density = "low"
    example_density: Density = "high"
    diagram_density: Density = "medium"
    max_section_words: int | None = Field(default=None, ge=150, le=2000)
    force_web_research: bool = Field(
        default=False,
        description="When True, run web research even if user PDFs are present (combined mode).",
    )
    urls: list[str] = Field(
        default_factory=list,
        description="Optional user-provided source URLs to include in web research.",
    )
    language_request: str | None = Field(
        default=None,
        description=(
            "Free-form language instruction injected into the planner prompt. "
            "Examples: 'Explain all theory in English, but write exercise solutions and exam formulas in German.' "
            "'Use French for all content.' "
            "'Bilingual: English explanations, German technical terms and exam answers.'"
        ),
    )


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    current_stage: str
    request_payload: dict
    config_snapshot: dict
    stages: dict
    summary: dict
    warnings: dict
    error_message: str | None
    run_dir: str | None
    process_id: int | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class GeneratedBookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    title: str
    topic: str
    status: str
    run_dir: str
    latex_path: str | None
    pdf_path: str | None
    summary_metrics: dict
    artifact_paths: dict
    created_at: datetime
