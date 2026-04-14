from __future__ import annotations

from enum import Enum
import json
import os
from typing import Any, Optional, Type, TypeVar, get_args, get_origin

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
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": self._build_system_prompt(system_prompt, response_model),
                },
                {"role": "user", "content": user_prompt.strip()},
            ],
        )

        content = response.choices[0].message.content
        if not content or not content.strip():
            raise StructuredLLMError("Empty response from model.")

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
                )
                parsed = self._parse_json(raw)
                return response_model.model_validate(parsed)
            except (ValidationError, StructuredLLMError) as e:
                last_error = e

        raise StructuredLLMError(
            f"Failed after retries. Last error: {str(last_error)}"
        ) from last_error