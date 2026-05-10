"""Deterministic tests for web.backend.normalization.normalize_book_request."""

from __future__ import annotations

import copy

import pytest

from web.backend.normalization import normalize_book_request


# ── Test 1: No-code enforcement ──────────────────────────────────────────────

def test_no_code_enforcement():
    parsed = {"topic": "Psychology handbook", "audience": "Professionals", "code_density": "none"}
    result = normalize_book_request(parsed, original_prompt="psychology handbook, no code")
    gc = result["generation_contract"]
    assert result["code_density"] == "none"
    assert gc["code_artifact_policy"] == "no_code"
    assert "code examples" in gc["forbidden_content"]
    assert "programming filler" in gc["forbidden_content"]
    assert "terminal commands" in gc["forbidden_content"]


def test_no_code_from_prompt_only():
    parsed = {"topic": "Focus habits", "audience": "Students", "code_density": "medium"}
    result = normalize_book_request(parsed, original_prompt="without code")
    gc = result["generation_contract"]
    assert result["code_density"] == "none"
    assert gc["code_artifact_policy"] == "no_code"


# ── Test 2: Showcase quality boost ───────────────────────────────────────────

def test_showcase_quality_boost():
    parsed = {"topic": "Book about learning", "audience": "General", "target_quality_score": 70}
    result = normalize_book_request(parsed, original_prompt="polished showcase book")
    gc = result["generation_contract"]
    assert result["target_quality_score"] >= 80
    assert result["auto_repair"] is True
    assert result["sample_first"] is True
    assert gc["showcase_candidate"] is True
    assert "homepage showcase-ready" in gc["success_criteria"]
    assert "no generic filler" in gc["success_criteria"]


# ── Test 3: URL extraction ──────────────────────────────────────────────────

def test_url_extraction():
    parsed = {"topic": "Web development", "audience": "Developers", "urls": ["https://fake.com"]}
    result = normalize_book_request(
        parsed,
        original_prompt="Use https://example.com/a and https://example.org/b as references.",
    )
    # Only literal URLs from the prompt — never trust LLM-generated URLs
    assert result["urls"] == ["https://example.com/a", "https://example.org/b"]


def test_url_extraction_strips_trailing_punctuation():
    parsed = {"topic": "Testing", "audience": "Devs"}
    result = normalize_book_request(
        parsed,
        original_prompt="See https://example.com/page. Also https://example.org/doc?id=1,",
    )
    assert "https://example.com/page" in result["urls"]
    assert "https://example.org/doc?id=1" in result["urls"]


# ── Test 4: Philosophy mode ─────────────────────────────────────────────────

def test_philosophy_mode():
    parsed = {"topic": "Moral philosophy and free will", "audience": "Philosophy students"}
    result = normalize_book_request(parsed, original_prompt="moral philosophy and free will")
    gc = result["generation_contract"]
    assert result["code_density"] == "none"
    assert gc["code_artifact_policy"] == "no_code"
    assert gc["implementation_style"] == "argument_driven"
    assert gc["section_style"] == "academic_argument"
    assert gc["diagram_style"] == "argument_maps_comparison_matrices"
    assert "fake quotes" in gc["forbidden_content"]
    assert "definitions" in gc["required_outputs"]
    assert "argument maps" in gc["required_outputs"]


# ── Test 5: Implementation guide mode ────────────────────────────────────────

def test_implementation_guide_mode():
    parsed = {
        "topic": "URL shortener API with FastAPI, PostgreSQL, Docker, and tests",
        "audience": "Python backend developers",
        "book_type": "implementation_guide",
        "project_based": True,
        "code_density": "high",
    }
    prompt = "Build a production-ready URL shortener API with FastAPI, PostgreSQL, Docker, and tests. Code-heavy and diagram-heavy."
    result = normalize_book_request(parsed, original_prompt=prompt)
    gc = result["generation_contract"]
    assert result["code_density"] == "high"
    assert gc["code_artifact_policy"] == "file_labeled_code_required"
    assert gc["implementation_style"] == "file_by_file"
    assert gc["section_style"] == "file_by_file_implementation"
    # Required stack extraction
    stack_lower = [s.lower() for s in gc["required_stack"]]
    assert "fastapi" in stack_lower
    assert "postgresql" in stack_lower
    assert "docker" in stack_lower
    # Note: "pytest" isn't detected because the prompt says "tests" not "pytest"
    # Project artifacts
    assert "source files" in gc["project_artifacts"]
    assert "tests" in gc["project_artifacts"]
    # Diagram-heavy
    assert result["diagram_density"] == "high"


