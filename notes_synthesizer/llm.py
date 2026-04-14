from __future__ import annotations

from enum import Enum
import json
import os
from typing import Any, Optional, Type, TypeVar, get_args, get_origin

from openai import OpenAI
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class StructuredLLMError(Exception):
    """Raised when a structured LLM call fails."""


class GroqStructuredLLM:
    """
    Thin structured-output wrapper for Groq/OpenAI-compatible chat completions.

    Notes Synthesizer requirements:
    - keep configuration style aligned with the Researcher layer
    - structured JSON output only
    - minimal coercion
    - no research-specific normalization logic
    """

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
        """
        Augment the given system prompt with strict JSON instructions and
        a schema-shaped example payload.
        """
        schema_hint = json.dumps(
            self._build_response_example(response_model),
            indent=2,
            ensure_ascii=False,
        )
        return (
            f"{system_prompt.strip()}\n\n"
            "You must return valid JSON only.\n"
            "Do not include markdown fences.\n"
            "Do not include explanations before or after the JSON.\n"
            "Do not include trailing commentary.\n"
            "Return one JSON object that matches this structure exactly:\n"
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
            raise StructuredLLMError("No content returned from the model.")

        return content.strip()

    def _parse_json(self, raw_text: str) -> Any:
        """
        Parse model output as JSON, handling common wrapper mistakes.
        """
        cleaned = raw_text.strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```")
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            for open_char, close_char in (("{", "}"), ("[", "]")):
                start = cleaned.find(open_char)
                end = cleaned.rfind(close_char)
                if start == -1 or end == -1 or end <= start:
                    continue
                try:
                    return json.loads(cleaned[start : end + 1])
                except json.JSONDecodeError:
                    continue
            raise exc

    def _build_response_example(self, response_model: Type[T]) -> dict[str, Any]:
        example: dict[str, Any] = {}
        for field_name, field_info in response_model.model_fields.items():
            example[field_name] = self._example_value_for_annotation(
                field_info.annotation
            )
        return example

    def _example_value_for_annotation(self, annotation: Any) -> Any:
        origin = get_origin(annotation)
        args = [arg for arg in get_args(annotation) if arg is not type(None)]

        if origin is not None:
            if str(origin).endswith("Literal"):
                return args[0] if args else "string"
            if origin in (list, tuple, set):
                item_annotation = args[0] if args else str
                return [self._example_value_for_annotation(item_annotation)]
            if origin is dict:
                return {}
            if args:
                return self._example_value_for_annotation(args[0])

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

    def _coerce_response_shape(
        self,
        parsed_json: Any,
        response_model: Type[T],
    ) -> Any:
        """
        Apply light response normalization for common structured-output mistakes.

        Notes Synthesizer intentionally keeps this minimal. We only repair a few
        common wrapper patterns rather than adding heavy task-specific coercion.
        """
        single_list_field = self._single_list_field_name(response_model)
        if single_list_field is not None and isinstance(parsed_json, list):
            parsed_json = {single_list_field: parsed_json}

        if not isinstance(parsed_json, dict):
            return parsed_json

        merged = self._merge_nested_payload(
            parsed_json,
            nested_keys=("output", "result", "data", "response", "note_artifact", "section_note"),
        )

        return merged

    def _single_list_field_name(self, response_model: Type[T]) -> str | None:
        if len(response_model.model_fields) != 1:
            return None

        field_name, field_info = next(iter(response_model.model_fields.items()))
        origin = get_origin(field_info.annotation)
        if origin in (list, tuple, set):
            return field_name
        return None

    def _merge_nested_payload(
        self,
        parsed_json: dict[str, Any],
        *,
        nested_keys: tuple[str, ...],
    ) -> dict[str, Any]:
        merged = dict(parsed_json)
        for key in nested_keys:
            nested_value = parsed_json.get(key)
            if isinstance(nested_value, dict):
                merged = {**merged, **nested_value}
        return merged

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
    ) -> T:
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 2):
            try:
                raw_text = self._generate_text(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_model=response_model,
                )
                parsed_json = self._parse_json(raw_text)
                normalized_json = self._coerce_response_shape(
                    parsed_json,
                    response_model,
                )
                return response_model.model_validate(normalized_json)
            except (json.JSONDecodeError, ValidationError, StructuredLLMError) as e:
                last_error = e
                if attempt > self.max_retries:
                    break

        raise StructuredLLMError(
            f"Structured generation failed for model={self.model}. "
            f"Last error: {str(last_error)}"
        ) from last_error