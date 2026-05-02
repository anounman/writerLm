from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from assembler.io import save_assembly_bundle, save_book_plan, save_latex_manuscript
from assembler.orchestrator import run_assembler
from llm_provider import resolve_openai_compatible_config
from llm_metrics import configure_llm_metrics, get_llm_metrics_summary
from notes_synthesizer.graph import build_notes_synthesizer_graph, initialize_state
from notes_synthesizer.llm import GroqStructuredLLM as NotesGroqStructuredLLM
from notes_synthesizer.schemas import SynthesisStatus
from notes_synthesizer.state import NotesSynthesizerInput, NotesSynthesizerState
from orchestration.planner_research_pipeline import PlannerResearchPipeline
from orchestration.parallel_section_pipeline import (
    ParallelSectionPipelineConfig,
    run_parallel_section_pipeline,
)
from orchestration.run_assembler_only import resolve_book_plan_for_review
from orchestration.run_notes_synthesizer import build_tasks_from_research_bundle
from orchestration.run_writer import build_tasks_from_notes_bundle
from planner_agent import PlannerWorkflow
from researcher.services.firecrawl_client import FirecrawlClient
from researcher.services.llm_structured import GroqStructuredLLM as ResearchGroqStructuredLLM
from researcher.services.pdf_extractor import PDFExtractor
from researcher.services.tavily_client import TavilySearchClient
from researcher.services.web_extractor import WebExtractor
from researcher.workflow import ResearcherWorkflow
from reviewer.io import build_reviewer_tasks, save_review_bundle
from reviewer.llm_client import build_reviewer_llm_client
from reviewer.orchestrator import run_reviewer
from writer.graph import build_writer_graph, initialize_writer_state
from writer.llm import GroqStructuredLLM as WriterGroqStructuredLLM
from writer.schemas import WritingStatus
from writer.state import WriterInput, WriterState


DEFAULT_PLANNER_INPUT: dict[str, Any] = {
    "topic": "build a retrieval-augmented generation system for answering questions over your own documents",
    "audience": "beginner to intermediate developers who understand basic Python but are new to RAG systems",
    "tone": "practical step by step guide",
    "goals": [
        "teach the reader how RAG works by building one from scratch",
        "help the reader implement each core component with code",
        "show how ingestion, chunking, embeddings, retrieval, prompting, and evaluation fit together",
        "end with a working mini project the reader can extend"
    ],
    "project_based": True,
    "content_density": {
        "code_density": "high",
        "example_density": "high",
        "diagram_density": "medium"
    }
}

RUNS_DIR = REPO_ROOT / "runs"
OUTPUTS_DIR = REPO_ROOT / "outputs"

BOOK_PLAN_OUTPUT_PATH = OUTPUTS_DIR / "book_plan.json"
CANONICAL_BOOK_PATH = OUTPUTS_DIR / "book.json"
RESEARCH_BUNDLE_OUTPUT_PATH = OUTPUTS_DIR / "research_bundle.json"
NOTES_BUNDLE_OUTPUT_PATH = OUTPUTS_DIR / "notes_bundle.json"
WRITER_BUNDLE_OUTPUT_PATH = OUTPUTS_DIR / "writer_bundle.json"
REVIEW_BUNDLE_OUTPUT_PATH = OUTPUTS_DIR / "review_bundle.json"
SECTION_PIPELINE_SUMMARY_OUTPUT_PATH = OUTPUTS_DIR / "section_pipeline_summary.json"
ASSEMBLY_BUNDLE_OUTPUT_PATH = OUTPUTS_DIR / "assembly_bundle.json"
LATEX_OUTPUT_PATH = OUTPUTS_DIR / "book.tex"
SUMMARY_OUTPUT_PATH = OUTPUTS_DIR / "run_summary.json"

