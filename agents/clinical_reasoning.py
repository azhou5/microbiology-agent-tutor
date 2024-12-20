from typing import List, Dict
from .base_agent import BaseAgent

class ClinicalReasoningAgent(BaseAgent):
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.7):
        super().__init__(model_name, temperature)
        self.system_prompt = """You are an expert medical microbiology educator evaluating student clinical reasoning.
        Assess their diagnostic conclusions and provide constructive feedback."""
    
    def evaluate_differential(self, case_details: Dict, student_differential: str) -> str:
        """Evaluate the student's differential diagnosis."""
        evaluation_prompt = f"""Given the following case:
        {case_details['full_case']}
        
        And the student's differential diagnosis:
        {student_differential}
        
        Evaluate their reasoning. Consider:
        1. Have they included the most likely organisms?
        2. Is their reasoning based on appropriate clinical findings?
        3. Have they missed any critical possibilities?
        4. Are there any incorrect assumptions?
        5. Have they included infectious and noninfectious causes?
        
        Provide constructive feedback that will help them improve their clinical reasoning."""
        
        return self.generate_response(self.system_prompt, evaluation_prompt)
    
    def evaluate_final_diagnosis(self, case_details: Dict, student_diagnosis: str) -> Dict:
        """Evaluate the student's final diagnosis."""
        evaluation_prompt = f"""Given the following case:
        {case_details['full_case_narrative']}
        
        And the student's final diagnosis:
        {student_diagnosis}
        
        Evaluate whether they are correct. If they are:
        1. Confirm their diagnosis
        2. Highlight the key findings that support it
        3. Identify any additional important aspects they should consider
        
        If they are incorrect:
        1. Explain why their diagnosis doesn't fully fit
        2. Point out the clinical findings they may have misinterpreted
        3. Guide them toward the correct diagnosis without immediately revealing it"""
        
        response = self.generate_response(self.system_prompt, evaluation_prompt)
        return {
            "feedback": response,
            "is_correct": "correct" in response.lower() and "incorrect" not in response.lower()
        }    
    def provide_hint(self, case_details: Dict, current_reasoning: str) -> str:
        """Provide a helpful hint based on the student's current reasoning."""
        hint_prompt = f"""Based on the case:
        {case_details['full_case']}
        
        And the student's current reasoning:
        {current_reasoning}
        
        Provide a subtle hint that will help guide their thinking without giving away the diagnosis.
        Focus on key clinical findings or epidemiological factors they might have overlooked."""
        
        return self.generate_response(self.system_prompt, hint_prompt)
