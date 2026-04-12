from __future__ import annotations

from typing import Iterable, Optional

from researcher.schemas import (
    DiscoveredSource,
    ExtractionMethod,
    SourceDocument,
    SourceRegistryEntry,
    SourceType,
)
from researcher.utils.hashing import stable_text_hash


class SourceRegistryError(Exception):
    """Raised when source registry operations fail."""


class SourceRegistry:
    """
    In-memory source registry for one research run.

    Responsibilities:
    - register discovered/fetched sources
    - preserve provenance metadata
    - maintain one canonical entry per source_id
    - attach extracted evidence ids back to sources
    """

    def __init__(self) -> None:
        self._entries: dict[str, SourceRegistryEntry] = {}

    def register_discovered_source(
        self, source: DiscoveredSource
    ) -> SourceRegistryEntry:
        """
        Create or update a registry entry from a discovered source.
        """
        existing = self._entries.get(source.source_id)
        if existing is not None:
            return existing

        entry = SourceRegistryEntry(
            source_id=source.source_id,
            url=source.url,
            title=source.title,
            source_type=source.source_type,
            discovery_query_id=source.query_id,
            extraction_method=ExtractionMethod.UNKNOWN,
            canonical_url=str(source.url),
            domain=self._extract_domain(str(source.url)),
        )
        self._entries[source.source_id] = entry
        return entry

    def register_source_document(
        self,
        *,
        source_document: SourceDocument,
        discovery_query_id: Optional[str] = None,
        relevance_score: Optional[float] = None,
        quality_score: Optional[float] = None,
    ) -> SourceRegistryEntry:
        """
        Create or update a registry entry from an extracted source document.
        """
        content_hash = stable_text_hash(source_document.text)
        canonical_url = str(source_document.url)
        domain = self._extract_domain(canonical_url)

        existing = self._entries.get(source_document.source_id)
        if existing is None:
            entry = SourceRegistryEntry(
                source_id=source_document.source_id,
                url=source_document.url,
                title=source_document.title,
                source_type=source_document.source_type,
                discovery_query_id=discovery_query_id,
                extraction_method=source_document.extraction_method,
                content_hash=content_hash,
                canonical_url=canonical_url,
                domain=domain,
                relevance_score=relevance_score,
                quality_score=quality_score,
            )
            self._entries[source_document.source_id] = entry
            return entry

        updated = existing.model_copy(
            update={
                "url": source_document.url,
                "title": source_document.title or existing.title,
                "source_type": self._prefer_source_type(
                    existing.source_type,
                    source_document.source_type,
                ),
                "discovery_query_id": existing.discovery_query_id or discovery_query_id,
                "extraction_method": source_document.extraction_method,
                "content_hash": content_hash,
                "canonical_url": canonical_url,
                "domain": domain or existing.domain,
                "relevance_score": (
                    relevance_score
                    if relevance_score is not None
                    else existing.relevance_score
                ),
                "quality_score": (
                    quality_score
                    if quality_score is not None
                    else existing.quality_score
                ),
            }
        )
        self._entries[source_document.source_id] = updated
        return updated

    def attach_evidence(
        self,
        *,
        source_id: str,
        evidence_id: str,
    ) -> SourceRegistryEntry:
        """
        Attach an evidence id to a registered source.
        """
        entry = self._entries.get(source_id)
        if entry is None:
            raise SourceRegistryError(
                f"Cannot attach evidence to unknown source_id='{source_id}'."
            )

        if evidence_id in entry.evidence_ids:
            return entry

        updated = entry.model_copy(
            update={"evidence_ids": [*entry.evidence_ids, evidence_id]}
        )
        self._entries[source_id] = updated
        return updated

    def add_reliability_note(self, *, source_id: str, note: str) -> SourceRegistryEntry:
        """
        Attach a reliability/quality note to a source.
        """
        entry = self._entries.get(source_id)
        if entry is None:
            raise SourceRegistryError(
                f"Cannot add reliability note to unknown source_id='{source_id}'."
            )

        updated = entry.model_copy(
            update={"reliability_notes": [*entry.reliability_notes, note]}
        )
        self._entries[source_id] = updated
        return updated

    def get(self, source_id: str) -> Optional[SourceRegistryEntry]:
        """
        Return one registry entry by source id.
        """
        return self._entries.get(source_id)

    def has(self, source_id: str) -> bool:
        """
        Whether a source id is already registered.
        """
        return source_id in self._entries

    def list_entries(self) -> list[SourceRegistryEntry]:
        """
        Return all registry entries in insertion order.
        """
        return list(self._entries.values())

    def list_by_source_type(self, source_type: SourceType) -> list[SourceRegistryEntry]:
        """
        Return registry entries filtered by source type.
        """
        return [
            entry
            for entry in self._entries.values()
            if entry.source_type == source_type
        ]

    def bulk_register_discovered(
        self,
        sources: Iterable[DiscoveredSource],
    ) -> list[SourceRegistryEntry]:
        """
        Register many discovered sources.
        """
        return [self.register_discovered_source(source) for source in sources]

    def bulk_attach_evidence(
        self,
        *,
        source_id: str,
        evidence_ids: Iterable[str],
    ) -> SourceRegistryEntry:
        """
        Attach multiple evidence ids to one source.
        """
        entry = self._entries.get(source_id)
        if entry is None:
            raise SourceRegistryError(
                f"Cannot attach evidence to unknown source_id='{source_id}'."
            )

        merged_ids = list(entry.evidence_ids)
        for evidence_id in evidence_ids:
            if evidence_id not in merged_ids:
                merged_ids.append(evidence_id)

        updated = entry.model_copy(update={"evidence_ids": merged_ids})
        self._entries[source_id] = updated
        return updated

    def _extract_domain(self, url: str) -> Optional[str]:
        """
        Best-effort domain extraction from a URL.
        """
        if "://" not in url:
            return None

        domain_part = url.split("://", maxsplit=1)[-1].split("/", maxsplit=1)[0].strip()
        return domain_part or None

    def _prefer_source_type(
        self,
        current: SourceType,
        incoming: SourceType,
    ) -> SourceType:
        """
        Prefer the more specific source type when possible.
        """
        if current == SourceType.UNKNOWN:
            return incoming
        if incoming == SourceType.UNKNOWN:
            return current
        return incoming
