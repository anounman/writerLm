from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO_ROOT / "outputs" / "book.tex"
DEFAULT_JSON_OUTPUT = REPO_ROOT / "outputs" / "book_evaluation.json"
DEFAULT_MD_OUTPUT = REPO_ROOT / "outputs" / "book_evaluation.md"


def evaluate_latex_book(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    sections = _extract_sections(content)
    section_evaluations = [_evaluate_section(section) for section in sections]

    totals = {
        "chapters": len(re.findall(r"\\chapter\{", content)),
        "sections": len(sections),
        "code_blocks": len(re.findall(r"\\begin\{lstlisting\}", content)),
        "figures": len(re.findall(r"\\begin\{figure\}", content)),
        "diagram_boxes": len(re.findall(r"\\begin\{diagramplaceholder\}", content)),
        "exercise_boxes": len(re.findall(r"\\begin\{exercisebox\}", content)),
        "gotcha_boxes": len(re.findall(r"\\begin\{gotchabox\}", content)),
        "urls": len(re.findall(r"\\url\{", content)),
        "estimated_words": _estimate_words(content),
    }

    weak_sections = [
        item
        for item in section_evaluations
        if item["score"] < 70
    ]

    return {
        "input_path": str(path),
        "totals": totals,
        "quality_score": _score_book(totals, section_evaluations),
        "weak_section_count": len(weak_sections),
        "weak_sections": weak_sections[:20],
        "section_evaluations": section_evaluations,
        "recommendations": _recommendations(totals, section_evaluations),
    }


def _extract_sections(content: str) -> list[dict[str, str]]:
    pattern = re.compile(r"\\section\{(?P<title>[^}]*)\}")
    matches = list(pattern.finditer(content))
    sections: list[dict[str, str]] = []

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        sections.append(
            {
                "title": match.group("title"),
                "content": content[start:end],
            }
        )

    return sections


def _evaluate_section(section: dict[str, str]) -> dict[str, Any]:
    content = section["content"]
    has_code = "\\begin{lstlisting}" in content
    has_diagram = "\\begin{figure}" in content or "\\begin{diagramplaceholder}" in content
    has_exercise = "\\begin{exercisebox}" in content or "Mini Exercise" in content
    has_gotcha = "\\begin{gotchabox}" in content or "Common Mistakes" in content
    has_url = "\\url{" in content
    word_count = _estimate_words(content)

    score = 0
    score += 20 if word_count >= 250 else 10 if word_count >= 120 else 0
    score += 20 if has_code else 0
    score += 20 if has_diagram else 0
    score += 15 if has_exercise else 0
    score += 15 if has_gotcha else 0
    score += 10 if has_url else 0

    missing = []
    if word_count < 250:
        missing.append("needs_more_depth")
    if not has_code:
        missing.append("missing_code")
    if not has_diagram:
        missing.append("missing_diagram")
    if not has_exercise:
        missing.append("missing_exercise")
    if not has_url:
        missing.append("missing_reference_link")

    return {
        "title": section["title"],
        "score": score,
        "word_count": word_count,
        "has_code": has_code,
        "has_diagram": has_diagram,
        "has_exercise": has_exercise,
        "has_gotcha": has_gotcha,
        "has_reference_link": has_url,
        "missing": missing,
    }


def _score_book(totals: dict[str, int], sections: list[dict[str, Any]]) -> int:
    if not sections:
        return 0

    avg_section_score = sum(item["score"] for item in sections) / len(sections)
    structure_bonus = 0
    structure_bonus += 5 if totals["chapters"] >= 4 else 0
    structure_bonus += 5 if totals["sections"] >= 12 else 0
    structure_bonus += 5 if totals["estimated_words"] >= 12000 else 0
    return min(100, round(avg_section_score * 0.85 + structure_bonus))


def _recommendations(
    totals: dict[str, int],
    sections: list[dict[str, Any]],
) -> list[str]:
    recommendations: list[str] = []
    section_count = max(len(sections), 1)

    if totals["code_blocks"] < section_count * 0.6:
        recommendations.append("Increase code coverage; most hands-on sections should include runnable code.")
    if totals["diagram_boxes"] < section_count * 0.5:
        recommendations.append("Increase visual coverage; add diagrams for architecture, process, and data flow sections.")
    if totals["exercise_boxes"] < section_count * 0.5:
        recommendations.append("Add more mini exercises or checkpoints so the book feels like a workbook.")
    if totals["urls"] < section_count * 0.4:
        recommendations.append("Carry more source links into Further Reading lists.")
    if totals["estimated_words"] < 12000:
        recommendations.append("The manuscript is still short for a proper hands-on book; increase section depth.")

    weak_titles = [item["title"] for item in sections if item["score"] < 70]
    if weak_titles:
        recommendations.append(
            "Prioritize weak sections: " + ", ".join(weak_titles[:8])
        )

    return recommendations


def _estimate_words(content: str) -> int:
    stripped = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^}]*\})?", " ", content)
    stripped = re.sub(r"[{}\\]", " ", stripped)
    return len(re.findall(r"[A-Za-z0-9_]+", stripped))


def write_outputs(evaluation: dict[str, Any], json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(evaluation, indent=2), encoding="utf-8")

    totals = evaluation["totals"]
    lines = [
        "# Book Evaluation",
        "",
        f"Input: `{evaluation['input_path']}`",
        f"Quality score: **{evaluation['quality_score']}/100**",
        "",
        "## Totals",
        "",
        f"- Chapters: {totals['chapters']}",
        f"- Sections: {totals['sections']}",
        f"- Estimated words: {totals['estimated_words']}",
        f"- Code blocks: {totals['code_blocks']}",
        f"- Diagram boxes: {totals['diagram_boxes']}",
        f"- Exercise boxes: {totals['exercise_boxes']}",
        f"- Gotcha boxes: {totals['gotcha_boxes']}",
        f"- Reference URLs: {totals['urls']}",
        "",
        "## Recommendations",
        "",
    ]

    recommendations = evaluation["recommendations"] or ["No major recommendations."]
    lines.extend(f"- {item}" for item in recommendations)

    lines.extend(["", "## Weak Sections", ""])
    weak_sections = evaluation["weak_sections"] or []
    if not weak_sections:
        lines.append("- None")
    else:
        for item in weak_sections:
            lines.append(
                f"- {item['title']}: {item['score']}/100, missing {', '.join(item['missing']) or 'nothing'}"
            )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate generated book LaTeX without compiling it.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    evaluation = evaluate_latex_book(args.input)
    write_outputs(evaluation, args.json_output, args.md_output)
    print(f"Quality score: {evaluation['quality_score']}/100")
    print(f"Evaluation saved to: {args.md_output}")


if __name__ == "__main__":
    main()
