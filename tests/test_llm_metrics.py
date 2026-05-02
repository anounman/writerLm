from __future__ import annotations

from dataclasses import dataclass

import pytest

from llm_metrics import (
    TokenBudgetExceeded,
    configure_llm_metrics,
    get_llm_metrics_summary,
    record_llm_call,
    reserve_llm_call_budget,
)


@dataclass
class _Usage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class _Response:
    usage: _Usage


def test_records_reported_usage(tmp_path) -> None:
    metrics_path = tmp_path / "llm_metrics.jsonl"
    messages = [
        {"role": "system", "content": "Return JSON."},
        {"role": "user", "content": "Write a tiny response."},
    ]

    configure_llm_metrics(path=metrics_path, token_budget=10_000, reset=True)
    prompt_estimate = reserve_llm_call_budget(
        layer="writer",
        operation="test_call",
        model="test-model",
        messages=messages,
    )
    record_llm_call(
        layer="writer",
        operation="test_call",
        model="test-model",
        messages=messages,
        response=_Response(usage=_Usage(10, 5, 15)),
        completion_text='{"ok": true}',
        elapsed_seconds=0.25,
        success=True,
        prompt_estimate_tokens=prompt_estimate,
    )

    summary = get_llm_metrics_summary()

    assert summary["call_count"] == 1
    assert summary["reported_prompt_tokens"] == 10
    assert summary["reported_completion_tokens"] == 5
    assert summary["reported_total_tokens"] == 15
    assert summary["accounted_total_tokens"] == 15
    assert summary["by_layer"]["writer"]["call_count"] == 1
    assert metrics_path.exists()
    assert "llm_call" in metrics_path.read_text(encoding="utf-8")


def test_budget_guard_blocks_before_call(tmp_path) -> None:
    configure_llm_metrics(
        path=tmp_path / "llm_metrics.jsonl",
        token_budget=5,
        reset=True,
    )

    with pytest.raises(TokenBudgetExceeded):
        reserve_llm_call_budget(
            layer="researcher",
            operation="oversized_prompt",
            model="test-model",
            messages=[{"role": "user", "content": "x" * 200}],
            completion_token_limit=1,
        )

    summary = get_llm_metrics_summary()

    assert summary["blocked_call_count"] == 1
    assert summary["budget_exceeded"] is True
    assert summary["last_budget_error"]["operation"] == "oversized_prompt"


def test_budget_guard_tracks_in_flight_reservations(tmp_path) -> None:
    messages = [{"role": "user", "content": "x" * 40}]
    configure_llm_metrics(
        path=tmp_path / "llm_metrics.jsonl",
        token_budget=100,
        reset=True,
    )

    prompt_estimate = reserve_llm_call_budget(
        layer="writer",
        operation="parallel_call",
        model="test-model",
        messages=messages,
        completion_token_limit=20,
    )
    reserved_summary = get_llm_metrics_summary()

    assert reserved_summary["reserved_total_tokens"] > 0

    with pytest.raises(TokenBudgetExceeded):
        reserve_llm_call_budget(
            layer="writer",
            operation="parallel_call",
            model="test-model",
            messages=[{"role": "user", "content": "x" * 300}],
            completion_token_limit=20,
        )

    record_llm_call(
        layer="writer",
        operation="parallel_call",
        model="test-model",
        messages=messages,
        response=None,
        completion_text="ok",
        elapsed_seconds=0.01,
        success=True,
        prompt_estimate_tokens=prompt_estimate,
        completion_token_limit=20,
    )
    final_summary = get_llm_metrics_summary()

    assert final_summary["reserved_total_tokens"] == 0
    assert final_summary["blocked_call_count"] == 1
