from typing import List, Dict
from .base_agent import BaseAgent

class KnowledgeAssessmentAgent(BaseAgent):
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.3):
        super().__init__(model_name, temperature)
        self.system_prompt = """You are an expert medical microbiology educator specializing in testing and reinforcing 
        student knowledge about specific organisms. Your role is to ask targeted questions about key microbiological 
        concepts and provide detailed feedback on student responses. Focus on critical aspects such as virulence factors, 
        transmission, laboratory diagnosis, and treatment."""
    
    def generate_targeted_questions(self, organism: str) -> List[str]:
        """Generate targeted questions about a specific organism."""
        question_prompt = f"""Generate 3 targeted questions about {organism} that assess understanding of:
        1. Key virulence factors and pathogenesis
        2. Treatment approaches and antimicrobial susceptibility
        3. Epidemiology and prevention
        
        Format each question to be specific and concise, as it will
        be given directly to the student. """
        
        response = self.generate_response(self.system_prompt, question_prompt)
        return [q.strip() for q in response.split('\n') if '?' in q]
    
    def evaluate_answer(self, organism: str, question: str, student_answer: str) -> Dict:
        """Evaluate a student's answer to a specific question."""
        evaluation_prompt = f"""Regarding {organism} and the question:
        {question}
        
        The student answered:
        {student_answer}
        
        Evaluate their response considering:
        1. Accuracy of the information provided
        2. Completeness of the answer
        3. Understanding of core concepts
        4. Clinical relevance
        
        Provide specific feedback and correct any misconceptions.
        
        Your response will be given directly to the student, so be concise and clear."""
        
        response = self.generate_response(self.system_prompt, evaluation_prompt)
        return {
            "feedback": response,
            "is_correct": "correct" in response.lower() and "incorrect" not in response.lower()
        }
    
    def provide_explanation(self, organism: str, concept: str) -> str:
        """Provide a detailed explanation of a specific concept related to an organism."""
        explanation_prompt = f"""Provide a detailed explanation of {concept} for {organism}. Include:
        1. Basic principles and mechanisms
        2. Clinical relevance
        3. Common misconceptions
        4. Key points students should remember
        
        Make the explanation clear and focused on practical understanding.
        
        Your response will be given directly to the student, so be concise and clear."""
        
        return self.generate_response(self.system_prompt, explanation_prompt)
    
    def start_assessment(self, organism: str) -> str:
        """Start a new knowledge assessment session for an organism."""
        self.current_questions = self.generate_targeted_questions(organism)
        self.current_question_index = 0
        return f"Great work on the diagnosis! Let's test your knowledge about {organism}.\n\n" + self.current_questions[0]
    
    def handle_response(self, organism: str, student_answer: str) -> Dict:
        """Handle a student's response during knowledge assessment."""
        if not hasattr(self, 'current_questions') or not self.current_questions:
            return {"error": "No active assessment session"}
        
        result = self.evaluate_answer(organism, self.current_questions[self.current_question_index], student_answer)
        
        self.current_question_index += 1
        
        response = {
            "feedback": result["feedback"],
            "complete": self.current_question_index >= len(self.current_questions)
        }
        
        if not response["complete"] and self.current_question_index < len(self.current_questions):
            response["feedback"] += f"\n\nNext question:\n{self.current_questions[self.current_question_index]}"
        
        return response