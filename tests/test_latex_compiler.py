from __future__ import annotations

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from assembler.compiler import LatexCompiler, parse_latex_issues


def test_parse_file_line_error() -> None:
    issues = parse_latex_issues(
        "./book.tex:42: Undefined control sequence.\n"
        "l.42 \\badcommand\n"
    )

    assert len(issues) == 1
    assert issues[0].severity == "error"
    assert issues[0].line == 42
    assert "Undefined control sequence" in issues[0].message


def test_parse_layout_and_duplicate_destination_warnings() -> None:
    issues = parse_latex_issues(
        "Overfull \\hbox (101.57pt too wide) in paragraph at lines 10--11\n"
        "pdfTeX warning (ext4): destination with the same identifier (name{figure.4.1}) has been already used, duplicate ignored\n"
    )

    assert len(issues) == 2
    assert all(issue.severity == "warning" for issue in issues)
    assert "Overfull" in issues[0].message
    assert "duplicate ignored" in issues[1].message


def test_missing_compiler_returns_clear_result() -> None:
    with TemporaryDirectory() as tmp:
        tex_path = Path(tmp) / "book.tex"
        tex_path.write_text("\\documentclass{article}\\begin{document}Hi\\end{document}", encoding="utf-8")

        with patch("assembler.compiler.shutil.which", return_value=None):
            result = LatexCompiler().compile_file(tex_path)

    assert result.status == "compiler_missing"
    assert not result.succeeded
    assert "No LaTeX compiler found" in result.issues[0].message


def test_latexmk_success_writes_pdf_result() -> None:
    with TemporaryDirectory() as tmp:
        tex_path = Path(tmp) / "book.tex"
        build_dir = Path(tmp) / "build"
        tex_path.write_text("\\documentclass{article}\\begin{document}Hi\\end{document}", encoding="utf-8")

        def fake_run(command, **kwargs):
            _write_fake_artifacts(command, tex_path, build_dir, success=True)
            return subprocess.CompletedProcess(command, 0, stdout="Latexmk: All targets are up-to-date")

        with patch("assembler.compiler.shutil.which", return_value="latexmk"), patch(
            "assembler.compiler.subprocess.run",
            side_effect=fake_run,
        ):
            result = LatexCompiler().compile_file(tex_path, build_dir=build_dir)

    assert result.status == "success"
    assert result.succeeded
    assert result.compiler == "latexmk"
    assert result.pdf_path is not None
    assert result.return_code == 0


def test_engine_failure_extracts_error_from_log() -> None:
    with TemporaryDirectory() as tmp:
        tex_path = Path(tmp) / "book.tex"
        build_dir = Path(tmp) / "build"
        tex_path.write_text("\\documentclass{article}\\begin{document}\\bad\\end{document}", encoding="utf-8")

        def fake_which(name):
            if name == "pdflatex":
                return "pdflatex"
            return None

        def fake_run(command, **kwargs):
            _write_fake_artifacts(command, tex_path, build_dir, success=False)
            return subprocess.CompletedProcess(command, 1, stdout="failed")

        with patch("assembler.compiler.shutil.which", side_effect=fake_which), patch(
            "assembler.compiler.subprocess.run",
            side_effect=fake_run,
        ):
            result = LatexCompiler().compile_file(tex_path, build_dir=build_dir)

    assert result.status == "failed"
    assert not result.succeeded
    assert result.compiler == "pdflatex"
    assert result.issues
    assert result.issues[0].line == 7
    assert "Undefined control sequence" in result.issues[0].message


def _write_fake_artifacts(
    command: list[str],
    tex_path: Path,
    build_dir: Path,
    *,
    success: bool,
) -> None:
    build_dir.mkdir(parents=True, exist_ok=True)
    log_path = build_dir / f"{tex_path.stem}.log"
    if success:
        (build_dir / f"{tex_path.stem}.pdf").write_bytes(b"%PDF-1.4 fake\n")
        log_path.write_text("Output written on book.pdf.\n", encoding="utf-8")
    else:
        log_path.write_text(
            "./book.tex:7: Undefined control sequence.\n"
            "l.7 \\bad\n",
            encoding="utf-8",
        )
