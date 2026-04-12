from __future__ import annotations

from researcher.constants import MAX_DISCOVERED_SOURCES_PER_SECTION
from researcher.registry.source_registry import SourceRegistry
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

            try:
                discovered = self.tavily_client.search(
                    query_text=query.query_text,
                    query_id=query.query_id,
                    max_results=remaining_capacity,
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

    def _build_registry_from_state(self, state: ResearcherState) -> SourceRegistry:
        """
        Rebuild an in-memory registry object from current state entries.
        """
        registry = SourceRegistry()
        for entry in state.source_registry:
            registry._entries[entry.source_id] = entry
        return registry
