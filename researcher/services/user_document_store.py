"""
researcher/services/user_document_store.py
------------------------------------------
Loads user-uploaded PDF files from a local directory and converts them into
``SourceDocument`` objects that the Researcher layer can consume directly.

Usage::

    store = UserDocumentStore(pdf_dir=Path("inputs/pdfs"))
    docs = store.load_all()   # list[SourceDocument], empty if nothing uploaded

The store is intentionally stateless after construction – call ``load_all()``
once at pipeline startup and pass the result around.
"""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

from researcher.schemas import ExtractionMethod, SourceDocument, SourceType
from researcher.services.pdf_extractor import PDFExtractionError, PDFExtractor

logger = logging.getLogger(__name__)

# Minimum extracted text length to treat a PDF as usable.
_MIN_TEXT_CHARS = 50


class UserDocumentStore:
    """
    Reads all ``*.pdf`` files from *pdf_dir* and returns them as a list of
    ``SourceDocument`` objects ready to be injected into ``ResearcherState``.

    Parameters
    ----------
    pdf_dir:
        Directory to scan. Defaults to ``inputs/pdfs`` relative to the repo
        root (two levels above this file).
    pdf_extractor:
        Optional pre-configured ``PDFExtractor`` instance. A default one is
        created automatically if not supplied.
    """

    def __init__(
        self,
        pdf_dir: Optional[Path] = None,
        pdf_extractor: Optional[PDFExtractor] = None,
    ) -> None:
        if pdf_dir is None:
            # Prefer the per-job directory set by the web backend worker.
            env_dir = os.environ.get("WRITERLM_USER_PDF_DIR", "").strip()
            if env_dir:
                pdf_dir = Path(env_dir)
            else:
                # Default: <repo_root>/inputs/pdfs
                pdf_dir = Path(__file__).resolve().parents[3] / "inputs" / "pdfs"
        self.pdf_dir = pdf_dir
        self.pdf_extractor = pdf_extractor or PDFExtractor(min_text_chars=_MIN_TEXT_CHARS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_all(self) -> list[SourceDocument]:
        """
        Scan *pdf_dir* for PDF files and extract them all.

        Returns an empty list (never raises) when:
        - the directory does not exist
        - no ``*.pdf`` files are found
        - all files fail extraction (individual failures are logged as warnings)
        """
        if not self.pdf_dir.exists():
            logger.debug("UserDocumentStore: pdf_dir '%s' does not exist — skipping.", self.pdf_dir)
            return []

        pdf_paths = sorted(self.pdf_dir.glob("*.pdf"))
        if not pdf_paths:
            logger.debug("UserDocumentStore: no PDF files found in '%s'.", self.pdf_dir)
            return []

        logger.info(
            "UserDocumentStore: found %d PDF file(s) in '%s'.",
            len(pdf_paths),
            self.pdf_dir,
        )

        documents: list[SourceDocument] = []
        for path in pdf_paths:
            doc = self._extract_one(path)
            if doc is not None:
                documents.append(doc)

        logger.info(
            "UserDocumentStore: successfully extracted %d / %d PDF(s).",
            len(documents),
            len(pdf_paths),
        )
        return documents

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_one(self, path: Path) -> SourceDocument | None:
        """Extract a single PDF file.  Returns None on failure."""
        source_id = f"user_doc_{self._stable_id(path)}"
        file_url = f"file://{path.resolve()}"

        try:
            pdf_bytes = path.read_bytes()
        except OSError as exc:
            logger.warning("UserDocumentStore: cannot read '%s': %s", path, exc)
            return None

        try:
            result = self.pdf_extractor.extract_from_bytes(
                pdf_bytes,
                source_url=file_url,
                final_url=file_url,
                title_hint=path.stem.replace("_", " ").replace("-", " ").title(),
            )
        except PDFExtractionError as exc:
            logger.warning("UserDocumentStore: extraction failed for '%s': %s", path, exc)
            return None

        if not result.text or len(result.text) < _MIN_TEXT_CHARS:
            logger.warning(
                "UserDocumentStore: '%s' produced too little text (%d chars) — skipping.",
                path.name,
                len(result.text or ""),
            )
            return None

        metadata: dict[str, object] = {
            "user_uploaded": True,
            "filename": path.name,
            "page_count": result.page_count,
            **result.metadata,
        }

        doc = SourceDocument(
            source_id=source_id,
            url=file_url,
            title=result.title or path.stem,
            source_type=SourceType.PDF,
            extraction_method=ExtractionMethod.PYMUPDF,
            text=result.text,
            metadata=metadata,
            extraction_success=True,
            extraction_error=None,
        )
        logger.debug(
            "UserDocumentStore: extracted '%s' → %d chars, %d pages.",
            path.name,
            len(result.text),
            result.page_count,
        )
        return doc

    @staticmethod
    def _stable_id(path: Path) -> str:
        """A short, stable, filesystem-safe identifier for a PDF path."""
        digest = hashlib.sha1(str(path.resolve()).encode()).hexdigest()[:8]
        safe_stem = "".join(c if c.isalnum() else "_" for c in path.stem)[:40]
        return f"{safe_stem}_{digest}"