RESEARCH_DEFAULT_MODELS = {
    "groq": "openai/gpt-oss-120b",
    "google": "gemini-2.5-flash",
}
GENERATION_DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "google": "gemini-2.5-flash",
}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def build_run_dir(base_dir: Path = RUNS_DIR) -> Path:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base_dir / run_id
    ensure_dir(run_dir)
    return run_dir


def save_json_to_run_and_outputs(
    *,
    relative_name: str,
    data: Any,
    run_dir: Path,
    output_path: Path,
) -> None:
    write_json(run_dir / relative_name, data)
    write_json(output_path, data)


def build_researcher_workflow() -> ResearcherWorkflow:
    llm_config = resolve_openai_compatible_config(
        layer="researcher",
        default_models=RESEARCH_DEFAULT_MODELS,
        legacy_env_names_by_provider={
            "groq": ("GROQ_MODEL_NAME", "GROQ_MODEL"),
            "google": ("GOOGLE_MODEL_NAME", "GOOGLE_MODEL", "GEMINI_MODEL"),
        },
    )

    llm = ResearchGroqStructuredLLM(
        api_key=llm_config.api_key,
        model=llm_config.model,
        base_url=llm_config.base_url,
    )

    tavily_client = TavilySearchClient(
        api_key=os.environ["TAVILY_API_KEY"],
    )

    web_extractor = WebExtractor()
    pdf_extractor = PDFExtractor()

    firecrawl_api_key = os.environ.get("FIRECRAWL_API_KEY")
    firecrawl_client = (
        FirecrawlClient(api_key=firecrawl_api_key) if firecrawl_api_key else None
    )

    return ResearcherWorkflow(
        llm=llm,
        tavily_client=tavily_client,
        web_extractor=web_extractor,
        pdf_extractor=pdf_extractor,
        firecrawl_client=firecrawl_client,
    )


def run_notes_layer(*, research_bundle_payload: dict[str, Any], book_title: str, run_id: str):
    tasks = build_tasks_from_research_bundle(research_bundle_payload)
    if not tasks:
        raise RuntimeError("No Notes Synthesizer tasks could be built from the research bundle.")

    llm_config = resolve_openai_compatible_config(
        layer="notes",
        default_models=GENERATION_DEFAULT_MODELS,
        legacy_env_names_by_provider={
            "groq": ("GROQ_MODEL", "GROQ_MODEL_NAME"),
            "google": ("GOOGLE_MODEL", "GOOGLE_MODEL_NAME", "GEMINI_MODEL"),
        },
    )

    llm = NotesGroqStructuredLLM(
        api_key=llm_config.api_key,
        model=llm_config.model,
        base_url=llm_config.base_url,
    )

    input_data = NotesSynthesizerInput(
        book_id=run_id,
        book_title=book_title,
        tasks=tasks,
    )

    graph = build_notes_synthesizer_graph(llm)
    state = initialize_state(input_data)
    final_state_raw = graph.invoke(state)
    final_state = NotesSynthesizerState.model_validate(final_state_raw)

    if final_state.output_bundle is None:
        raise RuntimeError("Notes Synthesizer completed without producing an output bundle.")

    return final_state


def run_writer_layer(*, notes_bundle_payload: dict[str, Any], book_title: str, run_id: str):
    tasks = build_tasks_from_notes_bundle(notes_bundle_payload)
    if not tasks:
        raise RuntimeError("No Writer tasks could be built from the notes bundle.")

    llm_config = resolve_openai_compatible_config(
        layer="writer",
        default_models=GENERATION_DEFAULT_MODELS,
        legacy_env_names_by_provider={
            "groq": ("GROQ_MODEL", "GROQ_MODEL_NAME"),
            "google": ("GOOGLE_MODEL", "GOOGLE_MODEL_NAME", "GEMINI_MODEL"),
        },
    )

    llm = WriterGroqStructuredLLM(
        api_key=llm_config.api_key,
        model=llm_config.model,
        base_url=llm_config.base_url,
    )

    input_data = WriterInput(
        book_id=run_id,
        book_title=book_title,
        tasks=tasks,
    )

    graph = build_writer_graph(llm)
    state = initialize_writer_state(input_data)
    final_state_raw = graph.invoke(state)
    final_state = WriterState.model_validate(final_state_raw)

    if final_state.output_bundle is None:
        raise RuntimeError("Writer completed without producing an output bundle.")

    return final_state


