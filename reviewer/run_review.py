from __future__ import annotations

import argparse
import time
from pathlib import Path

from reviewer.io import (
    build_reviewer_tasks,
    load_notes_bundle,
    load_writer_bundle,
    save_review_bundle,
)
from reviewer.llm_client import build_reviewer_llm_client
from reviewer.orchestrator import run_reviewer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Reviewer layer.")
    parser.add_argument(
        "--notes-bundle",
        type=Path,
        required=True,
        help="Path to notes_bundle.json",
    )
    parser.add_argument(
        "--writer-bundle",
        type=Path,
        required=True,
        help="Path to writer_bundle.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write review_bundle.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start_time = time.time()

    notes_bundle = load_notes_bundle(args.notes_bundle)
    writer_bundle = load_writer_bundle(args.writer_bundle)

    tasks = build_reviewer_tasks(
        notes_bundle=notes_bundle,
        writer_bundle=writer_bundle,
    )

    llm_client = build_reviewer_llm_client()
    review_bundle = run_reviewer(tasks=tasks, llm_client=llm_client)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    save_review_bundle(review_bundle, args.output)

    elapsed = time.time() - start_time

    print(f"Total sections: {review_bundle.metadata.total_sections}")
    print(f"Approved sections: {review_bundle.metadata.approved_sections}")
    print(f"Revised sections: {review_bundle.metadata.revised_sections}")
    print(f"Flagged sections: {review_bundle.metadata.flagged_sections}")
    print(f"Execution time: {elapsed:.2f}s")


if __name__ == "__main__":
    main()