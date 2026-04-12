from __future__ import annotations

import hashlib


def _short_hash(value: str, length: int = 10) -> str:
    """
    Create a short stable hash for readable internal IDs.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def make_research_task_id(section_id: str) -> str:
    """
    Build a stable research task id from a planner section id.
    """
    return f"task_{section_id}"


def make_query_id(section_id: str, query_text: str, index: int) -> str:
    """
    Build a stable query id for one search query.
    """
    digest = _short_hash(f"{section_id}:{query_text}:{index}")
    return f"query_{section_id}_{index}_{digest}"


def make_source_id(query_id: str, url: str, rank: int) -> str:
    """
    Build a stable-ish source id from query context and URL.
    """
    digest = _short_hash(f"{query_id}:{url}:{rank}")
    return f"src_{rank}_{digest}"


def make_evidence_id(source_id: str, evidence_type: str, index: int) -> str:
    """
    Build a stable evidence id for one extracted evidence item.
    """
    digest = _short_hash(f"{source_id}:{evidence_type}:{index}")
    return f"evidence_{index}_{digest}"


def make_packet_id(section_id: str) -> str:
    """
    Build a stable final research packet id from a section id.
    """
    return f"packet_{section_id}"
