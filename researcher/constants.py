from __future__ import annotations

from researcher.schemas import EvidenceType, ResearchDepth


# =========================================================
# Search / discovery
# =========================================================

DEFAULT_TAVILY_RESULTS_PER_QUERY = 5
MAX_DISCOVERED_SOURCES_PER_SECTION = 12
MAX_FETCHED_SOURCES_PER_SECTION = 6
MAX_FOLLOWUP_SOURCES_PER_ROUND = 3


# =========================================================
# Reflexion / loop control
# =========================================================

MAX_REFLEXION_ROUNDS = 2

# If evidence stays too weak after this many rounds,
# finalize with warnings instead of looping forever.
FINALIZE_ON_MAX_ROUNDS = True


# =========================================================
# Extraction / text quality
# =========================================================

MIN_EXTRACTED_TEXT_CHARS = 400
MIN_WEBPAGE_TEXT_CHARS = 500
MIN_PDF_TEXT_CHARS = 300

# If extracted text exceeds this size, downstream nodes
# should consider chunking/truncation before LLM calls.
MAX_SOURCE_TEXT_CHARS_FOR_SINGLE_PASS = 15000


# =========================================================
# Evidence expectations
# =========================================================

MIN_EVIDENCE_ITEMS_PER_SECTION = 6
TARGET_EVIDENCE_ITEMS_PER_SECTION = 12

DEFAULT_REQUIRED_EVIDENCE_TYPES = [
    EvidenceType.DEFINITION,
    EvidenceType.FACT,
    EvidenceType.EXAMPLE,
]

DEEP_RESEARCH_REQUIRED_EVIDENCE_TYPES = [
    EvidenceType.DEFINITION,
    EvidenceType.FACT,
    EvidenceType.EXAMPLE,
    EvidenceType.CASE_STUDY,
    EvidenceType.REFERENCE,
]


# =========================================================
# Coverage heuristics
# =========================================================

MIN_KEY_CONCEPTS_PER_SECTION = 3
MIN_SOURCE_COUNT_FOR_SUFFICIENT_COVERAGE = 3
MIN_DISTINCT_EVIDENCE_TYPES_FOR_SUFFICIENT_COVERAGE = 3


# =========================================================
# Quality / scoring
# =========================================================

DEFAULT_RELEVANCE_SCORE = 0.5
DEFAULT_QUALITY_SCORE = 0.5

MIN_ACCEPTABLE_RELEVANCE_SCORE = 0.45
MIN_ACCEPTABLE_QUALITY_SCORE = 0.40


# =========================================================
# Fallback behavior
# =========================================================

ENABLE_FIRECRAWL_FALLBACK = True

# Use Firecrawl only when extraction is empty or too weak.
FIRECRAWL_FALLBACK_MIN_TEXT_CHARS = 250

# Whether failed source fetches should be kept in state as warnings
# instead of stopping the whole pipeline.
ALLOW_PARTIAL_SOURCE_FAILURE = True


# =========================================================
# Depth-aware defaults
# =========================================================

DEPTH_TO_QUERY_COUNT = {
    ResearchDepth.LIGHT: 3,
    ResearchDepth.STANDARD: 5,
    ResearchDepth.DEEP: 7,
}

DEPTH_TO_TARGET_SOURCE_COUNT = {
    ResearchDepth.LIGHT: 3,
    ResearchDepth.STANDARD: 5,
    ResearchDepth.DEEP: 6,
}

DEPTH_TO_TARGET_EVIDENCE_COUNT = {
    ResearchDepth.LIGHT: 5,
    ResearchDepth.STANDARD: 8,
    ResearchDepth.DEEP: 12,
}