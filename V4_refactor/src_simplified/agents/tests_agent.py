from .base_agent import BaseAgent
from ..prompts import TESTS_MANAGEMENT_SYSTEM_PROMPT

class TestsAgent(BaseAgent):
    def __init__(self, case_data: str):
        super().__init__("tests_management")
        self.case_data = case_data
        self.system_prompt = TESTS_MANAGEMENT_SYSTEM_PROMPT.format(case=self.case_data)

    def chat(self, user_input: str) -> str:
        return super().chat(user_input, self.system_prompt)

