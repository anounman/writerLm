from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from .state import NotesSynthesizerState, NotesSynthesizerInput
from .llm import GroqStructuredLLM

from .nodes.build_synthesis_input import build_synthesis_input_node
from .nodes.synthesize_section_notes import synthesize_section_notes_node
from .nodes.validate_section_notes import validate_section_notes_node
from .nodes.assemble_notes_bundle import assemble_notes_bundle_node


def _router(state: NotesSynthesizerState) -> str:
    """
    Routing logic:
    - If active_task exists → continue processing it
    - Else if pending tasks exist → start next task
    - Else → assemble final bundle
    """
    if state.active_task is not None:
        return "synthesize"

    if state.pending_tasks:
        return "build_input"

    return "assemble"


def build_notes_synthesizer_graph(llm: GroqStructuredLLM):
    """
    Build LangGraph workflow for Notes Synthesizer.
    """

    graph = StateGraph(NotesSynthesizerState)

    # Nodes
    graph.add_node("build_input", build_synthesis_input_node)
    graph.add_node(
        "synthesize",
        lambda state: synthesize_section_notes_node(state, llm),
    )
    graph.add_node("validate", validate_section_notes_node)
    graph.add_node("assemble", assemble_notes_bundle_node)

    # Entry
    graph.add_edge(START, "build_input")

    # Routing after build_input
    graph.add_conditional_edges(
        "build_input",
        _router,
        {
            "synthesize": "synthesize",
            "build_input": "build_input",
            "assemble": "assemble",
        },
    )

    # After synthesize → validate
    graph.add_edge("synthesize", "validate")

    # After validate → decide next
    graph.add_conditional_edges(
        "validate",
        _router,
        {
            "synthesize": "synthesize",
            "build_input": "build_input",
            "assemble": "assemble",
        },
    )

    # Final
    graph.add_edge("assemble", END)

    return graph.compile()


def initialize_state(input_data: NotesSynthesizerInput) -> NotesSynthesizerState:
    """
    Convert input payload into initial graph state.
    """

    return NotesSynthesizerState(
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