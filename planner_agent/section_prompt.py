import json

from schemas import UserBookRequest, PlanningContext
from outline_schemas import ChapterOutlineItem
from section_schemas import ChapterSectionPlan


SECTION_PLANNER_SYSTEM_PROMPT = """
You are a section-planning engine.

Your task is to expand exactly one chapter into a clean section plan.

STRICT OUTPUT RULES:
- Return ONLY valid JSON.
- Do NOT return markdown.
- Do NOT wrap the JSON in code fences.
- Do NOT add explanations, notes, or extra text.
- Do NOT return a partial answer.
- The JSON must be complete and parseable.

PLANNING RULES:
- Expand exactly one chapter.
- The output must contain 3 to 6 sections.
- Each section must focus on one clear idea.
- Avoid overlap and repetition between sections.
- Keep section titles specific and concrete.
- Keep sections bounded so they can be written in one pass.
- estimated_words should usually stay between 200 and 1200.
- Each section must have a clear teaching goal.
- Each section must include key questions that guide later writing.

IMPORTANT:
- Do NOT create other chapters.
- Do NOT redesign the whole book.
- Do NOT add subsections yet.
- Only expand the given chapter into sections.
"""


def build_section_planner_prompt(
    request: UserBookRequest,
    context: PlanningContext,
    chapter: ChapterOutlineItem,
) -> str:
    schema_hint = {
        "chapter_number": 1,
        "chapter_title": "string",
        "chapter_goal": "string",
        "sections": [
            {
                "title": "string",
                "goal": "string",
                "key_questions": ["string"],
                "estimated_words": 500
            }
        ]
    }

    max_section_words_instruction = (
        f"- No section may exceed {request.max_section_words} estimated words."
        if request.max_section_words is not None
        else "- Choose appropriate estimated_words for each section, usually between 200 and 1200."
    )

    return f"""
Expand exactly one chapter into a section plan.

USER INPUT
Topic: {request.topic}
Audience: {request.audience}
Tone: {request.tone}
Depth: {request.depth}

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

CHAPTER TO EXPAND
Chapter number: {chapter.chapter_number}
Chapter title: {chapter.title}
Chapter goal: {chapter.chapter_goal}

IMPORTANT CONSTRAINTS:
{max_section_words_instruction}
- Create 3 to 6 sections for this chapter.
- Each section must support the chapter goal.
- Each section must focus on one clear idea only.
- Avoid vague titles unless they are clearly scoped.
- Avoid repetition between sections.
- Keep the order pedagogical and easy to follow.
- Every section must have title, goal, key_questions, and estimated_words.
- Return only this chapter's section plan.
- Do not create sections for any other chapter.

Before finalizing, silently check:
1. The JSON is complete.
2. The output expands exactly this chapter.
3. There are 3 to 6 sections.
4. Every section has title, goal, key_questions, and estimated_words.
5. The response contains only JSON.
6. The sections support the chapter goal.

Return ONLY JSON in this exact structure:
{json.dumps(schema_hint, indent=2)}
"""