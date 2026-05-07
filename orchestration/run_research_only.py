from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from planner_agent.schemas import BookPlan
from researcher.schemas import PlannerSectionRef, SectionResearchPacket
from llm_provider import (
    get_default_models_for_layer,
    get_legacy_model_env_names_by_provider,
    resolve_openai_compatible_config,
)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def build_run_dir(base_dir: str = "runs") -> Path:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = REPO_ROOT / base_dir / run_id
    ensure_dir(run_dir)
    return run_dir


def resolve_run_dir(*, base_dir: str, run_dir: Path | None, resume: bool) -> Path:
    if run_dir is not None:
        resolved = run_dir.resolve()
        ensure_dir(resolved)
        return resolved

    if resume:
        raise ValueError("--resume requires --run-dir so the runner knows which run to continue.")

    return build_run_dir(base_dir)


def slugify(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value)
    slug = "-".join(part for part in cleaned.split("-") if part)
    return slug or "untitled"


def build_chapter_id(*, chapter_number: int, chapter_title: str) -> str:
    return f"chapter-{chapter_number}-{slugify(chapter_title)}"


def build_section_id(*, chapter_number: int, section_title: str) -> str:
    return f"chapter-{chapter_number}-section-{slugify(section_title)}"


def build_planner_section_ref(*, chapter: Any, section: Any) -> PlannerSectionRef:
    return PlannerSectionRef(
        section_id=build_section_id(
            chapter_number=chapter.chapter_number,
            section_title=section.title,
        ),
        chapter_id=build_chapter_id(
            chapter_number=chapter.chapter_number,
            chapter_title=chapter.title,
        ),
        chapter_title=chapter.title,
        section_title=section.title,
        section_goal=section.goal,
        section_summary=getattr(section, "summary", None),
        key_points=getattr(section, "key_points", []),
    )


def prefix_messages(
    *,
    messages: list[str],
    chapter_title: str,
    section_title: str,
    level: str,
) -> list[str]:
    prefixed: list[str] = []
    for message in messages:
        cleaned = " ".join(message.split()).strip()
        if not cleaned:
            continue
        prefixed.append(
            f"[{level}] Chapter='{chapter_title}' Section='{section_title}': {cleaned}"
        )
    return prefixed


def format_missing_packet_message(*, chapter_title: str, section_title: str) -> str:
    return (
        f"[error] Chapter='{chapter_title}' Section='{section_title}': "
        "Researcher workflow completed without producing a research packet."
    )


def find_latest_book_plan() -> Path:
    candidate_paths: list[Path] = []

    for relative_root in ("runs", "orchestration/runs"):
        root = REPO_ROOT / relative_root
        if root.exists():
            candidate_paths.extend(root.glob("*/book_plan.json"))

    fallback_output = REPO_ROOT / "outputs" / "book_plan.json"
    if fallback_output.exists():
        candidate_paths.append(fallback_output)

    if not candidate_paths:
        raise FileNotFoundError(
            "No saved book_plan.json found in runs/, orchestration/runs/, or outputs/."
        )

    return max(candidate_paths, key=lambda path: path.stat().st_mtime)


def load_book_plan(book_plan_path: Path) -> BookPlan:
    with book_plan_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return BookPlan.model_validate(payload)


def load_saved_section_packet(path: Path) -> SectionResearchPacket:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return SectionResearchPacket.model_validate(payload)


def save_section_packet(*, run_dir: Path, packet: SectionResearchPacket) -> None:
    sections_dir = run_dir / "sections"
    ensure_dir(sections_dir)
    write_json(
        sections_dir / f"{packet.section_id}.json",
        packet.model_dump(mode="json"),
    )


