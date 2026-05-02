from __future__ import annotations

from enum import Enum
import json
import os
import time
from typing import Any, Optional, Type, TypeVar, get_args, get_origin

from llm_metrics import (
    completion_limit_kwargs,
    get_completion_token_limit,
    record_llm_call,
    record_llm_validation_error,
    reserve_llm_call_budget,
)
from llm_retry import call_with_rate_limit_retries
from openai import OpenAI
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class StructuredLLMError(Exception):
    pass


class GroqStructuredLLM:
    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.2,
        max_retries: int = 2,
        base_url: Optional[str] = None,
    ) -> None:
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url or os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        )
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries

    def _build_system_prompt(
        self,
        system_prompt: str,
        response_model: Type[T],
    ) -> str:
        schema_hint = json.dumps(
            self._build_response_example(response_model),
            indent=2,
            ensure_ascii=False,
        )
        return (
            f"{system_prompt.strip()}\n\n"
            "You must return valid JSON only.\n"
            "Do not include markdown fences.\n"
            "Do not include explanations.\n"
            "Return one JSON object matching this structure:\n"
            f"{schema_hint}\n"
            "Do not rename keys.\n"
        )

    def _generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        attempt: int = 1,
    ) -> str:
        messages = [
            {
                "role": "system",
                "content": self._build_system_prompt(system_prompt, response_model),
            },
            {"role": "user", "content": user_prompt.strip()},
        ]
        completion_limit = get_completion_token_limit("writer")
        prompt_estimate = reserve_llm_call_budget(
            layer="writer",
            operation="structured_generation",
            model=self.model,
            messages=messages,
            attempt=attempt,
            response_model=response_model.__name__,
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
                    **completion_limit_kwargs("writer"),
                )
            )
        except Exception as exc:
            record_llm_call(
                layer="writer",
                operation="structured_generation",
                model=self.model,
                messages=messages,
                response=None,
                completion_text=None,
                elapsed_seconds=time.perf_counter() - start_time,
                success=False,
                attempt=attempt,
                response_model=response_model.__name__,
                error=str(exc),
                prompt_estimate_tokens=prompt_estimate,
                completion_token_limit=completion_limit,
            )
            raise

        content = response.choices[0].message.content
        if not content or not content.strip():
            record_llm_call(
                layer="writer",
                operation="structured_generation",
                model=self.model,
                messages=messages,
                response=response,
                completion_text=content,
                elapsed_seconds=time.perf_counter() - start_time,
                success=False,
                attempt=attempt,
                response_model=response_model.__name__,
                error="Empty response from model.",
                prompt_estimate_tokens=prompt_estimate,
                completion_token_limit=completion_limit,
            )
            raise StructuredLLMError("Empty response from model.")

        record_llm_call(
            layer="writer",
            operation="structured_generation",
            model=self.model,
            messages=messages,
            response=response,
            completion_text=content,
            elapsed_seconds=time.perf_counter() - start_time,
            success=True,
            attempt=attempt,
            response_model=response_model.__name__,
            prompt_estimate_tokens=prompt_estimate,
            completion_token_limit=completion_limit,
        )
        return content.strip()

    def _parse_json(self, raw_text: str) -> Any:
        cleaned = raw_text.strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```")
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise StructuredLLMError(f"Invalid JSON: {str(exc)}") from exc

    def _build_response_example(self, response_model: Type[T]) -> dict[str, Any]:
        example: dict[str, Any] = {}
        for field_name, field_info in response_model.model_fields.items():
            example[field_name] = self._example_value(field_info.annotation)
        return example

    def _example_value(self, annotation: Any) -> Any:
        origin = get_origin(annotation)
        args = [a for a in get_args(annotation) if a is not type(None)]

        if origin in (list, tuple, set):
            return [self._example_value(args[0] if args else str)]
        if origin is dict:
            return {}

        if isinstance(annotation, type):
            if issubclass(annotation, BaseModel):
                return self._build_response_example(annotation)
            if issubclass(annotation, Enum):
                return next(iter(annotation)).value
            if annotation is str:
                return "string"
            if annotation is int:
                return 1
            if annotation is float:
                return 0.5
            if annotation is bool:
                return True

        return "string"

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
    ) -> T:
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                raw = self._generate_text(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_model=response_model,
                    attempt=attempt + 1,
                )
                parsed = self._parse_json(raw)
                return response_model.model_validate(parsed)
            except (ValidationError, StructuredLLMError) as e:
                last_error = e
                record_llm_validation_error(
                    layer="writer",
                    operation="structured_generation",
                    model=self.model,
                    attempt=attempt + 1,
                    response_model=response_model.__name__,
                    error=str(e),
                )

        raise StructuredLLMError(
            f"Failed after retries. Last error: {str(last_error)}"
        ) from last_error
