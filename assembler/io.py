from __future__ import annotations

import json
from pathlib import Path

from planner_agent.schemas import BookPlan
from reviewer.schemas import ReviewBundle

from .schemas import AssemblyBundle, LatexManuscript


def load_book_plan(path: str | Path) -> BookPlan:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return BookPlan.model_validate(data)


def load_review_bundle(path: str | Path) -> ReviewBundle:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return ReviewBundle.model_validate(data)


def save_book_plan(book_plan: BookPlan, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        book_plan.model_dump_json(indent=2),
        encoding="utf-8",
    )


def save_assembly_bundle(bundle: AssemblyBundle, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        bundle.model_dump_json(indent=2),
        encoding="utf-8",
    )


def save_latex_manuscript(manuscript: LatexManuscript, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        manuscript.content,
        encoding="utf-8",
    )
