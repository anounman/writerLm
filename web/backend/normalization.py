"""Deterministic normalization layer for BookRequest payloads.

Runs AFTER the LLM parser and BEFORE the planner input is constructed.
Enforces domain-specific rules that are too unreliable for LLM parsing alone.

This module is pure-function, idempotent, and makes zero LLM calls.
"""

from __future__ import annotations

import copy
import re
from typing import Any


# ── Pattern libraries ────────────────────────────────────────────────────────

_URL_PATTERN = re.compile(r"https?://[^\s<>\"')\]]+")

_NO_CODE_PHRASES = re.compile(
    r"\b(?:no[- ]code|without\s+code|no\s+programming|avoid\s+programming)\b",
    re.IGNORECASE,
)

_CODE_HEAVY_PHRASES = re.compile(
    r"\b(?:code[\s-]*heavy|runnable\s+code|implementation[\s-]*heavy|"
    r"build\s+from\s+scratch|from\s+scratch\s+implementation)\b",
    re.IGNORECASE,
)

_SHOWCASE_PHRASES = re.compile(
    r"\b(?:showcase|homepage|demo|portfolio|polished|publication[\s-]*ready)\b",
    re.IGNORECASE,
)

_IMPLEMENTATION_PHRASES = re.compile(
    r"\b(?:build|implement|project[\s-]*based|hands[\s-]*on|"
    r"step[\s-]*by[\s-]*step\s+(?:guide|tutorial)|practical\s+guide|"
    r"implementation\s+guide|coding\s+project|develop\s+a|create\s+a)\b",
    re.IGNORECASE,
)

_PHILOSOPHY_KEYWORDS = re.compile(
    r"\b(?:philosophy|philosophical|ethics|ethical|moral\s+responsibility|"
    r"epistemology|ontology|metaphysics|free\s+will|existential|"
    r"determinism|phenomenology|hermeneutics|deontolog|utilitarianism|"
    r"virtue\s+ethics)\b",
    re.IGNORECASE,
)

_HISTORY_KEYWORDS = re.compile(
    r"\b(?:history|historical|chronolog|revolution|war|empire|"
    r"timeline|ancient|medieval|colonial|dynasty|"
    r"century|era|epoch|civilization)\b",
    re.IGNORECASE,
)

_PSYCHOLOGY_KEYWORDS = re.compile(
    r"\b(?:psychology|psychological|habit|focus|deep\s+work|productivity|"
    r"therapy|therapeutic|cognitive\s+behavioral|mental\s+health|"
    r"self[\s-]*help|well[\s-]*being|mindfulness|emotional\s+intelligence|"
    r"resilience|anxiety|depression|stress\s+management|counseling|counselling)\b",
    re.IGNORECASE,
)

_EVIDENCE_BASED_PHRASES = re.compile(
    r"\b(?:evidence[\s-]*based|research[\s-]*grounded|research[\s-]*backed|"
    r"scientifically[\s-]*supported)\b",
    re.IGNORECASE,
)

_BUSINESS_KEYWORDS = re.compile(
    r"\b(?:startup|founder|go[\s-]*to[\s-]*market|business|marketing|"
    r"positioning|strategy|product\s+strategy|entrepreneurship|"
    r"venture|growth|revenue|customer|branding)\b",
    re.IGNORECASE,
)

_MATH_KEYWORDS = re.compile(
    r"\b(?:mathematics|mathematical|algebra|calculus|linear\s+algebra|"
    r"differential\s+equations|topology|number\s+theory|statistics|"
    r"probability|theorem|proof|lemma|corollary|equation|formula|"
    r"physics|quantum|mechanics|electrodynamics|thermodynamics)\b",
    re.IGNORECASE,
)

_DIAGRAM_HEAVY_PHRASES = re.compile(
    r"\b(?:diagram[\s-]*heavy|visual|architecture|concept\s+maps|"
    r"flowcharts|diagrams)\b",
    re.IGNORECASE,
)

_BEGINNER_KEYWORDS = re.compile(
    r"\b(?:beginner|beginners|novice|newcomer|introduction|introductory|"
    r"getting\s+started|first[\s-]*time|basics|fundamentals|"
    r"zero\s+knowledge|simple)\b",
    re.IGNORECASE,
)

_ADVANCED_KEYWORDS = re.compile(
    r"\b(?:advanced|expert|senior|experienced|specialist|researcher|"
    r"graduate[\s-]*level|phd|doctoral|postgraduate|deep\s+dive|"
    r"professional)\b",
    re.IGNORECASE,
)

