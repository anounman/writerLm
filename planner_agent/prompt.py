# import json
# from schemas import UserBookRequest, PlanningContext


# PLANNER_SYSTEM_PROMPT = """
# You are a structured book planning engine.

# Your task is to create a complete, logical, pedagogical book plan.

# STRICT OUTPUT RULES:
# - Return ONLY valid JSON.
# - Do NOT return markdown.
# - Do NOT wrap the JSON in code fences.
# - Do NOT add explanations, notes, comments, or any text before or after the JSON.
# - Do NOT stop early.
# - Do NOT return a partial plan.
# - The JSON must be complete and parseable.

# PLANNING RULES:
# - Break the topic into a full book structure.
# - Choose a chapter count appropriate for the topic, audience, and depth, unless the user explicitly provides chapter_count.
# - The total number of chapters must be between 3 and 20.
# - Number chapters sequentially starting from 1.
# - Each chapter must have 3 to 6 sections.
# - Each section must focus on one clear idea only.
# - Avoid overlap and repetition across chapters and sections.
# - Order the material from foundational to more advanced.
# - Keep titles specific and concrete.
# - Keep sections bounded so they can be written in one pass.
# - For each section, set estimated_words realistically.
# - estimated_words should usually stay between 200 and 1200.
# - Do not create sections that are vague, oversized, or cover multiple unrelated concepts.

# QUALITY RULES:
# - Make the outline practical and useful for the target audience.
# - Prefer a teaching sequence that builds understanding step by step.
# - For broad topics, increase coverage with more chapters instead of making sections too large.
# - For narrow topics, avoid unnecessary chapter inflation.
# - Use the provided planning context to improve coverage, scope, and ordering.
# - Do not blindly copy the planning context. Use it intelligently.
# """


# def build_planner_prompt(request: UserBookRequest, context: PlanningContext) -> str:
#     schema_hint = {
#         "title": "string",
#         "audience": "string",
#         "tone": "string",
#         "depth": "string",
#         "chapters": [
#             {
#                 "chapter_number": 1,
#                 "title": "string",
#                 "chapter_goal": "string",
#                 "sections": [
#                     {
#                         "title": "string",
#                         "goal": "string",
#                         "key_questions": ["string"],
#                         "estimated_words": 500
#                     }
#                 ]
#             }
#         ]
#     }

#     chapter_count_instruction = (
#         f"- Use exactly {request.chapter_count} chapters."
#         if request.chapter_count is not None
#         else "- Choose the total number of chapters yourself."
#     )

#     max_section_words_instruction = (
#         f"- No section may exceed {request.max_section_words} estimated words."
#         if request.max_section_words is not None
#         else "- Choose appropriate estimated_words for each section, usually between 200 and 1200."
#     )

#     return f"""
# Create a structured book plan using the following input:

# USER INPUT
# Topic: {request.topic}
# Audience: {request.audience}
# Tone: {request.tone}
# Depth: {request.depth}

# PLANNING CONTEXT
# Book purpose: {context.book_purpose}
# Core idea: {context.core_idea}

# Audience needs:
# {json.dumps(context.audience_needs, indent=2)}

# Main questions the book should answer:
# {json.dumps(context.main_questions, indent=2)}

# Scope should include:
# {json.dumps(context.scope_includes, indent=2)}

# Scope should exclude:
# {json.dumps(context.scope_excludes, indent=2)}

# Key themes:
# {json.dumps(context.key_themes, indent=2)}

# Sequence logic:
# {json.dumps(context.sequence_logic, indent=2)}

# Possible structure options:
# {json.dumps(context.structure_options, indent=2)}

# Evidence or example directions:
# {json.dumps(context.evidence_examples, indent=2)}

# Additional notes:
# {json.dumps(context.notes, indent=2)}

# IMPORTANT CONSTRAINTS:
# {chapter_count_instruction}
# {max_section_words_instruction}
# - The total number of chapters must be between 3 and 20.
# - Each chapter must contain 3 to 6 sections.
# - Each section must be small enough to draft in one focused writing pass.
# - Each section must have a clear teaching goal.
# - Avoid vague titles like "Introduction", "Overview", or "Basics" unless they are highly specific in context.
# - Avoid repeating the same idea across multiple chapters unless it is necessary and intentionally reframed.
# - Prefer a pedagogical order that builds from fundamentals to practice to advanced usage.
# - Use the planning context to avoid missing important themes.
# - Respect scope boundaries.
# - Return the FULL plan, not just the first chapter or first few chapters.
# - Ensure chapter_number values are sequential: 1, 2, 3, ...
# - Every chapter must have sections.
# - Every section must have title, goal, key_questions, and estimated_words.

# Before finalizing, silently check:
# 1. The JSON is complete.
# 2. The number of chapters is appropriate.
# 3. No chapter is missing sections.
# 4. No section is missing goal, key_questions, or estimated_words.
# 5. The response contains only JSON.
# 6. The outline covers the important themes without unnecessary repetition.
# 7. The order follows the sequence logic where appropriate.

# Return ONLY JSON in this exact structure:
# {json.dumps(schema_hint, indent=2)}
# """