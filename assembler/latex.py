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
            "\\usepackage{listings}",
            "\\usepackage{xcolor}",
            "\\usepackage{graphicx}",
            "\\usepackage{float}",
            "\\usepackage{tikz}",
            "\\usepackage{pgfplots}",
            "\\pgfplotsset{compat=1.18}",
            "\\usepackage{tcolorbox}",
            "\\tcbuselibrary{listings,skins}",
            "",
            "% Code listing style",
            "\\definecolor{codebg}{RGB}{245,245,245}",
            "\\definecolor{codeframe}{RGB}{200,200,200}",
            "\\definecolor{codecomment}{RGB}{106,153,85}",
            "\\definecolor{codestring}{RGB}{163,21,21}",
            "\\definecolor{codekeyword}{RGB}{0,0,200}",
            "",
            "\\lstdefinestyle{bookcode}{",
            "  backgroundcolor=\\color{codebg},",
            "  frame=single,",
            "  rulecolor=\\color{codeframe},",
            "  basicstyle=\\ttfamily\\small,",
            "  keywordstyle=\\color{codekeyword}\\bfseries,",
            "  commentstyle=\\color{codecomment}\\itshape,",
            "  stringstyle=\\color{codestring},",
            "  showstringspaces=false,",
            "  breaklines=true,",
            "  breakatwhitespace=true,",
            "  tabsize=4,",
            "  numbers=left,",
            "  numberstyle=\\tiny\\color{gray},",
            "  numbersep=8pt,",
            "  xleftmargin=2em,",
            "  framexleftmargin=1.5em,",
            "  captionpos=b,",
            "}",
            "\\lstset{style=bookcode}",
            "",
            "% Diagram placeholder box",
            "\\newtcolorbox{diagramplaceholder}[2][]{",
            "  colback=blue!5!white,",
            "  colframe=blue!40!white,",
            "  title={#2},",
            "  fonttitle=\\bfseries,",
            "  #1",
            "}",
            "",
            "% Exercise box",
            "\\newtcolorbox{exercisebox}[1][]{",
            "  colback=green!5!white,",
            "  colframe=green!40!white,",
            "  title={Try It Yourself},",
            "  fonttitle=\\bfseries,",
            "  #1",
            "}",
            "",
            "% Common mistakes box",
            "\\newtcolorbox{gotchabox}[1][]{",
            "  colback=red!5!white,",
            "  colframe=red!40!white,",
            "  title={Common Mistakes},",
            "  fonttitle=\\bfseries,",
            "  #1",
            "}",
            "",
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
    prepared = _prepare_text(text)
    segments = _split_code_and_text(prepared)
    rendered_blocks: list[str] = []

    for segment_type, segment_content in segments:
        if segment_type == "code":
            rendered_blocks.append(segment_content)
        elif segment_type == "diagram":
            rendered_blocks.append(segment_content)
        else:
            blocks = _split_blocks(segment_content)
            for block in blocks:
                if _is_bullet_list(block):
                    rendered_blocks.append(_render_itemize(block))
                elif _is_enumerated_list(block):
                    rendered_blocks.append(_render_enumerate(block))
                else:
                    rendered_blocks.append(_render_paragraph(block))

    return "\n\n".join(block for block in rendered_blocks if block.strip())


def _split_code_and_text(text: str) -> list[tuple[str, str]]:
    """Split text into segments: ('text', content), ('code', latex), ('diagram', latex)."""
    segments: list[tuple[str, str]] = []
    lines = text.split("\n")
    i = 0
    current_text_lines: list[str] = []

    while i < len(lines):
        line = lines[i]

        # Check for fenced code block: ```language
        if line.strip().startswith("```") and not line.strip() == "```":
            # Flush accumulated text
            if current_text_lines:
                segments.append(("text", "\n".join(current_text_lines)))
                current_text_lines = []

            lang_hint = line.strip().lstrip("`").strip().lower()
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1  # skip closing ```

            code_content = "\n".join(code_lines)
            latex_lang = _map_language_to_lstlisting(lang_hint)
            latex_code = (
                f"\\begin{{lstlisting}}[language={latex_lang}]\n"
                f"{code_content}\n"
                f"\\end{{lstlisting}}"
            )
            segments.append(("code", latex_code))
            continue

        # Check for DIAGRAM: hint
        if line.strip().startswith("DIAGRAM:"):
            if current_text_lines:
                segments.append(("text", "\n".join(current_text_lines)))
                current_text_lines = []

            diagram_title = line.strip()[len("DIAGRAM:"):].strip()
            desc_lines: list[str] = []
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith("DIAGRAM:") and not lines[i].strip().startswith("```"):
                desc_lines.append(lines[i].strip())
                i += 1

            description = " ".join(desc_lines) if desc_lines else diagram_title
            safe_title = _escape_latex(diagram_title) if diagram_title else "Diagram"
            safe_desc = _escape_latex(description)

            latex_diagram = (
                f"\\begin{{diagramplaceholder}}{{{safe_title}}}\n"
                f"{safe_desc}\n"
                f"\\end{{diagramplaceholder}}"
            )
            segments.append(("diagram", latex_diagram))
            continue

        current_text_lines.append(line)
        i += 1

    if current_text_lines:
        segments.append(("text", "\n".join(current_text_lines)))

    return segments


def _map_language_to_lstlisting(lang_hint: str) -> str:
    """Map a fenced code block language hint to lstlisting language name."""
    mapping = {
        "python": "Python",
        "py": "Python",
        "bash": "bash",
        "sh": "bash",
        "shell": "bash",
        "javascript": "JavaScript",
        "js": "JavaScript",
        "json": "Python",
        "sql": "SQL",
        "text": "",
        "output": "",
        "": "",
    }
    return mapping.get(lang_hint, "")


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
