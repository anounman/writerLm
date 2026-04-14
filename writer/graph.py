from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from .state import WriterState, WriterInput
from .llm import GroqStructuredLLM

from .nodes.build_writing_input import build_writing_input_node
from .nodes.write_section import write_section_node
from .nodes.validate_section import validate_section_node
from .nodes.assemble_writer_bundle import assemble_writer_bundle_node


def _router(state: WriterState) -> str:
    """
    Routing logic:
    - If active_task exists → continue processing it
    - Else if pending tasks exist → start next task
    - Else → assemble final bundle
    """
    if state.active_task is not None:
        return "write"

    if state.pending_tasks:
        return "build_input"

    return "assemble"


def build_writer_graph(llm: GroqStructuredLLM):
    graph = StateGraph(WriterState)

    # Nodes
    graph.add_node("build_input", build_writing_input_node)
    graph.add_node(
        "write",
        lambda state: write_section_node(state, llm),
    )
    graph.add_node("validate", validate_section_node)
    graph.add_node("assemble", assemble_writer_bundle_node)

    # Start
    graph.add_edge(START, "build_input")

    # After build_input
    graph.add_conditional_edges(
        "build_input",
        _router,
        {
            "write": "write",
            "build_input": "build_input",
            "assemble": "assemble",
        },
    )

    # write → validate
    graph.add_edge("write", "validate")

    # After validate
    graph.add_conditional_edges(
        "validate",
        _router,
        {
            "write": "write",
            "build_input": "build_input",
            "assemble": "assemble",
        },
    )

    # End
    graph.add_edge("assemble", END)

    return graph.compile()


def initialize_writer_state(input_data: WriterInput) -> WriterState:
    return WriterState(
        book_id=input_data.book_id,
        book_title=input_data.book_title,
        runtime=input_data.runtime,
        pending_tasks=list(input_data.tasks),
        completed_tasks=[],
        failed_tasks=[],
        active_task=None,
        output_bundle=None,
        run_warnings=[],
        run_errors=[],
    )