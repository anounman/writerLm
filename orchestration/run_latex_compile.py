from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from assembler.compiler import compile_latex_file


DEFAULT_TEX_PATH = REPO_ROOT / "outputs" / "book.tex"
DEFAULT_BUILD_DIR = REPO_ROOT / "outputs" / "latex_build"
DEFAULT_RESULT_PATH = REPO_ROOT / "outputs" / "latex_compile_result.json"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile a LaTeX manuscript to PDF.")
    parser.add_argument("--tex", type=Path, default=DEFAULT_TEX_PATH)
    parser.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD_DIR)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT_PATH)
    parser.add_argument("--engine", default=None, help="pdflatex, xelatex, or lualatex")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with a non-zero status when compilation does not succeed.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = compile_latex_file(
        args.tex,
        build_dir=args.build_dir,
        preferred_engine=args.engine,
    )
    write_json(args.result, result.model_dump())

    print(f"LaTeX compile status: {result.status}")
    if result.pdf_path:
        print(f"PDF: {result.pdf_path}")
    print(f"Result: {args.result.resolve()}")
    if result.issues:
        first_issue = result.issues[0]
        location = f" line {first_issue.line}" if first_issue.line else ""
        print(f"First issue:{location} {first_issue.message}")

    if args.strict and not result.succeeded:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
