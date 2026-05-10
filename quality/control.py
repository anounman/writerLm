from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DEFAULT_TARGET_QUALITY_SCORE = 75
DEFAULT_MAX_REPAIR_PASSES = 2
DEFAULT_HARD_FAIL_THRESHOLD = 45

QUALITY_STATUSES = {
    "running",
    "validating",
    "repairing",
    "completed",
    "completed_with_warnings",
    "completed_with_major_issues",
    "qa_failed",
    "needs_user_review",
}

SCORE_BREAKDOWN_LABELS = {
    "source_grounding": "Source grounding",
    "claim_support": "Claim support",
    "continuity": "Continuity",
    "audience_fit": "Audience fit",
    "domain_fit": "Project consistency",
    "code_validity": "Code validity",
    "visual_table_quality": "Diagram quality",
    "repetition_control": "Repetition/filler",
    "placeholder_cleanliness": "Placeholder cleanup",
    "final_polish": "Final polish",
}


@dataclass(frozen=True)
class QualityGateConfig:
    target_quality_score: int = DEFAULT_TARGET_QUALITY_SCORE
    max_repair_passes: int = DEFAULT_MAX_REPAIR_PASSES
    hard_fail_threshold: int = DEFAULT_HARD_FAIL_THRESHOLD
    auto_repair: bool = True
    sample_first: bool = False
    quality_mode: str = "full_auto_repair"

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "QualityGateConfig":
        payload = payload or {}
        target = _clamp_int(payload.get("target_quality_score"), DEFAULT_TARGET_QUALITY_SCORE, 0, 100)
        hard_fail = _clamp_int(payload.get("hard_fail_threshold"), DEFAULT_HARD_FAIL_THRESHOLD, 0, 100)
        max_passes = _clamp_int(payload.get("max_repair_passes"), DEFAULT_MAX_REPAIR_PASSES, 0, 5)
        return cls(
            target_quality_score=max(target, hard_fail),
            max_repair_passes=max_passes,
            hard_fail_threshold=hard_fail,
            auto_repair=bool(payload.get("auto_repair", True)),
            sample_first=bool(payload.get("sample_first", False)),
            quality_mode=str(payload.get("quality_mode") or "full_auto_repair"),
        )


def _clamp_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(low, min(high, number))


def quality_label(score: int | float | None) -> str:
    score = int(score or 0)
    if score >= 85:
        return "Excellent"
    if score >= 75:
        return "Good"
    if score >= 60:
        return "Usable draft"
    if score >= 45:
        return "Needs polish"
    return "Major issues"


def quality_status_for_score(
    score: int | float | None,
    config: QualityGateConfig,
    *,
    qa_passed: bool = True,
) -> str:
    score = int(score or 0)
    if score >= config.target_quality_score:
        return "completed"
    if score >= 60:
        return "completed_with_warnings"
    if score >= config.hard_fail_threshold:
        return "completed_with_major_issues"
    return "qa_failed" if not qa_passed else "needs_user_review"


def needs_automatic_repair(score: int | float | None, config: QualityGateConfig) -> bool:
    return bool(config.auto_repair and int(score or 0) < config.target_quality_score)


def qa_score(qa_report: dict[str, Any] | None) -> int:
    if not qa_report:
        return 0
    scores = qa_report.get("scores") or {}
    return int(scores.get("overall") or qa_report.get("overall_score") or 0)


def score_breakdown(qa_report: dict[str, Any] | None) -> dict[str, dict[str, int | str]]:
    scores = (qa_report or {}).get("scores") or {}
    breakdown: dict[str, dict[str, int | str]] = {}
    for key, label in SCORE_BREAKDOWN_LABELS.items():
        if key == "code_validity":
            value = _infer_code_validity(qa_report)
        else:
            value = int(scores.get(key) or scores.get(_fallback_score_key(key)) or 0)
        breakdown[key] = {"label": label, "score": max(0, min(100, int(value)))}
    return breakdown


def _fallback_score_key(key: str) -> str:
    return {"domain_fit": "project_consistency", "visual_table_quality": "diagram_quality"}.get(key, key)