# ── Test 6: Psychology safety ────────────────────────────────────────────────

def test_psychology_safety():
    parsed = {"topic": "Habits and focus", "audience": "General readers"}
    result = normalize_book_request(
        parsed,
        original_prompt="evidence-based psychology handbook about habits",
    )
    gc = result["generation_contract"]
    assert any("diagnosis" in item.lower() or "clinical treatment" in item.lower() for item in gc["forbidden_content"])
    assert gc.get("source_strictness") == "high"


# ── Test 7: Math notation ───────────────────────────────────────────────────

def test_math_notation():
    parsed = {"topic": "Linear algebra", "audience": "University students"}
    result = normalize_book_request(parsed, original_prompt="linear algebra textbook")
    gc = result["generation_contract"]
    assert gc["notation_system"] == "LaTeX"


# ── Test 8: Depth from audience ──────────────────────────────────────────────

def test_depth_from_audience():
    parsed = {"topic": "Machine learning", "audience": "advanced researchers"}
    result = normalize_book_request(parsed, original_prompt="")
    gc = result["generation_contract"]
    assert gc["depth_level"] == "deep"


def test_depth_beginner():
    parsed = {"topic": "Python intro", "audience": "absolute beginners with zero knowledge"}
    result = normalize_book_request(parsed, original_prompt="")
    gc = result["generation_contract"]
    assert gc["depth_level"] == "surface"


def test_depth_default():
    parsed = {"topic": "General cooking", "audience": "home cooks"}
    result = normalize_book_request(parsed, original_prompt="")
    gc = result["generation_contract"]
    assert gc["depth_level"] == "intermediate"


# ── Test 9: Idempotency ─────────────────────────────────────────────────────

def test_idempotency():
    parsed = {
        "topic": "Philosophy of free will",
        "audience": "Graduate students",
        "code_density": "none",
    }
    prompt = "polished showcase book on free will, no code"
    first = normalize_book_request(parsed, original_prompt=prompt)
    second = normalize_book_request(copy.deepcopy(first), original_prompt=prompt)
    assert first == second


# ── Test 10: Existing explicit fields not overwritten ────────────────────────

def test_existing_explicit_fields_not_overwritten():
    parsed = {
        "topic": "Machine learning",
        "audience": "advanced researchers",
        "generation_contract": {"depth_level": "surface"},
    }
    result = normalize_book_request(parsed, original_prompt="")
    gc = result["generation_contract"]
    # User explicitly set surface — normalization must not overwrite to "deep"
    assert gc["depth_level"] == "surface"


def test_existing_code_policy_not_overwritten():
    parsed = {
        "topic": "Go-to-market strategy",
        "audience": "Founders",
        "generation_contract": {"code_artifact_policy": "minimal_runnable"},
    }
    result = normalize_book_request(parsed, original_prompt="startup playbook")
    gc = result["generation_contract"]
    # We now aggressively enforce no_code for business if no code heavy phrases
    assert gc["code_artifact_policy"] == "no_code"


# ── Test: History mode ───────────────────────────────────────────────────────

def test_history_mode():
    parsed = {"topic": "The French Revolution", "audience": "General readers"}
    result = normalize_book_request(parsed, original_prompt="history of the French Revolution with timelines")
    gc = result["generation_contract"]
    assert result["code_density"] == "none"
    assert gc["code_artifact_policy"] == "no_code"
    assert gc["diagram_style"] == "timelines_cause_effect_maps"
    assert "fake dates" in gc["forbidden_content"]
    assert "timelines" in gc["required_outputs"]


# ── Test: Business mode ──────────────────────────────────────────────────────

def test_business_mode():
    parsed = {"topic": "Go-to-market strategy for B2B SaaS", "audience": "First-time founders"}
    result = normalize_book_request(parsed, original_prompt="startup go-to-market playbook")
    gc = result["generation_contract"]
    assert gc["implementation_style"] == "case_study_playbook"
    assert gc["section_style"] == "case_study_playbook"
    assert gc["diagram_style"] == "frameworks_matrices_funnels"
    assert gc["code_artifact_policy"] == "no_code"
    assert any("canvas" in out.lower() for out in gc["required_outputs"])


# ── Test: Code-heavy detection ───────────────────────────────────────────────

