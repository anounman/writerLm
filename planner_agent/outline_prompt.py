import json

from planner_agent.schemas import PlanningContext, UserBookRequest


CHAPTER_OUTLINE_SYSTEM_PROMPT = """
You are a chapter-outline planning engine for a multi-stage book generation system.

Your task is to create only the high-level chapter outline for a book.

STRICT OUTPUT RULES:
- Return ONLY valid JSON.
- Do NOT return markdown.
- Do NOT wrap the JSON in code fences.
- Do NOT add explanations or extra text.
- Do NOT return a partial answer.

CORE DESIGN PRINCIPLE:
Infer the right book form from the user's intent and sources.
The result may be a theory-first textbook, course companion, practice workbook,
implementation guide, reference handbook, conceptual guide, or exam-prep book.
Do not force every topic into a software, coding, or project-building structure.

PLANNING RULES:
- First infer the correct book archetype from the request:
  - theory-first textbook
  - theory plus worked examples
  - practice workbook or exam-prep guide
  - project/implementation guide
  - conceptual guide
  - reference handbook only if the user explicitly asks for broad coverage
- Uploaded source documents are authoritative when present. Use them to disambiguate acronyms, course names, terminology, and curriculum boundaries.
- Treat explicit user goals as hard scope boundaries, not optional inspiration.
- Keep chapter titles concrete, specific, and appropriate to the book type.
- Avoid overlap and repetition across chapters.
- Each chapter_goal should clearly describe what the reader understands, solves, applies, builds, or can do by the end.
- project_milestone may be a learning outcome, problem-solving milestone, or built artifact depending on book type.

SOURCE-AWARE PLANNING (CRITICAL):
- If uploaded sources are present, treat them as the primary domain signal.
- If web results conflict with uploaded sources, follow the uploaded sources.
- Build original explanations and examples; do not copy source exercises verbatim.
- When source exercise sheets are present, infer question patterns and include source-inspired worked examples/practice.

PROJECT-BASED PLANNING:
- When project_based is true, ALL chapters must contribute to building a single evolving project.
- The running_project field describes what the reader is building across the entire book.
- Chapter sequence must follow a BUILD progression:
  1. Setup & foundations (just enough to start coding)
  2. Core implementation (build the basic version)
  3. Enhancement & iteration (add features, improve quality)
  4. Testing & debugging (make it robust)
  5. Polish & extend (production-ready or next steps)
- Do NOT front-load theory. Introduce concepts WHEN the reader needs them to build the next feature.
- Each chapter_goal must reference what new capability is added to the running project.

FOCUSED-BEGINNER RULES:
- When the request is beginner-focused and implementation-oriented, plan a focused guide, not a comprehensive handbook.
- Include only the minimum background needed to understand and build the requested system.
- Prefer early practical payoff over long theoretical runways.
- Do NOT add advanced production, governance, compliance, ethics, future trends, broad case-study collections, or research-frontier chapters unless explicitly requested.
- Do NOT create broad standalone survey chapters just because they are common in related books.

IMPORTANT:
- Do NOT generate sections.
- Do NOT generate subsections.
- Only generate the book-level outline.
""".strip()


