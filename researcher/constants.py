from __future__ import annotations

import os

from researcher.schemas import EvidenceType, ResearchDepth


RESEARCH_EXECUTION_PROFILE = os.getenv("RESEARCH_EXECUTION_PROFILE", "full").strip().lower()
if RESEARCH_EXECUTION_PROFILE not in {"debug", "full"}:
    RESEARCH_EXECUTION_PROFILE = "full"

EXECUTION_PROFILES = {
    "debug": {
        "max_discovered_sources_per_section": 4,
        "max_fetched_sources_per_section": 2,
        "max_reflexion_rounds": 1,
        "max_followup_sources_per_round": 1,
        "max_source_text_chars_for_single_pass": 4000,
        "enable_firecrawl_fallback": False,
    },
    "full": {
        "max_discovered_sources_per_section": 8,
        "max_fetched_sources_per_section": 3,
        "max_reflexion_rounds": 1,
        "max_followup_sources_per_round": 2,
        "max_source_text_chars_for_single_pass": 8000,
        "enable_firecrawl_fallback": True,
    },
}

ACTIVE_EXECUTION_PROFILE = EXECUTION_PROFILES[RESEARCH_EXECUTION_PROFILE]


# =========================================================
# Search / discovery
# =========================================================

DEFAULT_TAVILY_RESULTS_PER_QUERY = 5
MAX_DISCOVERED_SOURCES_PER_SECTION = ACTIVE_EXECUTION_PROFILE["max_discovered_sources_per_section"]
MAX_FETCHED_SOURCES_PER_SECTION = ACTIVE_EXECUTION_PROFILE["max_fetched_sources_per_section"]
MAX_FOLLOWUP_SOURCES_PER_ROUND = ACTIVE_EXECUTION_PROFILE["max_followup_sources_per_round"]
DISCOVERY_OVERFETCH_FACTOR = 2


# =========================================================
# Reflexion / loop control
# =========================================================

MAX_REFLEXION_ROUNDS = ACTIVE_EXECUTION_PROFILE["max_reflexion_rounds"]

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
MAX_SOURCE_TEXT_CHARS_FOR_SINGLE_PASS = ACTIVE_EXECUTION_PROFILE["max_source_text_chars_for_single_pass"]


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

BLOCKED_SOURCE_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "medium.com",
    "pinterest.com",
    "pub.aimind.so",
    "reddit.com",
    "substack.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "youtu.be",
}

WEAK_SOURCE_DOMAINS = {
    "analyticsvidhya.com",
    "answers.com",
    "brainly.com",
    "coursehero.com",
    "quora.com",
    "scribd.com",
    "slideshare.net",
    "towardsdatascience.com",
}

UNSUPPORTED_SOURCE_EXTENSIONS = {
    ".csv",
    ".doc",
    ".docx",
    ".epub",
    ".jpg",
    ".jpeg",
    ".mp3",
    ".mp4",
    ".png",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".zip",
}

DOMAIN_TRUST_OVERRIDES = {
    "arxiv.org": 0.97,
    "docs.python.org": 0.98,
    "learn.microsoft.com": 0.98,
    "openai.com": 0.98,
    "platform.openai.com": 0.98,
    "python.org": 0.97,
    "wikipedia.org": 0.65,
}


# =========================================================
# Fallback behavior
# =========================================================

ENABLE_FIRECRAWL_FALLBACK = ACTIVE_EXECUTION_PROFILE["enable_firecrawl_fallback"]

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