def build_researcher_workflow(*, user_urls: list[str] | None = None):
    from researcher.services.firecrawl_client import FirecrawlClient
    from researcher.services.llm_structured import GroqStructuredLLM
    from researcher.services.pdf_extractor import PDFExtractor
    from researcher.services.tavily_client import TavilySearchClient
    from researcher.services.user_document_store import UserDocumentStore
    from researcher.services.web_extractor import WebExtractor
    from researcher.workflow import ResearcherWorkflow

    llm_config = resolve_openai_compatible_config(
        layer="researcher",
        default_models=get_default_models_for_layer("researcher"),
        legacy_env_names_by_provider=get_legacy_model_env_names_by_provider(),
    )

    llm = GroqStructuredLLM(
        api_key=llm_config.api_key,
        model=llm_config.model,
        base_url=llm_config.base_url,
    )

    web_extractor = WebExtractor()
    pdf_extractor = PDFExtractor()

    firecrawl_api_key = os.environ.get("FIRECRAWL_API_KEY")
    firecrawl_client = (
        FirecrawlClient(api_key=firecrawl_api_key) if firecrawl_api_key else None
    )

    # Load any user-uploaded PDFs from inputs/pdfs/.
    user_doc_store = UserDocumentStore()
    user_documents = user_doc_store.load_all()

    # Determine research mode (mirrors run_full_pipeline.py logic).
    has_user_pdfs = any(user_doc_store.pdf_dir.glob("*.pdf"))
    force_web = os.getenv("WRITERLM_FORCE_WEB_RESEARCH", "0").strip().lower() in {
        "1", "true", "yes", "on"
    }
    web_research_enabled = (not has_user_pdfs) or force_web
    tavily_client = None
    if web_research_enabled:
        tavily_api_key = os.environ.get("TAVILY_API_KEY")
        if not tavily_api_key:
            raise RuntimeError("TAVILY_API_KEY is required when web research is enabled.")
        tavily_client = TavilySearchClient(api_key=tavily_api_key)

    return ResearcherWorkflow(
        llm=llm,
        tavily_client=tavily_client,
        web_extractor=web_extractor,
        pdf_extractor=pdf_extractor,
        firecrawl_client=firecrawl_client,
        user_documents=user_documents or None,
        user_urls=user_urls,
        web_research_enabled=web_research_enabled,
    )


