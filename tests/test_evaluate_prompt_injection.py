import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure we can import scripts
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

# Test that it imports successfully
try:
    from scripts.evaluate_prompt_injection import run_evaluation, evaluate_case, CASES
except ImportError as e:
    pytest.fail(f"Failed to import evaluate_prompt_injection: {e}")

def test_script_imports_successfully():
    """Test that the script imports successfully and CASES are defined."""
    assert len(CASES) == 12

def test_deterministic_mode_runs_without_api_keys(tmp_path):
    """Test that deterministic-only mode runs without API keys."""
    try:
        run_evaluation(
            deterministic_only=True,
            output_dir=str(tmp_path),
            fail_under=0, # We just want to make sure it doesn't crash
            specific_case="case_05_history"
        )
    except Exception as e:
        pytest.fail(f"run_evaluation in deterministic mode failed: {e}")
        
    assert (tmp_path / "case_05_history" / "evaluation.json").exists()

def test_evaluator_url_extraction():
    """Test that the evaluator correctly checks URL extraction."""
    case_data = next(c for c in CASES if c["id"] == "case_10_url_extraction")
    
    # Mock good input
    planner_input = {"urls": ["https://example.com/a", "https://example.org/b"]}
    book_contract = {"must_not_do": []}
    
    result = evaluate_case(case_data, book_contract, planner_input)
    # The evaluation checks urls_exact
    url_check = next((c for c in result["checks"] if c["name"] == "urls"), None)
    assert url_check is not None
    assert url_check["passed"] is True

def test_evaluator_no_code_case():
    """Test that the evaluator correctly checks no-code policy."""
    case_data = next(c for c in CASES if c["id"] == "case_01_non_code_productivity")
    
    planner_input = {
        "code_density": "none",
        "generation_contract": {
            "code_artifact_policy": "no_code"
        }
    }
    book_contract = {"must_not_do": []}
    
    result = evaluate_case(case_data, book_contract, planner_input)
    code_density_check = next((c for c in result["checks"] if c["name"] == "code_density"), None)
    assert code_density_check["passed"] is True
    
    policy_check = next((c for c in result["checks"] if c["name"] == "code_artifact_policy"), None)
    assert policy_check["passed"] is True

def test_evaluator_technical_stack_extraction():
    """Test that the evaluator correctly checks required stack."""
    case_data = next(c for c in CASES if c["id"] == "case_03_url_shortener_showcase")
    
    planner_input = {
        "generation_contract": {
            "required_stack": ["FastAPI", "PostgreSQL", "SQLAlchemy", "Alembic", "Docker", "Docker Compose", "pytest"]
        }
    }
    book_contract = {"must_not_do": []}
    
    result = evaluate_case(case_data, book_contract, planner_input)
    stack_check = next((c for c in result["checks"] if c["name"] == "required_stack"), None)
    assert stack_check["passed"] is True
