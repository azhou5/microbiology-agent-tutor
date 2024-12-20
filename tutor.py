from typing import Dict, Optional
from agents.case_presenter import CasePresenterAgent
from agents.clinical_reasoning import ClinicalReasoningAgent
from agents.knowledge_assessment import KnowledgeAssessmentAgent
from agents.base_agent import BaseAgent

class MedicalMicrobiologyTutor:
    def __init__(self):
        self.case_presenter = CasePresenterAgent()
    
        self.clinical_reasoning = ClinicalReasoningAgent()
        self.knowledge_assessment = KnowledgeAssessmentAgent()
        self.current_organism = None
        self.in_knowledge_assessment = False
        self.differential_given = False
    
    def start_new_case(self) -> str:
        """Start a new case session."""
        case_data = self.case_presenter.generate_new_case()
        self.current_organism = None
        self.in_knowledge_assessment = False
        return case_data["presentation"]
    
    def is_final_diagnosis_attempt(self, student_input: str) -> bool:
        """Quickly check if the student is attempting a differential diagnosis."""
        check_prompt = f"""Determine if this student response is attempting to make a final diagnosis: "{student_input}"
        
        Respond with only "yes" or "no". Consider:
        - Are they stating that they want to make a differential diagnosis?
        - Are they stating a specific organism or disease as a diagnosis?
        - Are they using phrases like "I think it's", "the diagnosis is", "this is a case of"?
        - Are they making a definitive statement about what condition the patient has?
        
        
        Response (yes/no):"""
        
        # Use a faster model with low temperature for this quick check
        temp_agent = BaseAgent(model_name="gpt-4o-mini", temperature=0.1)
        response = temp_agent.generate_response("You are a medical diagnosis classifier.", check_prompt)
        return response.strip().lower().startswith("yes")
    
    def handle_input(self, student_input: str) -> str:
        """Process student input."""
        # Handle knowledge assessment phase
        if self.in_knowledge_assessment:
            result = self.knowledge_assessment.handle_response(
                self.current_organism,
                student_input
            )
            if result.get("complete"):
                self.in_knowledge_assessment = False
                return result["feedback"] + "\n\nCase complete! Type 'new case' to start another one."
            return result["feedback"]
        
        # Check if this is a differential diagnosis attempt
        if "differential" in student_input.lower() or "ddx" in student_input.lower():
            readiness = self.case_presenter.assess_differential_readiness()
            if not readiness["ready"]:
                return (
                    f"Before providing a differential diagnosis, you should gather more information. "
                    f"{readiness['message']}\n\n"
                    f"Missing information: \n- " + "\n- ".join(readiness["missing_information"])
                )
            self.case_presenter.differential_given = True
            self.differential_given = True
            
            # Evaluate the differential and provide feedback
            feedback = self.case_presenter.evaluate_differential(student_input)
            return feedback
        
        # Check if this is a final diagnosis attempt
        if self.is_final_diagnosis_attempt(student_input):
            if not self.differential_given:
                return ("Before making a final diagnosis, please provide your differential diagnosis "
                       "based on the history and physical examination findings.")
            
            if not self.case_presenter.differential_feedback_given:
                return ("Let's first discuss your differential diagnosis before moving to a final diagnosis. "
                       "What was your reasoning for each condition in your differential?")
            
            result = self.clinical_reasoning.evaluate_final_diagnosis(
                self.case_presenter.current_case,
                student_input
            )
            if result["is_correct"]:
                self.current_organism = student_input.strip()
                self.in_knowledge_assessment = True
                return result["feedback"] + "\n\n" + self.knowledge_assessment.start_assessment(self.current_organism)
            return result["feedback"]
        
        # Default to case presenter for questions and information gathering
        return self.case_presenter.evaluate_student_question(student_input)
    
    def reset(self):
        """Reset the tutor state."""
        self.case_presenter.reset()
        self.current_organism = None
        self.in_knowledge_assessment = False 