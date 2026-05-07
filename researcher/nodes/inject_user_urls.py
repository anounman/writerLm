from __future__ import annotations

import logging

from researcher.nodes.fetch_sources import FetchSourcesNode
from researcher.schemas import DiscoveredSource, SourceDocument, SourceType
from researcher.state import ResearcherState

logger = logging.getLogger(__name__)


class InjectUserUrlsNode:
    """
    Fetch user-provided URLs and prepend them to state.fetched_documents.
    """

    def __init__(self, user_urls: list[str], fetch_sources_node: FetchSourcesNode) -> None:
        self.user_urls = list(user_urls)
        self.fetch_sources_node = fetch_sources_node

    def run(self, state: ResearcherState) -> ResearcherState:
        if not self.user_urls:
            return state

        logger.info(
            "InjectUserUrlsNode: fetching %d user-provided URL(s) for section '%s'.",
            len(self.user_urls),
            state.section_id,
        )

        discovered_sources = [
            DiscoveredSource(
                query_id="user_injected",
                url=url,
                title="User Injected URL",
                snippet="",
                source_type=SourceType.WEBPAGE,
                discovery_score=1.0,
                rank=1,
            )
            for url in self.user_urls
        ]

        fetch_results = self.fetch_sources_node.fetch_sources(discovered_sources)
        new_docs: list[SourceDocument] = []
        
        registry = self._build_registry(state)

        for source, document, error in fetch_results:
            if error is not None:
                state.add_warning(
                    f"Failed to fetch user-injected URL '{source.url}': {error}"
                )
                continue
            
            assert document is not None
            new_docs.append(document)
            registry.register_source_document(
                source_document=document,
                discovery_query_id=source.query_id,
            )

        if new_docs:
            existing_ids = {d.source_id for d in state.fetched_documents}
            filtered_new = [d for d in new_docs if d.source_id not in existing_ids]

            state.fetched_documents = filtered_new + list(state.fetched_documents)
            state.source_registry = registry.list_entries()

            state.add_warning(
                f"Injected {len(filtered_new)} user-provided URL(s) as research sources."
            )

        return state

    def _build_registry(self, state: ResearcherState):
        from researcher.registry.source_registry import SourceRegistry
        registry = SourceRegistry()
        for entry in state.source_registry:
            registry._entries[entry.source_id] = entry
        return registry
