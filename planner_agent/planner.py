# from pydantic import ValidationError

# from config import get_client , get_model_name
# from prompt import PLANNER_SYSTEM_PROMPT , build_planner_prompt
# from schemas import UserBookRequest , BookPlan
# from search_tools import PlannerSearchTools
# from search_tools import PlannerSearchTools
# from utils import load_json_safe
# from scope_builder import ScopeBuilder

# class Planner:
#     def __init__(self) -> None:
#         self.client = get_client()
#         self.model_name = get_model_name()
#         self.scope_builder = ScopeBuilder()
#         self.search_tools = PlannerSearchTools()

#     def _generate_raw(self , request: UserBookRequest) -> str:
#         discovery_bundle = self.search_tools.run_planner_discovery(request.topic)
#         context = self.scope_builder.build_context(request=request , discovery_bundle=discovery_bundle)
#         response = self.client.chat.completions.create(
#             model=self.model_name,
#             temperature=0.2,
#             response_format={"type": "json_object"},
#             messages=[
#                 {"role": "system" , "content": PLANNER_SYSTEM_PROMPT},
#                 {"role": "user" , "content": build_planner_prompt(request , context)}
#             ]
#         )
#         conetent = response.choices[0].message.content
#         if not conetent:
#             raise ValueError("No content returned from the model.")
#         return conetent

#     def create_plan(self , request: UserBookRequest) -> BookPlan:
#         raw_output = self._generate_raw(request)
#         try:
#             data = load_json_safe(raw_output)
#             plan = BookPlan.model_validate(data)
#             return plan
#         except (ValueError , ValidationError) as e:
#             raise ValueError(f"Failed to create book plan: {str(e)}") from e
        
