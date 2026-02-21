from .base_agent import BaseAgent
from ..prompts import PATIENT_SYSTEM_PROMPT, FIRST_SENTENCE_GENERATION_PROMPT
from ..utils.llm import chat_complete

class PatientAgent(BaseAgent):
    def __init__(self, case_data: str):
        super().__init__("patient")
        self.case_data = case_data
        self.system_prompt = PATIENT_SYSTEM_PROMPT.format(case=self.case_data)
        self.first_sentence = self._generate_first_sentence()

    def _generate_first_sentence(self) -> str:
        """Generate the opening sentence for the case."""
        prompt = FIRST_SENTENCE_GENERATION_PROMPT.format(case=self.case_data)
        try:
            return chat_complete([{"role": "user", "content": prompt}])
        except Exception:
            return "I'm not feeling well, doctor."

    def chat(self, user_input: str) -> str:
        return super().chat(user_input, self.system_prompt)

