from __future__ import annotations

from dataclasses import dataclass
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from planner_agent.schemas import BookPlan, ChapterPlan, SectionPlan

from assembler.ids import build_section_id
from assembler.io import (
    load_book_plan,
    load_review_bundle,
    save_book_plan,
    save_assembly_bundle,
    save_latex_manuscript,
)
from assembler.orchestrator import run_assembler


OUTPUTS_DIR = REPO_ROOT / "outputs"
BOOK_PLAN_CANDIDATES = [
    OUTPUTS_DIR / "book.json",
    OUTPUTS_DIR / "book_plan.json",
]
BOOK_PLAN_SEARCH_GLOBS = [
    "runs/*/book_plan.json",
    "orchestration/runs/*/book_plan.json",
]
REVIEW_BUNDLE_CANDIDATES = [OUTPUTS_DIR / "review_bundle.json", OUTPUTS_DIR / "review.json"]
BOOK_JSON_PATH = OUTPUTS_DIR / "book.json"
ASSEMBLY_BUNDLE_PATH = REPO_ROOT / "outputs" / "assembly_bundle.json"
LATEX_OUTPUT_PATH = REPO_ROOT / "outputs" / "book.tex"


@dataclass
class BookPlanCandidateMatch:
    path: Path
    book_plan: BookPlan
    section_ids: set[str]
    overlap_count: int
    missing_review_ids: set[str]
    extra_plan_ids: set[str]


def resolve_input_path(candidates: list[Path], label: str) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate

    searched_paths = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"{label} not found. Checked: {searched_paths}")


def resolve_book_plan_for_review(review_bundle_path: Path) -> tuple[Path, BookPlan, str | None]:
    review_bundle = load_review_bundle(review_bundle_path)
    review_section_ids = {
        section.section_output.section_id
        for section in review_bundle.sections
    }

    if not review_section_ids:
        raise ValueError("Review bundle contains no sections, so assembler cannot resolve a planner artifact.")

    candidate_paths: list[Path] = []
    seen: set[Path] = set()

    for candidate in BOOK_PLAN_CANDIDATES:
        if candidate.exists() and candidate not in seen:
            candidate_paths.append(candidate)
            seen.add(candidate)

    for pattern in BOOK_PLAN_SEARCH_GLOBS:
        for candidate in sorted(REPO_ROOT.glob(pattern)):
            if candidate not in seen:
                candidate_paths.append(candidate)
                seen.add(candidate)

    if not candidate_paths:
        raise FileNotFoundError(
            "No book planner artifacts found. Checked outputs/book.json, outputs/book_plan.json, runs/*/book_plan.json, and orchestration/runs/*/book_plan.json."
        )

    matches: list[BookPlanCandidateMatch] = []
    for path in candidate_paths:
        try:
            book_plan = load_book_plan(path)
        except Exception:
            continue

        plan_section_ids = _derive_book_plan_section_ids(book_plan)
        matches.append(
            BookPlanCandidateMatch(
                path=path,
                book_plan=book_plan,
                section_ids=plan_section_ids,
                overlap_count=len(plan_section_ids & review_section_ids),
                missing_review_ids=review_section_ids - plan_section_ids,
                extra_plan_ids=plan_section_ids - review_section_ids,
            )
        )

    if not matches:
        raise ValueError("Assembler could not load any valid book planner artifacts.")

    exact_match = next(
        (
            match
            for match in matches
            if not match.missing_review_ids and not match.extra_plan_ids
        ),
        None,
    )
    if exact_match is not None:
        if exact_match.path != BOOK_JSON_PATH:
            save_book_plan(exact_match.book_plan, BOOK_JSON_PATH)
            note = f"Prepared {BOOK_JSON_PATH} from exact planner match {exact_match.path}."
            return BOOK_JSON_PATH, exact_match.book_plan, note
        return exact_match.path, exact_match.book_plan, None

    superset_matches = [
        match
        for match in matches
        if not match.missing_review_ids and match.overlap_count == len(review_section_ids)
    ]
    if superset_matches:
        best_match = sorted(
            superset_matches,
            key=lambda match: (len(match.extra_plan_ids), str(match.path)),
        )[0]
        filtered_book_plan = _filter_book_plan_to_section_ids(
            best_match.book_plan,
            review_section_ids,
        )
        save_book_plan(filtered_book_plan, BOOK_JSON_PATH)
        note = (
            f"Prepared {BOOK_JSON_PATH} from {best_match.path} by removing "
            f"{len(best_match.extra_plan_ids)} planner-only section(s) that never reached review."
        )
        return BOOK_JSON_PATH, filtered_book_plan, note

    best_match = sorted(
        matches,
        key=lambda match: (-match.overlap_count, len(match.missing_review_ids), len(match.extra_plan_ids), str(match.path)),
    )[0]
    raise ValueError(
        "Assembler could not find a compatible planner artifact for the current review bundle. "
        f"Best candidate: {best_match.path} "
        f"(overlap={best_match.overlap_count}, "
        f"missing_review_sections={len(best_match.missing_review_ids)}, "
        f"extra_plan_sections={len(best_match.extra_plan_ids)})."
    )


