from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from assembler.compiler import compile_latex_file
from assembler.io import (
    save_assembly_bundle,
    save_book_plan,
    save_latex_compile_result,
    save_latex_manuscript,
)
from assembler.orchestrator import run_assembler
from llm_metrics import configure_llm_metrics, get_llm_metrics_summary
from llm_provider import (
    get_default_models_for_layer,
    get_legacy_model_env_names_by_provider,
    resolve_openai_compatible_config,
)
from notes_synthesizer.llm import GroqStructuredLLM as NotesGroqStructuredLLM
from orchestration.evaluate_latex_book import evaluate_latex_book, write_outputs as write_evaluation_outputs
from orchestration.parallel_section_pipeline import (
    ParallelSectionPipelineConfig,
    run_parallel_section_pipeline,
)
from planner_agent.schemas import BookPlan
from reviewer.io import save_review_bundle
from reviewer.llm_client import build_reviewer_llm_client
from writer.llm import GroqStructuredLLM as WriterGroqStructuredLLM


OUTPUTS_DIR = REPO_ROOT / "outputs"
BOOK_PLAN_OUTPUT_PATH = OUTPUTS_DIR / "book_plan.json"
CANONICAL_BOOK_PATH = OUTPUTS_DIR / "book.json"
NOTES_BUNDLE_OUTPUT_PATH = OUTPUTS_DIR / "notes_bundle.json"
WRITER_BUNDLE_OUTPUT_PATH = OUTPUTS_DIR / "writer_bundle.json"
REVIEW_BUNDLE_OUTPUT_PATH = OUTPUTS_DIR / "review_bundle.json"
SECTION_PIPELINE_SUMMARY_OUTPUT_PATH = OUTPUTS_DIR / "section_pipeline_summary.json"
ASSEMBLY_BUNDLE_OUTPUT_PATH = OUTPUTS_DIR / "assembly_bundle.json"
LATEX_OUTPUT_PATH = OUTPUTS_DIR / "book.tex"
LATEX_BUILD_DIR = OUTPUTS_DIR / "latex_build"
LATEX_COMPILE_RESULT_OUTPUT_PATH = OUTPUTS_DIR / "latex_compile_result.json"
EVALUATION_JSON_OUTPUT_PATH = OUTPUTS_DIR / "book_evaluation.json"
EVALUATION_MD_OUTPUT_PATH = OUTPUTS_DIR / "book_evaluation.md"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)


