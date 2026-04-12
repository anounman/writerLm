from langgraph.graph import START, END, StateGraph

from planner_agent.assembler import BookPlanAssembler
from planner_agent.graph_state import PlannerState
from planner_agent.outline_node import ChapterOutlineNode
from planner_agent.scope_builder import ScopeBuilder
from planner_agent.search_tools import PlannerSearchTools
from planner_agent.section_node import SectionPlannerNode
from planner_agent.validator import validate_book_plan


search_tools = PlannerSearchTools()
scope_builder = ScopeBuilder()
outline_node = ChapterOutlineNode()
section_node = SectionPlannerNode()
assembler = BookPlanAssembler()


def build_scope_node(state: PlannerState) -> dict:
    request = state["request"]

    discovery_bundle = search_tools.run_planner_discovery(request.topic)
    planning_context = scope_builder.build_context(
        request=request,
        discovery_bundle=discovery_bundle,
    )

    return {
        "planning_context": planning_context,
    }


def build_outline_node(state: PlannerState) -> dict:
    request = state["request"]
    planning_context = state["planning_context"]

    if planning_context is None:
        raise ValueError("planning_context is missing before outline generation.")

    chapter_outline = outline_node.run(
        request=request,
        context=planning_context,
    )

    return {
        "chapter_outline": chapter_outline,
    }


def build_sections_node(state: PlannerState) -> dict:
    request = state["request"]
    planning_context = state["planning_context"]
    chapter_outline = state["chapter_outline"]

    if planning_context is None:
        raise ValueError("planning_context is missing before section generation.")

    if chapter_outline is None:
        raise ValueError("chapter_outline is missing before section generation.")

    chapter_section_plans = []

    for chapter in chapter_outline.chapters:
        section_plan = section_node.run(
            request=request,
            context=planning_context,
            chapter=chapter,
        )
        chapter_section_plans.append(section_plan)

    return {
        "chapter_section_plans": chapter_section_plans,
    }


def assemble_book_node(state: PlannerState) -> dict:
    request = state["request"]
    chapter_outline = state["chapter_outline"]
    chapter_section_plans = state["chapter_section_plans"]

    if chapter_outline is None:
        raise ValueError("chapter_outline is missing before assembly.")

    if chapter_section_plans is None:
        raise ValueError("chapter_section_plans is missing before assembly.")

    final_book_plan = assembler.assemble(
        request=request,
        chapter_section_plans=chapter_section_plans,
        title=chapter_outline.title,
    )

    return {
        "final_book_plan": final_book_plan,
    }


def validate_book_node(state: PlannerState) -> dict:
    request = state["request"]
    final_book_plan = state["final_book_plan"]

    if final_book_plan is None:
        raise ValueError("final_book_plan is missing before validation.")

    validation_issues = validate_book_plan(
        plan=final_book_plan,
        request=request,
    )

    return {
        "validation_issues": validation_issues,
    }


def build_planner_graph():
    graph_builder = StateGraph(PlannerState)

    graph_builder.add_node("build_scope", build_scope_node)
    graph_builder.add_node("build_outline", build_outline_node)
    graph_builder.add_node("build_sections", build_sections_node)
    graph_builder.add_node("assemble_book", assemble_book_node)
    graph_builder.add_node("validate_book", validate_book_node)

    graph_builder.add_edge(START, "build_scope")
    graph_builder.add_edge("build_scope", "build_outline")
    graph_builder.add_edge("build_outline", "build_sections")
    graph_builder.add_edge("build_sections", "assemble_book")
    graph_builder.add_edge("assemble_book", "validate_book")
    graph_builder.add_edge("validate_book", END)

    return graph_builder.compile()
