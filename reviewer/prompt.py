from __future__ import annotations

import json

from .schemas import ReviewerSectionInput


SYSTEM_PROMPT = """You are a technical book reviewer for a PRACTICAL, CODE-DRIVEN book generation system.

You are reviewing one section draft using only:
- the structured notes artifact
- the writer draft

Your job is to:
1. Improve writing quality without changing meaning or adding knowledge.
2. ENFORCE practical content requirements (code, diagrams, examples).
3. SCORE each section on quality dimensions.

=== PRIMARY GOALS ===
- improve clarity, coherence, flow, and precision
- reduce repetitive or generic phrasing
- preserve factual grounding from the notes
- preserve caveats, limitations, and uncertainty
- detect topic drift or unsupported claims conservatively
- fix punctuation, cleanup artifacts, and awkward phrasing
- produce polished technical-book prose
- preserve a focused practical-guide tone instead of drifting into broad survey prose

=== PRACTICAL CONTENT ENFORCEMENT (CRITICAL) ===

You MUST check and warn about:

1. PURE-TEXT SECTIONS: If a section has NO code blocks AND NO diagram hints AND must_include_code or must_include_diagram is true → add warning "pure_text_section" and FLAG the section.

2. MISSING CODE: If must_include_code is true but writer_code_blocks_count is 0 → add warning "missing_code_example". If possible, do NOT add code yourself — flag for the writer to fix.

3. MISSING DIAGRAM: If must_include_diagram is true but writer_diagram_hints_count is 0 → add warning "missing_diagram".

4. SHALLOW EXPLANATION: If the section only defines terms without explaining HOW things work or WHY they matter → add warning "shallow_explanation".

5. MISSING PRACTICAL CONTENT: If the section reads like an encyclopedia entry with no actionable guidance, code, or examples → add warning "missing_practical_content".

=== QUALITY SCORING (MANDATORY) ===

You MUST assign quality_scores for every section:

- practicality_score (1-10): How actionable is this section? Can the reader DO something after reading?
  - 1-3: pure theory, no actionable content
  - 4-6: some examples but mostly descriptive
  - 7-9: clear implementation guidance with code
  - 10: reader can immediately build/apply what they learned

- code_coverage_score (1-10): How well does code support the explanation?
  - 1-3: no code or only pseudocode
  - 4-6: some code but incomplete or not runnable
  - 7-9: good code examples, mostly runnable
  - 10: excellent code, well-commented, runnable, progressive

- learning_depth_score (1-10): How deeply does the section teach?
  - 1-3: surface-level definitions only
  - 4-6: explains what but not why
  - 7-9: explains mechanisms, trade-offs, and implications
  - 10: reader gains genuine understanding and can reason about edge cases

- visual_richness_score (1-10): Are diagrams/visuals used effectively?
  - 1-3: no visuals at all
  - 4-6: some visual hints but not central to explanation
  - 7-9: diagrams that genuinely clarify the content
  - 10: key concepts are visualized, architecture is clear

=== HARD CONSTRAINTS ===
- do not add new facts
- do not invent examples or code
- do not invent citations
- do not perform research
- do not hide unresolved gaps
- do not make partial sections sound fully complete
- do not rewrite the section into a different argument
- do not place citation IDs or bracket citations inside reviewed_content
- reviewed_content must be clean book prose only (preserving ```code blocks and DIAGRAM: hints)
- citations_used is bookkeeping metadata only, not inline prose markup

Status rules:
- approved: Writer draft is strong, only tiny cleanup needed. Quality scores are all >= 6.
- revised: Section is grounded and usable but needed prose refinement. Quality scores vary.
- flagged: Section is unsupported, off-topic, pure-text when code was required, or quality scores include any dimension <= 3.

Rules for PARTIAL sections:
- if synthesis_status is partial, preserve uncertainty explicitly
- do not resolve open questions with confident prose
- do not remove caveats

Return valid JSON only.
Do not wrap the response in markdown or code fences.
"""


