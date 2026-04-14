from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .schemas import CoverageSignal, SectionSynthesisInput


MAX_KEY_CONCEPTS = 12
MAX_EVIDENCE_ITEMS = 20
MAX_WRITING_GUIDANCE_ITEMS = 10
MAX_OPEN_QUESTIONS = 10
MAX_PLANNER_CONTEXT_CHARS = 500
MAX_EVIDENCE_ITEM_CHARS = 300


def _as_clean_string(value: Any) -> Optional[str]:
    """
    Convert arbitrary input to a stripped string.
    Return None for empty/invalid values.
    """
    if value is None:
        return None

    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None

    cleaned = str(value).strip()
    return cleaned or None


def _dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    """
    Remove duplicates while preserving original order.
    Empty items are removed.
    """
    seen = set()
    output: List[str] = []

    for item in items:
        cleaned = _as_clean_string(item)
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        output.append(cleaned)

    return output


def _clip_text(text: str, max_chars: int) -> str:
    """
    Light character clipping to keep synthesis input compact.
    """
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _extract_list_of_strings(value: Any) -> List[str]:
    """
    Normalize a value into a flat list of strings.

    Supports:
    - list[str]
    - list[dict] where useful text fields exist
    - single string
    - None
    """
    if value is None:
        return []

    if isinstance(value, str):
        cleaned = _as_clean_string(value)
        return [cleaned] if cleaned else []

    if not isinstance(value, list):
        cleaned = _as_clean_string(value)
        return [cleaned] if cleaned else []

    output: List[str] = []
    for item in value:
        if isinstance(item, str):
            cleaned = _as_clean_string(item)
            if cleaned:
                output.append(cleaned)
            continue

        if isinstance(item, dict):
            for key in (
                "text",
                "summary",
                "statement",
                "fact",
                "claim",
                "note",
                "description",
                "guidance",
                "question",
                "title",
            ):
                if key in item:
                    cleaned = _as_clean_string(item.get(key))
                    if cleaned:
                        output.append(cleaned)
                        break
            continue

        cleaned = _as_clean_string(item)
        if cleaned:
            output.append(cleaned)

    return _dedupe_preserve_order(output)


def _extract_source_ids(source_references: Any, evidence_items: Any) -> List[str]:
    """
    Collect source IDs from researcher artifacts.

    Supports common shapes such as:
    - source_references: [{"source_id": "src_1"}, ...]
    - source_references: [{"id": "src_1"}, ...]
    - source_references: ["src_1", "src_2"]
    - evidence_items: [{"source_id": "..."}], [{"source_ids": [...]}], etc.
    """
    collected: List[str] = []

    def add_source_id(value: Any) -> None:
        cleaned = _as_clean_string(value)
        if cleaned:
            collected.append(cleaned)

    if isinstance(source_references, list):
        for item in source_references:
            if isinstance(item, str):
                add_source_id(item)
            elif isinstance(item, dict):
                add_source_id(item.get("source_id"))
                add_source_id(item.get("id"))

    if isinstance(evidence_items, list):
        for item in evidence_items:
            if not isinstance(item, dict):
                continue
            add_source_id(item.get("source_id"))
            if isinstance(item.get("source_ids"), list):
                for source_id in item["source_ids"]:
                    add_source_id(source_id)

    return _dedupe_preserve_order(collected)


def _normalize_coverage_signal(coverage_report: Any) -> CoverageSignal:
    """
    Normalize uneven research coverage formats into a stable enum.

    Heuristics:
    - sufficient / strong / complete -> SUFFICIENT
    - partial / mixed / limited -> PARTIAL
    - weak / poor / insufficient / missing -> WEAK
    - fallback default -> PARTIAL
    """
    candidate_values: List[str] = []

    if isinstance(coverage_report, str):
        cleaned = _as_clean_string(coverage_report)
        if cleaned:
            candidate_values.append(cleaned.lower())

    elif isinstance(coverage_report, dict):
        for key in ("status", "coverage_status", "strength", "assessment", "summary"):
            value = coverage_report.get(key)
            cleaned = _as_clean_string(value)
            if cleaned:
                candidate_values.append(cleaned.lower())

    joined = " ".join(candidate_values)

    if any(token in joined for token in ("sufficient", "strong", "complete", "good", "adequate")):
        return CoverageSignal.SUFFICIENT

    if any(token in joined for token in ("weak", "poor", "insufficient", "missing", "thin")):
        return CoverageSignal.WEAK

    if any(token in joined for token in ("partial", "mixed", "limited", "uneven", "incomplete")):
        return CoverageSignal.PARTIAL

    return CoverageSignal.PARTIAL


