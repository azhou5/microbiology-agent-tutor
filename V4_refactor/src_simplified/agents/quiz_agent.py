import json
from .base_agent import BaseAgent
from ..prompts import WEAKNESS_ANALYSIS_PROMPT, MCQ_GENERATION_PROMPT
from ..utils.llm import chat_complete

class QuizAgent(BaseAgent):
    def __init__(self, case_data: str):
        super().__init__("post_case_mcq")
        self.case_data = case_data

    def generate_quiz(self, conversation_history: list, num_questions: int = 3) -> dict:
        """
        Generate a quiz based on the conversation history.
        """
        # Format conversation for analysis
        conversation_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])
        
        # Step 1: Analyze weaknesses
        analysis_prompt = WEAKNESS_ANALYSIS_PROMPT.format(conversation=conversation_text)
        try:
            analysis_response = chat_complete(
                [{"role": "user", "content": analysis_prompt}],
                response_format={"type": "json_object"}
            )
            analysis_data = json.loads(analysis_response)
            weak_areas = json.dumps(analysis_data.get("weak_areas", []), indent=2)
        except Exception as e:
            weak_areas = "General microbiology knowledge"

        # Step 2: Generate MCQs
        mcq_prompt = MCQ_GENERATION_PROMPT.format(
            case=self.case_data,
            weak_areas=weak_areas,
            num_questions=num_questions
        )
        
        try:
            mcq_response = chat_complete(
                [{"role": "user", "content": mcq_prompt}],
                response_format={"type": "json_object"}
            )
            return json.loads(mcq_response)
        except Exception as e:
            return {"error": str(e), "mcqs": []}

    def chat(self, user_input: str) -> str:
        # This agent is primarily for generation, but can handle chat if needed
        return "I'm generating your post-case assessment based on our discussion."

