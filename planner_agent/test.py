from search_tools import PlannerSearchTools
from scope_builder import ScopeBuilder
from outline_node import ChapterOutlineNode
from schemas import UserBookRequest

request = UserBookRequest(
    topic="Learn Generative AI and Agentic AI through practical projects",
    audience="beginner to intermediate software developers",
    tone="clear, practical, project-based",
    depth="intermediate",
)

tools = PlannerSearchTools()
bundle = tools.run_planner_discovery(request.topic)

builder = ScopeBuilder()
context = builder.build_context(request, bundle)

node = ChapterOutlineNode()
outline = node.run(request, context)

print(outline.model_dump_json(indent=2))