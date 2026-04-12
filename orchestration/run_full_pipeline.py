from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from planner_research_pipeline import PlannerResearchPipeline
from planner_agent import PlannerWorkflow
from researcher.services.firecrawl_client import FirecrawlClient
from researcher.services.llm_structured import GroqStructuredLLM
from researcher.services.pdf_extractor import PDFExtractor
from researcher.services.tavily_client import TavilySearchClient
from researcher.services.web_extractor import WebExtractor
from researcher.workflow import ResearcherWorkflow


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_run_dir(base_dir: str = "runs") -> Path:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(base_dir) / run_id
    ensure_dir(run_dir)
    return run_dir


def main() -> None:
    # ---------------------------------------------------------
    # 1. Build input
    # ---------------------------------------------------------
    planner_input = {
        "topic": "Retrieval-Augmented Generation for beginners",
        "audience": "software engineers new to GenAI",
        "tone": "practical and educational",
        "goals": [
            "explain what RAG is",
            "show why it matters",
            "explain the core architecture",
            "show a practical implementation view",
        ],
        "constraints": {
            "max_section_words": 900,
        },
    }

    # If your planner expects a Pydantic model instead of dict, use that:
    # planner_input = UserBookRequest(...)

    # ---------------------------------------------------------
    # 2. Shared services
    # ---------------------------------------------------------
    llm = GroqStructuredLLM(
        api_key=os.environ["GROQ_API_KEY"],
        model="llama-3.3-70b-versatile",
        base_url=os.environ.get("GROQ_BASE_URL"),
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

    # ---------------------------------------------------------
    # 3. Workflows
    # ---------------------------------------------------------
    planner_workflow = PlannerWorkflow(
        llm=llm,
    )

    researcher_workflow = ResearcherWorkflow(
        llm=llm,
        tavily_client=tavily_client,
        web_extractor=web_extractor,
        pdf_extractor=pdf_extractor,
        firecrawl_client=firecrawl_client,
    )

    pipeline = PlannerResearchPipeline(
        planner_workflow=planner_workflow,
        researcher_workflow=researcher_workflow,
    )

    # ---------------------------------------------------------
    # 4. Run full pipeline
    # ---------------------------------------------------------
    bundle = pipeline.run(planner_input)

    # ---------------------------------------------------------
    # 5. Save outputs
    # ---------------------------------------------------------
    run_dir = build_run_dir()

    write_json(
        run_dir / "book_plan.json",
        bundle.book_plan.model_dump(mode="json"),
    )

    write_json(
        run_dir / "research_bundle.json",
        bundle.model_dump(mode="json"),
    )

    section_count = sum(len(ch.section_packets) for ch in bundle.chapters)

    summary = {
        "chapter_count": len(bundle.chapters),
        "researched_section_count": section_count,
        "warning_count": len(bundle.warnings),
        "error_count": len(bundle.errors),
        "warnings": bundle.warnings,
        "errors": bundle.errors,
    }

    write_json(
        run_dir / "run_summary.json",
        summary,
    )

    print(f"Run saved to: {run_dir}")
    print(f"Chapters: {len(bundle.chapters)}")
    print(f"Researched sections: {section_count}")
    print(f"Warnings: {len(bundle.warnings)}")
    print(f"Errors: {len(bundle.errors)}")


if __name__ == "__main__":
    main()
