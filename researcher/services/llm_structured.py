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
from researcher.schemas import EvidenceType, QueryKind, ReflexionAction

T = TypeVar("T", bound=BaseModel)


class StructuredLLMError(Exception):
    """Raised when a structured LLM call fails."""


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
        """
        Augment the given system prompt with strict JSON instructions.
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
        attempt: int = 1,
    ) -> str:
        messages = [
            {
                "role": "system",
                "content": self._build_system_prompt(system_prompt, response_model),
            },
            {"role": "user", "content": user_prompt.strip()},
        ]
        completion_limit = get_completion_token_limit("researcher")
        prompt_estimate = reserve_llm_call_budget(
            layer="researcher",
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
                    **completion_limit_kwargs("researcher"),
                )
            )
        except Exception as exc:
            record_llm_call(
                layer="researcher",
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
                layer="researcher",
                operation="structured_generation",
                model=self.model,
                messages=messages,
                response=response,
                completion_text=content,
                elapsed_seconds=time.perf_counter() - start_time,
                success=False,
                attempt=attempt,
                response_model=response_model.__name__,
                error="No content returned from the model.",
                prompt_estimate_tokens=prompt_estimate,
                completion_token_limit=completion_limit,
            )
            raise StructuredLLMError("No content returned from the model.")

        record_llm_call(
            layer="researcher",
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
        single_list_field = self._single_list_field_name(response_model)
        if single_list_field is not None and isinstance(parsed_json, list):
            parsed_json = {single_list_field: parsed_json}

        if not isinstance(parsed_json, dict):
            return parsed_json

        if response_model.__name__ == "BuildResearchTaskOutput":
            return self._coerce_build_research_task_output(parsed_json)

        if response_model.__name__ == "PlanQueriesOutput":
            return self._coerce_query_output(parsed_json, field_name="queries")

        if response_model.__name__ == "ReflectOnResearchOutput":
            return self._coerce_reflect_on_research_output(parsed_json)

        if response_model.__name__ == "ExtractEvidenceOutput":
            return self._coerce_extract_evidence_output(parsed_json)

        return parsed_json

    def _single_list_field_name(self, response_model: Type[T]) -> str | None:
        if len(response_model.model_fields) != 1:
            return None

        field_name, field_info = next(iter(response_model.model_fields.items()))
        origin = get_origin(field_info.annotation)
        if origin in (list, tuple, set):
            return field_name
        return None

    def _coerce_build_research_task_output(
        self, parsed_json: dict[str, Any]
    ) -> dict[str, Any]:
        merged = self._merge_nested_payload(
            parsed_json,
            nested_keys=("research_task", "task", "research_brief", "output", "result"),
        )

        objective = self._clean_text(
            merged.get("objective")
            or merged.get("research_objective")
            or merged.get("task_objective")
            or merged.get("goal")
            or merged.get("section_goal")
            or merged.get("purpose")
        )
        if not objective:
            section_title = self._clean_text(
                merged.get("section_title") or merged.get("title")
            )
            if section_title:
                objective = f"Research the section '{section_title}' with accurate, practical coverage."
            else:
                objective = "Research this section with accurate, practical coverage."

        return {
            "objective": objective,
            "scope_inclusions": self._coerce_string_list(
                merged.get("scope_inclusions")
                or merged.get("inclusions")
                or merged.get("included_topics")
                or merged.get("topics_to_cover")
                or merged.get("key_points")
            ),
            "scope_exclusions": self._coerce_string_list(
                merged.get("scope_exclusions")
                or merged.get("exclusions")
                or merged.get("excluded_topics")
                or merged.get("out_of_scope")
                or merged.get("avoid_topics")
            ),
            "research_questions": self._coerce_string_list(
                merged.get("research_questions")
                or merged.get("questions")
                or merged.get("key_questions")
            ),
            "assumptions": self._coerce_string_list(
                merged.get("assumptions")
                or merged.get("notes")
                or merged.get("constraints")
            ),
        }

    def _coerce_query_output(
        self,
        parsed_json: dict[str, Any],
        *,
        field_name: str,
    ) -> dict[str, Any]:
        merged = self._merge_nested_payload(
            parsed_json,
            nested_keys=("query_plan", "search_plan", "output", "result"),
        )
        raw_queries = (
            merged.get(field_name)
            or merged.get("query_plan")
            or merged.get("search_queries")
            or merged.get("planned_queries")
            or merged.get("items")
        )

        if raw_queries is None and isinstance(parsed_json.get("queries"), dict):
            raw_queries = parsed_json.get("queries")

        if raw_queries is None:
            raw_queries = []

        if isinstance(raw_queries, dict):
            raw_queries = raw_queries.get("items") or list(raw_queries.values())

        normalized_queries = [
            self._coerce_query_item(item, index=index)
            for index, item in enumerate(self._coerce_iterable(raw_queries), start=1)
        ]

        return {field_name: normalized_queries}

    def _coerce_reflect_on_research_output(
        self,
        parsed_json: dict[str, Any],
    ) -> dict[str, Any]:
        merged = self._merge_nested_payload(
            parsed_json,
            nested_keys=("reflection", "reflexion", "decision", "output", "result"),
        )
        followup_payload = self._coerce_query_output(
            merged,
            field_name="followup_queries",
        )
        reasoning = self._clean_text(
            merged.get("reasoning")
            or merged.get("reason")
            or merged.get("decision_reason")
            or merged.get("notes")
        )

        return {
            "covered_topics": self._coerce_string_list(
                merged.get("covered_topics")
                or merged.get("covered")
                or merged.get("strengths")
            ),
            "missing_topics": self._coerce_string_list(
                merged.get("missing_topics")
                or merged.get("gaps")
                or merged.get("uncovered_topics")
            ),
            "weak_evidence_types": self._coerce_enum_list(
                merged.get("weak_evidence_types")
                or merged.get("missing_evidence_types")
                or merged.get("weak_types"),
                enum_cls=EvidenceType,
            ),
            "notes": self._coerce_string_list(merged.get("notes")),
            "action": self._normalize_reflexion_action(
                merged.get("action")
                or merged.get("decision")
                or merged.get("status")
                or merged.get("next_step"),
                has_followups=bool(followup_payload["followup_queries"]),
            ),
            "reasoning": reasoning
            or "Coverage decision inferred from the structured reflexion output.",
            "followup_queries": followup_payload["followup_queries"],
        }

    def _coerce_extract_evidence_output(
        self,
        parsed_json: dict[str, Any],
    ) -> dict[str, Any]:
        merged = self._merge_nested_payload(
            parsed_json,
            nested_keys=("evidence", "extraction", "output", "result"),
        )
        raw_items = (
            merged.get("evidence_items")
            or merged.get("evidence")
            or merged.get("items")
            or merged.get("extractions")
            or []
        )

        normalized_items = [
            self._coerce_evidence_item(item)
            for item in self._coerce_iterable(raw_items)
        ]

        return {"evidence_items": normalized_items}

    def _coerce_query_item(self, item: Any, *, index: int) -> dict[str, Any]:
        if isinstance(item, str):
            query_text = self._clean_text(item)
            return {
                "kind": self._infer_query_kind(None, query_text=query_text),
                "query_text": query_text,
                "rationale": "Covers a relevant research angle for the section.",
                "priority": self._coerce_priority(index, default=index),
            }

        if isinstance(item, dict):
            query_text = self._clean_text(
                item.get("query_text")
                or item.get("query")
                or item.get("search_query")
                or item.get("text")
                or item.get("title")
            )
            rationale = self._clean_text(
                item.get("rationale")
                or item.get("reason")
                or item.get("why")
                or item.get("purpose")
                or item.get("goal")
            )
            if not rationale and query_text:
                rationale = f"Investigates {query_text}."

            return {
                "kind": self._infer_query_kind(
                    item.get("kind")
                    or item.get("query_kind")
                    or item.get("type")
                    or item.get("category")
                    or item.get("purpose"),
                    query_text=query_text,
                ),
                "query_text": query_text,
                "rationale": rationale,
                "priority": self._coerce_priority(
                    item.get("priority") or item.get("rank") or item.get("importance"),
                    default=index,
                ),
            }

        fallback_text = self._clean_text(item)
        return {
            "kind": self._infer_query_kind(None, query_text=fallback_text),
            "query_text": fallback_text,
            "rationale": "Covers a relevant research angle for the section.",
            "priority": self._coerce_priority(index, default=index),
        }

    def _coerce_evidence_item(self, item: Any) -> dict[str, Any]:
        if isinstance(item, str):
            return {
                "evidence_type": EvidenceType.FACT.value,
                "content": self._clean_text(item),
                "summary": None,
                "relevance_note": None,
                "confidence": 0.7,
                "tags": [],
            }

        if isinstance(item, dict):
            return {
                "evidence_type": self._normalize_evidence_type(
                    item.get("evidence_type")
                    or item.get("type")
                    or item.get("category")
                ),
                "content": self._clean_text(
                    item.get("content")
                    or item.get("evidence")
                    or item.get("quote")
                    or item.get("text")
                ),
                "summary": self._clean_text(
                    item.get("summary") or item.get("explanation")
                )
                or None,
                "relevance_note": self._clean_text(
                    item.get("relevance_note")
                    or item.get("relevance")
                    or item.get("why_relevant")
                )
                or None,
                "confidence": self._coerce_confidence(
                    item.get("confidence") or item.get("score")
                ),
                "tags": self._coerce_string_list(
                    item.get("tags") or item.get("labels")
                ),
            }

        return {
            "evidence_type": EvidenceType.FACT.value,
            "content": self._clean_text(item),
            "summary": None,
            "relevance_note": None,
            "confidence": 0.7,
            "tags": [],
        }

    def _infer_query_kind(self, raw_kind: Any, *, query_text: str) -> str:
        normalized_kind = (
            self._clean_text(raw_kind).casefold().replace("-", "_").replace(" ", "_")
        )
        valid_kinds = {kind.value for kind in QueryKind}
        if normalized_kind in valid_kinds:
            return normalized_kind

        lowered_query = query_text.casefold()

        if any(token in lowered_query for token in ("what is", "define", "definition")):
            return QueryKind.DEFINITION.value
        if "example" in lowered_query:
            return QueryKind.EXAMPLE.value
        if "case study" in lowered_query:
            return QueryKind.CASE_STUDY.value
        if any(
            token in lowered_query
            for token in ("statistic", "metric", "benchmark", "percentage", "latency")
        ):
            return QueryKind.STATISTIC.value
        if any(token in lowered_query for token in ("histor", "evolution", "timeline")):
            return QueryKind.HISTORICAL.value
        if any(
            token in lowered_query
            for token in ("recent", "latest", "new", "2024", "2025", "2026")
        ):
            return QueryKind.RECENT_DEVELOPMENT.value
        if any(
            token in lowered_query
            for token in ("trade-off", "tradeoff", "vs", "versus", "limitation", "risk")
        ):
            return QueryKind.COUNTERPOINT.value
        if any(
            token in lowered_query
            for token in (
                "architecture",
                "implementation",
                "algorithm",
                "api",
                "workflow",
                "design",
                "integration",
                "deploy",
                "setup",
            )
        ):
            return QueryKind.TECHNICAL.value

        return QueryKind.CORE_CONCEPT.value

    def _normalize_evidence_type(self, raw_value: Any) -> str:
        normalized = (
            self._clean_text(raw_value).casefold().replace("-", "_").replace(" ", "_")
        )
        valid_values = {item.value for item in EvidenceType}
        if normalized in valid_values:
            return normalized

        if "defin" in normalized:
            return EvidenceType.DEFINITION.value
        if "example" in normalized:
            return EvidenceType.EXAMPLE.value
        if "case" in normalized:
            return EvidenceType.CASE_STUDY.value
        if any(token in normalized for token in ("stat", "metric", "benchmark")):
            return EvidenceType.STATISTIC.value
        if any(token in normalized for token in ("quot", "citation")):
            return EvidenceType.QUOTE.value
        if any(token in normalized for token in ("refer", "source")):
            return EvidenceType.REFERENCE.value
        if any(token in normalized for token in ("warn", "risk", "caution")):
            return EvidenceType.WARNING.value
        if any(token in normalized for token in ("insight", "lesson")):
            return EvidenceType.INSIGHT.value
        if any(token in normalized for token in ("claim", "argument")):
            return EvidenceType.CLAIM.value

        return EvidenceType.FACT.value

    def _normalize_reflexion_action(
        self, raw_value: Any, *, has_followups: bool
    ) -> str:
        normalized = (
            self._clean_text(raw_value).casefold().replace("-", "_").replace(" ", "_")
        )
        if normalized == ReflexionAction.FINALIZE.value:
            return ReflexionAction.FINALIZE.value
        if normalized in {
            ReflexionAction.FOLLOW_UP.value,
            "continue",
            "continue_research",
            "more_research",
            "needs_followup",
        }:
            return ReflexionAction.FOLLOW_UP.value
        return (
            ReflexionAction.FOLLOW_UP.value
            if has_followups
            else ReflexionAction.FINALIZE.value
        )

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

    def _coerce_string_list(self, value: Any) -> list[str]:
        normalized: list[str] = []
        for item in self._coerce_iterable(value):
            if isinstance(item, dict):
                item = (
                    item.get("text")
                    or item.get("value")
                    or item.get("title")
                    or item.get("query")
                    or item.get("content")
                )
            cleaned = self._clean_text(item)
            if cleaned:
                normalized.append(cleaned)
        return normalized

    def _coerce_enum_list(self, value: Any, *, enum_cls: type[Enum]) -> list[str]:
        normalized_values: list[str] = []
        valid_values = {item.value for item in enum_cls}
        for item in self._coerce_iterable(value):
            cleaned = (
                self._clean_text(item).casefold().replace("-", "_").replace(" ", "_")
            )
            if cleaned in valid_values:
                normalized_values.append(cleaned)
        return normalized_values

    def _coerce_iterable(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, set):
            return list(value)
        return [value]

    def _coerce_priority(self, value: Any, *, default: int) -> int:
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            numeric = default
        return min(max(numeric, 1), 5)

    def _coerce_confidence(self, value: Any) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = 0.7
        return min(max(numeric, 0.0), 1.0)

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""
        return " ".join(str(value).split()).strip()

    def generate_structured(
        self, *, system_prompt: str, user_prompt: str, response_model: Type[T]
    ) -> T:

        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 2):
            try:
                raw_text = self._generate_text(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_model=response_model,
                    attempt=attempt,
                )
                parsed_json = self._parse_json(raw_text)
                normalized_json = self._coerce_response_shape(
                    parsed_json,
                    response_model,
                )
                return response_model.model_validate(normalized_json)
            except (json.JSONDecodeError, ValidationError, StructuredLLMError) as e:
                last_error = e
                record_llm_validation_error(
                    layer="researcher",
                    operation="structured_generation",
                    model=self.model,
                    attempt=attempt,
                    response_model=response_model.__name__,
                    error=str(e),
                )
                if attempt > self.max_retries:
                    break

        raise StructuredLLMError(
            f"Structured generation failed for model={self.model}. "
            f"Last error: {str(last_error)}"
        ) from last_error
