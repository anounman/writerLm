from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")


ProgressCallback = Callable[[str, str], None]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def run_web_pipeline(
    *,
    planner_input: dict[str, Any],
    run_dir: Path,
    progress: Callable[..., None],
) -> dict[str, Any]:
    from assembler.compiler import compile_latex_file
    from assembler.io import (
        save_assembly_bundle,
        save_book_plan,
        save_latex_compile_result,
        save_latex_manuscript,
    )
    from assembler.orchestrator import run_assembler
    from llm_metrics import configure_llm_metrics, get_llm_metrics_summary
    from notes_synthesizer.llm import GroqStructuredLLM as NotesGroqStructuredLLM
    from orchestration.evaluate_latex_book import evaluate_latex_book, write_outputs as write_evaluation_outputs
    from orchestration.parallel_section_pipeline import ParallelSectionPipelineConfig, run_parallel_section_pipeline
    from orchestration.planner_research_pipeline import PlannerResearchPipeline
    from orchestration.run_assembler_only import resolve_book_plan_for_review
    from orchestration.run_full_pipeline import (
        NOTES_DEFAULT_MODELS,
        WRITER_DEFAULT_MODELS,
        build_researcher_workflow,
        latex_compile_enabled,
        parallel_section_pipeline_enabled,
        run_notes_layer,
        run_writer_layer,
        strict_latex_compile_enabled,
    )
    from llm_provider import get_legacy_model_env_names_by_provider, resolve_openai_compatible_config
    from planner_agent import PlannerWorkflow
    from reviewer.io import build_reviewer_tasks, save_review_bundle
    from reviewer.llm_client import build_reviewer_llm_client
    from reviewer.orchestrator import run_reviewer
    from writer.llm import GroqStructuredLLM as WriterGroqStructuredLLM

    start_time = time.time()
    run_dir.mkdir(parents=True, exist_ok=True)
    configure_llm_metrics(path=run_dir / "llm_metrics.jsonl", reset=True)

    book_plan_path = run_dir / "book_plan.json"
    canonical_book_path = run_dir / "book.json"
    research_bundle_path = run_dir / "research_bundle.json"
    notes_bundle_path = run_dir / "notes_bundle.json"
    writer_bundle_path = run_dir / "writer_bundle.json"
    review_bundle_path = run_dir / "review_bundle.json"
    section_summary_path = run_dir / "section_pipeline_summary.json"
    assembly_bundle_path = run_dir / "assembly_bundle.json"
    latex_path = run_dir / "book.tex"
    latex_build_dir = run_dir / "latex_build"
    latex_compile_result_path = run_dir / "latex_compile_result.json"
    evaluation_json_path = run_dir / "book_evaluation.json"
    evaluation_md_path = run_dir / "book_evaluation.md"
    run_summary_path = run_dir / "run_summary.json"

    stage_timings: dict[str, float] = {}

    progress("planner_research", "running")
    stage_start = time.perf_counter()
    planner_workflow = PlannerWorkflow()
    researcher_workflow = build_researcher_workflow()
    pipeline = PlannerResearchPipeline(
        planner_workflow=planner_workflow,
        researcher_workflow=researcher_workflow,
    )
    research_bundle = pipeline.run(planner_input)
    stage_timings["planner_research"] = round(time.perf_counter() - stage_start, 2)
    book_plan = research_bundle.book_plan
    save_book_plan(book_plan, book_plan_path)
    save_book_plan(book_plan, canonical_book_path)
    research_bundle_payload = research_bundle.model_dump(mode="json")
    write_json(research_bundle_path, research_bundle_payload)
    progress(
        "planner_research",
        "completed",
        seconds=stage_timings["planner_research"],
        details={
            "chapters": book_plan.get_chapter_count(),
            "researched_sections": sum(len(ch.section_packets) for ch in research_bundle.chapters),
            "warnings": len(research_bundle.warnings),
            "errors": len(research_bundle.errors),
        },
    )

    if parallel_section_pipeline_enabled():
        notes_llm_config = resolve_openai_compatible_config(
            layer="notes",
            default_models=NOTES_DEFAULT_MODELS,
            legacy_env_names_by_provider=get_legacy_model_env_names_by_provider(),
        )
        writer_llm_config = resolve_openai_compatible_config(
            layer="writer",
            default_models=WRITER_DEFAULT_MODELS,
            legacy_env_names_by_provider=get_legacy_model_env_names_by_provider(),
        )
        progress("notes_synthesis", "running")
        progress("writer", "running")
        progress("reviewer", "running")
        stage_start = time.perf_counter()
        section_pipeline_result = run_parallel_section_pipeline(
            research_bundle_payload=research_bundle_payload,
            book_title=book_plan.title,
            run_id=run_dir.name,
            notes_llm_factory=lambda: NotesGroqStructuredLLM(
                api_key=notes_llm_config.api_key,
                model=notes_llm_config.model,
                base_url=notes_llm_config.base_url,
            ),
            writer_llm_factory=lambda: WriterGroqStructuredLLM(
                api_key=writer_llm_config.api_key,
                model=writer_llm_config.model,
                base_url=writer_llm_config.base_url,
            ),
            reviewer_llm_client_factory=build_reviewer_llm_client,
            config=ParallelSectionPipelineConfig.from_env(),
        )
        section_seconds = round(time.perf_counter() - stage_start, 2)
        stage_timings["parallel_section_pipeline"] = section_seconds
        notes_state = section_pipeline_result.notes_state
        writer_state = section_pipeline_result.writer_state
        review_bundle = section_pipeline_result.review_bundle
        section_pipeline_summary = section_pipeline_result.summary
        shared_details = {
            "mode": section_pipeline_summary.get("mode"),
            "completed_sections": section_pipeline_summary.get("completed_sections"),
            "failed_sections": section_pipeline_summary.get("failed_sections"),
        }
        final_status = "failed" if section_pipeline_summary.get("failed_sections") else "completed"
        progress("notes_synthesis", final_status, seconds=section_seconds, details=shared_details)
        progress("writer", final_status, seconds=section_seconds, details=shared_details)
        progress("reviewer", final_status, seconds=section_seconds, details=shared_details)
    else:
        progress("notes_synthesis", "running")
        stage_start = time.perf_counter()
        notes_state = run_notes_layer(
            research_bundle_payload=research_bundle_payload,
            book_title=book_plan.title,
            run_id=run_dir.name,
        )
        stage_timings["notes_synthesis"] = round(time.perf_counter() - stage_start, 2)
        progress("notes_synthesis", "completed", seconds=stage_timings["notes_synthesis"])

        notes_bundle_for_writer = notes_state.output_bundle
        if notes_bundle_for_writer is None:
            raise RuntimeError("Notes layer completed without an output bundle.")

        progress("writer", "running")
        stage_start = time.perf_counter()
        writer_state = run_writer_layer(
            notes_bundle_payload=notes_bundle_for_writer.model_dump(mode="json"),
            book_title=book_plan.title,
            run_id=run_dir.name,
        )
        stage_timings["writer"] = round(time.perf_counter() - stage_start, 2)
        progress("writer", "completed", seconds=stage_timings["writer"])

        writer_bundle_for_review = writer_state.output_bundle
        if writer_bundle_for_review is None:
            raise RuntimeError("Writer completed without an output bundle.")

        progress("reviewer", "running")
        reviewer_tasks = build_reviewer_tasks(
            notes_bundle=notes_bundle_for_writer,
            writer_bundle=writer_bundle_for_review,
        )
        stage_start = time.perf_counter()
        review_bundle = run_reviewer(tasks=reviewer_tasks, llm_client=build_reviewer_llm_client())
        stage_timings["reviewer"] = round(time.perf_counter() - stage_start, 2)
        progress("reviewer", "completed", seconds=stage_timings["reviewer"])
        section_pipeline_summary = {"mode": "sequential_layer_pipeline", "failed_sections": 0}

    write_json(section_summary_path, section_pipeline_summary)

    notes_bundle = notes_state.output_bundle
    writer_bundle = writer_state.output_bundle
    if notes_bundle is None or writer_bundle is None:
        raise RuntimeError("Section pipeline did not produce notes/writer bundles.")
    write_json(notes_bundle_path, notes_bundle.model_dump(mode="json"))
    write_json(writer_bundle_path, writer_bundle.model_dump(mode="json"))
    save_review_bundle(review_bundle, review_bundle_path)

    failed_section_count = int(section_pipeline_summary.get("failed_sections") or 0)
    if failed_section_count:
        failed_section_ids = section_pipeline_summary.get("failed_section_ids") or []
        raise RuntimeError(f"Section pipeline failed before assembly: {failed_section_ids}")

    progress("assembler", "running")
    stage_start = time.perf_counter()
    _, assembler_book_plan, preparation_note = resolve_book_plan_for_review(review_bundle_path)
    save_book_plan(assembler_book_plan, canonical_book_path)
    assembly_artifacts = run_assembler(
        book_plan=assembler_book_plan,
        review_bundle=review_bundle,
        book_plan_path=canonical_book_path,
        review_bundle_path=review_bundle_path,
        latex_output_path=latex_path,
    )
    stage_timings["assembler"] = round(time.perf_counter() - stage_start, 2)
    save_assembly_bundle(assembly_artifacts.assembly_bundle, assembly_bundle_path)
    save_latex_manuscript(assembly_artifacts.latex_manuscript, latex_path)
    progress(
        "assembler",
        "completed",
        seconds=stage_timings["assembler"],
        details={
            "status": assembly_artifacts.assembly_bundle.metadata.assembly_status.value,
            "assembled_sections": assembly_artifacts.assembly_bundle.metadata.assembled_section_count,
            "flagged_sections": assembly_artifacts.assembly_bundle.metadata.flagged_sections,
            "note": preparation_note,
        },
    )

    latex_compile_result = None
    if latex_compile_enabled():
        progress("latex_compile", "running")
        stage_start = time.perf_counter()
        latex_compile_result = compile_latex_file(latex_path, build_dir=latex_build_dir)
        stage_timings["latex_compile"] = round(time.perf_counter() - stage_start, 2)
        save_latex_compile_result(latex_compile_result, latex_compile_result_path)
        latex_status = "completed" if latex_compile_result.succeeded else "failed"
        progress(
            "latex_compile",
            latex_status,
            seconds=stage_timings["latex_compile"],
            details={
                "status": latex_compile_result.status,
                "pdf_path": latex_compile_result.pdf_path,
                "issues": [issue.message for issue in latex_compile_result.issues[:5]],
            },
        )
        if strict_latex_compile_enabled() and not latex_compile_result.succeeded:
            first_issue = latex_compile_result.issues[0].message if latex_compile_result.issues else "Unknown LaTeX compile failure."
            raise RuntimeError(f"LaTeX compilation failed: {first_issue}")
    else:
        progress("latex_compile", "completed", details={"status": "disabled"})

    evaluation = evaluate_latex_book(latex_path)
    write_evaluation_outputs(evaluation, evaluation_json_path, evaluation_md_path)

    llm_usage = get_llm_metrics_summary()
    book_status = (
        "completed"
        if latex_compile_result is None or latex_compile_result.succeeded
        else "completed_with_latex_issue"
    )
    artifacts = {
        "book_plan": str(book_plan_path),
        "research_bundle": str(research_bundle_path),
        "notes_bundle": str(notes_bundle_path),
        "writer_bundle": str(writer_bundle_path),
        "review_bundle": str(review_bundle_path),
        "section_pipeline_summary": str(section_summary_path),
        "assembly_bundle": str(assembly_bundle_path),
        "latex": str(latex_path),
        "latex_compile_result": str(latex_compile_result_path) if latex_compile_result else None,
        "pdf": latex_compile_result.pdf_path if latex_compile_result and latex_compile_result.pdf_path else None,
        "book_evaluation": str(evaluation_md_path),
        "llm_metrics": str(run_dir / "llm_metrics.jsonl"),
    }
    summary = {
        "elapsed_seconds": round(time.time() - start_time, 2),
        "stage_timings": stage_timings,
        "section_pipeline": section_pipeline_summary,
        "llm_usage": llm_usage,
        "evaluation": {
            "quality_score": evaluation["quality_score"],
            "totals": evaluation["totals"],
            "weak_section_count": evaluation["weak_section_count"],
            "recommendations": evaluation["recommendations"],
        },
        "latex_compile": latex_compile_result.model_dump() if latex_compile_result else None,
    }
    write_json(run_summary_path, {**summary, "artifacts": artifacts})
    return {
        "title": book_plan.title,
        "book_status": book_status,
        "summary": summary,
        "warnings": {
            "research": research_bundle.warnings,
            "research_errors": research_bundle.errors,
        },
        "artifacts": artifacts,
    }