def build_summary(
    *,
    planner_input: dict[str, Any],
    run_dir: Path,
    research_bundle,
    notes_state: NotesSynthesizerState,
    writer_state: WriterState,
    review_bundle,
    assembly_artifacts,
    resolved_book_source: Path,
    preparation_note: str | None,
    elapsed_seconds: float,
    llm_metrics: dict[str, Any],
    stage_timings: dict[str, float],
    section_pipeline_summary: dict[str, Any],
) -> dict[str, Any]:
    notes_bundle = notes_state.output_bundle
    writer_bundle = writer_state.output_bundle

    return {
        "run_dir": str(run_dir),
        "planner_input": planner_input,
        "resolved_book_plan_source": str(resolved_book_source),
        "preparation_note": preparation_note,
        "planner": {
            "chapter_count": research_bundle.book_plan.get_chapter_count(),
        },
        "researcher": {
            "chapter_count": len(research_bundle.chapters),
            "researched_section_count": sum(len(ch.section_packets) for ch in research_bundle.chapters),
            "warning_count": len(research_bundle.warnings),
            "error_count": len(research_bundle.errors),
            "warnings": research_bundle.warnings,
            "errors": research_bundle.errors,
        },
        "notes_synthesizer": {
            "total_sections": notes_bundle.total_sections if notes_bundle else 0,
            "ready_sections": notes_bundle.ready_sections if notes_bundle else 0,
            "partial_sections": notes_bundle.partial_sections if notes_bundle else 0,
            "blocked_sections": notes_bundle.blocked_sections if notes_bundle else 0,
            "completed_sections": notes_state.completed_sections,
            "failed_sections": notes_state.failed_sections,
            "run_warnings": notes_state.run_warnings,
            "run_errors": notes_state.run_errors,
        },
        "writer": {
            "total_sections": writer_bundle.total_sections if writer_bundle else 0,
            "ready_sections": writer_bundle.ready_sections if writer_bundle else 0,
            "partial_sections": writer_bundle.partial_sections if writer_bundle else 0,
            "blocked_sections": writer_bundle.blocked_sections if writer_bundle else 0,
            "completed_sections": writer_state.completed_sections,
            "failed_sections": writer_state.failed_sections,
            "run_warnings": writer_state.run_warnings,
            "run_errors": writer_state.run_errors,
        },
        "reviewer": {
            "total_sections": review_bundle.metadata.total_sections,
            "approved_sections": review_bundle.metadata.approved_sections,
            "revised_sections": review_bundle.metadata.revised_sections,
            "flagged_sections": review_bundle.metadata.flagged_sections,
        },
        "assembler": {
            "assembly_status": assembly_artifacts.assembly_bundle.metadata.assembly_status.value,
            "chapter_count": assembly_artifacts.assembly_bundle.metadata.chapter_count,
            "planned_section_count": assembly_artifacts.assembly_bundle.metadata.planned_section_count,
            "assembled_section_count": assembly_artifacts.assembly_bundle.metadata.assembled_section_count,
            "approved_sections": assembly_artifacts.assembly_bundle.metadata.approved_sections,
            "revised_sections": assembly_artifacts.assembly_bundle.metadata.revised_sections,
            "flagged_sections": assembly_artifacts.assembly_bundle.metadata.flagged_sections,
        },
        "artifacts": {
            "book_plan": str(BOOK_PLAN_OUTPUT_PATH),
            "canonical_book_plan": str(CANONICAL_BOOK_PATH),
            "research_bundle": str(RESEARCH_BUNDLE_OUTPUT_PATH),
            "notes_bundle": str(NOTES_BUNDLE_OUTPUT_PATH),
            "writer_bundle": str(WRITER_BUNDLE_OUTPUT_PATH),
            "review_bundle": str(REVIEW_BUNDLE_OUTPUT_PATH),
            "section_pipeline_summary": str(SECTION_PIPELINE_SUMMARY_OUTPUT_PATH),
            "assembly_bundle": str(ASSEMBLY_BUNDLE_OUTPUT_PATH),
            "latex_manuscript": str(LATEX_OUTPUT_PATH),
            "llm_metrics": llm_metrics.get("metrics_path"),
        },
        "llm_usage": llm_metrics,
        "stage_timings": stage_timings,
        "section_pipeline": section_pipeline_summary,
        "elapsed_seconds": round(elapsed_seconds, 2),
    }