def run_research(
    book_plan: BookPlan,
    researcher_workflow,
    *,
    run_dir: Path,
    resume: bool,
) :
    from planner_research_pipeline import BookResearchBundle, ChapterResearchBundle
    from researcher.state import ResearcherState

    all_chapter_bundles: list[ChapterResearchBundle] = []
    all_warnings: list[str] = []
    all_errors: list[str] = []

    for chapter in book_plan.chapters:
        chapter_packets: list[SectionResearchPacket] = []

        for section in chapter.sections:
            planner_section = build_planner_section_ref(
                chapter=chapter,
                section=section,
            )
            section_cache_path = run_dir / "sections" / f"{planner_section.section_id}.json"

            if resume and section_cache_path.exists():
                try:
                    chapter_packets.append(load_saved_section_packet(section_cache_path))
                    continue
                except Exception as exc:
                    all_warnings.append(
                        f"[warning] Chapter='{chapter.title}' Section='{section.title}': "
                        f"Failed to load saved section result, reprocessing section. {exc}"
                    )

            state = ResearcherState(planner_section=planner_section)
            final_state = researcher_workflow.run(state)

            all_warnings.extend(
                prefix_messages(
                    messages=final_state.warnings,
                    chapter_title=chapter.title,
                    section_title=section.title,
                    level="warning",
                )
            )
            all_errors.extend(
                prefix_messages(
                    messages=final_state.errors,
                    chapter_title=chapter.title,
                    section_title=section.title,
                    level="error",
                )
            )

            if final_state.research_packet is not None:
                chapter_packets.append(final_state.research_packet)
                save_section_packet(
                    run_dir=run_dir,
                    packet=final_state.research_packet,
                )
            else:
                all_errors.append(
                    format_missing_packet_message(
                        chapter_title=chapter.title,
                        section_title=section.title,
                    )
                )

        all_chapter_bundles.append(
            ChapterResearchBundle(
                chapter_id=build_chapter_id(
                    chapter_number=chapter.chapter_number,
                    chapter_title=chapter.title,
                ),
                chapter_title=chapter.title,
                section_packets=chapter_packets,
            )
        )

    return BookResearchBundle(
        book_plan=book_plan,
        chapters=all_chapter_bundles,
        warnings=all_warnings,
        errors=all_errors,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run only the research layer using a saved book_plan.json."
    )
    parser.add_argument(
        "--book-plan",
        type=Path,
        default=None,
        help="Optional path to a specific book_plan.json. Defaults to the latest saved run.",
    )
    parser.add_argument(
        "--runs-dir",
        default="runs",
        help="Directory where the new research-only run output should be written.",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Optional concrete run directory to write into or resume from.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from previously saved per-section results in --run-dir.",
    )
    parser.add_argument(
        "--profile",
        choices=("debug", "full"),
        default=None,
        help="Execution profile override. Defaults to RESEARCH_EXECUTION_PROFILE or full.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.profile is not None:
        os.environ["RESEARCH_EXECUTION_PROFILE"] = args.profile

    book_plan_path = (
        args.book_plan.resolve()
        if args.book_plan is not None
        else find_latest_book_plan().resolve()
    )

    if not book_plan_path.exists():
        raise FileNotFoundError(f"book_plan.json not found: {book_plan_path}")

    run_dir = resolve_run_dir(
        base_dir=args.runs_dir,
        run_dir=args.run_dir,
        resume=args.resume,
    )
    book_plan = load_book_plan(book_plan_path)
    # The book plan doesn't natively carry urls in this testing script right now,
    # but we can pass None safely, since it's just research_only for saved plans.
    researcher_workflow = build_researcher_workflow(user_urls=None)

    user_pdf_count = (
        len(researcher_workflow.inject_user_documents_node.user_documents)
        if researcher_workflow.inject_user_documents_node is not None
        else 0
    )
    if user_pdf_count and not researcher_workflow.web_research_enabled:
        print(f"User PDFs loaded: {user_pdf_count} file(s) — running in PDF-only mode (no web research)")
        print("  Tip: set WRITERLM_FORCE_WEB_RESEARCH=1 to also run web research alongside PDFs")
    elif user_pdf_count and researcher_workflow.web_research_enabled:
        print(f"User PDFs loaded: {user_pdf_count} file(s) — running in combined mode (PDFs + web research)")
    else:
        print("User PDFs: none found in inputs/pdfs/ — using full web research")

    bundle = run_research(
        book_plan,
        researcher_workflow,
        run_dir=run_dir,
        resume=args.resume,
    )

    write_json(
        run_dir / "book_plan.json",
        bundle.book_plan.model_dump(mode="json"),
    )
    write_json(
        run_dir / "research_bundle.json",
        bundle.model_dump(mode="json"),
    )

    section_count = sum(len(chapter.section_packets) for chapter in bundle.chapters)
    summary = {
        "source_book_plan": str(book_plan_path),
        "resume_enabled": args.resume,
        "run_dir": str(run_dir),
        "chapter_count": len(bundle.chapters),
        "researched_section_count": section_count,
        "warning_count": len(bundle.warnings),
        "error_count": len(bundle.errors),
        "warnings": bundle.warnings,
        "errors": bundle.errors,
    }
    write_json(run_dir / "run_summary.json", summary)

    print(f"Loaded book plan from: {book_plan_path}")
    print(f"Research-only run saved to: {run_dir}")
    print(f"Chapters: {len(bundle.chapters)}")
    print(f"Researched sections: {section_count}")
    print(f"Warnings: {len(bundle.warnings)}")
    print(f"Errors: {len(bundle.errors)}")


if __name__ == "__main__":
    main()
