from __future__ import annotations

import json
import sys
from pathlib import Path


def load_report(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def compare_reports(baseline: dict, candidate: dict) -> dict:
    baseline_score = float(baseline.get("gate", {}).get("overall_score", 0))
    candidate_score = float(candidate.get("gate", {}).get("overall_score", 0))
    delta = round(candidate_score - baseline_score, 1)

    baseline_critical = int(baseline.get("gate", {}).get("critical_issues", 0))
    candidate_critical = int(candidate.get("gate", {}).get("critical_issues", 0))

    return {
        "baseline_profile": baseline.get("profile"),
        "candidate_profile": candidate.get("profile"),
        "baseline_score": baseline_score,
        "candidate_score": candidate_score,
        "score_delta": delta,
        "baseline_critical_issues": baseline_critical,
        "candidate_critical_issues": candidate_critical,
        "critical_issue_delta": candidate_critical - baseline_critical,
        "full_clearly_better": delta >= 8 and candidate_critical <= baseline_critical,
    }


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if len(args) != 2:
        print("Usage: python -m orchestration.compare_quality_reports BASELINE.json CANDIDATE.json")
        return 1

    baseline = load_report(Path(args[0]))
    candidate = load_report(Path(args[1]))
    print(json.dumps(compare_reports(baseline, candidate), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

