import os
import re
from pathlib import Path
from typing import Any
import requests
from dotenv import load_dotenv
from tavily import TavilyClient
from tavily.errors import BadRequestError

from planner_agent.schemas import UserBookRequest


load_dotenv(Path(os.path.dirname(__file__)) / "../.env")


class PlannerSearchTools:
    MAX_TAVILY_QUERY_LENGTH = 380

    def __init__(self, enable_jina_fetch: bool = False) -> None:
        tavli_api_key = os.getenv("TAVILY_API_KEY")
        self.tavily_client = TavilyClient(api_key=tavli_api_key) if tavli_api_key else None
        self.enable_jina_fetch = enable_jina_fetch

    def _normalize_query_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def _limit_query_length(self, query: str, max_length: int | None = None) -> str:
        limit = max_length or self.MAX_TAVILY_QUERY_LENGTH
        normalized = self._normalize_query_text(query)
        if len(normalized) <= limit:
            return normalized

        truncated = normalized[: limit - 3].rstrip(" ,;:-")
        return f"{truncated}..."

    def search_web(
        self, query: str, max_results: int = 5, topic: str = "general"
    ) -> dict[str, Any]:
        """
        Run a Tavily search for planner-stage discovery.

        topic:
        - "general" for normal topics
        - "news" only when recency really matters
        """
        safe_query = self._limit_query_length(query)
        if self.tavily_client is None:
            return {"answer": "", "results": [], "error": "TAVILY_API_KEY not configured"}

        try:
            reponse = self.tavily_client.search(
                query=safe_query,
                max_results=max_results,
                topic=topic,
                search_depth="basic",
                include_answer=True,
                include_raw_content=False,
            )
        except BadRequestError as exc:
            # Tavily enforces a hard 400-character limit. Retry once with a shorter query
            # so planner discovery still works even when the user request becomes verbose.
            if "Query is too long" not in str(exc):
                raise

            fallback_query = self._limit_query_length(safe_query, max_length=240)
            reponse = self.tavily_client.search(
                query=fallback_query,
                max_results=max_results,
                topic=topic,
                search_depth="basic",
                include_answer=True,
                include_raw_content=False,
            )

        return reponse

    def fetch_with_jina(self, url: str, timeout: int = 5) -> str:
        """
        Fetches content from a URL using Jina's web reader API.
        """
        jina_url = f"https://r.jina.ai/http://{url.removeprefix('http://').removeprefix('https://')}"
        reponse = requests.get(jina_url, timeout=timeout)
        reponse.raise_for_status()
        return reponse.text

    def fetch_many_with_jina(
        self,
        urls: list[str],
        timeout: int = 20,
        limit: int = 5,
    ) -> list[dict[str, str]]:
        """
        Fetches content from multiple URLs using Jina's web reader API.
        """
        if not self.enable_jina_fetch:
            return []

        results: list[dict[str, str]] = []
        for url in urls[:limit]:
            try:
                content = self.fetch_with_jina(url, timeout)
                results.append({"url": url, "content": content})
            except Exception as e:
                results.append(
                    {"url": url, "content": f"Error fetching content: {str(e)}"}
                )
                print(f"Failed to fetch {url} with Jina: {str(e)}")
        return results

    def get_top_urls(self, search_result: dict[str, Any]) -> list[str]:
        """
        Extracts top URLs from Tavily search result.
        """
        urls: list[str] = []
        for item in search_result.get("results", []):
            url = item.get("url")
            if url:
                urls.append(url)
        return urls

    def get_seccessful_pages(
        self, fetched_pages: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        return [
            page
            for page in fetched_pages
            if page.get("status") == "success" and page.get("content")
        ]

    def _build_queries(self, request: UserBookRequest) -> dict[str, str]:
        topic_base = request.topic
        if request.source_context and request.source_context.has_uploaded_sources:
            source_terms = " ".join(request.source_context.source_topics[:6])
            likely_domain = request.source_context.likely_domain
            topic_base = f"{request.topic} {likely_domain} {source_terms}".strip()

        topic = self._limit_query_length(topic_base, max_length=160)
        audience = self._limit_query_length(request.audience, max_length=100)
        goals = self._limit_query_length(
            "; ".join(request.normalized_goals[:3]) or "None specified",
            max_length=120,
        )

        if request.effective_book_type in {"textbook", "course_companion", "practice_workbook", "exam_prep"}:
            return {
                "topic_structure": (
                    f"main concepts, curriculum structure, and learning progression for {topic}"
                ),
                "worked_examples": (
                    f"worked examples, exercises, problem styles, and common misconceptions for {topic}"
                ),
                "audience_needs": (
                    f"common learner questions, struggles, and roadmap for {topic} for {audience}"
                ),
                "teaching_approach": (
                    f"teaching sequence for {topic} with goals: {goals}"
                ),
            }

        if request.is_focused_beginner_guide:
            return {
                "audience_needs": (
                    f"common beginner questions, struggles, misconceptions, and FAQ for "
                    f"{topic} for {audience}"
                ),
                "minimal_architecture": (
                    f"simple end-to-end architecture, core components, and mental model for "
                    f"{topic}"
                ),
                "implementation_patterns": (
                    f"practical tutorial, starter project, walkthrough, or implementation guide for {topic} with goals: {goals}"
                ),
                "debugging_pitfalls": (
                    f"common beginner mistakes, pitfalls, and debugging tips for {topic}"
                ),
            }

        return {
            "audience_needs": (
                f"common questions, struggles, FAQ, and learning roadmap for {topic}"
            ),
            "applied_examples": (
                f"practical examples, applications, workflows, and teaching examples for {topic}"
            ),
            "topic_structure": (
                f"main concepts, learning progression, and structure for {topic}"
            ),
            "common_pitfalls": (
                f"common mistakes, trade-offs, and practical pitfalls for {topic}"
            ),
        }

    def run_planner_discovery(self, request: UserBookRequest | str) -> dict[str, Any]:
        if isinstance(request, UserBookRequest):
            queries = self._build_queries(request)
        else:
            topic = self._limit_query_length(str(request), max_length=180)
            queries = {
                "audience_needs": (
                    f"common questions, struggles, FAQ, and learning roadmap for {topic}"
                ),
                "implementation_patterns": (
                    f"practical implementation patterns, workflows, and tutorials for {topic}"
                ),
                "topic_structure": f"main concepts and structure for {topic}",
                "common_pitfalls": f"common mistakes and pitfalls for {topic}",
            }

        bundle: dict[str, Any] = {}

        if isinstance(request, UserBookRequest) and request.source_context and request.source_context.has_uploaded_sources:
            source_context = request.source_context.model_dump(mode="json")
            bundle["uploaded_documents"] = {
                "query": "uploaded source document planning context",
                "search_result": {
                    "answer": request.source_context.summary,
                    "results": [],
                },
                "urls": [],
                "fetched_pages": [],
                "successful_pages": [
                    {
                        "url": f"uploaded://{index}",
                        "content": "\n".join(
                            [
                                source.get("text_preview", ""),
                                "Topics: " + ", ".join(source.get("likely_topics", [])),
                                "Questions: " + " | ".join(source.get("sample_questions", [])),
                            ]
                        ),
                    }
                    for index, source in enumerate(source_context.get("uploaded_sources", []), start=1)
                ],
                "source_context": source_context,
            }

        if isinstance(request, UserBookRequest) and request.source_context and request.source_context.has_uploaded_sources and not request.force_web_research:
            return bundle

        for key, query in queries.items():
            search_result = self.search_web(query, topic="general", max_results=5)
            urls = self.get_top_urls(search_result)
            fetched_pages = self.fetch_many_with_jina(urls, timeout=20, limit=5)
            successful_pages = self.get_seccessful_pages(fetched_pages)
            bundle[key] = {
                "query": query,
                "search_result": search_result,
                "urls": urls,
                "fetched_pages": fetched_pages,
                "successful_pages": successful_pages,
            }

        return bundle
