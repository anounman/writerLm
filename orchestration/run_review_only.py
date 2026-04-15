from __future__ import annotations

import sys
import time
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from reviewer.io import (
    build_reviewer_tasks,
    load_notes_bundle,
    load_writer_bundle,
    save_review_bundle,
)
from reviewer.llm_client import build_reviewer_llm_client
from reviewer.orchestrator import run_reviewer


NOTES_BUNDLE_PATH = REPO_ROOT / "outputs" / "notes_bundle.json"
WRITER_BUNDLE_PATH = REPO_ROOT / "outputs" / "writer_bundle.json"
OUTPUT_PATH = REPO_ROOT / "outputs" / "review_bundle.json"


def ensure_input_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def main() -> None:
    start_time = time.time()

    ensure_input_exists(NOTES_BUNDLE_PATH, "Notes bundle")
    ensure_input_exists(WRITER_BUNDLE_PATH, "Writer bundle")

    notes_bundle = load_notes_bundle(NOTES_BUNDLE_PATH)
    writer_bundle = load_writer_bundle(WRITER_BUNDLE_PATH)

    tasks = build_reviewer_tasks(
        notes_bundle=notes_bundle,
        writer_bundle=writer_bundle,
    )
    if not tasks:
        raise RuntimeError("No Reviewer tasks could be created from the bundles.")

    llm_client = build_reviewer_llm_client()
    review_bundle = run_reviewer(tasks=tasks, llm_client=llm_client)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    save_review_bundle(review_bundle, OUTPUT_PATH)

    elapsed = time.time() - start_time

    print(f"Notes bundle: {NOTES_BUNDLE_PATH}")
    print(f"Writer bundle: {WRITER_BUNDLE_PATH}")
    print(f"Review bundle: {OUTPUT_PATH}")
    print(f"Total sections: {review_bundle.metadata.total_sections}")
    print(f"Approved sections: {review_bundle.metadata.approved_sections}")
    print(f"Revised sections: {review_bundle.metadata.revised_sections}")
    print(f"Flagged sections: {review_bundle.metadata.flagged_sections}")
    print(f"Execution time: {elapsed:.2f}s")


if __name__ == "__main__":
    main()
