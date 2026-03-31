import json
import logging

from .base_agent import BaseAgent
from ..prompts import WEAKNESS_ANALYSIS_PROMPT, MCQ_GENERATION_PROMPT
from ..utils.llm import chat_complete

logger = logging.getLogger(__name__)


class QuizAgent(BaseAgent):
    """Generates targeted MCQs from a specific module's conversation log."""

    def __init__(self, case_data: str):
        super().__init__("quiz")
        self.case_data = case_data

    def generate_quiz(
        self,
        conversation_text: str,
        module_name: str = "General",
        num_questions: int = 3,
    ) -> dict:
        """Generate MCQs based on a module's conversation.

        Args:
            conversation_text: Pre-formatted conversation string.
            module_name: Friendly name of the module (e.g. "DDx Deep Dive").
            num_questions: How many MCQs to produce.

        Returns:
            Dict with ``mcqs`` key containing the generated questions.
        """
        # Step 1: weakness analysis scoped to the module
        analysis_prompt = WEAKNESS_ANALYSIS_PROMPT.format(
            module_name=module_name,
            conversation=conversation_text,
        )
        try:
            analysis_response = chat_complete(
                [{"role": "user", "content": analysis_prompt}],
                response_format={"type": "json_object"},
            )
            analysis_data = json.loads(analysis_response)
            weak_areas = json.dumps(analysis_data.get("weak_areas", []), indent=2)
        except Exception:
            weak_areas = "General microbiology knowledge"

        # Step 2: MCQ generation scoped to the module
        mcq_prompt = MCQ_GENERATION_PROMPT.format(
            case=self.case_data,
            module_name=module_name,
            weak_areas=weak_areas,
            num_questions=num_questions,
        )
        try:
            mcq_response = chat_complete(
                [{"role": "user", "content": mcq_prompt}],
                response_format={"type": "json_object"},
            )
            return json.loads(mcq_response)
        except Exception as e:
            logger.error(f"MCQ generation failed for {module_name}: {e}")
            return {"error": str(e), "mcqs": []}

    def chat(self, user_input: str) -> str:
        return "I'm generating your assessment based on our discussion."
