from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from planner_agent.schemas import BookPlan


DIAGRAM_RE = re.compile(r"(?im)^DIAGRAM:\s*(.+)$")
HEADING_RE = re.compile(r"(?im)^#{2,4}\s+(.+?)\s*$")
TERM_RE = re.compile(r"\b[A-Z][a-z]+(?:[ -][A-Z][a-z]+){0,3}\b")


class SectionStateEntry(BaseModel):
    section_id: str
    section_title: str
    summary: str = ""
    terminology: list[str] = Field(default_factory=list)
    examples_used: list[str] = Field(default_factory=list)
    diagrams_created: list[str] = Field(default_factory=list)
    citations_used: list[str] = Field(default_factory=list)


class BookState(BaseModel):
    title: str
    thesis: str
    target_audience: str
    expected_depth: str
    pedagogy_style: str
    running_project: str | None = None
    implementation_strategy: str = "single-consistent-strategy"
    terminology: list[str] = Field(default_factory=list)
    style_conventions: list[str] = Field(default_factory=list)
    notation_conventions: list[str] = Field(default_factory=list)
    example_conventions: list[str] = Field(default_factory=list)
    unresolved_assumptions: list[str] = Field(default_factory=list)
    forbidden_contradictions: list[str] = Field(default_factory=list)
    source_map: dict[str, list[str]] = Field(default_factory=dict)
    chapter_dependencies: dict[str, list[str]] = Field(default_factory=dict)
    diagrams_created: list[str] = Field(default_factory=list)
    section_history: list[SectionStateEntry] = Field(default_factory=list)


def build_initial_book_state(
    *,
    book_plan: BookPlan,
    planner_input: dict[str, Any],
    research_bundle_payload: dict[str, Any] | None = None,
) -> BookState:
    pedagogy_style = str(planner_input.get("pedagogy_style") or "auto")
    theory_practice_balance = str(planner_input.get("theory_practice_balance") or "balanced")
    book_type = str(planner_input.get("book_type") or "auto")
    running_project = book_plan.running_project or planner_input.get("running_project_description")

    thesis_parts = [
        str(planner_input.get("topic") or book_plan.title),
        f"for {planner_input.get('audience') or book_plan.audience}",
        f"with {theory_practice_balance.replace('_', ' ')} emphasis",
    ]
    thesis = " ".join(part.strip() for part in thesis_parts if part).strip()

    implementation_strategy = _infer_implementation_strategy(planner_input, book_plan)
    style_conventions = [
        f"Honor the requested book type: {book_type}.",
        f"Honor the requested pedagogy style: {pedagogy_style}.",
        f"Honor the requested depth: {book_plan.depth}.",
        "Do not silently switch notation, tooling, or narrative structure between chapters.",
    ]
    example_conventions = [
        "Reuse earlier examples or extend them when possible instead of restarting from zero.",
        "When the user requested project-based learning, each later chapter should build on the same project state.",
    ]
    notation_conventions = [
        "Keep terminology stable once introduced.",
        "Avoid introducing new aliases for the same concept unless you explicitly explain the mapping.",
    ]
    forbidden_contradictions = [
        "Do not contradict earlier definitions, assumptions, or implementation choices.",
        "Do not downgrade the audience depth from the original request.",
        "Do not abandon the running project or running example unless the outline explicitly closes it.",
    ]

    source_map = _build_source_map(research_bundle_payload)
    chapter_dependencies = _build_chapter_dependencies(book_plan)

    return BookState(
        title=book_plan.title,
        thesis=thesis,
        target_audience=book_plan.audience,
        expected_depth=book_plan.depth,
        pedagogy_style=pedagogy_style,
        running_project=running_project,
        implementation_strategy=implementation_strategy,
        style_conventions=style_conventions,
        notation_conventions=notation_conventions,
        example_conventions=example_conventions,
        unresolved_assumptions=_clean_list(planner_input.get("goals") or []),
        forbidden_contradictions=forbidden_contradictions,
        source_map=source_map,
        chapter_dependencies=chapter_dependencies,
    )


def build_section_context(
    *,
    book_state: BookState,
    section_id: str,
    section_title: str,
    chapter_title: str,
) -> dict[str, Any]:
    previous_sections = book_state.section_history[-3:]
    prior_text = [
        f"{entry.section_title}: {entry.summary}".strip(": ")
        for entry in previous_sections
        if entry.summary
    ]
    context_lines = [
        f"Book thesis: {book_state.thesis}",
        f"Audience: {book_state.target_audience}",
        f"Depth: {book_state.expected_depth}",
        f"Pedagogy style: {book_state.pedagogy_style}",
        f"Implementation/story strategy: {book_state.implementation_strategy}",
    ]
    if book_state.running_project:
        context_lines.append(f"Running project/example: {book_state.running_project}")
    if book_state.terminology:
        context_lines.append("Established terminology: " + ", ".join(book_state.terminology[:12]))
    if previous_sections:
        context_lines.append("Most recent section continuity:")
        context_lines.extend(f"- {line}" for line in prior_text[:3])
    dependencies = book_state.chapter_dependencies.get(section_id) or book_state.chapter_dependencies.get(chapter_title) or []
    if dependencies:
        context_lines.append("This section builds on: " + ", ".join(dependencies[:5]))

    return {
        "book_state_summary": "\n".join(context_lines),
        "continuity_rules": list(book_state.forbidden_contradictions + book_state.style_conventions + book_state.notation_conventions),
        "chapter_dependencies": dependencies,
        "implementation_strategy": book_state.implementation_strategy,
        "pedagogy_style": book_state.pedagogy_style,
    }