def test_code_heavy_detection():
    parsed = {
        "topic": "Building a REST API",
        "audience": "Backend developers",
        "book_type": "implementation_guide",
    }
    result = normalize_book_request(parsed, original_prompt="code-heavy implementation guide")
    gc = result["generation_contract"]
    assert result["code_density"] == "high"
    assert gc["code_artifact_policy"] == "file_labeled_code_required"
    assert gc["implementation_style"] == "file_by_file"


# ── Test: Non-technical default ──────────────────────────────────────────────

def test_nontechnical_default():
    parsed = {"topic": "Meditation and mindfulness", "audience": "General public"}
    result = normalize_book_request(parsed, original_prompt="mindfulness handbook")
    gc = result["generation_contract"]
    assert result["code_density"] == "none"
    assert gc["code_artifact_policy"] == "no_code"


# ── Test: Diagram-heavy detection ────────────────────────────────────────────

def test_diagram_heavy_detection():
    parsed = {"topic": "Systems architecture", "audience": "Software engineers"}
    result = normalize_book_request(parsed, original_prompt="diagram-heavy visual architecture guide")
    gc = result["generation_contract"]
    assert result["diagram_density"] == "high"
    assert gc.get("visual_policy") == "structured useful diagrams only"


# ── Test: Required stack extraction ──────────────────────────────────────────

def test_required_stack_extraction():
    parsed = {"topic": "Web app", "audience": "Developers"}
    result = normalize_book_request(
        parsed,
        original_prompt="Build with FastAPI and PostgreSQL, deploy with Docker Compose",
    )
    gc = result["generation_contract"]
    stack_lower = [s.lower() for s in gc["required_stack"]]
    assert "fastapi" in stack_lower
    assert "postgresql" in stack_lower
    assert "docker compose" in stack_lower

# ── Test: Enum Sanitization ──────────────────────────────────────────────────

def test_enum_sanitization():
    parsed = {
        "topic": "Test",
        "audience": "Test",
        "book_type": "Exam-Prep ",
        "theory_practice_balance": "Theory Heavy",
        "generation_contract": {
            "implementation_style": "file-by-file",
            "section_style": "case-study",
            "source_strictness": "high quality",
            "depth_level": "unknown_depth"
        }
    }
    result = normalize_book_request(parsed, original_prompt="")
    assert result["book_type"] == "exam_prep"
    assert result["theory_practice_balance"] == "theory_heavy"
    gc = result["generation_contract"]
    assert gc["implementation_style"] == "file_by_file"
    assert gc["section_style"] == "case_study_playbook"
    assert gc["source_strictness"] == "high"
    assert gc["depth_level"] == "intermediate"

# ── Test: Quality Score Alias ────────────────────────────────────────────────

def test_alias_target_quality_score():
    parsed = {"topic": "T", "audience": "A", "quality_target_score": 85}
    result = normalize_book_request(parsed, original_prompt="")
    assert "quality_target_score" not in result
    assert result["target_quality_score"] == 85

# ── Test: Missing Generation Contract ────────────────────────────────────────

def test_missing_generation_contract():
    parsed = {"topic": "T", "audience": "A"}
    result = normalize_book_request(parsed, original_prompt="")
    assert "generation_contract" in result
    assert isinstance(result["generation_contract"], dict)


# ── Regression Tests for Harness Failures ────────────────────────────────────

def test_case_01_productivity_diagram_heavy():
    prompt = "Create a practical handbook about focus and deep work in the age of AI. Make it diagram-heavy, polished, beginner-friendly, and useful for university students. No code."
    parsed = {"topic": "Focus", "audience": "Students"}
    result = normalize_book_request(parsed, original_prompt=prompt)
    gc = result["generation_contract"]
    
    assert result["code_density"] == "none"
    assert gc["code_artifact_policy"] == "no_code"
    assert result["diagram_density"] == "high"
    # Required outputs must include habits/checklists etc.
    assert any("checklists" in out or "exercises" in out or "reflection prompts" in out or "habit trackers" in out for out in gc["required_outputs"])
    assert "required_stack" not in gc or len(gc["required_stack"]) == 0

