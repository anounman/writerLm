from search_tools import PlannerSearchTools
from scope_builder import ScopeBuilder
from outline_node import ChapterOutlineNode
from schemas import UserBookRequest

request = UserBookRequest(
    topic="HMI 2 practice handbook with theory",
    audience="beginner to intermediate students",
    tone="clear, rigorous, and friendly",
    depth="intermediate",
    book_type="course_companion",
    theory_practice_balance="practice_heavy",
    exercise_strategy="worked_examples",
)

tools = PlannerSearchTools()
bundle = tools.run_planner_discovery(request.topic)

builder = ScopeBuilder()
context = builder.build_context(request, bundle)

node = ChapterOutlineNode()
outline = node.run(request, context)

print(outline.model_dump_json(indent=2))