def latex_compile_enabled() -> bool:
    value = os.getenv("WRITERLM_COMPILE_LATEX", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def strict_latex_compile_enabled() -> bool:
    value = os.getenv("WRITERLM_STRICT_LATEX_COMPILE", "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def run_from_research_bundle(*, run_dir: Path, deterministic: bool) -> dict[str, Any]:
    start_time = time.time()
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    research_bundle_path = run_dir / "research_bundle.json"
    research_bundle_payload = load_json(research_bundle_path)
    book_plan = BookPlan.model_validate(research_bundle_payload["book_plan"])

    if deterministic:
        os.environ["WRITERLM_DETERMINISTIC_NOTES"] = "1"
        os.environ["WRITERLM_DETERMINISTIC_WRITER"] = "1"
        os.environ["WRITERLM_DETERMINISTIC_REVIEWER"] = "1"

    configure_llm_metrics(path=run_dir / "post_research_llm_metrics.jsonl", reset=True)

    notes_llm_config = resolve_openai_compatible_config(
        layer="notes",
        default_models=get_default_models_for_layer("notes"),
        legacy_env_names_by_provider=get_legacy_model_env_names_by_provider(),
    )
    writer_llm_config = resolve_openai_compatible_config(
        layer="writer",
        default_models=get_default_models_for_layer("writer"),
        legacy_env_names_by_provider=get_legacy_model_env_names_by_provider(),
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
    section_pipeline_seconds = round(time.perf_counter() - stage_start, 2)

    notes_bundle = section_pipeline_result.notes_state.output_bundle
    writer_bundle = section_pipeline_result.writer_state.output_bundle
    if notes_bundle is None or writer_bundle is None:
        raise RuntimeError("Section pipeline did not produce notes/writer bundles.")

    save_book_plan(book_plan, run_dir / "book_plan.json")
    save_book_plan(book_plan, BOOK_PLAN_OUTPUT_PATH)
    save_book_plan(book_plan, CANONICAL_BOOK_PATH)
    write_json(run_dir / "notes_bundle.json", notes_bundle.model_dump(mode="json"))
    write_json(NOTES_BUNDLE_OUTPUT_PATH, notes_bundle.model_dump(mode="json"))
    write_json(run_dir / "writer_bundle.json", writer_bundle.model_dump(mode="json"))
    write_json(WRITER_BUNDLE_OUTPUT_PATH, writer_bundle.model_dump(mode="json"))
    save_review_bundle(section_pipeline_result.review_bundle, run_dir / "review_bundle.json")
    save_review_bundle(section_pipeline_result.review_bundle, REVIEW_BUNDLE_OUTPUT_PATH)
    write_json(run_dir / "section_pipeline_summary.json", section_pipeline_result.summary)
    write_json(SECTION_PIPELINE_SUMMARY_OUTPUT_PATH, section_pipeline_result.summary)

    failed_section_count = int(section_pipeline_result.summary.get("failed_sections") or 0)
    if failed_section_count:
        raise RuntimeError(
            "Section pipeline failed before assembly: "
            f"{section_pipeline_result.summary.get('failed_section_ids')}"
        )

    stage_start = time.perf_counter()
    assembly_artifacts = run_assembler(
        book_plan=book_plan,
        review_bundle=section_pipeline_result.review_bundle,
        book_plan_path=CANONICAL_BOOK_PATH,
        review_bundle_path=REVIEW_BUNDLE_OUTPUT_PATH,
        latex_output_path=LATEX_OUTPUT_PATH,
    )
    assembler_seconds = round(time.perf_counter() - stage_start, 2)

    save_assembly_bundle(assembly_artifacts.assembly_bundle, run_dir / "assembly_bundle.json")
    save_assembly_bundle(assembly_artifacts.assembly_bundle, ASSEMBLY_BUNDLE_OUTPUT_PATH)
    save_latex_manuscript(assembly_artifacts.latex_manuscript, run_dir / "book.tex")
    save_latex_manuscript(assembly_artifacts.latex_manuscript, LATEX_OUTPUT_PATH)

    latex_compile_result = None
    if latex_compile_enabled():
        latex_compile_result = compile_latex_file(
            LATEX_OUTPUT_PATH,
            build_dir=LATEX_BUILD_DIR,
        )
        save_latex_compile_result(
            latex_compile_result,
            run_dir / "latex_compile_result.json",
        )
        save_latex_compile_result(
            latex_compile_result,
            LATEX_COMPILE_RESULT_OUTPUT_PATH,
        )
        if strict_latex_compile_enabled() and not latex_compile_result.succeeded:
            first_issue = (
                latex_compile_result.issues[0].message
                if latex_compile_result.issues
                else "Unknown LaTeX compile failure."
            )
            raise RuntimeError(f"LaTeX compilation failed: {first_issue}")

    evaluation = evaluate_latex_book(LATEX_OUTPUT_PATH)
    write_evaluation_outputs(
        evaluation,
        run_dir / "book_evaluation.json",
        run_dir / "book_evaluation.md",
    )
    write_evaluation_outputs(
        evaluation,
        EVALUATION_JSON_OUTPUT_PATH,
        EVALUATION_MD_OUTPUT_PATH,
    )

    summary = {
        "run_dir": str(run_dir),
        "source_research_bundle": str(research_bundle_path),
        "deterministic": deterministic,
        "section_pipeline_seconds": section_pipeline_seconds,
        "assembler_seconds": assembler_seconds,
        "elapsed_seconds": round(time.time() - start_time, 2),
        "section_pipeline": section_pipeline_result.summary,
        "llm_usage": get_llm_metrics_summary(),
        "evaluation": {
            "quality_score": evaluation["quality_score"],
            "totals": evaluation["totals"],
            "weak_section_count": evaluation["weak_section_count"],
            "recommendations": evaluation["recommendations"],
        },
        "latex_compile": latex_compile_result.model_dump() if latex_compile_result else None,
        "artifacts": {
            "latex_manuscript": str(LATEX_OUTPUT_PATH),
            "latex_compile_result": str(LATEX_COMPILE_RESULT_OUTPUT_PATH),
            "compiled_pdf": latex_compile_result.pdf_path if latex_compile_result else None,
            "book_evaluation": str(EVALUATION_MD_OUTPUT_PATH),
        },
    }
    write_json(run_dir / "post_research_run_summary.json", summary)
    write_json(OUTPUTS_DIR / "post_research_run_summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build notes/writer/review/assembly from an existing research_bundle.json."
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="Use deterministic notes/writer/reviewer to avoid LLM quota use.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_from_research_bundle(
        run_dir=args.run_dir.resolve(),
        deterministic=args.deterministic,
    )
    print(f"Book rebuilt from research bundle: {summary['run_dir']}")
    print(f"Quality score: {summary['evaluation']['quality_score']}/100")
    print(f"LaTeX: {summary['artifacts']['latex_manuscript']}")
    if summary["latex_compile"]:
        print(f"LaTeX compile status: {summary['latex_compile']['status']}")
        if summary["artifacts"]["compiled_pdf"]:
            print(f"Compiled PDF: {summary['artifacts']['compiled_pdf']}")
    print(f"Evaluation: {summary['artifacts']['book_evaluation']}")


if __name__ == "__main__":
    main()
