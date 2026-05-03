from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from planner_agent.document_context import build_source_context_from_pdf_dir
from web.backend.models import ApiKey, BookJob, User, UserConfig
from web.backend.schemas import BookRequest, PipelineConfig
from web.backend.security import decrypt_secret


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = REPO_ROOT / "runs"


def default_config() -> dict:
    return PipelineConfig().model_dump()


def get_or_create_user_config(db: Session, user: User) -> UserConfig:
    config = user.config
    if config is None:
        config = UserConfig(user_id=user.id, settings=default_config())
        db.add(config)
        db.commit()
        db.refresh(config)
    else:
        merged = {**default_config(), **(config.settings or {})}
        if merged != config.settings:
            config.settings = merged
            db.add(config)
            db.commit()
            db.refresh(config)
    return config


def launch_job(db: Session, *, user: User, request: BookRequest, user_pdf_dir: Path | None = None) -> BookJob:
    config = get_or_create_user_config(db, user)
    config_payload = PipelineConfig.model_validate(config.settings or {}).model_dump()
    _validate_required_keys(db, user=user, config=config_payload, has_user_pdfs=user_pdf_dir is not None, force_web=request.force_web_research)
    planner_payload = _book_request_to_planner_input(request, user_pdf_dir=user_pdf_dir)

    stages = _initial_stages()
    job = BookJob(
        user_id=user.id,
        status="queued",
        current_stage="queued",
        request_payload=planner_payload,
        config_snapshot=config_payload,
        stages=stages,
        summary={},
        warnings={},
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    env = _build_job_environment(db, user=user, config=config_payload, request=request, user_pdf_dir=user_pdf_dir)
    env["WRITERLM_WEB_JOB_ID"] = str(job.id)
    env["WRITERLM_WEB_USER_ID"] = str(user.id)

    command = [
        sys.executable,
        "-m",
        "web.backend.pipeline_worker",
        "--job-id",
        str(job.id),
    ]
    process = subprocess.Popen(
        command,
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    job.process_id = process.pid
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _book_request_to_planner_input(request: BookRequest, *, user_pdf_dir: Path | None = None) -> dict:
    payload = {
        "topic": request.topic,
        "audience": request.audience,
        "tone": request.tone,
        "book_type": request.book_type,
        "theory_practice_balance": request.theory_practice_balance,
        "pedagogy_style": request.pedagogy_style,
        "source_usage": request.source_usage,
        "exercise_strategy": request.exercise_strategy,
        "goals": [goal.strip() for goal in request.goals if goal.strip()],
        "project_based": request.project_based,
        "running_project_description": request.running_project_description,
        "max_section_words": request.max_section_words,
        "content_density": {
            "code_density": request.code_density,
            "example_density": request.example_density,
            "diagram_density": request.diagram_density,
        },
        "force_web_research": request.force_web_research,
    }
    source_context = build_source_context_from_pdf_dir(user_pdf_dir)
    if source_context is not None:
        payload["source_context"] = source_context.model_dump(mode="json")
    return payload


def _build_job_environment(
    db: Session,
    *,
    user: User,
    config: dict,
    request: BookRequest | None = None,
    user_pdf_dir: Path | None = None,
) -> dict[str, str]:
    env = os.environ.copy()
    api_keys = _api_keys_by_provider(db, user=user)
    _remove_deployment_provider_secrets(env)

    key_env_map = {
        "google": "GOOGLE_API_KEY",
        "groq": "GROQ_API_KEY",
        "tavily": "TAVILY_API_KEY",
        "firecrawl": "FIRECRAWL_API_KEY",
    }
    for provider, env_name in key_env_map.items():
        value = api_keys.get(provider)
        if value:
            env[env_name] = value

    if api_keys.get("neon"):
        env["WRITERLM_USER_NEON_DATABASE_URL"] = api_keys["neon"]

    env.update(
        {
            "LLM_PROVIDER": config["llm_provider"],
            "PLANNER_GOOGLE_MODEL": config["planner_google_model"],
            "RESEARCHER_GOOGLE_MODEL": config["researcher_google_model"],
            "NOTES_GOOGLE_MODEL": config["notes_google_model"],
            "WRITER_GOOGLE_MODEL": config["writer_google_model"],
            "REVIEWER_GOOGLE_MODEL": config["reviewer_google_model"],
            "PLANNER_GROQ_MODEL": config["planner_groq_model"],
            "RESEARCHER_GROQ_MODEL": config["researcher_groq_model"],
            "NOTES_GROQ_MODEL": config["notes_groq_model"],
            "WRITER_GROQ_MODEL": config["writer_groq_model"],
            "REVIEWER_GROQ_MODEL": config["reviewer_groq_model"],
            "WRITERLM_PARALLEL_SECTION_PIPELINE": _bool_env(config["parallel_section_pipeline"]),
            "WRITERLM_SECTION_PIPELINE_CONCURRENCY": str(config["section_pipeline_concurrency"]),
            "WRITERLM_COMPILE_LATEX": _bool_env(config["compile_latex"]),
            "WRITERLM_STRICT_LATEX_COMPILE": _bool_env(config["strict_latex_compile"]),
            "LATEX_ENGINE": config["latex_engine"],
            "RESEARCH_EXECUTION_PROFILE": config["research_execution_profile"],
        }
    )

    if config.get("token_budget"):
        env["WRITERLM_TOKEN_BUDGET"] = str(config["token_budget"])
    if config.get("max_completion_tokens"):
        env["WRITERLM_MAX_COMPLETION_TOKENS"] = str(config["max_completion_tokens"])

    # PDF upload support
    if user_pdf_dir is not None and user_pdf_dir.exists():
        env["WRITERLM_USER_PDF_DIR"] = str(user_pdf_dir)
    if request is not None and request.force_web_research:
        env["WRITERLM_FORCE_WEB_RESEARCH"] = "1"

    return env


def _remove_deployment_provider_secrets(env: dict[str, str]) -> None:
    for name in (
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_GENERATIVE_AI_API_KEY",
        "GOOGLE_AI_API_KEY",
        "GOOGLE_AI_STUDIO_API_KEY",
        "GROQ_API_KEY",
        "TAVILY_API_KEY",
        "FIRECRAWL_API_KEY",
        "FIRECRAWL_KEY",
        "NEON_DATABASE_URL",
        "WRITERLM_USER_NEON_DATABASE_URL",
    ):
        env.pop(name, None)


def _validate_required_keys(
    db: Session,
    *,
    user: User,
    config: dict,
    has_user_pdfs: bool = False,
    force_web: bool = False,
) -> None:
    api_keys = _api_keys_by_provider(db, user=user)
    missing = []
    # Tavily is only required when web research will actually run
    web_research_needed = (not has_user_pdfs) or force_web
    if web_research_needed and "tavily" not in api_keys:
        missing.append("Tavily")
    if config["llm_provider"] == "google" and "google" not in api_keys:
        missing.append("Google/Gemini")
    if config["llm_provider"] == "groq" and "groq" not in api_keys:
        missing.append("Groq")
    if missing:
        raise ValueError("Missing required API keys: " + ", ".join(missing))


def _api_keys_by_provider(db: Session, *, user: User) -> dict[str, str]:
    rows = db.query(ApiKey).filter(ApiKey.user_id == user.id).all()
    values: dict[str, str] = {}
    for row in rows:
        try:
            values[row.provider] = decrypt_secret(row.encrypted_value)
        except Exception:
            continue
    return values


def _bool_env(value: bool) -> str:
    return "1" if value else "0"


def _initial_stages() -> dict:
    return {
        name: {
            "label": label,
            "status": "queued",
            "started_at": None,
            "completed_at": None,
            "seconds": None,
            "details": {},
        }
        for name, label in [
            ("planner_research", "Planner + Researcher"),
            ("notes_synthesis", "Notes Synthesis"),
            ("writer", "Writer"),
            ("reviewer", "Reviewer"),
            ("assembler", "Assembler"),
            ("latex_compile", "LaTeX Compiler"),
        ]
    }
