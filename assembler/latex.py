from __future__ import annotations

import re
import unicodedata

from .schemas import AssembledChapter, AssembledSection, AssemblyFrontMatter, LatexManuscript


COMMON_TEXT_REPLACEMENTS = {
    "\u00a0": " ",
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "--",
    "\u2014": "---",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": "``",
    "\u201d": "''",
    "\u2026": "...",
    "\u2212": "-",
    "\u221a": "sqrt",
}


def render_latex_manuscript(
    *,
    front_matter: AssemblyFrontMatter,
    chapters: list[AssembledChapter],
) -> LatexManuscript:
    parts = [
        _render_preamble(),
        "\\begin{document}",
    ]

    if front_matter.include_title_page:
        parts.append(_render_title_page(front_matter))

    parts.append("\\frontmatter")

    if front_matter.include_toc:
        parts.append("\\tableofcontents")

    parts.append("\\mainmatter")

    for chapter in chapters:
        parts.append(_render_chapter(chapter))

    parts.append("\\end{document}")

    return LatexManuscript(
        content="\n\n".join(part for part in parts if part.strip()),
    )


def _render_preamble() -> str:
    return "\n".join(
        [
            "\\documentclass[11pt,oneside,openany]{scrbook}",
            "\\usepackage{iftex}",
            "\\ifPDFTeX",
            "\\usepackage[T1]{fontenc}",
            "\\usepackage[utf8]{inputenc}",
            "\\usepackage{lmodern}",
            "\\else",
            "\\usepackage{fontspec}",
            "\\fi",
            "\\usepackage{microtype}",
            "\\usepackage[a4paper,margin=1in]{geometry}",
            "\\usepackage{hyperref}",
            "\\usepackage{bookmark}",
            "\\usepackage{enumitem}",
            "\\KOMAoptions{parskip=half}",
            "\\setlist[itemize]{leftmargin=2em}",
            "\\setlist[enumerate]{leftmargin=2em}",
        ]
    )


def _render_title_page(front_matter: AssemblyFrontMatter) -> str:
    title = _escape_latex(front_matter.title)
    audience = _escape_latex(front_matter.audience)
    tone = _escape_latex(front_matter.tone)
    depth = _escape_latex(front_matter.depth)

    return "\n".join(
        [
            "\\begin{titlepage}",
            "\\centering",
            "\\vspace*{0.18\\textheight}",
            "{\\Huge\\bfseries " + title + "\\par}",
            "\\vspace{1.5cm}",
            "{\\Large Technical Book Manuscript\\par}",
            "\\vspace{1.2cm}",
            "{\\large Audience: " + audience + "\\par}",
            "\\vspace{0.3cm}",
            "{\\large Tone: " + tone + "\\par}",
            "\\vspace{0.3cm}",
            "{\\large Depth: " + depth + "\\par}",
            "\\vfill",
            "\\end{titlepage}",
        ]
    )


def _render_chapter(chapter: AssembledChapter) -> str:
    parts = [
        _render_comment("chapter_id", chapter.chapter_id),
        _render_comment("chapter_goal", chapter.chapter_goal),
        "\\chapter{" + _escape_latex(chapter.chapter_title) + "}",
    ]

    for section in chapter.sections:
        parts.append(_render_section(section))

    return "\n\n".join(part for part in parts if part.strip())


def _render_section(section: AssembledSection) -> str:
    parts = [
        _render_comment("section_id", section.section_id),
        _render_comment("review_status", section.review_status.value),
        _render_comment(
            "reviewer_warnings",
            ",".join(w.value for w in section.reviewer_warnings),
        ),
        _render_comment("citations_used", ",".join(section.citations_used)),
        "\\section{" + _escape_latex(section.section_title) + "}",
        "\\label{" + section.latex_label + "}",
        _render_content_blocks(section.content),
    ]

    return "\n".join(part for part in parts if part)


def _render_content_blocks(text: str) -> str:
    blocks = _split_blocks(_prepare_text(text))
    rendered_blocks: list[str] = []

    for block in blocks:
        if _is_bullet_list(block):
            rendered_blocks.append(_render_itemize(block))
        elif _is_enumerated_list(block):
            rendered_blocks.append(_render_enumerate(block))
        else:
            rendered_blocks.append(_render_paragraph(block))

    return "\n\n".join(block for block in rendered_blocks if block.strip())


def _render_itemize(lines: list[str]) -> str:
    items = ["\\item " + _escape_latex(_strip_list_marker(line)) for line in lines]
    return "\n".join(["\\begin{itemize}", *items, "\\end{itemize}"])


def _render_enumerate(lines: list[str]) -> str:
    items = ["\\item " + _escape_latex(_strip_enum_marker(line)) for line in lines]
    return "\n".join(["\\begin{enumerate}", *items, "\\end{enumerate}"])


def _render_paragraph(lines: list[str]) -> str:
    paragraph = " ".join(line.strip() for line in lines if line.strip())
    return _escape_latex(paragraph)


def _split_blocks(text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            if current:
                blocks.append(current)
                current = []
            continue

        current.append(stripped)

    if current:
        blocks.append(current)

    return blocks


def _is_bullet_list(lines: list[str]) -> bool:
    return bool(lines) and all(re.match(r"^([*-])\s+", line) for line in lines)


def _is_enumerated_list(lines: list[str]) -> bool:
    return bool(lines) and all(re.match(r"^\d+\.\s+", line) for line in lines)


def _strip_list_marker(line: str) -> str:
    return re.sub(r"^([*-])\s+", "", line, count=1)


def _strip_enum_marker(line: str) -> str:
    return re.sub(r"^\d+\.\s+", "", line, count=1)


def _prepare_text(text: str) -> str:
    normalized = _normalize_text_artifacts(text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _escape_latex(text: str) -> str:
    text = _normalize_text_artifacts(text)
    escaped: list[str] = []

    for char in text:
        if char == "\\":
            escaped.append("\\textbackslash{}")
        elif char == "{":
            escaped.append("\\{")
        elif char == "}":
            escaped.append("\\}")
        elif char == "#":
            escaped.append("\\#")
        elif char == "$":
            escaped.append("\\$")
        elif char == "%":
            escaped.append("\\%")
        elif char == "&":
            escaped.append("\\&")
        elif char == "_":
            escaped.append("\\_")
        elif char == "^":
            escaped.append("\\textasciicircum{}")
        elif char == "~":
            escaped.append("\\textasciitilde{}")
        else:
            escaped.append(char)

    return "".join(escaped)


def _render_comment(key: str, value: str) -> str:
    safe_value = " ".join(_normalize_text_artifacts(value).split()).strip()
    return f"% {key}: {safe_value}"


def _normalize_text_artifacts(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)

    for source, replacement in COMMON_TEXT_REPLACEMENTS.items():
        normalized = normalized.replace(source, replacement)

    return normalized