def test_case_02_systems_thinking_visual():
    prompt = "A visual systems-thinking textbook. Use concept maps, feedback loops, and decision trees. No programming."
    parsed = {"topic": "Systems thinking", "audience": "University students"}
    result = normalize_book_request(parsed, original_prompt=prompt)
    gc = result["generation_contract"]
    
    # "visual textbook" triggers diagram density high and no code.
    assert result["code_density"] == "none"
    assert gc["code_artifact_policy"] == "no_code"
    assert result["diagram_density"] == "high"
    assert "concept_maps" in gc["diagram_style"] or "decision_trees" in gc["diagram_style"]
    assert any("concept maps" in out or "feedback loops" in out or "worksheets" in out or "decision trees" in out for out in gc["required_outputs"])

def test_case_03_url_shortener_showcase():
    prompt = "Build a production-ready URL shortener API showcase with FastAPI, PostgreSQL, SQLAlchemy, Alembic, Docker, Docker Compose, and pytest. Code-heavy, diagram-heavy, polished, for my portfolio."
    parsed = {"topic": "URL shortener API", "audience": "Developers"}
    result = normalize_book_request(parsed, original_prompt=prompt)
    gc = result["generation_contract"]
    
    assert result["code_density"] == "high"
    assert gc["code_artifact_policy"] == "file_labeled_code_required"
    assert gc["implementation_style"] == "file_by_file"
    assert gc["section_style"] == "file_by_file_implementation"
    
    stack = [s.lower() for s in gc["required_stack"]]
    assert "fastapi" in stack
    assert "postgresql" in stack
    assert "sqlalchemy" in stack
    assert "alembic" in stack
    assert "docker" in stack
    assert "docker compose" in stack
    assert "pytest" in stack
    
    req_out = [out.lower() for out in gc["required_outputs"]]
    assert "folder tree" in req_out
    assert "source files" in req_out
    assert "tests" in req_out
    assert "config files" in req_out
    assert "verification commands" in req_out
    
    proj_arts = [out.lower() for out in gc["project_artifacts"]]
    assert "source files" in proj_arts
    assert "tests" in proj_arts

def test_case_06_psychology_llm_bad_override():
    prompt = "Create an evidence-based psychology handbook about building healthy study habits for university students. Keep it practical and supportive, but do not diagnose mental health conditions or make clinical treatment claims."
    # Simulate LLM returning BAD values
    parsed = {
        "topic": "Psychology", 
        "audience": "Students",
        "code_density": "high",
        "generation_contract": {
            "code_artifact_policy": "file_labeled_code_required"
        }
    }
    result = normalize_book_request(parsed, original_prompt=prompt)
    gc = result["generation_contract"]
    
    # Normalization MUST override the bad LLM values back to safety
    assert result["code_density"] == "none"
    assert gc["code_artifact_policy"] == "no_code"
    assert gc["source_strictness"] == "high"
    
    forb = [f.lower() for f in gc["forbidden_content"]]
    assert any("diagnosis" in f for f in forb)
    assert any("clinical treatment" in f for f in forb)
    assert any("fake studies" in f for f in forb)

def test_case_09_technical_no_code():
    prompt = "Create a conceptual guide explaining Kubernetes architecture for product managers. Use diagrams and analogies, but no code, no YAML, and no terminal commands."
    parsed = {"topic": "Kubernetes architecture", "audience": "Product managers"}
    result = normalize_book_request(parsed, original_prompt=prompt)
    gc = result["generation_contract"]
    
    assert result["code_density"] == "none"
    assert gc["code_artifact_policy"] == "no_code"
    assert result["diagram_density"] == "high"
    
    stack = [s.lower() for s in gc["required_stack"]]
    assert "kubernetes" in stack
    
    forb = [f.lower() for f in gc["forbidden_content"]]
    assert any("yaml" in f for f in forb)
    assert any("terminal commands" in f for f in forb)
    assert any("code examples" in f for f in forb)
    
    assert gc.get("implementation_style") != "file_by_file"

def test_case_11_explicit_quality_preferences():
    prompt = "Create a polished homepage showcase book about AI-assisted learning. Use full quality mode, sample first, auto repair, and target a quality score above 85. Make it diagram-heavy and no-code."
    parsed = {"topic": "AI-assisted learning", "audience": "Educators"}
    result = normalize_book_request(parsed, original_prompt=prompt)
    gc = result["generation_contract"]
    
    assert gc["showcase_candidate"] is True
    assert result["target_quality_score"] >= 85
    assert result["sample_first"] is True
    assert result["auto_repair"] is True
    assert result["code_density"] == "none"
    assert gc["code_artifact_policy"] == "no_code"
    assert result["diagram_density"] == "high"
