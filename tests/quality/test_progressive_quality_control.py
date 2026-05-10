from __future__ import annotations

from quality.book_contract import BookContract
from quality.control import (
    QualityGateConfig,
    build_quality_checkpoint,
    build_repair_history,
    estimate_quality_risk,
    quality_label,
    quality_status_for_score,
    weak_sections,
)
from quality.repair_loop import run_quality_repair_loop
from quality.validator_registry import select_validators


def test_low_quality_section_triggers_repair_before_final_assembly() -> None:
    contract = BookContract(domain="psychology", sensitive_domain=True, code_expected=False, code_density="none")
    sections = [{
        "id": "s1",
        "section": "Habits",
        "content": "TODO\nYou should diagnose symptoms yourself. It is important to note that overall this section explores habits.",
    }]

    repaired_sections, qa_report = run_quality_repair_loop(sections=sections, contract=contract, max_passes=2)

    assert qa_report["repaired_sections"] == 1
    assert "TODO" not in repaired_sections[0]["content"]
    assert "informational" in repaired_sections[0]["content"].lower()


def test_final_job_with_score_below_45_is_not_plain_completed() -> None:
    config = QualityGateConfig(target_quality_score=75, hard_fail_threshold=45)

    assert quality_status_for_score(31, config) == "completed_with_major_issues"
    assert quality_status_for_score(52, config) == "completed_with_warnings"
    assert quality_status_for_score(78, config) == "completed"


def test_quality_timeline_checkpoint_contains_required_fields() -> None:
    config = QualityGateConfig()
    qa_report = {
        "scores": {"overall": 48, "source_grounding": 40, "claim_support": 40},
        "section_reports": [{
            "section_id": "s1",
            "section": "Sample",
            "issues": [{"validator": "code_validator", "message": "Code block failed validation."}],
            "scores": {"final_polish": 45},
        }],
    }

    checkpoint = build_quality_checkpoint(stage="sample_section", qa_report=qa_report, action="repair_prompt", config=config)

    assert checkpoint["stage"] == "sample_section"
    assert checkpoint["score"] == 48
    assert checkpoint["automatic_repair_required"] is True
    assert checkpoint["repair_recommendations"]


def test_repair_history_is_created() -> None:
    before = {"scores": {"overall": 42}, "section_reports": []}
    after = {"scores": {"overall": 67}, "section_reports": [], "repaired_sections": 2}

    history = build_repair_history(before_report=before, after_report=after, pass_name="repair_pass_1", action="repair_book")

    assert history["passes"][0]["before_score"] == 42
    assert history["passes"][0]["after_score"] == 67
    assert history["passes"][0]["score_delta"] == 25


def test_sample_first_mode_catches_broken_code_before_full_generation() -> None:
    contract = BookContract(
        domain="software",
        book_type="implementation_guide",
        implementation_heavy=True,
        code_expected=True,
        code_density="high",
    )
    sample = [{
        "id": "sample",
        "section": "Setup",
        "content": "Install the API and run the command, but no runnable code or configuration is shown.",
    }]

    _, qa_report = run_quality_repair_loop(sections=sample, contract=contract, max_passes=1)
    checkpoint = build_quality_checkpoint(
        stage="sample_section",
        qa_report=qa_report,
        action="repair_prompt",
        config=QualityGateConfig(sample_first=True),
    )

    assert checkpoint["automatic_repair_required"] is True
    assert any("code" in issue.lower() for issue in checkpoint["issues"])


def test_non_technical_book_does_not_trigger_code_repair_validator() -> None:
    contract = BookContract(domain="philosophy", code_expected=False, code_density="none")

    assert "code_validator" not in {validator.name for validator in select_validators(contract)}


def test_technical_book_triggers_code_repair_validator() -> None:
    contract = BookContract(
        domain="software",
        book_type="implementation_guide",
        implementation_heavy=True,
        code_expected=True,
        code_density="high",
    )

    assert "code_validator" in {validator.name for validator in select_validators(contract)}


def test_api_quality_options_are_accepted_by_gate_config() -> None:
    config = QualityGateConfig.from_payload({
        "target_quality_score": 82,
        "auto_repair": True,
        "sample_first": True,
        "quality_mode": "sample_first",
    })

    assert config.target_quality_score == 82
    assert config.auto_repair is True
    assert config.sample_first is True


def test_ui_status_maps_score_to_correct_label() -> None:
    assert quality_label(90) == "Excellent"
    assert quality_label(80) == "Good"
    assert quality_label(65) == "Usable draft"
    assert quality_label(50) == "Needs polish"
    assert quality_label(31) == "Major issues"


def test_pre_run_quality_estimate_flags_high_risk_requests() -> None:
    estimate = estimate_quality_risk({
        "topic": "Comprehensive current research-heavy project based Python implementation book",
        "audience": "Advanced engineers",
        "project_based": True,
        "content_density": {"code_density": "high"},
        "force_web_research": True,
    })

    assert estimate["risk"] == "High"
    assert "sample" in estimate["recommended"]


def test_weak_sections_are_reported_with_repair_actions() -> None:
    weak = weak_sections({
        "section_reports": [{
            "section_id": "s1",
            "section": "Weak section",
            "scores": {"final_polish": 40, "source_grounding": 50},
            "issues": [{"message": "Repeated template phrases reduce manuscript quality."}],
        }]
    })

    assert weak[0]["section_id"] == "s1"
    assert weak[0]["recommended_actions"]
