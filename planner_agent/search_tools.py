import os
from pathlib import Path
from typing import Any
import requests
from dotenv import load_dotenv
from tavily import TavilyClient


load_dotenv(Path(os.path.dirname(__file__)) / "../.env")


class PlannerSearchTools:
    def __init__(self, enable_jina_fetch: bool = False) -> None:
        tavli_api_key = os.getenv("TAVILY_API_KEY")
        if not tavli_api_key:
            raise ValueError("TAVILY_API_KEY not found in environment variables.")
        self.tavily_client = TavilyClient(api_key=tavli_api_key)
        self.enable_jina_fetch = enable_jina_fetch

    def search_web(
        self, query: str, max_results: int = 5, topic: str = "general"
    ) -> dict[str, Any]:
        """
        Run a Tavily search for planner-stage discovery.

        topic:
        - "general" for normal topics
        - "news" only when recency really matters
        """

        reponse = self.tavily_client.search(
            query=query,
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

    def run_planner_discovery(self, topic: str) -> dict[str, Any]:
        queries = {
            "audience_needs": f"common questions, struggles, FAQ, beginner roadmap for {topic}",
            "competitor_books": f"best books guides syllabus table of contents for {topic}",
            "topic_subareas": f"main concepts subtopics branches of {topic}",
            "structure_frameworks": f"learning roadmap framework curriculum outline for {topic}",
        }

        bundle: dict[str, Any] = {}

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
