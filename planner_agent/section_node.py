import re
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
from planner_agent.outline_schemas import ChapterOutlineItem
from planner_agent.schemas import PlanningContext, UserBookRequest
from planner_agent.section_prompt import (
    SECTION_PLANNER_SYSTEM_PROMPT,
    build_section_planner_prompt,
)
from planner_agent.section_schemas import ChapterSectionPlan
from planner_agent.utils import load_json_safe


class SectionPlannerNode:
    def __init__(self) -> None:
        self.client = get_client()
        self.model_name = get_model_name()

    def _generate_raw(
        self,
        request: UserBookRequest,
        context: PlanningContext,
        chapter: ChapterOutlineItem,
    ) -> str:
        messages = build_chat_messages(
            model=self.model_name,
            system_prompt=SECTION_PLANNER_SYSTEM_PROMPT,
            user_prompt=build_section_planner_prompt(
                request=request,
                context=context,
                chapter=chapter,
            ),
        )
        completion_limit = get_completion_token_limit("planner")
        prompt_estimate = reserve_llm_call_budget(
            layer="planner",
            operation="section_plan",
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
                operation="section_plan",
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
                operation="section_plan",
                model=self.model_name,
                messages=messages,
                response=response,
                completion_text=content,
                elapsed_seconds=time.perf_counter() - start_time,
                success=False,
                error="No content returned from the section planner model.",
                prompt_estimate_tokens=prompt_estimate,
                completion_token_limit=completion_limit,
            )
            raise ValueError("No content returned from the section planner model.")

        record_llm_call(
            layer="planner",
            operation="section_plan",
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
            operation="section_plan_text_fallback",
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
                operation="section_plan_text_fallback",
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
                operation="section_plan_text_fallback",
                model=self.model_name,
                messages=messages,
                response=response,
                completion_text=content,
                elapsed_seconds=time.perf_counter() - start_time,
                success=False,
                error="No content returned from the section planner model.",
                prompt_estimate_tokens=prompt_estimate,
                completion_token_limit=completion_limit,
            )
            raise ValueError("No content returned from the section planner model.")

        record_llm_call(
            layer="planner",
            operation="section_plan_text_fallback",
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

    def _clean_text(self, value: object) -> str:
        if value is None:
            return ""
        return " ".join(str(value).split()).strip()

    def _coerce_string_list(self, value: object) -> list[str]:
        if value is None:
            return []

        if isinstance(value, list):
            items = value
        elif isinstance(value, tuple):
            items = list(value)
        elif isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if "\n" in stripped:
                items = [part.strip("-* \t") for part in stripped.splitlines()]
            else:
                items = [part.strip() for part in stripped.split("|")]
        else:
            items = [value]

        normalized: list[str] = []
        for item in items:
            if isinstance(item, dict):
                item = (
                    item.get("question")
                    or item.get("text")
                    or item.get("value")
                    or item.get("content")
                )
            cleaned = self._clean_text(item)
            if cleaned:
                normalized.append(cleaned)
        return normalized

    def _coerce_int(self, value: object, *, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _extract_estimated_words(self, raw_section: object) -> int | None:
        if isinstance(raw_section, dict):
            for candidate_key in (
                "estimated_words",
                "estimatedWords",
                "word_count",
                "wordCount",
                "words",
            ):
                value = raw_section.get(candidate_key)
                try:
                    return int(value)
                except (TypeError, ValueError):
                    pass

            fragments: list[str] = []
            for key, value in raw_section.items():
                fragments.append(str(key))
                fragments.append(str(value))
            joined = " ".join(fragments)
            match = re.search(
                r"estimated[_ ]?words[^0-9]{0,20}(\d{2,4})",
                joined,
                re.IGNORECASE,
            )
            if match:
                return int(match.group(1))

        if isinstance(raw_section, str):
            match = re.search(r"(\d{2,4})", raw_section)
            if match:
                return int(match.group(1))

        return None

    def _default_estimated_words(
        self,
        request: UserBookRequest,
        *,
        section_count: int,
    ) -> int:
        max_allowed = min(request.max_section_words or 900, 2000)
        baseline = min(max_allowed, 450)

        if section_count >= 5:
            baseline = min(max_allowed, 350)
        elif section_count <= 3:
            baseline = min(max_allowed, 550)

        return max(150, baseline)

    def _normalize_content_requirements(self, raw_section: object) -> dict[str, object]:
        raw_dict = raw_section if isinstance(raw_section, dict) else {}
        cr = raw_dict.get("content_requirements")
        if not isinstance(cr, dict):
            return {
                "must_include_code": False,
                "must_include_example": True,
                "must_include_diagram": False,
                "suggested_diagram_type": None,
            }

        must_code = bool(cr.get("must_include_code", False))
        must_example = bool(cr.get("must_include_example", True))
        must_diagram = bool(cr.get("must_include_diagram", False))
        suggested_diagram = cr.get("suggested_diagram_type")
        if isinstance(suggested_diagram, str):
            suggested_diagram = suggested_diagram.strip() or None
        else:
            suggested_diagram = None

        # Enforce: at least one must be true
        if not must_code and not must_example and not must_diagram:
            must_example = True

        return {
            "must_include_code": must_code,
            "must_include_example": must_example,
            "must_include_diagram": must_diagram,
            "suggested_diagram_type": suggested_diagram,
        }

    def _normalize_section(
        self,
        raw_section: object,
        *,
        request: UserBookRequest,
        chapter: ChapterOutlineItem,
        fallback_words: int,
        index: int,
    ) -> dict[str, object]:
        raw_dict = raw_section if isinstance(raw_section, dict) else {}

        title = self._clean_text(
            raw_dict.get("title")
            or raw_dict.get("section_title")
            or raw_dict.get("name")
            or raw_dict.get("heading")
            or raw_section
        )
        if not title:
            title = f"{chapter.title}: Section {index + 1}"

        goal = self._clean_text(
            raw_dict.get("goal")
            or raw_dict.get("objective")
            or raw_dict.get("purpose")
            or raw_dict.get("summary")
        )
        if not goal:
            goal = (
                f"Help the reader understand {title.lower()} "
                f"in the context of {chapter.title.lower()}."
            )

        key_questions = self._coerce_string_list(
            raw_dict.get("key_questions")
            or raw_dict.get("questions")
            or raw_dict.get("guiding_questions")
            or raw_dict.get("question_list")
        )
        if not key_questions:
            key_questions = [f"What should the reader learn from {title}?"]

        estimated_words = self._extract_estimated_words(raw_section)
        if estimated_words is None:
            estimated_words = fallback_words

        estimated_words = min(
            max(int(estimated_words), 150),
            min(request.max_section_words or 2000, 2000),
        )

        content_requirements = self._normalize_content_requirements(raw_section)

        builds_on_raw = raw_dict.get("builds_on")
        builds_on = self._clean_text(builds_on_raw) if builds_on_raw else None

        return {
            "title": title,
            "goal": goal,
            "key_questions": key_questions,
            "estimated_words": estimated_words,
            "content_requirements": content_requirements,
            "builds_on": builds_on,
        }

    def _normalize_section_plan(
        self,
        data: object,
        *,
        request: UserBookRequest,
        chapter: ChapterOutlineItem,
    ) -> dict[str, object]:
        if not isinstance(data, dict):
            raise ValueError("Section planner output did not decode to a JSON object.")

        raw_sections = data.get("sections") or data.get("items") or []
        if isinstance(raw_sections, dict):
            raw_sections = list(raw_sections.values())
        if not isinstance(raw_sections, list):
            raw_sections = [raw_sections]

        fallback_words = self._default_estimated_words(
            request,
            section_count=max(len(raw_sections), 1),
        )

        normalized_sections = [
            self._normalize_section(
                raw_section,
                request=request,
                chapter=chapter,
                fallback_words=fallback_words,
                index=index,
            )
            for index, raw_section in enumerate(raw_sections)
        ]

        if request.is_focused_beginner_guide:
            _, max_sections = request.preferred_sections_per_chapter_range
            normalized_sections = normalized_sections[:max_sections]

        project_milestone = self._clean_text(
            data.get("project_milestone")
        ) or getattr(chapter, "project_milestone", None)

        return {
            "chapter_number": self._coerce_int(
                data.get("chapter_number"),
                default=chapter.chapter_number,
            ),
            "chapter_title": self._clean_text(
                data.get("chapter_title") or data.get("title")
            )
            or chapter.title,
            "chapter_goal": self._clean_text(
                data.get("chapter_goal") or data.get("goal")
            )
            or chapter.chapter_goal,
            "project_milestone": project_milestone,
            "sections": normalized_sections,
        }

    def run(
        self,
        request: UserBookRequest,
        context: PlanningContext,
        chapter: ChapterOutlineItem,
    ) -> ChapterSectionPlan:
        raw_output = self._generate_raw(
            request=request,
            context=context,
            chapter=chapter,
        )

        try:
            data = load_json_safe(raw_output)
            normalized_data = self._normalize_section_plan(
                data,
                request=request,
                chapter=chapter,
            )
            section_plan = ChapterSectionPlan.model_validate(normalized_data)
            return section_plan
        except (ValueError, ValidationError) as e:
            raise ValueError(f"Failed to create section plan: {str(e)}") from e