def build_chapter_outline_prompt(
    request: UserBookRequest,
    context: PlanningContext,
) -> str:
    schema_hint = {
        "title": "string",
        "audience": "string",
        "tone": "string",
        "depth": "string",
        "running_project": "string or null (description of the evolving project)",
        "chapters": [
            {
                "chapter_number": 1,
                "title": "string",
                "chapter_goal": "string (what the reader understands, solves, applies, builds, or achieves)",
                "project_milestone": "string or null (learning/practice milestone, or what is working by end of chapter for project books)",
            }
        ],
    }

    chapter_min, chapter_max = request.preferred_chapter_range
    chapter_count_instruction = (
        f"- Use exactly {request.chapter_count} chapters."
        if request.chapter_count is not None
        else (
            f"- Target {chapter_min} to {chapter_max} chapters for this request profile."
            if request.is_focused_beginner_guide
            else f"- Choose an appropriate chapter count, usually between {chapter_min} and {chapter_max}."
        )
    )

    archetype = (
        "focused beginner implementation guide"
        if request.is_focused_beginner_guide
        else request.effective_book_type.replace("_", " ")
    )

    banned_chapters_instruction = (
        "- Forbidden chapter families unless the user explicitly asked for them: "
        "broad LLM survey chapters, production scaling/ops, compliance/governance, "
        "ethics/legal/societal coverage, research frontiers, future directions, "
        "and broad case-study collections."
        if request.is_focused_beginner_guide
        else "- Avoid scope drift into unrelated or weakly related topics."
    )

    practical_payoff_instruction = (
        "- Ensure a practical implementation or hands-on architecture chapter appears by Chapter "
        f"{request.preferred_practical_payoff_latest_chapter} at the latest."
        if request.preferred_practical_payoff_latest_chapter is not None
        else "- Keep the chapter sequence pedagogical and aligned with the requested theory/practice balance."
    )

    project_instruction = ""
    if request.project_based:
        running_desc = request.running_project_description or f"a practical {request.topic} system"
        project_instruction = f"""
PROJECT-BASED STRUCTURE (MANDATORY):
- This book teaches through building: {running_desc}
- Set running_project to a one-sentence description of what the reader builds across all chapters.
- Each chapter MUST advance the running project. chapter_goal must describe what NEW capability is added.
- Each chapter MUST have a project_milestone describing what works by chapter end.
- Chapter 1 should get the reader to a minimal working version FAST (not pure theory).
- Theory/background is introduced ONLY when the reader needs it for the next build step.
- The progression must be: setup → core build → enhance → debug/test → polish.
"""
    else:
        project_instruction = """
- running_project may be null for non-project-based books.
- project_milestone is optional. When useful, use it as a learning outcome, problem-solving checkpoint, or practice milestone.
"""

    content_density = request.content_density
    density_instruction = f"""
CONTENT DENSITY REQUIREMENTS:
- Code density target: {content_density.code_density} ({"code in every section when this is a programming/software topic" if content_density.code_density == "high" else "code in most implementation sections when the topic requires code" if content_density.code_density == "medium" else "code only where the subject genuinely requires it"})
- Example density target: {content_density.example_density} ({"concrete example in every section" if content_density.example_density == "high" else "examples in most sections" if content_density.example_density == "medium" else "examples where helpful"})
- Diagram density target: {content_density.diagram_density} ({"diagram/visual in every section" if content_density.diagram_density == "high" else "at least one diagram per chapter" if content_density.diagram_density == "medium" else "diagrams for key concepts only"})
- Plan chapters that ENABLE these density targets without changing the subject. For mathematics, examples mean worked problems; diagrams mean visual intuition/graphs/tables, not software architecture.
"""

    goals_json = json.dumps(request.normalized_goals, indent=2)

    return f"""
Create a high-level chapter outline for a book.

USER INPUT
Topic: {request.topic}
Audience: {request.audience}
Tone: {request.tone}
Depth: {request.depth}
Book type: {request.book_type} (effective: {request.effective_book_type})
Theory/practice balance: {request.theory_practice_balance} (effective: {request.effective_theory_practice_balance})
Pedagogy style: {request.pedagogy_style}
Source usage: {request.source_usage}
Exercise strategy: {request.exercise_strategy}
Language request: {request.language_request if request.language_request else "Not specified — default to English."}
Goals:
{goals_json}

REQUEST PROFILE
Book archetype: {archetype}
Project-based: {str(request.project_based).lower()}
Focused beginner practical guide: {str(request.is_focused_beginner_guide).lower()}
Practical focus: {str(request.is_practical_focused).lower()}
Beginner focus: {str(request.is_beginner_focused).lower()}
Comprehensive coverage requested: {str(request.wants_comprehensive_coverage).lower()}
{project_instruction}
{density_instruction}

PLANNING CONTEXT
Book purpose: {context.book_purpose}
Core idea: {context.core_idea}

Audience needs:
{json.dumps(context.audience_needs, indent=2)}

Main questions the book should answer:
{json.dumps(context.main_questions, indent=2)}

Scope should include:
{json.dumps(context.scope_includes, indent=2)}

Scope should exclude:
{json.dumps(context.scope_excludes, indent=2)}

Key themes:
{json.dumps(context.key_themes, indent=2)}

Sequence logic:
{json.dumps(context.sequence_logic, indent=2)}

Possible structure options:
{json.dumps(context.structure_options, indent=2)}

Evidence or example directions:
{json.dumps(context.evidence_examples, indent=2)}

Additional notes:
{json.dumps(context.notes, indent=2)}

UPLOADED SOURCE CONTEXT:
{json.dumps(request.source_context.model_dump(mode="json") if request.source_context else {}, indent=2)}

IMPORTANT CONSTRAINTS:
{chapter_count_instruction}
- The total number of chapters must be between 3 and 20.
{banned_chapters_instruction}
{practical_payoff_instruction}
- Chapters must be ordered logically.
- Chapters must cover the user goals without unnecessary breadth.
- Prefer concrete chapter titles. For implementation guides, action verbs such as "Build" or "Implement" are good. For textbooks, titles such as "Linear Systems and Rank" or "Differentiability in Several Variables" are better than fake build verbs.
- Do not create software/project chapters unless project_based is true, book_type is implementation_guide, or the user's topic genuinely requires implementation.
- For math/course books, prefer definitions, theorem/proof intuition, worked examples, common mistakes, and practice sections.
- For German/theory-heavy style, front-load rigorous conceptual structure before practice.
- For Indian theory-then-examples style, introduce theory and then show detailed worked examples and practice patterns.
- Respect the scope boundaries strictly.
- Return the FULL outline, not just the first chapter or first few chapters.
- Ensure chapter_number values are sequential: 1, 2, 3, ...
{f"- LANGUAGE INSTRUCTION (MANDATORY): {request.language_request}" if request.language_request else ""}

Before finalizing, silently check:
1. The JSON is complete.
2. The number of chapters matches the request profile.
3. The outline matches the effective book type and theory/practice balance.
4. The chapter order reaches practical payoff early enough.
5. The outline covers the user goals without drifting into excluded chapter families.
6. Every chapter has a concrete project_milestone if project_based is true.
7. Chapter titles fit the domain and do not force a coding/project frame.
8. The response contains only JSON.
9. No sections or subsections are included.

Return ONLY JSON in this exact structure:
{json.dumps(schema_hint, indent=2)}
""".strip()
