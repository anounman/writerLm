
import json
from schemas import UserBookRequest, PlanningContext
from outline_schemas import ChapterOutlinePlan


CHAPTER_OUTLINE_SYSTEM_PROMPT = """
You are a chapter-outline planning engine.

Your task is to create only the high-level chapter outline for a book.

STRICT OUTPUT RULES:
- Return ONLY valid JSON.
- Do NOT return markdown.
- Do NOT wrap the JSON in code fences.
- Do NOT add explanations or extra text.
- Do NOT return a partial answer.

PLANNING RULES:
- Decide an appropriate number of chapters for the topic, audience, and depth.
- The total number of chapters must be between 3 and 20 unless the user explicitly provides chapter_count.
- Number chapters sequentially starting from 1.
- Each chapter must represent one major theme or step in the learning journey.
- Keep chapter titles specific and concrete.
- Avoid overlap and repetition across chapters.
- Order chapters from foundations to more advanced or applied material.
- Each chapter_goal should clearly describe what that chapter is meant to achieve.

IMPORTANT:
- Do NOT generate sections.
- Do NOT generate subsections.
- Only generate the book-level outline.
"""


def build_chapter_outline_prompt(
    request: UserBookRequest,
    context: PlanningContext,
) -> str:
    schema_hint = {
        "title": "string",
        "audience": "string",
        "tone": "string",
        "depth": "string",
        "chapters": [
            {
                "chapter_number": 1,
                "title": "string",
                "chapter_goal": "string"
            }
        ]
    }

    chapter_count_instruction = (
        f"- Use exactly {request.chapter_count} chapters."
        if request.chapter_count is not None
        else "- Choose the total number of chapters yourself."
    )

    return f"""
Create a high-level chapter outline for a book.

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

Possible structure options:
{json.dumps(context.structure_options, indent=2)}

Evidence or example directions:
{json.dumps(context.evidence_examples, indent=2)}

Additional notes:
{json.dumps(context.notes, indent=2)}

IMPORTANT CONSTRAINTS:
{chapter_count_instruction}
- The total number of chapters must be between 3 and 20.
- Chapters must be ordered logically.
- Chapters must cover the major themes without unnecessary repetition.
- Use the planning context intelligently.
- Respect the scope boundaries.
- Return the FULL outline, not just the first chapter or first few chapters.
- Ensure chapter_number values are sequential: 1, 2, 3, ...

Before finalizing, silently check:
1. The JSON is complete.
2. The number of chapters is appropriate.
3. The chapter order is logical.
4. The outline covers the major themes.
5. The response contains only JSON.
6. No sections or subsections are included.

Return ONLY JSON in this exact structure:
{json.dumps(schema_hint, indent=2)}
"""