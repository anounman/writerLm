from __future__ import annotations

from urllib.parse import urlparse

from researcher.constants import (
    BLOCKED_SOURCE_DOMAINS,
    DEFAULT_TAVILY_RESULTS_PER_QUERY,
    DISCOVERY_OVERFETCH_FACTOR,
    MAX_DISCOVERED_SOURCES_PER_SECTION,
    UNSUPPORTED_SOURCE_EXTENSIONS,
    WEAK_SOURCE_DOMAINS,
)
from researcher.registry.source_registry import SourceRegistry
from researcher.schemas import DiscoveredSource, SourceType
from researcher.services.tavily_client import TavilySearchClient, TavilySearchError
from researcher.state import ResearcherState


class DiscoverSourcesNode:
    """
    Execute the current SearchPlan and populate discovered sources.

    Responsibilities:
    - read structured search queries from state
    - execute discovery via Tavily
    - deduplicate discovered sources across queries
    - register discovered sources in the source registry
    - write discovered sources back into state
    """

    def __init__(
        self,
        tavily_client: TavilySearchClient,
        max_discovered_sources: int = MAX_DISCOVERED_SOURCES_PER_SECTION,
    ) -> None:
        self.tavily_client = tavily_client
        self.max_discovered_sources = max_discovered_sources
        self.blocked_domains = BLOCKED_SOURCE_DOMAINS
        self.weak_domains = WEAK_SOURCE_DOMAINS
        self.unsupported_extensions = UNSUPPORTED_SOURCE_EXTENSIONS

    def run(self, state: ResearcherState) -> ResearcherState:
        """
        Execute source discovery for the current section.
        """
        if state.discovered_sources:
            return state

        if state.search_plan is None:
            state.add_error("Cannot discover sources because search_plan is missing.")
            return state

        registry = self._build_registry_from_state(state)

        all_sources = []
        seen_urls: set[str] = set()

        sorted_queries = sorted(
            state.search_plan.queries,
            key=lambda query: (query.priority, query.query_id),
        )

        for query in sorted_queries:
            if len(all_sources) >= self.max_discovered_sources:
                break

            remaining_capacity = self.max_discovered_sources - len(all_sources)
            if remaining_capacity <= 0:
                break

            requested_results = max(
                remaining_capacity * DISCOVERY_OVERFETCH_FACTOR,
                DEFAULT_TAVILY_RESULTS_PER_QUERY,
            )

            try:
                discovered = self.tavily_client.search(
                    query_text=query.query_text,
                    query_id=query.query_id,
                    max_results=requested_results,
                )
            except TavilySearchError as exc:
                state.add_warning(
                    f"Discovery failed for query '{query.query_id}' "
                    f"({query.query_text}): {exc}"
                )
                continue

            for source in discovered:
                normalized_url = str(source.url).strip().lower()
                if not normalized_url or normalized_url in seen_urls:
                    continue
                if self._should_skip_source(source):
                    continue

                seen_urls.add(normalized_url)
                all_sources.append(source)
                registry.register_discovered_source(source)

                if len(all_sources) >= self.max_discovered_sources:
                    break

        if not all_sources:
            state.add_error(
                f"No sources were discovered for section '{state.section_id}'."
            )
            return state

        state.discovered_sources = all_sources
        state.source_registry = registry.list_entries()
        return state

    def _should_skip_source(self, source: DiscoveredSource) -> bool:
        domain = self._extract_domain(str(source.url))
        if domain is not None:
            if self._is_blocked_domain(domain):
                return True
            if self._is_obvious_weak_domain(domain):
                return True

        if self._has_unsupported_content_type(str(source.url), source.source_type):
            return True

        if self._is_obvious_weak_source(source):
            return True

        return False

    def _extract_domain(self, url: str) -> str | None:
        parsed = urlparse(url)
        host = parsed.netloc.lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host or None

    def _is_blocked_domain(self, domain: str) -> bool:
        return any(
            domain == blocked_domain or domain.endswith(f".{blocked_domain}")
            for blocked_domain in self.blocked_domains
        )

    def _is_obvious_weak_domain(self, domain: str) -> bool:
        return any(
            domain == weak_domain or domain.endswith(f".{weak_domain}")
            for weak_domain in self.weak_domains
        )

    def _has_unsupported_content_type(self, url: str, source_type: SourceType) -> bool:
        if source_type == SourceType.PDF:
            return False

        lowered_url = url.lower()
        return any(lowered_url.endswith(extension) for extension in self.unsupported_extensions)

    def _is_obvious_weak_source(self, source: DiscoveredSource) -> bool:
        title = (source.title or "").strip().lower()
        snippet = (source.snippet or "").strip().lower()
        combined_text = f"{title} {snippet}".strip()

        if not title or title in {"home", "login", "sign in"}:
            return True

        weak_markers = (
            "community answer",
            "download pdf",
            "forum",
            "login required",
            "paywall",
            "sign up",
            "thread",
            "user-generated",
        )
        if any(marker in combined_text for marker in weak_markers):
            return True

        return False

    def _build_registry_from_state(self, state: ResearcherState) -> SourceRegistry:
        """
        Rebuild an in-memory registry object from current state entries.
        """
        registry = SourceRegistry()
        for entry in state.source_registry:
            registry._entries[entry.source_id] = entry
        return registry