# Non-technical book domains where code defaults to "none"
_NON_TECHNICAL_DOMAINS = {
    "productivity", "psychology", "self-help", "self_help", "philosophy",
    "history", "business", "education", "general_nonfiction", "general",
    "society", "politics", "medicine_adjacent", "ethics", "systems_thinking",
    "systems-thinking", "visual_textbook", "visual-textbook",
}

# Technologies to extract from prompts
_STACK_TECHNOLOGIES = [
    "FastAPI", "Django", "Flask", "React", "Next.js",
    "PostgreSQL", "SQLite", "MySQL", "Redis",
    "Docker", "Docker Compose", "Kubernetes",
    "AWS", "Azure", "GCP", "Terraform",
    "Python", "JavaScript", "TypeScript",
    "SQLAlchemy", "Alembic", "pytest",
    "LangChain", "Chroma", "pgvector", "Pinecone", "FAISS",
]

# Compiled regex patterns for each technology, matching case-insensitively
# but preserving the canonical capitalization.
_STACK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (tech, re.compile(r"\b" + re.escape(tech) + r"\b", re.IGNORECASE))
    for tech in _STACK_TECHNOLOGIES
]


def _is_technical_context(parsed: dict[str, Any], text_pool: str) -> bool:
    """Return True if the request is about a technical/programming topic."""
    technical_signals = (
        "programming", "software", "api", "rest api", "devops", "infrastructure",
        "backend", "frontend", "full-stack", "microservice", "database", "cli",
        "code", "coding", "python", "javascript", "typescript", "docker",
        "kubernetes", "terraform", "deploy", "authentication", "authorization",
        "fastapi", "postgresql", "sqlalchemy", "alembic", "docker compose", "pytest",
    )
    book_type = str(parsed.get("book_type") or "")
    if book_type in ("implementation_guide",):
        return True
    for signal in technical_signals:
        if re.search(r"\b" + re.escape(signal) + r"\b", text_pool, re.IGNORECASE):
            return True
    return False


def _is_nontechnical_domain(parsed: dict[str, Any], text_pool: str) -> bool:
    """Return True if the request is clearly non-technical."""
    topic = str(parsed.get("topic") or "").lower()
    for domain_key in _NON_TECHNICAL_DOMAINS:
        if domain_key.replace("_", " ") in topic or domain_key.replace("_", "-") in topic:
            return True
    # Check for domain-specific keywords
    for pattern in (_PHILOSOPHY_KEYWORDS, _HISTORY_KEYWORDS, _PSYCHOLOGY_KEYWORDS, _BUSINESS_KEYWORDS):
        if pattern.search(text_pool) and not _is_technical_context(parsed, text_pool):
            return True
    if "systems thinking" in text_pool.lower() or "visual textbook" in text_pool.lower():
        return True
    return False


def _add_unique(target: list[str], items: list[str]) -> list[str]:
    """Append items to target without duplicates, preserving order."""
    existing = {item.lower().strip().rstrip(".") for item in target}
    for item in items:
        clean_item = item.strip().rstrip(".")
        if clean_item.lower() not in existing:
            target.append(item)
            existing.add(clean_item.lower())
    return target


# ── Main normalization function ──────────────────────────────────────────────

def _sanitize_enum(val: Any, allowed: set[str], default: str | None = None) -> str | None:
    if not val:
        return default
    s = str(val).lower().strip().replace("-", "_").replace(" ", "_")
    if s == "case_study":
        s = "case_study_playbook"
    if s == "high_quality":
        s = "high"
    if s in allowed:
        return s
    return default

