from planner_agent.schemas import UserBookRequest
from planner_agent.storage import save_book_plan
from planner_agent.workflow import PlannerWorkflow


def main() -> None:
    request = UserBookRequest(
        topic="HMI 2 practice handbook with theory",
        audience="beginner to intermediate students",
        tone="clear, rigorous, and friendly",
        depth="intermediate",
        book_type="course_companion",
        theory_practice_balance="practice_heavy",
        exercise_strategy="worked_examples",
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
