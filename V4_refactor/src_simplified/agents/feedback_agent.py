from .base_agent import BaseAgent
from ..prompts import FEEDBACK_SYSTEM_PROMPT
from ..tools.feedback_tool import FeedbackTool

class FeedbackAgent(BaseAgent):
    def __init__(self, case_data: str, feedback_tool: FeedbackTool = None):
        super().__init__("feedback")
        self.case_data = case_data
        self.feedback_tool = feedback_tool or FeedbackTool()
        self.system_prompt = FEEDBACK_SYSTEM_PROMPT.format(case=self.case_data)

    def chat(self, user_input: str) -> str:
        # In a real implementation, we might save the feedback here
        # self.feedback_tool.save_feedback(...)
        return super().chat(user_input, self.system_prompt)

