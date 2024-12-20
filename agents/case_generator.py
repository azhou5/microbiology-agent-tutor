from typing import Dict
from .base_agent import BaseAgent

class CaseGeneratorAgent(BaseAgent):
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.3):
        super().__init__(model_name, temperature)
        self.system_prompt = """You are an expert medical microbiologist specializing in creating realistic clinical cases.
        Generate detailed, medically accurate cases that include subtle but important diagnostic clues. Each case should be
        challenging but solvable with proper clinical reasoning."""

    def generate_case(self) -> Dict:
        """Generate a new clinical case with structured data."""
        case_format = """{
            "demographics": {"age": "", "sex": "", "occupation": ""},
            "presenting_symptoms": [],
            "medical_history": "",
            "physical_exam": {},
            "lab_results": {},
            "epidemiology": "",
            "causative_organism": "",
            "full_case_narrative": ""
        }"""
        
        case_prompt = """Generate a new clinical case involving a microbial infection. Include:
        1. Patient demographics
        2. Presenting symptoms
        3. Relevant medical history
        4. Initial physical examination findings
        5. Laboratory results
        6. Epidemiological factors
        7. The causative organism
        
        Provide specific clinical details and include subtle but important diagnostic clues.
        Return the response in the specified JSON format."""
        
        return self.generate_structured_response(self.system_prompt, case_prompt, case_format) 