def _infer_code_validity(qa_report: dict[str, Any] | None) -> int:
    if not qa_report:
        return 0
    section_reports = qa_report.get("section_reports") or []
    code_issues = 0
    for report in section_reports:
        for issue in report.get("issues") or []:
            validator = str(issue.get("validator") or "")
            message = str(issue.get("message") or "")
            if "code" in validator or "code" in message.lower() or "runnable" in message.lower():
                code_issues += 1
    if code_issues:
        return max(20, 90 - code_issues * 15)
    return int((qa_report.get("scores") or {}).get("example_quality") or 80)


def summarize_top_issues(qa_report: dict[str, Any] | None, *, limit: int = 5) -> list[str]:
    if not qa_report:
        return []
    issue_counts: dict[str, int] = {}
    for report in qa_report.get("section_reports") or []:
        for issue in report.get("issues") or []:
            message = str(issue.get("message") or "").strip()
            validator = str(issue.get("validator") or "quality").replace("_", " ")
            if not message:
                continue
            key = _issue_bucket(validator, message)
            issue_counts[key] = issue_counts.get(key, 0) + 1
    claim_summary = qa_report.get("claim_support_summary") or {}
    unsupported = int(claim_summary.get("unsupported") or 0) + int(claim_summary.get("contradicted") or 0)
    if unsupported:
        issue_counts["Source grounding is weak"] = issue_counts.get("Source grounding is weak", 0) + unsupported
    remaining = qa_report.get("remaining_risks") or []
    if remaining:
        issue_counts["Hard validation issues remain"] = issue_counts.get("Hard validation issues remain", 0) + len(remaining)
    return [
        f"{count} {label.lower()}." if count > 1 else f"{label}."
        for label, count in sorted(issue_counts.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]


def _issue_bucket(validator: str, message: str) -> str:
    text = f"{validator} {message}".lower()
    if "code" in text or "runnable" in text:
        return "Code blocks need validation"
    if "filler" in text or "template" in text or "repetition" in text:
        return "Sections contain generic filler"
    if "visual" in text or "diagram" in text or "table" in text:
        return "Diagrams or tables are too generic"
    if "audience" in text or "shallow" in text:
        return "Audience depth is off"
    if "source" in text or "claim" in text or "unsupported" in text:
        return "Source grounding is weak"
    if "domain" in text or "drift" in text or "project" in text:
        return "Project consistency is weak"
    if "placeholder" in text or "debug" in text:
        return "Placeholder cleanup is incomplete"
    return message.rstrip(".")


def build_quality_checkpoint(
    *,
    stage: str,
    qa_report: dict[str, Any] | None,
    action: str,
    config: QualityGateConfig,
    continue_generation: bool | None = None,
    automatic_repair_required: bool | None = None,
) -> dict[str, Any]:
    score = qa_score(qa_report)
    should_repair = needs_automatic_repair(score, config) if automatic_repair_required is None else automatic_repair_required
    should_continue = score >= config.hard_fail_threshold or not should_repair if continue_generation is None else continue_generation
    return {
        "stage": stage,
        "score": score,
        "label": quality_label(score),
        "issues": summarize_top_issues(qa_report),
        "repair_recommendations": repair_recommendations(qa_report),
        "continue_generation": bool(should_continue),
        "automatic_repair_required": bool(should_repair),
        "action": action,
        "score_breakdown": score_breakdown(qa_report),
    }


def repair_recommendations(qa_report: dict[str, Any] | None) -> list[str]:
    issues = " ".join(summarize_top_issues(qa_report, limit=10)).lower()
    recommendations: list[str] = []
    if "code" in issues:
        recommendations.append("Fix code blocks")
    if "diagram" in issues or "table" in issues:
        recommendations.append("Improve diagrams")
    if "source" in issues or "claim" in issues:
        recommendations.append("Strengthen source grounding")
    if "filler" in issues or "placeholder" in issues:
        recommendations.append("Regenerate weak sections")
    if "audience" in issues:
        recommendations.append("Adjust audience depth")
    if not recommendations:
        recommendations.append("Polish final manuscript")
    return recommendations


def weak_sections(qa_report: dict[str, Any] | None, *, threshold: int = 60) -> list[dict[str, Any]]:
    weak: list[dict[str, Any]] = []
    for report in (qa_report or {}).get("section_reports") or []:
        scores = report.get("scores") or {}
        section_score = round(sum(int(value or 0) for value in scores.values()) / max(1, len(scores)))
        if section_score < threshold or report.get("remaining_hard_errors"):
            weak.append({
                "section_id": report.get("section_id"),
                "section": report.get("section"),
                "score": section_score,
                "issues": [issue.get("message") for issue in report.get("issues") or [] if issue.get("message")],
                "recommended_actions": repair_recommendations({"section_reports": [report], "scores": scores}),
            })
    return weak


def showcase_readiness(qa_report: dict[str, Any] | None, config: QualityGateConfig) -> dict[str, Any]:
    score = qa_score(qa_report)
    issues = summarize_top_issues(qa_report)
    qa_passed = bool((qa_report or {}).get("qa_passed", True))
    return {
        "ready": score >= max(85, config.target_quality_score) and not issues,
        "score": score,
        "label": quality_label(score),
        "status": quality_status_for_score(score, config, qa_passed=qa_passed),
        "blocking_issues": issues,
        "recommendation": (
            "Showcase-ready."
            if score >= 85 and not issues
            else "Run Polish for showcase before presenting this book."
            if score >= config.target_quality_score
            else "Run Repair book or targeted repair actions before export."
        ),
    }


def build_repair_history(
    *,
    before_report: dict[str, Any] | None,
    after_report: dict[str, Any],
    pass_name: str,
    action: str,
) -> dict[str, Any]:
    before_score = qa_score(before_report)
    after_score = qa_score(after_report)
    return {
        "passes": [
            {
                "pass": pass_name,
                "action": action,
                "before_score": before_score,
                "after_score": after_score,
                "score_delta": after_score - before_score,
                "issues_after": summarize_top_issues(after_report),
                "repaired_sections": after_report.get("repaired_sections", 0),
            }
        ]
    }


def estimate_quality_risk(planner_input: dict[str, Any]) -> dict[str, Any]:
    topic = str(planner_input.get("topic") or "")
    audience = str(planner_input.get("audience") or "")
    goals = " ".join(str(goal) for goal in planner_input.get("goals") or [])
    text = f"{topic} {audience} {goals}".lower()
    density = planner_input.get("content_density") or {}
    code_density = str(density.get("code_density") or planner_input.get("code_density") or "none")
    long_book = any(token in text for token in ("comprehensive", "complete", "full", "masterclass", "advanced"))
    research_heavy = bool(planner_input.get("force_web_research") or planner_input.get("urls") or any(token in text for token in ("research", "current", "evidence", "history", "case study")))
    vague = len(topic.split()) < 5 and len(goals.split()) < 10
    project_based = bool(planner_input.get("project_based") or "project" in text)

    factors: list[str] = []
    score = 0
    if code_density == "high":
        score += 30
        factors.append("High code density raises code validation risk.")
    elif code_density == "medium":
        score += 18
        factors.append("Medium code density needs code QA.")
    if long_book:
        score += 20
        factors.append("Long full-profile books have higher continuity risk.")
    if research_heavy:
        score += 20
        factors.append("Research-heavy topics need stronger source grounding.")
    if project_based:
        score += 18
        factors.append("Project-based books need project consistency checks.")
    if vague:
        score += 16
        factors.append("The prompt is broad, so coherence risk is higher.")

    level = "High" if score >= 55 else "Medium" if score >= 30 else "Low"
    return {
        "risk": level,
        "score": min(100, score),
        "factors": factors or ["Request is specific enough for normal quality controls."],
        "recommended": "generate a sample chapter first" if level == "High" else "full generation + auto-repair",
        "expected_runtime": "2-3 hours" if long_book or level == "High" else "45-120 minutes",
        "recommended_quality_mode": "full + repair" if level != "Low" else "standard QA",
    }
