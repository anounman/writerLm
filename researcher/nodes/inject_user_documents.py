
from __future__ import annotations

import logging

from researcher.registry.source_registry import SourceRegistry
from researcher.schemas import SourceDocument
from researcher.state import ResearcherState

logger = logging.getLogger(__name__)


class InjectUserDocumentsNode:
    """
    Prepend user-uploaded PDF documents to ``state.fetched_documents``.

    Parameters
    ----------
    user_documents:
        Pre-extracted ``SourceDocument`` objects produced by
        ``UserDocumentStore.load_all()``.  When the list is empty this node
        is a no-op, preserving full backwards compatibility.
    """

    def __init__(self, user_documents: list[SourceDocument]) -> None:
        self.user_documents = list(user_documents)

    def run(self, state: ResearcherState) -> ResearcherState:
        """
        Inject user documents into the researcher state.

        - If there are no user documents, returns state unchanged.
        - Adds a ``SourceRegistryEntry`` for every injected document so
          provenance is correctly tracked through to the final packet.
        - User documents are prepended (highest priority) so they appear
          before web sources in the fetched_documents list.
        """
        if not self.user_documents:
            return state

        logger.info(
            "InjectUserDocumentsNode: injecting %d user-uploaded PDF(s) into section '%s'.",
            len(self.user_documents),
            state.section_id,
        )

        # Build / update the source registry
        registry = self._build_registry(state)
        for doc in self.user_documents:
            registry.register_source_document(
                source_document=doc,
                discovery_query_id=None,  # Not discovered via search
            )

        # Prepend user docs to whatever is already in state (normally empty
        # at this point, but safe to merge if something is already there).
        existing_ids = {d.source_id for d in state.fetched_documents}
        new_docs = [d for d in self.user_documents if d.source_id not in existing_ids]

        state.fetched_documents = new_docs + list(state.fetched_documents)
        state.source_registry = registry.list_entries()

        state.add_warning(
            f"Injected {len(new_docs)} user-uploaded PDF(s) as research sources."
        )
        return state

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_registry(state: ResearcherState) -> SourceRegistry:
        registry = SourceRegistry()
        for entry in state.source_registry:
            registry._entries[entry.source_id] = entry
        return registry
