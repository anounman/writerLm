from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from planner_agent.schemas import SourcePlanningContext, UploadedSourceSummary
from researcher.schemas import SourceDocument


_MATH_TERMS = {
    "matrix",
    "matrices",
    "vektor",
    "vector",
    "linear",
    "gleichung",
    "gleichungssystem",
    "ableitung",
    "integral",
    "funktion",
    "eigenwert",
    "determinante",
    "rang",
    "beweis",
    "satz",
    "definition",
}

_EXERCISE_MARKERS = (
    "aufgabe",
    "übung",
    "uebung",
    "exercise",
    "problem",
    "question",
    "solve",
    "berechnen",
    "zeigen sie",
    "bestimmen sie",
)


def build_source_context_from_pdf_dir(pdf_dir: Path | None) -> SourcePlanningContext | None:
    if pdf_dir is None or not pdf_dir.exists():
        return None

    from researcher.services.user_document_store import UserDocumentStore

    documents = UserDocumentStore(pdf_dir=pdf_dir).load_all()
    if not documents:
        return None

    return build_source_context(documents)


def build_source_context(documents: list[SourceDocument]) -> SourcePlanningContext:
    summaries = [_summarize_document(document) for document in documents]
    combined_text = "\n".join(document.text[:8000] for document in documents)
    combined_lower = combined_text.lower()

    source_topics = _top_terms(combined_text, limit=18)
    question_patterns = _extract_question_patterns(combined_text, limit=16)
    likely_language = _detect_language(combined_lower)
    likely_domain = _detect_domain(combined_lower, source_topics)
    has_exercises = any(summary.contains_exercises for summary in summaries) or bool(question_patterns)

    guidance = [
        "Uploaded documents are primary planning evidence; do not let web search redefine their subject.",
        "Use uploaded source terminology to disambiguate acronyms and course names before outlining.",
    ]
    if has_exercises:
        guidance.append(
            "Exercise sheets are present: infer question styles, then create original worked examples and practice problems inspired by them."
        )
    if likely_domain == "mathematics":
        guidance.append(
            "For mathematics, prefer definitions, theorems, intuition, worked examples, and source-inspired exercises over software/project implementation."
        )

    summary = _build_summary(
        summaries=summaries,
        likely_domain=likely_domain,
        likely_language=likely_language,
        has_exercises=has_exercises,
    )

    return SourcePlanningContext(
        has_uploaded_sources=True,
        source_priority="uploaded_sources_primary",
        summary=summary,
        likely_domain=likely_domain,
        likely_language=likely_language,
        uploaded_sources=summaries,
        source_topics=source_topics,
        question_patterns=question_patterns,
        guidance=guidance,
    )


def _summarize_document(document: SourceDocument) -> UploadedSourceSummary:
    text = document.text or ""
    lower = text.lower()
    sample_questions = _extract_question_patterns(text, limit=6)
    sample_terms = _top_terms(text, limit=10)
    return UploadedSourceSummary(
        filename=str(document.metadata.get("filename") or document.title),
        title=document.title,
        page_count=_as_int(document.metadata.get("page_count")),
        language_hints=[_detect_language(lower)],
        likely_topics=sample_terms[:8],
        sample_questions=sample_questions,
        sample_terms=sample_terms,
        text_preview=_clean_preview(text, limit=900),
        contains_exercises=_contains_exercises(lower),
    )


def _as_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _clean_preview(text: str, *, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned[:limit]


def _detect_language(lower_text: str) -> str:
    german_markers = (" der ", " die ", " das ", " und ", " aufgabe", " zeigen sie", " bestimmen sie")
    if any(marker in lower_text for marker in german_markers):
        return "de"
    return "en"


def _detect_domain(lower_text: str, terms: list[str]) -> str:
    term_set = {term.lower() for term in terms}
    math_hits = sum(1 for term in _MATH_TERMS if term in lower_text or term in term_set)
    if math_hits >= 3:
        return "mathematics"
    if any(word in lower_text for word in ("code", "api", "python", "implementation", "software")):
        return "software"
    return "general"


def _contains_exercises(lower_text: str) -> bool:
    return any(marker in lower_text for marker in _EXERCISE_MARKERS)


def _extract_question_patterns(text: str, *, limit: int) -> list[str]:
    patterns: list[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        lower = line.lower()
        if len(line) < 12 or len(line) > 240:
            continue
        if "?" in line or any(marker in lower for marker in _EXERCISE_MARKERS):
            patterns.append(line)
        if len(patterns) >= limit:
            break
    return patterns


def _top_terms(text: str, *, limit: int) -> list[str]:
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "into", "eine", "einer",
        "eines", "der", "die", "das", "und", "ist", "sind", "von", "mit", "auf", "für",
        "sie", "den", "dem", "des", "zur", "zum", "chapter", "seite", "page", "www",
    }
    words = [
        word.lower()
        for word in re.findall(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß0-9+\-]{3,}", text)
        if word.lower() not in stopwords
    ]
    counter = Counter(words)
    return [word for word, _ in counter.most_common(limit)]


def _build_summary(
    *,
    summaries: list[UploadedSourceSummary],
    likely_domain: str,
    likely_language: str,
    has_exercises: bool,
) -> str:
    filenames = ", ".join(summary.filename for summary in summaries[:6])
    if len(summaries) > 6:
        filenames += f", and {len(summaries) - 6} more"
    exercise_text = " Exercise/question material is present." if has_exercises else ""
    return (
        f"{len(summaries)} uploaded PDF source(s): {filenames}. "
        f"Likely domain: {likely_domain}. Likely language: {likely_language}."
        f"{exercise_text}"
    )
