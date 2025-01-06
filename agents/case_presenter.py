from typing import Dict, Optional
from .base_agent import BaseAgent
from .case_generator import CaseGeneratorAgent

class CasePresenterAgent(BaseAgent):
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.3):
        super().__init__(model_name, temperature)
        self.current_case: Optional[Dict] = None
        self.differential_given = False
        self.diagnostic_tests_revealed = False
        self.differential_feedback_given = False
        self.current_differential = None
        
        self.system_prompt = """You are an expert medical microbiology tutor. Your role is to present clinical cases and 
        guide students through the diagnostic process in specific phases:
        1. Initial information gathering (history and physical examination) - minimum 3 questions
        2. Differential diagnosis with feedback and discussion
        3. Laboratory/diagnostic testing to refine differential
        4. Final diagnosis
        
        Format your responses concisely and clearly, as they will be read directly by the student. 
        Your response will not be filtered and will be read directly by the student. 
        Present cases in a clear, engaging manner, starting with only the most basic presenting symptoms. Do not reveal 
        laboratory or diagnostic test results until after the student has provided a differential diagnosis.
        """
    
    def assess_differential_readiness(self) -> Dict:
        """Assess if the student has gathered enough information for a differential diagnosis."""
        if not self.current_case:
            return {"ready": False, "message": "No active case."}
            
        assessment_prompt = """Review the following conversation history and assess if the student has gathered sufficient 
        information to formulate a reasonable differential diagnosis. They should have gathered information about:
        1. Key symptoms and their progression
        2. Relevant patient history
        3. Physical examination findings
        4. Epidemiological factors
        
        Do NOT consider laboratory results at this stage.
        They should have asked at least 3 questions about the above categories.
        
        Respond with a JSON object containing:
        1. Whether they are ready (true/false)
        2. A message explaining why
        3. A list of critical information they're missing (if any)
        """
        
        readiness_format = """{
            "ready": boolean,
            "message": "string",
            "missing_information": ["string"]
        }"""
        
        return self.generate_structured_response(self.system_prompt, assessment_prompt, readiness_format)

    def generate_new_case(self) -> Dict:
        """Generate a new clinical case using the CaseGeneratorAgent."""
        case_generator = CaseGeneratorAgent()
        self.current_case = case_generator.generate_case()
        return self.get_initial_presentation()
    
    def get_initial_presentation(self) -> Dict:
        """Get the initial case presentation without revealing too much."""
        if not self.current_case:
            return {"error": "No case currently active"}
        
        initial_prompt = """Based on the following case, provide only the initial presentation that would be appropriate
        to share with a student at the start of the case. Include only presenting symptoms and basic patient information.
        At the end, ask the student to ask questions about the case.
        Case: """ + self.current_case["full_case_narrative"]
        
        initial_presentation = self.generate_response(self.system_prompt, initial_prompt)
        return {"presentation": initial_presentation}
    
    def evaluate_differential(self, differential: str) -> str:
        """Evaluate the student's differential diagnosis and provide feedback."""
        if not self.current_case:
            return "No active case."
            
        evaluation_prompt = f"""Based on the case:
        {self.current_case["full_case_narrative"]}
        
        And the student's differential diagnosis:
        {differential}
        Provide constructive feedback on their differential diagnosis. Consider:
        1. Are the proposed conditions reasonable given the symptoms?
        2. Are there any important conditions they missed?
        3. What is the reasoning behind including each condition?
        
        Provide brief, focused feedback and then guide them to ask about specific tests that would help distinguish between 
        these conditions.
        """
        
        self.current_differential = differential
        self.differential_feedback_given = True
        return self.generate_response(self.system_prompt, evaluation_prompt)
    
    def evaluate_student_question(self, question: str) -> str:
        """Evaluate and respond to a student's question about the case."""
        if not self.current_case:
            return "No active case. Please start a new case first."
        
        if not self.differential_given and ("lab" in question.lower() or "test" in question.lower()):
            return ("Before requesting laboratory tests, please provide your differential diagnosis based on the history "
                   "and physical examination findings. What conditions are you considering?")
        
        if self.differential_given and not self.differential_feedback_given:
            return ("Let's first discuss your differential diagnosis before moving on to laboratory tests. "
                   "I'll provide feedback on your proposed conditions.")
        
        evaluation_prompt = f"""Based on the current case:
        {self.current_case["full_case_narrative"]}

        The transcript of the last few messages : {self.conversation_history[-5:]}
        
        {self.current_differential + " - Student's differential diagnosis" if self.differential_given else ""}
        Current phase: {'Post-differential diagnosis' if self.differential_given else 'Initial information gathering'}
        
        Student question: '{question}'
        
        If they're asking about laboratory or diagnostic tests, relate the results to their differential diagnosis 
        and help them understand how each result supports or rules out specific conditions they proposed. Don't suggest tests
        unless the student is stuck.
        
        Format your responses concisely and clearly. Don't give away too much information,
        let the student develop their own diagnostic approach.
        """
        
        return self.generate_response(self.system_prompt, evaluation_prompt)

    def reset(self):
        """Reset the agent state."""
        self.current_case = None
        self.differential_given = False
        self.diagnostic_tests_revealed = False
        self.differential_feedback_given = False
        self.current_differential = None