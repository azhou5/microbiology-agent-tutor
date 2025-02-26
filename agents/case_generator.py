from typing import Dict
from .base_agent import BaseAgent
from agentlite.commons import TaskPackage

class CaseGeneratorAgent(BaseAgent):
    def __init__(self, model_name: str = "gpt-4", temperature: float = 0.3):
        super().__init__(model_name, temperature)
        self.system_prompt = """You are an expert medical microbiologist specializing in creating realistic clinical cases.
        Generate detailed, medically accurate cases that include subtle but important diagnostic clues. Each case should be
        challenging but solvable with proper clinical reasoning."""

    def __call__(self, task: TaskPackage) -> Dict:
        """Handle task requests by generating a new case."""
        case = self.generate_case()
        return {
            "case_text": case,
            "case_presentation": "A new case has been generated."
        }

    def generate_case(self) -> str:
        """Generate a new clinical case as unstructured text."""
        prompt = """Generate a new clinical case involving a microbial infection. Write it as a natural narrative that includes:
        1. Patient demographics and background
        2. Chief complaint and other symptoms
        3. Vital signs and physical exam findings
        4. Relevant medical history
        5. Epidemiological context
        6. Initial labs (these will be hidden initially)
        7. A clear causative organism (this will be hidden)
        
        Write this as a natural paragraph that a physician would read in a chart, not as structured data.
        Make sure all values are realistic and clinically accurate.
        Do not include any headings or labels - just write it as flowing text.
        
        Example style:
        "Mr. Smith is a 45-year-old male who presents to the emergency department with fever and productive cough for the past 3 days. He reports yellow sputum and right-sided chest pain. His temperature is 38.5°C, blood pressure 120/80, heart rate 88, and respiratory rate 20. Physical examination reveals crackles in the right lung base. He was previously healthy with no significant medical history. He works as a teacher and notes several students in his class have had similar symptoms recently. Initial labs show elevated WBC and CRP..."
        """
        
        try:
            response = self.llm_layer(prompt)
            
            # Ensure we got a valid response
            if isinstance(response, str) and len(response) > 50:  # Basic validation
                return response
        except Exception as e:
            print(f"Error in case generation: {str(e)}")
        
        # Return a fallback case if there was an error or invalid response
        return """A 45-year-old male presents with fever and productive cough for 3 days. Temperature is 38.5°C, blood pressure 120/80, heart rate 88, respiratory rate 20. Examination reveals crackles in the right lung base. Previously healthy, working as an office worker. Several coworkers have had similar symptoms.""" 