def _derive_book_plan_section_ids(book_plan: BookPlan) -> set[str]:
    section_ids: set[str] = set()

    for chapter in book_plan.chapters:
        for section in chapter.sections:
            section_ids.add(
                build_section_id(
                    chapter_number=chapter.chapter_number,
                    section_title=section.title,
                )
            )

    return section_ids


def _filter_book_plan_to_section_ids(book_plan: BookPlan, allowed_section_ids: set[str]) -> BookPlan:
    filtered_chapters: list[ChapterPlan] = []

    for chapter in book_plan.chapters:
        filtered_sections: list[SectionPlan] = []

        for section in chapter.sections:
            section_id = build_section_id(
                chapter_number=chapter.chapter_number,
                section_title=section.title,
            )
            if section_id in allowed_section_ids:
                filtered_sections.append(
                    SectionPlan(
                        title=section.title,
                        goal=section.goal,
                        key_questions=list(section.key_questions),
                        estimated_words=section.estimated_words,
                    )
                )

        if filtered_sections:
            filtered_chapters.append(
                ChapterPlan(
                    chapter_number=chapter.chapter_number,
                    title=chapter.title,
                    chapter_goal=chapter.chapter_goal,
                    sections=filtered_sections,
                )
            )

    return BookPlan(
        title=book_plan.title,
        audience=book_plan.audience,
        tone=book_plan.tone,
        depth=book_plan.depth,
        chapters=filtered_chapters,
    )


def main() -> None:
    start_time = time.time()

    review_bundle_path = resolve_input_path(REVIEW_BUNDLE_CANDIDATES, "Review bundle")
    book_plan_path, book_plan, preparation_note = resolve_book_plan_for_review(review_bundle_path)

    review_bundle = load_review_bundle(review_bundle_path)

    artifacts = run_assembler(
        book_plan=book_plan,
        review_bundle=review_bundle,
        book_plan_path=book_plan_path,
        review_bundle_path=review_bundle_path,
        latex_output_path=LATEX_OUTPUT_PATH,
    )

    save_assembly_bundle(artifacts.assembly_bundle, ASSEMBLY_BUNDLE_PATH)
    save_latex_manuscript(artifacts.latex_manuscript, LATEX_OUTPUT_PATH)

    elapsed = time.time() - start_time

    if preparation_note:
        print(preparation_note)
    print(f"Book plan: {book_plan_path}")
    print(f"Review bundle: {review_bundle_path}")
    print(f"Assembly bundle: {ASSEMBLY_BUNDLE_PATH}")
    print(f"LaTeX manuscript: {LATEX_OUTPUT_PATH}")
    print(f"Assembly status: {artifacts.assembly_bundle.metadata.assembly_status.value}")
    print(f"Chapters: {artifacts.assembly_bundle.metadata.chapter_count}")
    print(f"Planned sections: {artifacts.assembly_bundle.metadata.planned_section_count}")
    print(f"Assembled sections: {artifacts.assembly_bundle.metadata.assembled_section_count}")
    print(f"Approved sections: {artifacts.assembly_bundle.metadata.approved_sections}")
    print(f"Revised sections: {artifacts.assembly_bundle.metadata.revised_sections}")
    print(f"Flagged sections: {artifacts.assembly_bundle.metadata.flagged_sections}")
    print(f"Execution time: {elapsed:.2f}s")


if __name__ == "__main__":
    main()
