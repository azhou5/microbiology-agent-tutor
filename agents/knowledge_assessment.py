from typing import List, Dict

import os 

from agentlite.agents import BaseAgent as AgentLiteBaseAgent
from agentlite.llm.agent_llms import BaseLLM, get_llm_backend
from agentlite.llm.LLMConfig import LLMConfig
from agentlite.actions import BaseAction
from agentlite.actions.InnerActions import ThinkAction, FinishAction
from agentlite.commons import TaskPackage, AgentAct

class GenerateQuestionsAction(BaseAction):
    def __init__(self):
        super().__init__(
            action_name="GenerateQuestions",
            action_desc="Generate targeted questions about a specific organism",
            params_doc={"organism": "Name of the organism to generate questions about"}
        )
    
    def __call__(self, **kwargs) -> str:
        return ["Question 1...", "Question 2...", "Question 3..."]

class EvaluateAnswerAction(BaseAction):
    def __init__(self):
        super().__init__(
            action_name="EvaluateAnswer",
            action_desc="Evaluate student's answer to a specific question",
            params_doc={
                "organism": "Name of the organism",
                "question": "The question asked",
                "student_answer": "Student's answer to evaluate"
            }
        )
    
    def __call__(self, **kwargs) -> str:
        return {
            "feedback": "Evaluation of answer...",
            "is_correct": True
        }

class ProvideExplanationAction(BaseAction):
    def __init__(self):
        super().__init__(
            action_name="ProvideExplanation",
            action_desc="Provide detailed explanation of a concept",
            params_doc={
                "organism": "Name of the organism",
                "concept": "Concept to explain"
            }
        )
    
    def __call__(self, **kwargs) -> str:
        return "Detailed explanation of concept..."

class KnowledgeAssessmentAgent(AgentLiteBaseAgent):
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.3):
        # Initialize LLM configuration
        llm_config = LLMConfig({"llm_name": model_name, "temperature": temperature})
        llm = get_llm_backend(llm_config)
        
        # Initialize custom actions
        actions = [
            GenerateQuestionsAction(),
            EvaluateAnswerAction(),
            ProvideExplanationAction(),
            ThinkAction(),
            FinishAction()
        ]
        
        super().__init__(
            name="knowledge_assessment",
            role="""I am an expert medical microbiology educator specializing in testing and reinforcing 
            student knowledge about specific organisms. I focus on:
            1. Virulence factors and pathogenesis
            2. Epidemiology and transmission
            3. Laboratory diagnosis
            4. Treatment and prevention
            
            I provide targeted questions and detailed feedback to ensure deep understanding.""",
            llm=llm,
            actions=actions,
            reasoning_type="react"
        )
        
        # Add examples of successful interactions
        self._add_examples()
    
    def _add_examples(self):
        """Add comprehensive examples of successful agent interactions."""
        
        # Example 1: Starting knowledge assessment
        task1 = TaskPackage(instruction="Begin assessment for N. meningitidis")
        action_chain1 = [
            (AgentAct(name="Think", params={"response": "Starting structured assessment of N. meningitidis knowledge."}),
             "OK"),
            (AgentAct(name="GenerateQuestions", params={"organism": "N. meningitidis"}),
             ["Let's discuss N. meningitidis. What are its key virulence factors and how do they contribute to pathogenesis?"]),
            (AgentAct(name="Finish", params={"response": "Let's discuss N. meningitidis. What are its key virulence factors and how do they contribute to pathogenesis?"}),
             "Task completed.")
        ]
        self.add_example(task1, action_chain1)

        # Example 2: Evaluating good answer about virulence
        task2 = TaskPackage(instruction="N. meningitidis has a polysaccharide capsule that helps evade phagocytosis, and its endotoxin triggers inflammatory response")
        action_chain2 = [
            (AgentAct(name="Think", params={"response": "Student shows good understanding of key virulence factors."}),
             "OK"),
            (AgentAct(name="EvaluateAnswer", params={
                "organism": "N. meningitidis",
                "question": "virulence factors",
                "student_answer": "polysaccharide capsule for phagocytosis evasion, endotoxin for inflammation"
            }),
             {"feedback": """Excellent understanding! You've identified two critical virulence factors:
             1. Polysaccharide capsule: Indeed helps evade phagocytosis
             2. Endotoxin (LPS): Triggers inflammatory cascade
             
             Let's build on this. How does understanding these virulence factors inform our vaccination strategies?""",
              "is_correct": True}),
            (AgentAct(name="Finish", params={"response": "Excellent understanding! [...]"}),
             "Task completed.")
        ]
        self.add_example(task2, action_chain2)

        # Example 3: Evaluating incomplete answer
        task3 = TaskPackage(instruction="It has a capsule")
        action_chain3 = [
            (AgentAct(name="Think", params={"response": "Student's answer is correct but incomplete."}),
             "OK"),
            (AgentAct(name="EvaluateAnswer", params={
                "organism": "N. meningitidis",
                "question": "virulence factors",
                "student_answer": "It has a capsule"
            }),
             {"feedback": """You're on the right track identifying the capsule, but let's expand:
             1. What type of capsule is it?
             2. How exactly does it help the organism?
             3. What other virulence factors are important?
             
             Can you elaborate on these points?""",
              "is_correct": False}),
            (AgentAct(name="Finish", params={"response": "You're on the right track identifying the capsule, but let's expand: [...]"}),
             "Task completed.")
        ]
        self.add_example(task3, action_chain3)

        # Example 4: Providing detailed explanation
        task4 = TaskPackage(instruction="Can you explain more about meningococcal vaccines?")
        action_chain4 = [
            (AgentAct(name="Think", params={"response": "Student requesting detailed information about vaccination."}),
             "OK"),
            (AgentAct(name="ProvideExplanation", params={
                "organism": "N. meningitidis",
                "concept": "vaccines"
            }),
             """Let's discuss meningococcal vaccines:
             1. Types available:
                - Polysaccharide vaccines (older)
                - Conjugate vaccines (newer, preferred)
             2. Coverage:
                - Typically cover serogroups A, C, W, and Y
                - Separate vaccine for serogroup B
             3. Key principles:
                - Target capsular antigens
                - Conjugate vaccines provide T-cell dependent response
                - Better memory response than pure polysaccharide vaccines
             
             Would you like to explore any of these aspects in more detail?"""),
            (AgentAct(name="Finish", params={"response": "Let's discuss meningococcal vaccines: [...]"}),
             "Task completed.")
        ]
        self.add_example(task4, action_chain4)

        # Example 5: Testing treatment knowledge
        task5 = TaskPackage(instruction="What's the recommended antibiotic treatment for N. meningitidis?")
        action_chain5 = [
            (AgentAct(name="Think", params={"response": "Moving to assessment of treatment knowledge."}),
             "OK"),
            (AgentAct(name="GenerateQuestions", params={
                "organism": "N. meningitidis",
                "topic": "treatment"
            }),
             """Let's discuss treatment comprehensively:
             1. What is the first-line empiric therapy?
             2. How do you modify treatment once N. meningitidis is confirmed?
             3. What about prophylaxis for close contacts?
             
             Please address each of these aspects."""),
            (AgentAct(name="Finish", params={"response": "Let's discuss treatment comprehensively: [...]"}),
             "Task completed.")
        ]
        self.add_example(task5, action_chain5)