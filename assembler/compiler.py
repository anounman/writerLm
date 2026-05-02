from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_LATEX_TIMEOUT_SECONDS = 240
DEFAULT_BUILD_DIR_NAME = "latex_build"
LATEXMK_COMMAND = "latexmk"
ENGINE_COMMANDS = ("pdflatex", "xelatex", "lualatex")

# Mapping of Unicode characters that pdflatex cannot handle to safe ASCII
# equivalents.  This table mirrors the one in assembler/latex.py so that even
# .tex files produced by old runs (before latex.py was fixed) can be compiled.
_UNICODE_SAFE_MAP: dict[str, str] = {
    "\u00a0": " ",
    "\u2010": "-", "\u2011": "-", "\u2012": "-",
    "\u2013": "--", "\u2014": "---",
    "\u2018": "'", "\u2019": "'",
    "\u201c": "``", "\u201d": "''",
    "\u2026": "...",
    "\u2212": "-",
    "\u221a": "sqrt",
    # Box-drawing characters (directory trees, ASCII art)
    "\u2500": "-",  "\u2501": "=",
    "\u2502": "|",  "\u2503": "|",
    "\u250c": "+",  "\u2510": "+",
    "\u2514": "+",  "\u2518": "+",
    "\u251c": "+",  "\u2524": "+",
    "\u252c": "+",  "\u2534": "+",
    "\u253c": "+",
    "\u2550": "=",  "\u2551": "|",
    "\u255a": "+",  "\u2560": "+",
    "\u2566": "+",  "\u256c": "+",
    # Arrows
    "\u2192": "->", "\u2190": "<-", "\u2194": "<->",
    "\u21d2": "=>", "\u21d4": "<=>",
    # Misc symbols
    "\u2022": "*",  "\u25cf": "*",  "\u25cb": "o",
    "\u25a0": "[]", "\u25a1": "[]",
    "\u2713": "OK", "\u2717": "X",
    "\u00b7": ".",  "\u00d7": "x",  "\u00f7": "/",
    "\u00b1": "+/-",
    "\u2248": "~=", "\u2260": "!=",
    "\u2264": "<=", "\u2265": ">=",
    "\u00ae": "(R)", "\u2122": "(TM)", "\u00a9": "(C)",
}


@dataclass(frozen=True)
class LatexIssue:
    severity: str
    message: str
    line: int | None = None


@dataclass(frozen=True)
class LatexCompileResult:
    status: str
    tex_path: str
    build_dir: str
    pdf_path: str | None = None
    compiler: str | None = None
    command: list[str] = field(default_factory=list)
    return_code: int | None = None
    stdout_tail: str = ""
    log_path: str | None = None
    issues: list[LatexIssue] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.status == "success"

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


