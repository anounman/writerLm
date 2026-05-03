__all__ = ["PlannerWorkflow"]


def __getattr__(name: str):
    if name == "PlannerWorkflow":
        from planner_agent.workflow import PlannerWorkflow

        return PlannerWorkflow
    raise AttributeError(name)
