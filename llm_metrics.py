from __future__ import annotations

import json
import math
import os
import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Any


class TokenBudgetExceeded(RuntimeError):
    """Raised before an LLM call when the configured run budget is exhausted."""


_LOCK = threading.Lock()
_CONFIGURED = False
_METRICS_PATH: Path | None = None
_TOKEN_BUDGET: int | None = None
_CHARS_PER_TOKEN = 4
_SUMMARY: dict[str, Any] = {}


def configure_llm_metrics(
    *,
    path: str | Path | None = None,
    token_budget: int | None = None,
    reset: bool = True,
) -> None:
    """
    Configure process-local LLM instrumentation.

    When no path is configured, metrics are still kept in memory and can be
    retrieved through get_llm_metrics_summary().
    """
    global _CONFIGURED, _METRICS_PATH, _TOKEN_BUDGET, _CHARS_PER_TOKEN, _SUMMARY

    with _LOCK:
        _CONFIGURED = True
        _METRICS_PATH = _resolve_metrics_path(path)
        _TOKEN_BUDGET = token_budget if _token_budget_enabled() else None
        _CHARS_PER_TOKEN = max(
            _read_int_env("WRITERLM_CHARS_PER_TOKEN") or 4,
            1,
        )

        if reset or not _SUMMARY:
            _SUMMARY = _empty_summary()

        if _METRICS_PATH is not None:
            _METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
            if reset and _METRICS_PATH.exists():
                _METRICS_PATH.unlink()


def reserve_llm_call_budget(
    *,
    layer: str,
    operation: str,
    model: str,
    messages: list[dict[str, Any]],
    attempt: int = 1,
    response_model: str | None = None,
    completion_token_limit: int | None = None,
) -> int:
    """
    Estimate prompt tokens and fail before the API call if it would exceed budget.
    """
    _ensure_configured()
    prompt_estimate = estimate_messages_tokens(messages)
    completion_reserve = completion_token_limit or _completion_reserve_tokens(layer)

    with _LOCK:
        budget = _TOKEN_BUDGET
        reserved_tokens = prompt_estimate + completion_reserve
        if budget is None:
            return prompt_estimate

        projected_total = (
            int(_SUMMARY["accounted_total_tokens"])
            + int(_SUMMARY["reserved_total_tokens"])
            + prompt_estimate
            + completion_reserve
        )
        if projected_total <= budget:
            _SUMMARY["reserved_total_tokens"] += reserved_tokens
            _SUMMARY["max_reserved_total_tokens"] = max(
                int(_SUMMARY["max_reserved_total_tokens"]),
                int(_SUMMARY["reserved_total_tokens"]),
            )
            return prompt_estimate

        _SUMMARY["blocked_call_count"] += 1
        _SUMMARY["budget_exceeded"] = True
        _SUMMARY["last_budget_error"] = {
            "layer": layer,
            "operation": operation,
            "model": model,
            "attempt": attempt,
            "response_model": response_model,
            "token_budget": budget,
            "accounted_total_tokens": _SUMMARY["accounted_total_tokens"],
            "reserved_total_tokens": _SUMMARY["reserved_total_tokens"],
            "estimated_prompt_tokens": prompt_estimate,
            "completion_reserve_tokens": completion_reserve,
            "projected_total_tokens": projected_total,
        }
        _write_event_locked(
            {
                "event": "llm_budget_blocked",
                "timestamp": _now(),
                **_SUMMARY["last_budget_error"],
            }
        )

    raise TokenBudgetExceeded(
        "LLM token budget would be exceeded "
        f"(budget={budget}, projected={projected_total}, "
        f"layer={layer}, operation={operation}, model={model})."
    )


