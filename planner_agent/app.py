from planner_agent.schemas import UserBookRequest
from planner_agent.storage import save_book_plan
from planner_agent.workflow import PlannerWorkflow


def main() -> None:
    request = UserBookRequest(
        topic="Learn Generative AI and Agentic AI through practical projects",
        audience="beginner to intermediate software developers",
        tone="clear, practical, project-based",
        depth="intermediate",
    )

    workflow = PlannerWorkflow()
    final_book_plan = workflow.run(request)

    print("\n=== GENERATED BOOK PLAN ===\n")
    print(final_book_plan.model_dump_json(indent=2))

    print("\nNo validation issues found.")

    saved_path = save_book_plan(final_book_plan)
    print(f"\nSaved to: {saved_path}")


if __name__ == "__main__":
    main()
