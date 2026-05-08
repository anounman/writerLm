from __future__ import annotations

from planner_agent.schemas import BookPlan, ChapterPlan, SectionContentRequirements, SectionPlan
from notes_synthesizer.selectors import build_section_synthesis_input
from orchestration.compare_quality_reports import compare_reports
from orchestration.quality_gate import run_quality_gate
from reviewer.schemas import (
    QualityScores,
    ReviewBundle,
    ReviewBundleMetadata,
    ReviewerSectionInput,
    ReviewerSectionOutput,
    ReviewerSectionResult,
    ReviewStatus,
)


def _book_plan() -> BookPlan:
    return BookPlan(
        title="Advanced AWS Delivery Guide",
        audience="advanced DevOps engineers",
        tone="direct",
        depth="advanced",
        running_project="One production deployment platform",
        chapters=[
            ChapterPlan(
                chapter_number=1,
                title="Foundation",
                chapter_goal="Establish the platform",
                sections=[
                    SectionPlan(
                        title="Platform Setup",
                        goal="Set up the first infrastructure slice.",
                        estimated_words=900,
                        content_requirements=SectionContentRequirements(must_include_code=True, must_include_diagram=True),
                    )
                ],
            )
        ],
    )


def _review_bundle(content: str) -> ReviewBundle:
    return ReviewBundle(
        metadata=ReviewBundleMetadata(
            total_sections=1,
            approved_sections=1,
            revised_sections=0,
            flagged_sections=0,
        ),
        sections=[
            ReviewerSectionResult(
                section_input=ReviewerSectionInput(
                    section_id="chapter-1-section-platform-setup",
                    section_title="Platform Setup",
                    synthesis_status="ready",
                    central_thesis="Build the first production stack.",
                    core_points=["Use a single stack strategy."],
                    supporting_facts=[],
                    examples=[],
                    important_caveats=[],
                    unresolved_gaps=[],
                    recommended_flow=[],
                    writer_guidance=[],
                    allowed_citation_source_ids=["src-1"],
                    must_include_code=True,
                    must_include_diagram=True,
                    writer_content=content,
                    writer_citations_used=[],
                    writer_code_blocks_count=1,
                    writer_diagram_hints_count=1,
                    writing_status="ready",
                ),
                section_output=ReviewerSectionOutput(
                    section_id="chapter-1-section-platform-setup",
                    section_title="Platform Setup",
                    reviewed_content=content,
                    review_status=ReviewStatus.APPROVED,
                    citations_used=["src-1"],
                    applied_changes_summary=[],
                    reviewer_warnings=[],
                    quality_scores=QualityScores(
                        practicality_score=8,
                        code_coverage_score=8,
                        learning_depth_score=8,
                        visual_richness_score=8,
                    ),
                ),
            )
        ],
    )


def test_quality_gate_repairs_placeholders_and_marks_invalid_code() -> None:
    content = """
## Platform Setup

TODO: fill this in later

```python
def broken(
    return 42
```

DIAGRAM: [architecture] - this diagram should illustrate the stack
Elements: Placeholder, Result
""".strip()
    result = run_quality_gate(
        book_plan=_book_plan(),
        review_bundle=_review_bundle(content),
        research_bundle_payload={
            "chapters": [
                {
                    "section_packets": [
                        {
                            "section_id": "chapter-1-section-platform-setup",
                            "source_references": [
                                {"source_id": "src-1", "title": "AWS Docs", "url": "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-s3-bucket.html"}
                            ],
                        }
                    ]
                }
            ]
        },
        run_dir=None,
        profile="full",
        strict_full=False,
    )

    repaired = result.review_bundle.sections[0].section_output.reviewed_content
    assert "TODO" not in repaired
    assert "Conceptual example only." in repaired
    assert result.report["gate"]["critical_issues"] >= 1


def test_compare_reports_detects_clear_full_profile_improvement() -> None:
    baseline = {"profile": "budget", "gate": {"overall_score": 58, "critical_issues": 3}}
    candidate = {"profile": "full", "gate": {"overall_score": 72, "critical_issues": 1}}
    comparison = compare_reports(baseline, candidate)
    assert comparison["full_clearly_better"] is True
    assert comparison["score_delta"] == 14.0


def test_quality_gate_flags_missing_required_code_and_diagram() -> None:
    result = run_quality_gate(
        book_plan=_book_plan(),
        review_bundle=_review_bundle("## Platform Setup\n\nA prose-only section with no visual or runnable example."),
        research_bundle_payload=None,
        run_dir=None,
        profile="full",
        strict_full=False,
    )
    categories = result.report["gate"]["issue_count_by_category"]
    assert categories["code_validity"] >= 1
    assert categories["diagram_quality"] >= 1


def test_notes_synthesis_keeps_research_evidence_content() -> None:
    section_input = build_section_synthesis_input(
        planner_section={
            "section_id": "chapter-1-section-grounding",
            "section_title": "Grounding",
            "section_objective": "Use researched evidence.",
            "content_requirements": {},
        },
        research_section={
            "section_id": "chapter-1-section-grounding",
            "section_title": "Grounding",
            "section_objective": "Use researched evidence.",
            "evidence_items": [
                {
                    "evidence_id": "ev-1",
                    "source_id": "src-1",
                    "content": "Primary evidence text that must reach notes synthesis.",
                    "relevance_note": "Supports the section's main claim.",
                }
            ],
            "source_references": [{"source_id": "src-1", "title": "Docs", "url": "https://docs.python.org/3/"}],
        },
    )
    assert any("Primary evidence text" in item for item in section_input.evidence_items)