class LatexCompiler:
    """
    Local Overleaf-style PDF compiler.

    It prefers latexmk because latexmk handles repeated passes, references, TOC,
    and bibliography-like reruns. If latexmk is unavailable, it falls back to
    running a TeX engine multiple times.
    """

    def __init__(
        self,
        *,
        preferred_engine: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.preferred_engine = (preferred_engine or os.getenv("LATEX_ENGINE") or "pdflatex").strip()
        self.timeout_seconds = timeout_seconds or _read_positive_int_env(
            "WRITERLM_LATEX_TIMEOUT_SECONDS",
            "LATEX_TIMEOUT_SECONDS",
            default=DEFAULT_LATEX_TIMEOUT_SECONDS,
        )

    def compile_file(
        self,
        tex_path: str | Path,
        *,
        build_dir: str | Path | None = None,
    ) -> LatexCompileResult:
        source_path = Path(tex_path).resolve()
        output_dir = (
            Path(build_dir).resolve()
            if build_dir is not None
            else source_path.parent / DEFAULT_BUILD_DIR_NAME
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        if not source_path.exists():
            return LatexCompileResult(
                status="source_missing",
                tex_path=str(source_path),
                build_dir=str(output_dir),
                issues=[
                    LatexIssue(
                        severity="error",
                        message=f"LaTeX source not found: {source_path}",
                    )
                ],
            )

        command = self._build_command(source_path=source_path, output_dir=output_dir)
        if command is None:
            return LatexCompileResult(
                status="compiler_missing",
                tex_path=str(source_path),
                build_dir=str(output_dir),
                issues=[
                    LatexIssue(
                        severity="error",
                        message=(
                            "No LaTeX compiler found. Install MiKTeX or TeX Live "
                            "with latexmk, pdflatex, xelatex, or lualatex."
                        ),
                    )
                ],
            )

        # Sanitize the .tex source: replace Unicode characters that pdflatex
        # cannot handle, writing a clean copy into the build dir.  The original
        # source file is never modified.
        sanitized_path = _sanitize_tex_file(source_path, output_dir)

        # Rewrite the command to point at the sanitized copy.
        command = [
            arg if arg != str(source_path) else str(sanitized_path)
            for arg in command
        ]

        return self._run_command(
            command=command,
            source_path=sanitized_path,
            output_dir=output_dir,
        )

    def _build_command(
        self,
        *,
        source_path: Path,
        output_dir: Path,
    ) -> list[str] | None:
        latexmk = shutil.which(LATEXMK_COMMAND)
        if latexmk:
            engine = _normalize_engine(self.preferred_engine)
            engine_flag = {
                "pdflatex": "-pdf",
                "xelatex": "-xelatex",
                "lualatex": "-lualatex",
            }.get(engine, "-pdf")
            return [
                latexmk,
                engine_flag,
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-file-line-error",
                f"-outdir={output_dir}",
                str(source_path),
            ]

        engine = self._resolve_engine()
        if engine is None:
            return None

        return [
            engine,
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            f"-output-directory={output_dir}",
            str(source_path),
        ]

    def _resolve_engine(self) -> str | None:
        candidates = [_normalize_engine(self.preferred_engine)]
        candidates.extend(engine for engine in ENGINE_COMMANDS if engine not in candidates)
        for candidate in candidates:
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        return None

    def _run_command(
        self,
        *,
        command: list[str],
        source_path: Path,
        output_dir: Path,
    ) -> LatexCompileResult:
        compiler = Path(command[0]).name
        stdout_chunks: list[str] = []
        return_code: int | None = None
        timed_out = False

        try:
            if Path(command[0]).name.lower().startswith("latexmk"):
                completed = subprocess.run(
                    command,
                    cwd=str(source_path.parent),
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=self.timeout_seconds,
                    check=False,
                )
                return_code = completed.returncode
                stdout_chunks.append(completed.stdout or "")
            else:
                for _ in range(_engine_pass_count()):
                    completed = subprocess.run(
                        command,
                        cwd=str(source_path.parent),
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        timeout=self.timeout_seconds,
                        check=False,
                    )
                    return_code = completed.returncode
                    stdout_chunks.append(completed.stdout or "")
                    if completed.returncode != 0:
                        break
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            return_code = None
            stdout_chunks.append(_decode_timeout_output(exc))

        stdout = "\n".join(stdout_chunks)
        log_path = _find_log_path(source_path=source_path, output_dir=output_dir)
        log_text = _read_text(log_path) if log_path else ""
        issues = parse_latex_issues(log_text or stdout)
        pdf_path = output_dir / f"{source_path.stem}.pdf"

        if timed_out:
            status = "timeout"
            issues = [
                LatexIssue(
                    severity="error",
                    message=f"LaTeX compilation timed out after {self.timeout_seconds} seconds.",
                ),
                *issues,
            ]
        elif return_code == 0 and pdf_path.exists():
            status = "success"
        else:
            status = "failed"
            if not issues:
                issues = [
                    LatexIssue(
                        severity="error",
                        message="LaTeX compiler failed. Check stdout_tail and log_path for details.",
                    )
                ]

        return LatexCompileResult(
            status=status,
            tex_path=str(source_path),
            build_dir=str(output_dir),
            pdf_path=str(pdf_path) if pdf_path.exists() else None,
            compiler=compiler,
            command=command,
            return_code=return_code,
            stdout_tail=_tail(stdout),
            log_path=str(log_path) if log_path else None,
            issues=issues[:25],
        )


def parse_latex_issues(log_text: str) -> list[LatexIssue]:
    issues: list[LatexIssue] = []
    lines = log_text.splitlines()

    for index, line in enumerate(lines):
        stripped = line.strip()
        file_line_error = re.search(r"(?P<file>[^:\s][^:]*\.tex):(?P<line>\d+):\s*(?P<message>.+)", stripped)
        if file_line_error:
            issues.append(
                LatexIssue(
                    severity="error",
                    line=int(file_line_error.group("line")),
                    message=file_line_error.group("message").strip(),
                )
            )
            continue

        if stripped.startswith("!"):
            context = _next_non_empty(lines, index + 1)
            line_number = _extract_latex_line_number(context or "")
            message = stripped.lstrip("!").strip()
            if context and context != message:
                message = f"{message} ({context.strip()})"
            issues.append(
                LatexIssue(
                    severity="error",
                    line=line_number,
                    message=message,
                )
            )
            continue

        if "LaTeX Warning:" in stripped:
            issues.append(
                LatexIssue(
                    severity="warning",
                    message=stripped,
                    line=_extract_latex_line_number(stripped),
                )
            )

    return _dedupe_issues(issues)


def compile_latex_file(
    tex_path: str | Path,
    *,
    build_dir: str | Path | None = None,
    preferred_engine: str | None = None,
) -> LatexCompileResult:
    return LatexCompiler(preferred_engine=preferred_engine).compile_file(
        tex_path,
        build_dir=build_dir,
    )


def _normalize_engine(engine: str) -> str:
    value = engine.strip().lower()
    if value in {"pdf", "pdftex"}:
        return "pdflatex"
    if value in {"xe", "xetex"}:
        return "xelatex"
    if value in {"lua", "luatex"}:
        return "lualatex"
    return value or "pdflatex"


def _engine_pass_count() -> int:
    return _read_positive_int_env(
        "WRITERLM_LATEX_ENGINE_PASSES",
        "LATEX_ENGINE_PASSES",
        default=2,
    )


def _read_positive_int_env(*names: str, default: int) -> int:
    for name in names:
        value = os.getenv(name)
        if value is None or not value.strip():
            continue
        try:
            parsed = int(value)
        except ValueError:
            continue
        if parsed > 0:
            return parsed
    return default


def _find_log_path(*, source_path: Path, output_dir: Path) -> Path | None:
    candidates = [
        output_dir / f"{source_path.stem}.log",
        source_path.with_suffix(".log"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _tail(text: str, *, max_chars: int = 6000) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _next_non_empty(lines: list[str], start: int) -> str | None:
    for line in lines[start : start + 4]:
        if line.strip():
            return line.strip()
    return None


def _extract_latex_line_number(text: str) -> int | None:
    match = re.search(r"l\.(\d+)", text)
    if match:
        return int(match.group(1))
    match = re.search(r"line\s+(\d+)", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _decode_timeout_output(exc: subprocess.TimeoutExpired) -> str:
    output = exc.output or exc.stdout or ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return str(output)


def _dedupe_issues(issues: list[LatexIssue]) -> list[LatexIssue]:
    seen: set[tuple[str, str, int | None]] = set()
    deduped: list[LatexIssue] = []
    for issue in issues:
        key = (issue.severity, issue.message, issue.line)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return deduped


def _sanitize_tex_file(source_path: Path, output_dir: Path) -> Path:
    """Return a path to a Unicode-sanitized copy of *source_path*.

    pdflatex (and latexmk driving it) fatally crashes when it encounters
    Unicode characters outside its supported range – most commonly box-drawing
    characters (├, │, └, ─ …) that LLMs generate in directory-tree diagrams.

    This function:
    1. Reads the source .tex file.
    2. Replaces every character listed in ``_UNICODE_SAFE_MAP`` with its ASCII
       equivalent.
    3. Replaces any remaining non-ASCII character with ``?`` as a last-resort
       safety net.
    4. Writes the sanitized content to ``<output_dir>/<stem>_sanitized.tex``
       and returns that path.

    The original source file is **never modified**.
    """
    raw = _read_text(source_path)

    # Apply the explicit replacement table first.
    for unicode_char, ascii_replacement in _UNICODE_SAFE_MAP.items():
        raw = raw.replace(unicode_char, ascii_replacement)

    # Final safety pass: replace any remaining non-ASCII characters.
    sanitized = "".join(
        char if ord(char) <= 127 else "?" for char in raw
    )

    sanitized_path = output_dir / f"{source_path.stem}_sanitized.tex"
    try:
        sanitized_path.write_text(sanitized, encoding="utf-8")
    except OSError:
        # If we can't write to the build dir for some reason, fall back to the
        # original file (compilation will likely still fail, but at least we
        # don't swallow the error silently).
        return source_path

    return sanitized_path
