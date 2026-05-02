from __future__ import annotations

import json

from notes_synthesizer.schemas import CoverageSignal, SectionNoteArtifact, SynthesisStatus
from orchestration.parallel_section_pipeline import (
    ParallelSectionPipelineConfig,
    run_parallel_section_pipeline,
)
from writer.schemas import SectionDraft, WritingStatus


_CONTENT = "Clean draft with enough substance for reviewer validation. " * 4


class FakeNotesLLM:
    def generate_structured(self, *, system_prompt, user_prompt, response_model):
        return SectionNoteArtifact(
            section_id="chapter-1-section-intro",
            section_title="Intro",
            section_objective="Explain the intro.",
            synthesis_status=SynthesisStatus.READY,
            coverage_signal=CoverageSignal.SUFFICIENT,
            central_thesis="Intro thesis.",
            core_points=["Point one"],
            supporting_facts=[],
            examples=[],
            code_snippets=[],
            diagram_suggestions=[],
            implementation_steps=[],
            must_include_code=False,
            must_include_diagram=False,
            important_caveats=[],
            unresolved_gaps=[],
            recommended_flow=[],
            writer_guidance=[],
            allowed_citation_source_ids=[],
            source_trace=[],
        )


class FakeWriterLLM:
    def generate_structured(self, *, system_prompt, user_prompt, response_model):
        return SectionDraft(
            section_id="chapter-1-section-intro",
            section_title="Intro",
            content=_CONTENT,
            citations_used=[],
            diagram_hints=[],
            code_blocks_count=0,
            writing_status=WritingStatus.READY,
        )


class FakeReviewerClient:
    def generate(self, *, system_prompt, user_prompt):
        return json.dumps(
            {
                "section_id": "chapter-1-section-intro",
                "section_title": "Intro",
                "reviewed_content": _CONTENT,
                "review_status": "approved",
                "citations_used": [],
                "applied_changes_summary": [],
                "reviewer_warnings": [],
                "quality_scores": {
                    "practicality_score": 7,
                    "code_coverage_score": 7,
                    "learning_depth_score": 7,
                    "visual_richness_score": 7,
                },
            }
        )


def test_parallel_section_pipeline_processes_one_section() -> None:
    result = run_parallel_section_pipeline(
        research_bundle_payload=_research_bundle_payload(),
        book_title="Test Book",
        run_id="test-run",
        notes_llm=FakeNotesLLM(),
        writer_llm=FakeWriterLLM(),
        reviewer_llm_client=FakeReviewerClient(),
        config=ParallelSectionPipelineConfig(max_workers=2),
    )

    assert result.notes_state.output_bundle is not None
    assert result.writer_state.output_bundle is not None
    assert result.notes_state.output_bundle.total_sections == 1
    assert result.writer_state.output_bundle.total_sections == 1
    assert result.review_bundle.metadata.total_sections == 1
    assert result.summary["mode"] == "parallel_section_pipeline"
    assert result.summary["failed_sections"] == 0


def test_parallel_section_pipeline_supports_client_factories() -> None:
    result = run_parallel_section_pipeline(
        research_bundle_payload=_research_bundle_payload(),
        book_title="Test Book",
        run_id="test-run",
        notes_llm_factory=FakeNotesLLM,
        writer_llm_factory=FakeWriterLLM,
        reviewer_llm_client_factory=FakeReviewerClient,
        config=ParallelSectionPipelineConfig(max_workers=2),
    )

    assert result.review_bundle.metadata.total_sections == 1
    assert result.summary["failed_sections"] == 0


def _research_bundle_payload() -> dict:
    return {
        "book_plan": {
            "chapters": [
                {
                    "chapter_number": 1,
                    "title": "Chapter One",
                    "chapter_goal": "Goal",
                    "sections": [
                        {
                            "title": "Intro",
                            "goal": "Explain the intro.",
                            "key_questions": ["What is intro?"],
                            "content_requirements": {},
                        }
                    ],
                }
            ]
        },
        "chapters": [
            {
                "chapter_title": "Chapter One",
                "section_packets": [
                    {
                        "section_id": "chapter-1-section-intro",
                        "section_title": "Intro",
                        "objective": "Explain the intro.",
                        "chapter_id": "chapter-1-chapter-one",
                        "key_concepts": ["Intro"],
                        "evidence_items": [
                            {
                                "content": "Evidence",
                                "summary": "Evidence summary",
                            }
                        ],
                        "writing_guidance": [],
                        "open_questions": [],
                        "coverage_report": {"status": "sufficient"},
                        "source_references": [],
                    }
                ],
            }
        ],
    }
