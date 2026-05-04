from __future__ import annotations

import re

from assembler.latex import render_latex_manuscript
from assembler.schemas import AssembledChapter, AssembledSection, AssemblyFrontMatter
from reviewer.schemas import ReviewStatus


def test_html_sub_sup_tags_render_as_latex_math() -> None:
    latex = _render_section(
        "Each element C<sub>ij</sub> equals a<sub>11</sub>. A symmetric matrix satisfies A<sup>T</sup> = A."
    )

    assert "<sub>" not in latex
    assert "</sub>" not in latex
    assert "<sup>" not in latex
    assert "</sup>" not in latex
    assert r"\ensuremath{C_{ij}}" in latex
    assert r"\ensuremath{a_{11}}" in latex
    assert r"\ensuremath{A^{T}}" in latex


def test_private_uploaded_file_links_are_removed_from_further_reading() -> None:
    latex = _render_section(
        "A useful explanation.\n\n"
        "### Further Reading\n\n"
        "- Kapitel 1 | file:///app/.cache/uploads/writerlm_pdfs/run/Kapitel_1.pdf\n"
        "- Local file | /Users/example/private.pdf"
    )

    assert "Further Reading" not in latex
    assert "file://" not in latex
    assert "/app/.cache" not in latex
    assert "/Users/" not in latex


def test_public_urls_survive_as_wrapped_latex_urls() -> None:
    latex = _render_section(
        "### Further Reading\n\n"
        "- Public source: https://example.com/linear-algebra"
    )

    assert r"\url{https://example.com/linear-algebra}" in latex


def _render_section(content: str) -> str:
    manuscript = render_latex_manuscript(
        front_matter=AssemblyFrontMatter(
            title="Linear Algebra",
            audience="Students",
            tone="Clear",
            depth="introductory",
            include_title_page=False,
            include_toc=False,
        ),
        chapters=[
            AssembledChapter(
                chapter_id="chapter-1",
                chapter_number=1,
                chapter_title="Matrices",
                chapter_goal="Teach matrix basics.",
                sections=[
                    AssembledSection(
                        section_id="section-1",
                        chapter_id="chapter-1",
                        chapter_number=1,
                        section_number=1,
                        chapter_title="Matrices",
                        section_title="Matrix notation",
                        planner_goal="Teach notation.",
                        estimated_words=100,
                        review_status=ReviewStatus.APPROVED,
                        synthesis_status="ready",
                        writing_status="ready",
                        reviewer_warnings=[],
                        citations_used=[],
                        applied_changes_summary=[],
                        content=content,
                        content_hash="hash",
                        latex_label="sec:test",
                    )
                ],
            )
        ],
    )
    return re.sub(r"\s+", " ", manuscript.content)
