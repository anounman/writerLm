from __future__ import annotations

import re


def slugify(value: str | None) -> str:
    if not value:
        return "untitled"

    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value)
    slug = "-".join(part for part in cleaned.split("-") if part)
    return slug or "untitled"


def build_chapter_id(*, chapter_number: int, chapter_title: str) -> str:
    return f"chapter-{chapter_number}-{slugify(chapter_title)}"


def build_section_id(*, chapter_number: int, section_title: str) -> str:
    return f"chapter-{chapter_number}-section-{slugify(section_title)}"


def build_latex_label(*, chapter_number: int, section_number: int, section_id: str) -> str:
    safe_suffix = re.sub(r"[^a-zA-Z0-9:-]+", "-", section_id).strip("-")
    return f"sec:{chapter_number}.{section_number}:{safe_suffix}"
