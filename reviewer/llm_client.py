from __future__ import annotations

import os
import time

from llm_metrics import (
    completion_limit_kwargs,
    get_completion_token_limit,
    record_llm_call,
    reserve_llm_call_budget,
)
from llm_retry import call_with_rate_limit_retries
from openai import OpenAI

from llm_provider import resolve_openai_compatible_config
from .node import LLMClientProtocol


class OpenAICompatibleReviewerClient(LLMClientProtocol):
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None = None,
        temperature: float = 0.2,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        completion_limit = get_completion_token_limit("reviewer")
        prompt_estimate = reserve_llm_call_budget(
            layer="reviewer",
            operation="review_section",
            model=self.model,
            messages=messages,
            completion_token_limit=completion_limit,
        )

        start_time = time.perf_counter()
        try:
            response = call_with_rate_limit_retries(
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    response_format={"type": "json_object"},
                    messages=messages,
                    **completion_limit_kwargs("reviewer"),
                )
            )
        except Exception as exc:
            record_llm_call(
                layer="reviewer",
                operation="review_section",
                model=self.model,
                messages=messages,
                response=None,
                completion_text=None,
                elapsed_seconds=time.perf_counter() - start_time,
                success=False,
                error=str(exc),
                prompt_estimate_tokens=prompt_estimate,
                completion_token_limit=completion_limit,
            )
            raise

        content = response.choices[0].message.content
        if not content:
            record_llm_call(
                layer="reviewer",
                operation="review_section",
                model=self.model,
                messages=messages,
                response=response,
                completion_text=content,
                elapsed_seconds=time.perf_counter() - start_time,
                success=False,
                error="Reviewer model returned empty content.",
                prompt_estimate_tokens=prompt_estimate,
                completion_token_limit=completion_limit,
            )
            raise ValueError("Reviewer model returned empty content.")

        record_llm_call(
            layer="reviewer",
            operation="review_section",
            model=self.model,
            messages=messages,
            response=response,
            completion_text=content,
            elapsed_seconds=time.perf_counter() - start_time,
            success=True,
            prompt_estimate_tokens=prompt_estimate,
            completion_token_limit=completion_limit,
        )
        return content


def build_reviewer_llm_client() -> OpenAICompatibleReviewerClient:
    config = resolve_openai_compatible_config(
        layer="reviewer",
        default_models={
            "groq": os.environ.get("REVIEWER_MODEL", "openai/gpt-oss-120b"),
            "google": os.environ.get("REVIEWER_GOOGLE_MODEL", os.environ.get("GOOGLE_MODEL", "gemini-2.5-flash")),
        },
        legacy_env_names=("REVIEWER_MODEL",),
        legacy_env_names_by_provider={
            "groq": ("GROQ_MODEL_NAME", "GROQ_MODEL"),
            "google": ("REVIEWER_GOOGLE_MODEL", "GOOGLE_MODEL_NAME", "GOOGLE_MODEL", "GEMINI_MODEL"),
        },
    )
    temperature = float(os.environ.get("REVIEWER_TEMPERATURE", "0.2"))

    return OpenAICompatibleReviewerClient(
        model=config.model,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=temperature,
    )