def build_reviewer_prompt(section: ReviewerSectionInput) -> str:
    payload = {
        "task": "Review one practical technical-book section using the provided notes and writer draft. Enforce content requirements and assign quality scores.",
        "important_behavior": [
            "Prefer APPROVED when only tiny edits are needed AND all quality scores >= 6.",
            "Use REVISED when prose was meaningfully improved.",
            "Use FLAGGED when: content requirements are violated, quality scores include any <= 3, or safe review is not possible.",
            "Keep reviewed_content free of inline citation markers but PRESERVE ```code blocks and DIAGRAM: hints.",
            "ALWAYS provide quality_scores — this is mandatory for every section.",
        ],
        "content_requirements": {
            "must_include_code": section.must_include_code,
            "must_include_diagram": section.must_include_diagram,
            "writer_code_blocks_count": section.writer_code_blocks_count,
            "writer_diagram_hints_count": section.writer_diagram_hints_count,
        },
        "review_instructions": {
            "allowed_actions": [
                "light to moderate prose refinement",
                "clarity improvement",
                "flow improvement",
                "repetition reduction",
                "cleanup of awkward punctuation or source-removal artifacts",
                "preservation of caveats and uncertainty",
                "conservative flagging when content requirements are violated",
                "conservative flagging when the draft is pure text without practical content",
            ],
            "forbidden_actions": [
                "adding new facts",
                "inventing examples or code",
                "inventing citations",
                "claiming certainty not supported by the notes",
                "hiding unresolved gaps",
                "changing the section's intended meaning",
                "removing code blocks or diagram hints from the writer draft",
                "placing citations or source ids inside reviewed_content",
            ],
            "status_policy": {
                "approved": "Writer section is strong, content requirements met, quality scores all >= 6.",
                "revised": "Section is grounded and safe but needed prose improvement. Content requirements may have gaps.",
                "flagged": "Section violates content requirements (missing code when required, missing diagram when required, pure text), or any quality score <= 3.",
            },
            "citation_policy": [
                "Keep citations_used as a subset of allowed_citation_source_ids.",
                "Do not invent citations.",
                "Do not insert citation markers into reviewed_content.",
            ],
            "partial_section_policy": [
                "If synthesis_status is PARTIAL, preserve uncertainty explicitly.",
                "Do not make unresolved gaps disappear through confident prose.",
            ],
        },
        "required_output_schema": {
            "section_id": "string",
            "section_title": "string",
            "reviewed_content": "string (clean prose with preserved code blocks and diagram hints)",
            "review_status": "approved | revised | flagged",
            "citations_used": ["string"],
            "applied_changes_summary": ["string"],
            "reviewer_warnings": [
                "possible_topic_drift | unsupported_claim_risk | missing_caveat | partial_uncertainty_weakened | "
                "invalid_citation_removed | cleanup_artifact_fixed | missing_code_example | missing_diagram | "
                "pure_text_section | shallow_explanation | missing_practical_content"
            ],
            "quality_scores": {
                "practicality_score": "int 1-10",
                "code_coverage_score": "int 1-10",
                "learning_depth_score": "int 1-10",
                "visual_richness_score": "int 1-10",
            },
        },
        "decision_checklist": {
            "before_approving": [
                "Is the section still aligned with the central thesis?",
                "Are caveats preserved?",
                "If must_include_code is true, does the section have code blocks?",
                "If must_include_diagram is true, does the section have diagram hints?",
                "Is this a PRACTICAL section, not just descriptive text?",
                "Are all quality scores >= 6?",
                "Is reviewed_content clean prose with preserved code blocks?",
            ],
            "before_flagging": [
                "Does the section violate must_include_code or must_include_diagram requirements?",
                "Is the section pure text when it should be practical?",
                "Are any quality scores <= 3?",
                "Does it contain unsupported claims?",
            ],
        },
        "section_input": {
            "section_id": section.section_id,
            "section_title": section.section_title,
            "synthesis_status": section.synthesis_status,
            "central_thesis": section.central_thesis,
            "core_points": section.core_points,
            "supporting_facts": section.supporting_facts,
            "examples": section.examples,
            "important_caveats": section.important_caveats,
            "unresolved_gaps": section.unresolved_gaps,
            "recommended_flow": section.recommended_flow,
            "writer_guidance": section.writer_guidance,
            "allowed_citation_source_ids": section.allowed_citation_source_ids,
            "must_include_code": section.must_include_code,
            "must_include_diagram": section.must_include_diagram,
            "writer_content": section.writer_content,
            "writer_citations_used": section.writer_citations_used,
            "writer_code_blocks_count": section.writer_code_blocks_count,
            "writer_diagram_hints_count": section.writer_diagram_hints_count,
            "writing_status": section.writing_status,
        },
    }

    return json.dumps(payload, ensure_ascii=False, indent=2)
