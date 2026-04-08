from graph_state import PlannerState
from planner_graph import build_planner_graph
from schemas import UserBookRequest
from storage import save_book_plan


def main() -> None:
    request = UserBookRequest(
        topic="Learn Generative AI and Agentic AI through practical projects",
        audience="beginner to intermediate software developers",
        tone="clear, practical, project-based",
        depth="intermediate",
    )

    graph = build_planner_graph()

    initial_state: PlannerState = {
        "request": request,
        "planning_context": None,
        "chapter_outline": None,
        "chapter_section_plans": None,
        "final_book_plan": None,
        "validation_issues": [],
    }

    result = graph.invoke(initial_state)

    final_book_plan = result.get("final_book_plan")
    validation_issues = result.get("validation_issues", [])

    if final_book_plan is None:
        raise ValueError("Graph finished without producing a final_book_plan.")

    print("\n=== GENERATED BOOK PLAN ===\n")
    print(final_book_plan.model_dump_json(indent=2))

    if validation_issues:
        print("\n=== VALIDATION ISSUES ===\n")
        for issue in validation_issues:
            print(f"- {issue}")
    else:
        print("\nNo validation issues found.")

    saved_path = save_book_plan(final_book_plan)
    print(f"\nSaved to: {saved_path}")


if __name__ == "__main__":
    main()