def parallel_section_pipeline_enabled() -> bool:
    value = os.getenv("WRITERLM_PARALLEL_SECTION_PIPELINE", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def main() -> None:
    start_time = time.time()
    ensure_dir(OUTPUTS_DIR)
    run_dir = build_run_dir()
    configure_llm_metrics(path=run_dir / "llm_metrics.jsonl", reset=True)
    stage_timings: dict[str, float] = {}

    planner_input = DEFAULT_PLANNER_INPUT

    planner_workflow = PlannerWorkflow()
    researcher_workflow = build_researcher_workflow()
    pipeline = PlannerResearchPipeline(
        planner_workflow=planner_workflow,
        researcher_workflow=researcher_workflow,
    )

    stage_start = time.perf_counter()
    research_bundle = pipeline.run(planner_input)
    stage_timings["planner_research"] = round(time.perf_counter() - stage_start, 2)
    book_plan = research_bundle.book_plan

    save_book_plan(book_plan, run_dir / "book_plan.json")
    save_book_plan(book_plan, BOOK_PLAN_OUTPUT_PATH)
    save_book_plan(book_plan, CANONICAL_BOOK_PATH)

    research_bundle_payload = research_bundle.model_dump(mode="json")
    save_json_to_run_and_outputs(
        relative_name="research_bundle.json",
        data=research_bundle_payload,
        run_dir=run_dir,
        output_path=RESEARCH_BUNDLE_OUTPUT_PATH,
    )

    if parallel_section_pipeline_enabled():
        notes_llm_config = resolve_openai_compatible_config(
            layer="notes",
            default_models=GENERATION_DEFAULT_MODELS,
            legacy_env_names_by_provider={
                "groq": ("GROQ_MODEL", "GROQ_MODEL_NAME"),
                "google": ("GOOGLE_MODEL", "GOOGLE_MODEL_NAME", "GEMINI_MODEL"),
            },
        )
        writer_llm_config = resolve_openai_compatible_config(
            layer="writer",
            default_models=GENERATION_DEFAULT_MODELS,
            legacy_env_names_by_provider={
                "groq": ("GROQ_MODEL", "GROQ_MODEL_NAME"),
                "google": ("GOOGLE_MODEL", "GOOGLE_MODEL_NAME", "GEMINI_MODEL"),
            },
        )
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
        stage_timings["parallel_section_pipeline"] = round(
            time.perf_counter() - stage_start,
            2,
        )
        section_pipeline_summary = section_pipeline_result.summary
        notes_state = section_pipeline_result.notes_state
        writer_state = section_pipeline_result.writer_state
        review_bundle = section_pipeline_result.review_bundle
    else:
        stage_start = time.perf_counter()
        notes_state = run_notes_layer(
            research_bundle_payload=research_bundle_payload,
            book_title=book_plan.title,
            run_id=run_dir.name,
        )
        stage_timings["notes_synthesizer"] = round(time.perf_counter() - stage_start, 2)
        notes_bundle_for_writer = notes_state.output_bundle
        assert notes_bundle_for_writer is not None
        notes_bundle_payload_for_writer = notes_bundle_for_writer.model_dump(mode="json")

        stage_start = time.perf_counter()
        writer_state = run_writer_layer(
            notes_bundle_payload=notes_bundle_payload_for_writer,
            book_title=book_plan.title,
            run_id=run_dir.name,
        )
        stage_timings["writer"] = round(time.perf_counter() - stage_start, 2)
        writer_bundle_for_review = writer_state.output_bundle
        assert writer_bundle_for_review is not None

        reviewer_tasks = build_reviewer_tasks(
            notes_bundle=notes_bundle_for_writer,
            writer_bundle=writer_bundle_for_review,
        )
        if not reviewer_tasks:
            raise RuntimeError("No Reviewer tasks could be created from the notes and writer bundles.")

        reviewer_llm_client = build_reviewer_llm_client()
        stage_start = time.perf_counter()
        review_bundle = run_reviewer(
            tasks=reviewer_tasks,
            llm_client=reviewer_llm_client,
        )
        stage_timings["reviewer"] = round(time.perf_counter() - stage_start, 2)
        section_pipeline_summary = {
            "mode": "sequential_layer_pipeline",
        }

    save_json_to_run_and_outputs(
        relative_name="section_pipeline_summary.json",
        data=section_pipeline_summary,
        run_dir=run_dir,
        output_path=SECTION_PIPELINE_SUMMARY_OUTPUT_PATH,
    )

    notes_bundle = notes_state.output_bundle
    assert notes_bundle is not None
    notes_bundle_payload = notes_bundle.model_dump(mode="json")
    save_json_to_run_and_outputs(
        relative_name="notes_bundle.json",
        data=notes_bundle_payload,
        run_dir=run_dir,
        output_path=NOTES_BUNDLE_OUTPUT_PATH,
    )

    writer_bundle = writer_state.output_bundle
    assert writer_bundle is not None
    writer_bundle_payload = writer_bundle.model_dump(mode="json")
    save_json_to_run_and_outputs(
        relative_name="writer_bundle.json",
        data=writer_bundle_payload,
        run_dir=run_dir,
        output_path=WRITER_BUNDLE_OUTPUT_PATH,
    )

    save_review_bundle(review_bundle, run_dir / "review_bundle.json")
    save_review_bundle(review_bundle, REVIEW_BUNDLE_OUTPUT_PATH)

    failed_section_count = int(section_pipeline_summary.get("failed_sections") or 0)
    if failed_section_count:
        failed_section_ids = section_pipeline_summary.get("failed_section_ids") or []
        raise RuntimeError(
            "Parallel section pipeline failed before assembly. "
            f"Failed sections: {failed_section_ids}. "
            f"Partial artifacts were saved under {run_dir}."
        )

    resolved_book_source, assembler_book_plan, preparation_note = resolve_book_plan_for_review(
        REVIEW_BUNDLE_OUTPUT_PATH
    )
    save_book_plan(assembler_book_plan, CANONICAL_BOOK_PATH)
    save_book_plan(assembler_book_plan, run_dir / "book.json")

    stage_start = time.perf_counter()
    assembly_artifacts = run_assembler(
        book_plan=assembler_book_plan,
        review_bundle=review_bundle,
        book_plan_path=CANONICAL_BOOK_PATH,
        review_bundle_path=REVIEW_BUNDLE_OUTPUT_PATH,
        latex_output_path=LATEX_OUTPUT_PATH,
    )
    stage_timings["assembler"] = round(time.perf_counter() - stage_start, 2)

    save_assembly_bundle(assembly_artifacts.assembly_bundle, run_dir / "assembly_bundle.json")
    save_assembly_bundle(assembly_artifacts.assembly_bundle, ASSEMBLY_BUNDLE_OUTPUT_PATH)
    save_latex_manuscript(assembly_artifacts.latex_manuscript, run_dir / "book.tex")
    save_latex_manuscript(assembly_artifacts.latex_manuscript, LATEX_OUTPUT_PATH)

    elapsed_seconds = time.time() - start_time
    summary = build_summary(
        planner_input=planner_input,
        run_dir=run_dir,
        research_bundle=research_bundle,
        notes_state=notes_state,
        writer_state=writer_state,
        review_bundle=review_bundle,
        assembly_artifacts=assembly_artifacts,
        resolved_book_source=resolved_book_source,
        preparation_note=preparation_note,
        elapsed_seconds=elapsed_seconds,
        llm_metrics=get_llm_metrics_summary(),
        stage_timings=stage_timings,
        section_pipeline_summary=section_pipeline_summary,
    )

    save_json_to_run_and_outputs(
        relative_name="run_summary.json",
        data=summary,
        run_dir=run_dir,
        output_path=SUMMARY_OUTPUT_PATH,
    )

    notes_ready = sum(
        1
        for note in notes_bundle.section_notes
        if note.synthesis_status == SynthesisStatus.READY
    )
    notes_partial = sum(
        1
        for note in notes_bundle.section_notes
        if note.synthesis_status == SynthesisStatus.PARTIAL
    )
    notes_blocked = sum(
        1
        for note in notes_bundle.section_notes
        if note.synthesis_status == SynthesisStatus.BLOCKED
    )

    writer_ready = sum(
        1
        for draft in writer_bundle.section_drafts
        if draft.writing_status == WritingStatus.READY
    )
    writer_partial = sum(
        1
        for draft in writer_bundle.section_drafts
        if draft.writing_status == WritingStatus.PARTIAL
    )
    writer_blocked = sum(
        1
        for draft in writer_bundle.section_drafts
        if draft.writing_status == WritingStatus.BLOCKED
    )

    print(f"Run saved to: {run_dir}")
    if preparation_note:
        print(preparation_note)
    print(f"Book plan: {BOOK_PLAN_OUTPUT_PATH}")
    print(f"Canonical book plan: {CANONICAL_BOOK_PATH}")
    print(f"Research bundle: {RESEARCH_BUNDLE_OUTPUT_PATH}")
    print(f"Notes bundle: {NOTES_BUNDLE_OUTPUT_PATH}")
    print(f"Writer bundle: {WRITER_BUNDLE_OUTPUT_PATH}")
    print(f"Review bundle: {REVIEW_BUNDLE_OUTPUT_PATH}")
    print(f"Assembly bundle: {ASSEMBLY_BUNDLE_OUTPUT_PATH}")
    print(f"LaTeX manuscript: {LATEX_OUTPUT_PATH}")
    print(f"LLM metrics: {summary['artifacts']['llm_metrics']}")
    print(f"Research warnings: {len(research_bundle.warnings)}")
    print(f"Research errors: {len(research_bundle.errors)}")
    print(f"Notes READY/PARTIAL/BLOCKED: {notes_ready}/{notes_partial}/{notes_blocked}")
    print(f"Writer READY/PARTIAL/BLOCKED: {writer_ready}/{writer_partial}/{writer_blocked}")
    print(
        "Reviewer APPROVED/REVISED/FLAGGED: "
        f"{review_bundle.metadata.approved_sections}/"
        f"{review_bundle.metadata.revised_sections}/"
        f"{review_bundle.metadata.flagged_sections}"
    )
    print(f"Assembly status: {assembly_artifacts.assembly_bundle.metadata.assembly_status.value}")
    print(f"Section pipeline mode: {section_pipeline_summary.get('mode')}")
    print(f"Stage timings: {stage_timings}")
    print(f"Execution time: {elapsed_seconds:.2f}s")


if __name__ == "__main__":
    main()