def _token_budget_enabled() -> bool:
    value = os.getenv("WRITERLM_ENABLE_TOKEN_BUDGET", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def record_llm_call(
    *,
    layer: str,
    operation: str,
    model: str,
    messages: list[dict[str, Any]],
    response: Any | None,
    completion_text: str | None,
    elapsed_seconds: float,
    success: bool,
    attempt: int = 1,
    response_model: str | None = None,
    error: str | None = None,
    prompt_estimate_tokens: int | None = None,
    completion_token_limit: int | None = None,
) -> None:
    _ensure_configured()

    prompt_estimate = prompt_estimate_tokens or estimate_messages_tokens(messages)
    completion_estimate = estimate_text_tokens(completion_text or "")
    usage = _extract_usage(response)
    reported_total = usage.get("total_tokens")
    accounted_total = reported_total or prompt_estimate + completion_estimate

    event = {
        "event": "llm_call",
        "timestamp": _now(),
        "layer": layer,
        "operation": operation,
        "response_model": response_model,
        "model": model,
        "attempt": attempt,
        "success": success,
        "elapsed_seconds": round(elapsed_seconds, 4),
        "prompt_chars": _messages_char_count(messages),
        "completion_chars": len(completion_text or ""),
        "estimated_prompt_tokens": prompt_estimate,
        "estimated_completion_tokens": completion_estimate,
        "reported_prompt_tokens": usage.get("prompt_tokens"),
        "reported_completion_tokens": usage.get("completion_tokens"),
        "reported_total_tokens": reported_total,
        "accounted_total_tokens": accounted_total,
        "error": error,
    }

    with _LOCK:
        _release_reserved_tokens_locked(
            prompt_estimate
            + (completion_token_limit or _completion_reserve_tokens(layer))
        )
        _SUMMARY["call_count"] += 1
        if not success:
            _SUMMARY["failed_call_count"] += 1
        if attempt > 1:
            _SUMMARY["retry_call_count"] += 1
        _SUMMARY["elapsed_seconds"] += elapsed_seconds
        _SUMMARY["estimated_prompt_tokens"] += prompt_estimate
        _SUMMARY["estimated_completion_tokens"] += completion_estimate
        _SUMMARY["estimated_total_tokens"] += prompt_estimate + completion_estimate
        _SUMMARY["accounted_total_tokens"] += accounted_total

        if usage.get("prompt_tokens") is not None:
            _SUMMARY["reported_prompt_tokens"] += usage["prompt_tokens"]
        if usage.get("completion_tokens") is not None:
            _SUMMARY["reported_completion_tokens"] += usage["completion_tokens"]
        if reported_total is not None:
            _SUMMARY["reported_total_tokens"] += reported_total

        layer_summary = _SUMMARY["by_layer"].setdefault(layer, _empty_layer_summary())
        _add_event_to_bucket(layer_summary, event)

        operation_key = f"{layer}.{operation}"
        operation_summary = _SUMMARY["by_operation"].setdefault(
            operation_key,
            _empty_layer_summary(),
        )
        _add_event_to_bucket(operation_summary, event)

        _write_event_locked(event)


def record_llm_validation_error(
    *,
    layer: str,
    operation: str,
    model: str,
    attempt: int,
    response_model: str | None,
    error: str,
) -> None:
    _ensure_configured()
    event = {
        "event": "llm_validation_error",
        "timestamp": _now(),
        "layer": layer,
        "operation": operation,
        "model": model,
        "attempt": attempt,
        "response_model": response_model,
        "error": error,
    }
    with _LOCK:
        _SUMMARY["validation_error_count"] += 1
        _write_event_locked(event)


def get_completion_token_limit(layer: str) -> int | None:
    layer_key = layer.upper()
    return _read_int_env(
        f"{layer_key}_MAX_COMPLETION_TOKENS",
        f"{layer_key}_MAX_TOKENS",
        "WRITERLM_MAX_COMPLETION_TOKENS",
        "LLM_MAX_COMPLETION_TOKENS",
    )


def completion_limit_kwargs(layer: str) -> dict[str, int]:
    limit = get_completion_token_limit(layer)
    return {"max_tokens": limit} if limit is not None else {}


def get_llm_metrics_summary() -> dict[str, Any]:
    _ensure_configured()
    with _LOCK:
        summary = deepcopy(_SUMMARY)
        summary["elapsed_seconds"] = round(summary["elapsed_seconds"], 4)
        summary["token_budget"] = _TOKEN_BUDGET
        summary["metrics_path"] = str(_METRICS_PATH) if _METRICS_PATH else None
        for bucket in summary["by_layer"].values():
            bucket["elapsed_seconds"] = round(bucket["elapsed_seconds"], 4)
        for bucket in summary["by_operation"].values():
            bucket["elapsed_seconds"] = round(bucket["elapsed_seconds"], 4)
        return summary


def estimate_messages_tokens(messages: list[dict[str, Any]]) -> int:
    return estimate_text_tokens("".join(_message_content_to_text(message) for message in messages))


def estimate_text_tokens(text: str) -> int:
    if not text:
        return 0
    return int(math.ceil(len(text) / _CHARS_PER_TOKEN))


def _ensure_configured() -> None:
    if _CONFIGURED:
        return
    configure_llm_metrics(reset=False)


def _resolve_metrics_path(path: str | Path | None) -> Path | None:
    if path is not None:
        return Path(path)
    env_path = os.getenv("WRITERLM_METRICS_PATH") or os.getenv("LLM_METRICS_PATH")
    return Path(env_path) if env_path else None


def _read_int_env(*names: str) -> int | None:
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
    return None


def _completion_reserve_tokens(layer: str) -> int:
    layer_key = layer.upper()
    return (
        _read_int_env(
            f"{layer_key}_COMPLETION_RESERVE_TOKENS",
            "WRITERLM_COMPLETION_RESERVE_TOKENS",
            "LLM_COMPLETION_RESERVE_TOKENS",
        )
        or get_completion_token_limit(layer)
        or 1024
    )


def _extract_usage(response: Any | None) -> dict[str, int | None]:
    usage = getattr(response, "usage", None) if response is not None else None
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if usage is None:
        return {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
        }

    prompt_tokens = _usage_value(usage, "prompt_tokens", "input_tokens")
    completion_tokens = _usage_value(usage, "completion_tokens", "output_tokens")
    total_tokens = _usage_value(usage, "total_tokens")
    if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def _usage_value(usage: Any, *names: str) -> int | None:
    for name in names:
        if isinstance(usage, dict):
            value = usage.get(name)
        else:
            value = getattr(usage, name, None)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _messages_char_count(messages: list[dict[str, Any]]) -> int:
    return sum(len(_message_content_to_text(message)) for message in messages)


def _message_content_to_text(message: dict[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False, default=str)


def _empty_summary() -> dict[str, Any]:
    return {
        "call_count": 0,
        "failed_call_count": 0,
        "blocked_call_count": 0,
        "retry_call_count": 0,
        "validation_error_count": 0,
        "elapsed_seconds": 0.0,
        "estimated_prompt_tokens": 0,
        "estimated_completion_tokens": 0,
        "estimated_total_tokens": 0,
        "reported_prompt_tokens": 0,
        "reported_completion_tokens": 0,
        "reported_total_tokens": 0,
        "accounted_total_tokens": 0,
        "reserved_total_tokens": 0,
        "max_reserved_total_tokens": 0,
        "budget_exceeded": False,
        "last_budget_error": None,
        "by_layer": {},
        "by_operation": {},
    }


def _empty_layer_summary() -> dict[str, Any]:
    return {
        "call_count": 0,
        "failed_call_count": 0,
        "retry_call_count": 0,
        "elapsed_seconds": 0.0,
        "estimated_prompt_tokens": 0,
        "estimated_completion_tokens": 0,
        "estimated_total_tokens": 0,
        "reported_prompt_tokens": 0,
        "reported_completion_tokens": 0,
        "reported_total_tokens": 0,
        "accounted_total_tokens": 0,
    }


def _add_event_to_bucket(bucket: dict[str, Any], event: dict[str, Any]) -> None:
    bucket["call_count"] += 1
    if not event["success"]:
        bucket["failed_call_count"] += 1
    if event["attempt"] > 1:
        bucket["retry_call_count"] += 1
    bucket["elapsed_seconds"] += float(event["elapsed_seconds"])
    bucket["estimated_prompt_tokens"] += int(event["estimated_prompt_tokens"] or 0)
    bucket["estimated_completion_tokens"] += int(event["estimated_completion_tokens"] or 0)
    bucket["estimated_total_tokens"] += (
        int(event["estimated_prompt_tokens"] or 0)
        + int(event["estimated_completion_tokens"] or 0)
    )
    bucket["accounted_total_tokens"] += int(event["accounted_total_tokens"] or 0)

    if event["reported_prompt_tokens"] is not None:
        bucket["reported_prompt_tokens"] += int(event["reported_prompt_tokens"])
    if event["reported_completion_tokens"] is not None:
        bucket["reported_completion_tokens"] += int(event["reported_completion_tokens"])
    if event["reported_total_tokens"] is not None:
        bucket["reported_total_tokens"] += int(event["reported_total_tokens"])


def _write_event_locked(event: dict[str, Any]) -> None:
    if _METRICS_PATH is None:
        return
    with _METRICS_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False, default=str))
        file.write("\n")


def _release_reserved_tokens_locked(reserved_tokens: int) -> None:
    if reserved_tokens <= 0:
        return
    _SUMMARY["reserved_total_tokens"] = max(
        0,
        int(_SUMMARY["reserved_total_tokens"]) - reserved_tokens,
    )


def _now() -> float:
    return round(time.time(), 3)
