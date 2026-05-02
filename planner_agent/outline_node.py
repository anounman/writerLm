import time

from llm_metrics import (
    completion_limit_kwargs,
    get_completion_token_limit,
    record_llm_call,
    reserve_llm_call_budget,
)
from llm_retry import call_with_rate_limit_retries
from llm_provider import build_chat_messages, json_response_format_kwargs
from pydantic import ValidationError
from planner_agent.config import get_client, get_model_name
from planner_agent.outline_prompt import (
    CHAPTER_OUTLINE_SYSTEM_PROMPT,
    build_chapter_outline_prompt,
)

from planner_agent.outline_schemas import ChapterOutlinePlan
from planner_agent.schemas import PlanningContext, UserBookRequest
from planner_agent.utils import load_json_safe

class ChapterOutlineNode:
    def __init__(self) -> None:
        self.client = get_client()
        self.model_name = get_model_name()

    def _generate_raw(self, request: UserBookRequest, context: PlanningContext) -> str:
        prompt = build_chapter_outline_prompt(request, context)
        messages = build_chat_messages(
            model=self.model_name,
            system_prompt=CHAPTER_OUTLINE_SYSTEM_PROMPT,
            user_prompt=prompt,
        )
        completion_limit = get_completion_token_limit("planner")
        prompt_estimate = reserve_llm_call_budget(
            layer="planner",
            operation="chapter_outline",
            model=self.model_name,
            messages=messages,
            completion_token_limit=completion_limit,
        )
        start_time = time.perf_counter()
        try:
            response = call_with_rate_limit_retries(
                lambda: self.client.chat.completions.create(
                    model=self.model_name,
                    temperature=0.2,
                    messages=messages,
                    **json_response_format_kwargs(self.model_name),
                    **completion_limit_kwargs("planner"),
                )
            )
        except Exception as exc:
            record_llm_call(
                layer="planner",
                operation="chapter_outline",
                model=self.model_name,
                messages=messages,
                response=None,
                completion_text=None,
                elapsed_seconds=time.perf_counter() - start_time,
                success=False,
                error=str(exc),
                prompt_estimate_tokens=prompt_estimate,
                completion_token_limit=completion_limit,
            )
            if self._should_retry_without_provider_json_mode(exc):
                return self._generate_raw_without_provider_json_mode(
                    messages=messages,
                    completion_limit=completion_limit,
                )
            raise

        content = response.choices[0].message.content
        if not content:
            record_llm_call(
                layer="planner",
                operation="chapter_outline",
                model=self.model_name,
                messages=messages,
                response=response,
                completion_text=content,
                elapsed_seconds=time.perf_counter() - start_time,
                success=False,
                error="No content returned from the model.",
                prompt_estimate_tokens=prompt_estimate,
                completion_token_limit=completion_limit,
            )
            raise ValueError("No content returned from the model.")
        record_llm_call(
            layer="planner",
            operation="chapter_outline",
            model=self.model_name,
            messages=messages,
            response=response,
            completion_text=content,
            elapsed_seconds=time.perf_counter() - start_time,
            success=True,
            prompt_estimate_tokens=prompt_estimate,
            completion_token_limit=completion_limit,
        )
        return content

    def _generate_raw_without_provider_json_mode(
        self,
        *,
        messages: list[dict[str, str]],
        completion_limit: int | None,
    ) -> str:
        prompt_estimate = reserve_llm_call_budget(
            layer="planner",
            operation="chapter_outline_text_fallback",
            model=self.model_name,
            messages=messages,
            completion_token_limit=completion_limit,
        )
        start_time = time.perf_counter()
        try:
            response = call_with_rate_limit_retries(
                lambda: self.client.chat.completions.create(
                    model=self.model_name,
                    temperature=0.2,
                    messages=messages,
                    **completion_limit_kwargs("planner"),
                )
            )
        except Exception as exc:
            record_llm_call(
                layer="planner",
                operation="chapter_outline_text_fallback",
                model=self.model_name,
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
                layer="planner",
                operation="chapter_outline_text_fallback",
                model=self.model_name,
                messages=messages,
                response=response,
                completion_text=content,
                elapsed_seconds=time.perf_counter() - start_time,
                success=False,
                error="No content returned from the model.",
                prompt_estimate_tokens=prompt_estimate,
                completion_token_limit=completion_limit,
            )
            raise ValueError("No content returned from the model.")

        record_llm_call(
            layer="planner",
            operation="chapter_outline_text_fallback",
            model=self.model_name,
            messages=messages,
            response=response,
            completion_text=content,
            elapsed_seconds=time.perf_counter() - start_time,
            success=True,
            prompt_estimate_tokens=prompt_estimate,
            completion_token_limit=completion_limit,
        )
        return content

    def _should_retry_without_provider_json_mode(self, exc: Exception) -> bool:
        message = str(exc).lower()
        return (
            "json_validate_failed" in message
            or "failed to validate json" in message
            or "json mode is not enabled" in message
        )

    def run(
        self,
        request: UserBookRequest,
        context: PlanningContext,
    ) -> ChapterOutlinePlan:
        raw_output = self._generate_raw(request, context)
        try:
            data = load_json_safe(raw_output)
            chapter_outline = ChapterOutlinePlan.model_validate(data)
            return chapter_outline
        except (ValueError, ValidationError) as e:
            raise ValueError(f"Failed to create chapter outline: {str(e)}") from e