def update_book_state_from_reviewed_section(
    *,
    book_state: BookState,
    section_id: str,
    section_title: str,
    reviewed_content: str,
    citations_used: list[str] | None = None,
) -> BookState:
    headings = [match.group(1).strip() for match in HEADING_RE.finditer(reviewed_content)]
    diagrams = [match.group(1).strip() for match in DIAGRAM_RE.finditer(reviewed_content)]
    terminology = _pick_terms(reviewed_content)
    summary = _summarize_section(reviewed_content)

    book_state.terminology = _merge_unique(book_state.terminology, terminology)[:40]
    book_state.diagrams_created = _merge_unique(book_state.diagrams_created, diagrams)
    book_state.section_history.append(
        SectionStateEntry(
            section_id=section_id,
            section_title=section_title,
            summary=summary,
            terminology=terminology,
            examples_used=headings[:5],
            diagrams_created=diagrams,
            citations_used=list(citations_used or []),
        )
    )
    return book_state


def write_book_state(path: Path, book_state: BookState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(book_state.model_dump_json(indent=2), encoding="utf-8")


def load_book_state(path: Path) -> BookState:
    return BookState.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _infer_implementation_strategy(planner_input: dict[str, Any], book_plan: BookPlan) -> str:
    corpus = " ".join(
        [
            str(planner_input.get("topic") or ""),
            str(planner_input.get("running_project_description") or ""),
            book_plan.title,
            book_plan.running_project or "",
        ]
    ).lower()
    if "terraform" in corpus:
        return "Terraform"
    if "cloudformation" in corpus:
        return "CloudFormation"
    if "cdk" in corpus:
        return "AWS CDK"
    if any(keyword in corpus for keyword in ("python", "pandas", "notebook")):
        return "Python"
    if any(keyword in corpus for keyword in ("typescript", "node", "react", "javascript")):
        return "TypeScript/JavaScript"
    if any(keyword in corpus for keyword in ("math", "algebra", "proof", "theorem")):
        return "Textbook-style mathematical exposition"
    return "single-consistent-strategy"


def _build_source_map(research_bundle_payload: dict[str, Any] | None) -> dict[str, list[str]]:
    source_map: dict[str, list[str]] = {}
    if not isinstance(research_bundle_payload, dict):
        return source_map

    for chapter in research_bundle_payload.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        for packet in chapter.get("section_packets") or []:
            if not isinstance(packet, dict):
                continue
            section_id = str(packet.get("section_id") or "")
            refs = packet.get("source_references") or packet.get("sources") or []
            urls = []
            if isinstance(refs, list):
                for item in refs:
                    if isinstance(item, dict) and item.get("url"):
                        urls.append(str(item["url"]))
            if section_id and urls:
                source_map[section_id] = urls[:8]
    return source_map


def _build_chapter_dependencies(book_plan: BookPlan) -> dict[str, list[str]]:
    dependencies: dict[str, list[str]] = {}
    seen_sections: list[str] = []
    for chapter in book_plan.chapters:
        chapter_seen = [section.title for section in chapter.sections]
        for section in chapter.sections:
            deps = []
            if section.builds_on:
                deps.append(section.builds_on)
            deps.extend(seen_sections[-3:])
            dependencies[section.title] = _merge_unique([], deps)
            section_id = f"chapter-{chapter.chapter_number}-section-{_slugify(section.title)}"
            dependencies[section_id] = list(dependencies[section.title])
        seen_sections.extend(chapter_seen)
    return dependencies


def _pick_terms(content: str) -> list[str]:
    return _merge_unique([], [match.group(0).strip() for match in TERM_RE.finditer(content)])[:15]


def _summarize_section(content: str) -> str:
    clean = re.sub(r"```[\s\S]*?```", "", content)
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) <= 240:
        return clean
    return clean[:237].rstrip() + "..."


def _merge_unique(existing: list[str], new_items: list[str]) -> list[str]:
    merged = list(existing)
    seen = {item.casefold() for item in merged}
    for item in new_items:
        cleaned = item.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(cleaned)
    return merged


def _clean_list(values: list[Any]) -> list[str]:
    output = []
    for value in values:
        cleaned = str(value).strip()
        if cleaned:
            output.append(cleaned)
    return output


def _slugify(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value)
    return "-".join(part for part in cleaned.split("-") if part) or "untitled"