def _extract_planner_context(planner_section: Dict[str, Any]) -> Optional[str]:
    """
    Build a short planner-derived context string.

    Keep this small. It is only supporting context, not a second prompt.
    """
    parts: List[str] = []

    for key in ("chapter_title", "chapter_goal", "section_position", "summary", "notes"):
        value = planner_section.get(key)
        cleaned = _as_clean_string(value)
        if cleaned:
            parts.append(f"{key}: {cleaned}")

    if not parts:
        return None

    return _clip_text(" | ".join(parts), MAX_PLANNER_CONTEXT_CHARS)


def _extract_evidence_statements(evidence_items: Any) -> List[str]:
    """
    Convert researcher evidence items into compact textual evidence statements.

    This intentionally avoids carrying full raw evidence structures forward.
    """
    if not isinstance(evidence_items, list):
        return []

    output: List[str] = []

    for item in evidence_items:
        if isinstance(item, str):
            cleaned = _as_clean_string(item)
            if cleaned:
                output.append(_clip_text(cleaned, MAX_EVIDENCE_ITEM_CHARS))
            continue

        if not isinstance(item, dict):
            cleaned = _as_clean_string(item)
            if cleaned:
                output.append(_clip_text(cleaned, MAX_EVIDENCE_ITEM_CHARS))
            continue

        parts: List[str] = []

        for key in ("claim", "statement", "fact", "summary", "description", "note"):
            value = item.get(key)
            cleaned = _as_clean_string(value)
            if cleaned:
                parts.append(cleaned)
                break

        for key in ("relevance", "reason", "importance"):
            value = item.get(key)
            cleaned = _as_clean_string(value)
            if cleaned:
                parts.append(f"{key}: {cleaned}")
                break

        combined = " | ".join(parts)
        cleaned_combined = _as_clean_string(combined)
        if cleaned_combined:
            output.append(_clip_text(cleaned_combined, MAX_EVIDENCE_ITEM_CHARS))

    return _dedupe_preserve_order(output)[:MAX_EVIDENCE_ITEMS]


def build_section_synthesis_input(
    planner_section: Dict[str, Any],
    research_section: Dict[str, Any],
) -> SectionSynthesisInput:
    """
    Build the compact SectionSynthesisInput from upstream planner/research artifacts.

    This function is intentionally deterministic and cheap:
    - no network
    - no LLM
    - no source fetching
    - no raw document rereading
    """
    section_id = _as_clean_string(
        research_section.get("section_id") or planner_section.get("section_id")
    )
    if not section_id:
        raise ValueError("Missing section_id in planner/research section inputs.")

    section_title = _as_clean_string(
        research_section.get("section_title") or planner_section.get("section_title")
    )
    if not section_title:
        raise ValueError(f"Missing section_title for section_id={section_id!r}.")

    section_objective = _as_clean_string(
        research_section.get("section_objective") or planner_section.get("section_objective")
    )
    if not section_objective:
        raise ValueError(f"Missing section_objective for section_id={section_id!r}.")

    key_concepts = _extract_list_of_strings(
        research_section.get("key_concepts") or planner_section.get("key_concepts")
    )[:MAX_KEY_CONCEPTS]

    writing_guidance = _extract_list_of_strings(research_section.get("writing_guidance"))[
        :MAX_WRITING_GUIDANCE_ITEMS
    ]

    open_questions = _extract_list_of_strings(research_section.get("open_questions"))[
        :MAX_OPEN_QUESTIONS
    ]

    evidence_items = _extract_evidence_statements(research_section.get("evidence_items"))

    coverage_signal = _normalize_coverage_signal(research_section.get("coverage_report"))

    available_source_ids = _extract_source_ids(
        source_references=research_section.get("source_references"),
        evidence_items=research_section.get("evidence_items"),
    )

    planner_context = _extract_planner_context(planner_section)

    return SectionSynthesisInput(
        section_id=section_id,
        section_title=section_title,
        section_objective=section_objective,
        planner_context=planner_context,
        key_concepts=key_concepts,
        evidence_items=evidence_items,
        writing_guidance=writing_guidance,
        open_questions=open_questions,
        coverage_signal=coverage_signal,
        available_source_ids=available_source_ids,
    )