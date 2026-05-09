from __future__ import annotations

import argparse
import json
import os
import traceback
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

warnings.filterwarnings(
    "ignore",
    message=r"The default value of `allowed_objects` will change in a future version\..*",
    module=r"langgraph\.cache\.base\.__init__",
)

from sqlalchemy.orm import Session

from web.backend.database import SessionLocal, init_db
from web.backend.models import BookJob, GeneratedBook
from web.backend.pipeline_jobs import RUNS_DIR


STALE_PROCESS_MESSAGES = {
    "Job process is no longer running.",
    "Job process exited unexpectedly. Check worker.log for details.",
    "Job worker exited before starting. Check worker.log for details.",
}


def utciso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_worker_state(run_dir: Path, payload: dict[str, Any]) -> None:
    state = {"updated_at": utciso(), "pid": os.getpid(), **payload}
    try:
        (run_dir / "worker_state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass


def _stage_update(
    db: Session,
    job: BookJob,
    stage: str,
    status: str,
    *,
    details: dict[str, Any] | None = None,
    seconds: float | None = None,
) -> None:
    stages = dict(job.stages or {})
    entry = dict(stages.get(stage) or {})
    entry.setdefault("label", stage.replace("_", " ").title())
    entry["status"] = status
    if status == "running" and not entry.get("started_at"):
        entry["started_at"] = utciso()
    if status in {"completed", "failed"}:
        entry["completed_at"] = utciso()
    if seconds is not None:
        entry["seconds"] = seconds
    if details:
        entry["details"] = {**(entry.get("details") or {}), **details}
    stages[stage] = entry
    job.stages = stages
    job.current_stage = stage
    if status in {"running", "completed"} and (
        job.status in {"queued", "running"}
        or job.error_message in STALE_PROCESS_MESSAGES
    ):
        job.status = "running"
        job.error_message = None
        job.completed_at = None
    db.add(job)
    db.commit()
    db.refresh(job)


def _mark_job_failed(db: Session, job: BookJob, message: str) -> None:
    job.status = "failed"
    job.error_message = message
    job.completed_at = datetime.now(timezone.utc)
    stages = dict(job.stages or {})
    current = job.current_stage
    if current in stages:
        stages[current] = {**stages[current], "status": "failed", "completed_at": utciso()}
    job.stages = stages
    db.add(job)
    db.commit()


def run_job(job_id: int) -> None:
    init_db()
    run_dir: Path | None = None
    request_payload: dict[str, Any] = {}
    try:
        with SessionLocal() as db:
            job = db.get(BookJob, job_id)
            if job is None:
                return

            run_dir = Path(job.run_dir) if job.run_dir else RUNS_DIR / f"web_job_{job.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            run_dir.mkdir(parents=True, exist_ok=True)

            request_payload = dict(job.request_payload or {})
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            job.run_dir = str(run_dir)
            db.add(job)
            db.commit()
            db.refresh(job)
            current_stage = job.current_stage

        _write_worker_state(run_dir, {"job_id": job_id, "status": "running", "stage": current_stage})

        request_path = run_dir / "user_request.json"
        request_path.write_text(json.dumps(request_payload, indent=2), encoding="utf-8")

        def progress(stage: str, status: str, **kwargs: Any) -> None:
            _write_worker_state(run_dir, {"job_id": job_id, "status": status, "stage": stage})
            with SessionLocal() as progress_db:
                fresh_job = progress_db.get(BookJob, job_id)
                if fresh_job is None:
                    return
                _stage_update(
                    progress_db,
                    fresh_job,
                    stage,
                    status,
                    details=kwargs.get("details"),
                    seconds=kwargs.get("seconds"),
                )

        from web.backend.web_pipeline import run_web_pipeline
        resume_from = os.getenv("WRITERLM_RESUME_FROM_RUN_DIR", "").strip()

        result = run_web_pipeline(
            planner_input=request_payload,
            run_dir=run_dir,
            progress=progress,
            resume_from_dir=Path(resume_from) if resume_from else None,
        )

        with SessionLocal() as db:
            fresh_job = db.get(BookJob, job_id)
            if fresh_job is None:
                return
            fresh_job.status = result["book_status"]
            fresh_job.current_stage = "completed"
            fresh_job.summary = result["summary"]
            fresh_job.warnings = result.get("warnings") or {}
            fresh_job.completed_at = datetime.now(timezone.utc)
            db.add(fresh_job)

            book = GeneratedBook(
                user_id=fresh_job.user_id,
                job_id=fresh_job.id,
                title=result["title"],
                topic=(fresh_job.request_payload or {}).get("topic", result["title"]),
                status=result["book_status"],
                run_dir=str(run_dir),
                latex_path=result["artifacts"].get("latex"),
                pdf_path=result["artifacts"].get("pdf"),
                summary_metrics=result["summary"],
                artifact_paths=result["artifacts"],
            )
            db.add(book)
            db.commit()
            final_status = fresh_job.status
            final_stage = fresh_job.current_stage
        _write_worker_state(run_dir, {"job_id": job_id, "status": final_status, "stage": final_stage})
    except Exception as exc:
        error_text = traceback.format_exc()
        with SessionLocal() as db:
            job = db.get(BookJob, job_id)
            if job is not None:
                failure_run_dir = Path(job.run_dir) if job.run_dir else run_dir or RUNS_DIR
                error_path = failure_run_dir / "job_error.txt"
                try:
                    error_path.parent.mkdir(parents=True, exist_ok=True)
                    error_path.write_text(error_text, encoding="utf-8")
                except Exception:
                    pass
                if job.run_dir or run_dir:
                    _write_worker_state(failure_run_dir, {"job_id": job_id, "status": "failed", "stage": job.current_stage, "error": str(exc)})
                _mark_job_failed(db, job, str(exc))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one WriterLM Studio pipeline job.")
    parser.add_argument("--job-id", type=int, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_job(args.job_id)


if __name__ == "__main__":
    main()