def normalize_book_request(parsed: dict[str, Any], original_prompt: str = "") -> dict[str, Any]:
    """Apply deterministic normalization rules to a parsed book request.
    
    This function is the final authority and MUST override LLM output when 
    user intent is clear from the prompt.
    """
    result = copy.deepcopy(parsed)
    
    # ── Alias handling ───────────────────────────────────────────────────
    if "quality_target_score" in result:
        result["target_quality_score"] = result.pop("quality_target_score")

    contract = dict(result.get("generation_contract") or {})
    topic = str(result.get("topic") or "")
    audience = str(result.get("audience") or "")
    goals = result.get("goals") or []
    goals_text = " ".join(str(g) for g in goals)
    desc = str(result.get("running_project_description") or "")
    outcome = str(contract.get("target_reader_outcome") or "")
    text_pool = f"{topic} {audience} {goals_text} {desc} {outcome} {original_prompt}"

    is_technical = _is_technical_context(result, text_pool)
    is_nontechnical = _is_nontechnical_domain(result, text_pool)

    # ── Rule 1: URL extraction ───────────────────────────────────────────
    if original_prompt:
        urls_in_prompt = _URL_PATTERN.findall(original_prompt)
        clean_urls: list[str] = []
        seen: set[str] = set()
        for url in urls_in_prompt:
            url = url.rstrip(".,;:!?)")
            if url not in seen:
                clean_urls.append(url)
                seen.add(url)
        result["urls"] = clean_urls

    # ── Rule 2: Explicit no-code always wins ─────────────────────────────
    # This must override ANY LLM output.
    explicit_no_code = _NO_CODE_PHRASES.search(text_pool) or \
                       re.search(r"\bno\s+(?:yaml|terminal\s+commands|shell\s+commands)\b", text_pool, re.I)
    
    if explicit_no_code:
        result["code_density"] = "none"
        contract["code_artifact_policy"] = "no_code"
        _add_unique(
            contract.setdefault("forbidden_content", []),
            ["code examples", "programming filler", "terminal commands", "YAML", "shell commands"],
        )

    # ── Rule 3: Non-technical domains default to no-code ─────────────────
    if is_nontechnical and not explicit_no_code:
        # Default to no-code unless user explicitly asked for code-heavy
        if not _CODE_HEAVY_PHRASES.search(text_pool):
            result["code_density"] = "none"
            contract["code_artifact_policy"] = "no_code"

    # ── Rule 4: Technical no-code must stay no-code ──────────────────────
    # Topic technical but prompt says "no code"
    if is_technical and explicit_no_code:
        result["code_density"] = "none"
        contract["code_artifact_policy"] = "no_code"

    # ── Rule 5: Code-heavy technical prompts ─────────────────────────────
    if _CODE_HEAVY_PHRASES.search(text_pool) and is_technical and not explicit_no_code:
        result["code_density"] = "high"
        contract["code_artifact_policy"] = "file_labeled_code_required"
        contract["implementation_style"] = "file_by_file"
        contract["section_style"] = "file_by_file_implementation"

    # ── Rule 6: Diagram-heavy / visual ───────────────────────────────────
    if _DIAGRAM_HEAVY_PHRASES.search(text_pool):
        result["diagram_density"] = "high"
        contract.setdefault("visual_policy", "structured useful diagrams only")
        
        # Infer diagram_style by domain if missing or weak
        if not contract.get("diagram_style") or contract.get("diagram_style") == "none":
            if "systems thinking" in text_pool.lower() or "psychology" in text_pool.lower() or "productivity" in text_pool.lower():
                contract["diagram_style"] = "concept_maps_decision_trees_checklists"
            elif is_technical:
                contract["diagram_style"] = "architecture_sequence_schema_deployment"
            elif _PHILOSOPHY_KEYWORDS.search(text_pool):
                contract["diagram_style"] = "argument_maps_comparison_matrices"
            elif _HISTORY_KEYWORDS.search(text_pool):
                contract["diagram_style"] = "timelines_cause_effect_maps"
            elif _BUSINESS_KEYWORDS.search(text_pool):
                contract["diagram_style"] = "frameworks_matrices_funnels"

    # ── Rule 7: Showcase always sets quality controls ───────────────────
    if _SHOWCASE_PHRASES.search(text_pool):
        contract["showcase_candidate"] = True
        
        current_score = result.get("target_quality_score", 0) or 0
        score_match = re.search(r'quality score(?: target)? (?:above |of |>|>=)?\s*(\d+)', text_pool, re.I)
        if score_match:
            prompt_score = int(score_match.group(1))
            if prompt_score > current_score:
                current_score = prompt_score
                
        if current_score < 80:
            result["target_quality_score"] = 80
        else:
            result["target_quality_score"] = current_score
            
        result["auto_repair"] = True
        result["sample_first"] = True
        if result.get("quality_mode") in (None, "fast_draft", "full_generation"):
            result["quality_mode"] = "full_auto_repair"
        _add_unique(
            contract.setdefault("success_criteria", []),
            [
                "homepage showcase-ready",
                "polished final manuscript",
                "coherent book arc",
                "no generic filler",
            ],
        )
        _add_unique(
            contract.setdefault("forbidden_content", []),
            [
                "generic filler",
                "placeholder text",
                "internal QA text",
                "weak diagrams",
                "fake sources",
                "unsupported statistics",
            ],
        )

    # ── Rule 8: Required stack extraction (Full Pool) ────────────────────
    existing_stack = {s.lower() for s in (contract.get("required_stack") or [])}
    stack: list[str] = list(contract.get("required_stack") or [])
    for canonical, pattern in _STACK_PATTERNS:
        if pattern.search(text_pool) and canonical.lower() not in existing_stack:
            stack.append(canonical)
            existing_stack.add(canonical.lower())
    if stack:
        contract["required_stack"] = stack

    # ── Rule 9: Domain-specific Required Outputs ─────────────────────────
    req_out = contract.setdefault("required_outputs", [])
    
    if is_technical and result.get("code_density") != "none":
        _add_unique(req_out, ["folder tree", "source files", "config files", "tests", "verification commands", "troubleshooting checklist", "deployment checklist"])
        _add_unique(contract.setdefault("project_artifacts", []), ["folder tree", "source files", "tests", "config files", "deployment checklist"])
    
    if "systems thinking" in text_pool.lower():
        _add_unique(req_out, ["concept maps", "feedback loop diagrams", "decision trees", "worksheets", "real-life examples"])
    elif _BUSINESS_KEYWORDS.search(text_pool):
        contract.setdefault("implementation_style", "case_study_playbook")
        contract.setdefault("section_style", "case_study_playbook")
        contract.setdefault("diagram_style", "frameworks_matrices_funnels")
        _add_unique(req_out, ["ICP worksheet", "positioning canvas", "pricing decision table", "launch experiment template", "action checklist", "fictional case studies"])
    elif _MATH_KEYWORDS.search(text_pool):
        contract.setdefault("notation_system", "LaTeX")
        _add_unique(req_out, ["definitions", "solved examples", "diagrams", "practice problems", "exam-style exercises", "formula summaries"])
    elif _PSYCHOLOGY_KEYWORDS.search(text_pool) or "productivity" in text_pool.lower():
        if _EVIDENCE_BASED_PHRASES.search(text_pool):
            contract.setdefault("source_strictness", "high")
        _add_unique(req_out, ["evidence notes", "exercises", "reflection prompts", "habit trackers", "checklists"])
    elif _PHILOSOPHY_KEYWORDS.search(text_pool):
        contract.setdefault("implementation_style", "argument_driven")
        contract.setdefault("section_style", "academic_argument")
        contract.setdefault("diagram_style", "argument_maps_comparison_matrices")
        _add_unique(req_out, ["definitions", "argument maps", "objections", "counterarguments", "conclusion summaries"])
    elif _HISTORY_KEYWORDS.search(text_pool):
        contract.setdefault("diagram_style", "timelines_cause_effect_maps")
        _add_unique(req_out, ["timelines", "chronology tables", "cause-effect maps", "disputed interpretation notes"])

    # ── Rule 10: Domain-specific Forbidden Content ───────────────────────
    forb = contract.setdefault("forbidden_content", [])
    if _PSYCHOLOGY_KEYWORDS.search(text_pool):
        _add_unique(forb, ["diagnosis", "clinical treatment advice", "overclaiming causality", "fake studies", "fake statistics"])
    if _PHILOSOPHY_KEYWORDS.search(text_pool):
        _add_unique(forb, ["fake quotes", "unsupported attribution", "unclear terminology"])
    if _HISTORY_KEYWORDS.search(text_pool):
        _add_unique(forb, ["fake dates", "fake events", "invented quotes", "unsupported claims"])
    if _BUSINESS_KEYWORDS.search(text_pool):
        _add_unique(forb, ["fake real company case studies", "unsupported market claims", "vague startup buzzwords"])
    if is_technical and result.get("code_density") != "none":
        _add_unique(forb, ["broken code", "fake APIs", "unlabeled code blocks", "disconnected snippets", "placeholder code"])
    if result.get("diagram_density") == "high":
        _add_unique(forb, ["generic keyword diagrams", "internal diagram labels", "low-value visuals"])
    if _EVIDENCE_BASED_PHRASES.search(text_pool) or "digital minimalism" in text_pool.lower():
        _add_unique(forb, ["fake studies", "fake statistics", "unsupported claims", "fake quotes"])

    # ── Depth inference from audience ───────────────────────────
    if not contract.get("depth_level"):
        if _BEGINNER_KEYWORDS.search(audience):
            contract["depth_level"] = "surface"
        elif _ADVANCED_KEYWORDS.search(audience):
            contract["depth_level"] = "deep"
        else:
            contract["depth_level"] = "intermediate"

    # ── Section style inference (if still unset) ─────────────────────────
    if not contract.get("section_style"):
        book_type = result.get("book_type", "auto")
        if book_type in ("textbook", "exam_prep"):
            contract["section_style"] = "academic"
        elif book_type in ("implementation_guide", "practice_workbook"):
            contract["section_style"] = "tutorial"
        elif book_type == "reference_handbook":
            contract["section_style"] = "reference"
        elif book_type == "conceptual_guide":
            contract["section_style"] = "conversational"
            
    # ── Enum sanitization ────────────────────────────────────────────────
    book_types = {"auto", "textbook", "practice_workbook", "course_companion", "implementation_guide", "reference_handbook", "conceptual_guide", "exam_prep"}
    theory_practices = {"auto", "theory_heavy", "balanced", "practice_heavy", "implementation_heavy"}
    pedagogy_styles = {"auto", "german_theoretical", "indian_theory_then_examples", "socratic", "exam_oriented", "project_based"}
    source_usages = {"auto", "primary_curriculum", "supplemental", "example_inspiration"}
    exercise_strats = {"auto", "none", "extract_patterns", "worked_examples", "practice_sets"}
    code_densities = {"none", "low", "medium", "high"}
    content_densities = {"low", "medium", "high"}
    quality_modes = {"fast_draft", "full_generation", "full_auto_repair", "sample_first"}
    
    depth_levels = {"surface", "intermediate", "deep", "exhaustive"}
    impl_styles = {"conceptual_only", "pseudocode", "recipe_steps", "file_by_file", "project_progressive", "argument_driven", "case_study_playbook", "workbook", "visual_textbook", "reference"}
    section_styles = {"academic", "conversational", "handbook", "tutorial", "reference", "file_by_file_implementation", "academic_argument", "case_study_playbook", "visual_textbook", "workbook"}
    code_policies = {"no_code", "pseudocode_only", "minimal_runnable", "file_labeled_code_required"}
    diagram_styles = {"none", "conceptual", "architecture", "data_flow", "comparison_matrix", "architecture_sequence_schema_deployment", "concept_maps_decision_trees_checklists", "argument_maps_comparison_matrices", "timelines_cause_effect_maps", "frameworks_matrices_funnels"}
    source_strictness_enum = {"low", "medium", "high", "primary_sources_required"}
    evidence_standards = {"anecdotal", "curated", "primary_source", "peer_reviewed"}

    result["book_type"] = _sanitize_enum(result.get("book_type"), book_types, "auto")
    result["theory_practice_balance"] = _sanitize_enum(result.get("theory_practice_balance"), theory_practices, "balanced")
    result["pedagogy_style"] = _sanitize_enum(result.get("pedagogy_style"), pedagogy_styles, "auto")
    result["source_usage"] = _sanitize_enum(result.get("source_usage"), source_usages, "auto")
    result["exercise_strategy"] = _sanitize_enum(result.get("exercise_strategy"), exercise_strats, "auto")
    result["code_density"] = _sanitize_enum(result.get("code_density"), code_densities, "medium" if is_technical else "none")
    result["example_density"] = _sanitize_enum(result.get("example_density"), content_densities, "high")
    result["diagram_density"] = _sanitize_enum(result.get("diagram_density"), content_densities, "medium")
    
    if "quality_mode" in result:
        result["quality_mode"] = _sanitize_enum(result.get("quality_mode"), quality_modes, "full_auto_repair")

    if "depth_level" in contract: contract["depth_level"] = _sanitize_enum(contract["depth_level"], depth_levels, "intermediate")
    if "implementation_style" in contract: contract["implementation_style"] = _sanitize_enum(contract["implementation_style"], impl_styles, None)
    if "section_style" in contract: contract["section_style"] = _sanitize_enum(contract["section_style"], section_styles, None)
    if "code_artifact_policy" in contract: contract["code_artifact_policy"] = _sanitize_enum(contract["code_artifact_policy"], code_policies, None)
    if "diagram_style" in contract: contract["diagram_style"] = _sanitize_enum(contract["diagram_style"], diagram_styles, None)
    if "source_strictness" in contract: contract["source_strictness"] = _sanitize_enum(contract["source_strictness"], source_strictness_enum, None)
    if "evidence_standard" in contract: contract["evidence_standard"] = _sanitize_enum(contract["evidence_standard"], evidence_standards, None)

    result["generation_contract"] = contract
    return result

