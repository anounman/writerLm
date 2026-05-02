from __future__ import annotations

import json
import os
from typing import Callable

from .deterministic import build_deterministic_reviewer_output
from .prompt import SYSTEM_PROMPT, build_reviewer_prompt
from .schemas import ReviewerSectionOutput
from .state import ReviewerSectionTask
from .validator import (
    normalize_reviewer_output,
    normalize_reviewer_task,
    validate_reviewer_output,
    validate_reviewer_task,
)


class LLMClientProtocol:
    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError


def review_section(
    task: ReviewerSectionTask,
    llm_client: LLMClientProtocol,
) -> ReviewerSectionTask:
    task = normalize_reviewer_task(task)
    validate_reviewer_task(task)

    if _deterministic_reviewer_enabled():
        task.section_output = build_deterministic_reviewer_output(task.section_input)
        task.error_message = None
        return task

    user_prompt = build_reviewer_prompt(task.section_input)
    raw_response = llm_client.generate(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    parsed_output = _parse_reviewer_output(raw_response)
    normalized_output = normalize_reviewer_output(task, parsed_output)
    validate_reviewer_output(task, normalized_output)

    task.section_output = normalized_output
    task.error_message = None
    return task


def review_section_safe(
    task: ReviewerSectionTask,
    llm_client: LLMClientProtocol,
    error_formatter: Callable[[Exception], str] | None = None,
) -> ReviewerSectionTask:
    try:
        return review_section(task=task, llm_client=llm_client)
    except Exception as exc:
        message = error_formatter(exc) if error_formatter else str(exc)
        try:
            task = normalize_reviewer_task(task)
            task.section_output = build_deterministic_reviewer_output(
                task.section_input,
                error_message=message,
            )
            task.error_message = None
        except Exception:
            task.section_output = None
            task.error_message = message
        return task


def _deterministic_reviewer_enabled() -> bool:
    value = os.getenv("WRITERLM_DETERMINISTIC_REVIEWER", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _parse_reviewer_output(raw_response: str) -> ReviewerSectionOutput:
    try:
        data = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Reviewer model returned invalid JSON: {exc}") from exc

    try:
        return ReviewerSectionOutput.model_validate(data)
    except Exception as exc:
        raise ValueError(f"Reviewer output failed schema validation: {exc}") from exc
