from typing import List, Dict
import os 
import glob

from custom_agent_wrapper import CustomAgentWrapper
from agentlite.llm.agent_llms import BaseLLM, get_llm_backend
from agentlite.llm.LLMConfig import LLMConfig
from agentlite.actions import BaseAction
from agentlite.actions.InnerActions import ThinkAction, FinishAction
from agentlite.commons import TaskPackage, AgentAct
from shared_definitions import TutorStage  # Import the stage enum from shared_definitions
from langchain.chat_models import AzureChatOpenAI

class LoadGuidingQuestionsAction(BaseAction):
    def __init__(self):
        super().__init__(
            action_name="LoadGuidingQuestions",
            action_desc="Load guiding questions from the RAG-generated files",
            params_doc={"organism": "Name of the organism to load questions for"}
        )
    
    def __call__(self, **kwargs) -> Dict:
        organism = kwargs.get("organism", "")
        if not organism:
            return {"success": False, "message": "No organism specified", "questions": []}
            
        # Normalize organism name for file path
        organism_normalized = organism.lower().replace(" ", "_")
        output_dir = f"outputs/{organism_normalized}_case_study"
        
        # Find all question files
        question_files = glob.glob(f"{output_dir}/*_questions.txt")
        
        if not question_files:
            return {"success": False, "message": f"No question files found for {organism}", "questions": []}
        
        # Load questions from files
        all_questions = []
        for file_path in question_files:
            try:
                with open(file_path, 'r') as f:
                    content = f.read().strip()
                    # Extract questions (assuming they're numbered or prefixed with "Question:")
                    for line in content.split('\n'):
                        line = line.strip()
                        if line.startswith("Question:"):
                            question = line.replace("Question:", "").strip()
                            all_questions.append(question)
                        elif line and (line[0].isdigit() and "." in line):
                            # For numbered questions like "1. What is..."
                            question = line.split(".", 1)[1].strip()
                            all_questions.append(question)
            except Exception as e:
                print(f"Error reading {file_path}: {str(e)}")
        
        return {
            "success": True, 
            "message": f"Loaded {len(all_questions)} questions for {organism}",
            "questions": all_questions
        }

class LoadKeyConcepts(BaseAction):
    def __init__(self):
        super().__init__(
            action_name="LoadKeyConcepts",
            action_desc="Load key concepts from the RAG-generated files",
            params_doc={"organism": "Name of the organism to load key concepts for"}
        )
    
    def __call__(self, **kwargs) -> Dict:
        organism = kwargs.get("organism", "")
        if not organism:
            return {"success": False, "message": "No organism specified", "concepts": []}
            
        # Normalize organism name for file path
        organism_normalized = organism.lower().replace(" ", "_")
        output_dir = f"outputs/{organism_normalized}_case_study"
        
        # Try to load key concepts file
        key_concepts_path = f"{output_dir}/key_concepts.txt"
        
        if not os.path.exists(key_concepts_path):
            return {"success": False, "message": f"No key concepts file found for {organism}", "concepts": []}
        
        # Load key concepts from file
        try:
            with open(key_concepts_path, 'r') as f:
                content = f.read().strip()
                # Extract bullet points
                concepts = []
                for line in content.split('\n'):
                    line = line.strip()
                    if line.startswith("-") or line.startswith("•"):
                        concept = line.replace("-", "", 1).replace("•", "", 1).strip()
                        concepts.append(concept)
            
            return {
                "success": True, 
                "message": f"Loaded {len(concepts)} key concepts for {organism}",
                "concepts": concepts
            }
        except Exception as e:
            print(f"Error reading {key_concepts_path}: {str(e)}")
            return {"success": False, "message": f"Error reading key concepts: {str(e)}", "concepts": []}

class GenerateQuestionsAction(BaseAction):
    def __init__(self):
        super().__init__(
            action_name="GenerateQuestions",
            action_desc="Generate targeted questions about a specific organism",
            params_doc={"organism": "Name of the organism to generate questions about"}
        )
        # Initialize Azure OpenAI
        self.llm = AzureChatOpenAI(
            openai_api_type="azure",
            openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0.3
        )
    
    def __call__(self, **kwargs) -> List[str]:
        organism = kwargs.get("organism", "")
        if not organism:
            return ["What organism are we discussing?"]
            
        # Create a prompt for the LLM to generate questions
        from langchain.schema import SystemMessage, HumanMessage
        
        system_prompt = """You are an expert medical microbiologist creating educational questions about pathogens.
        Generate 3-5 challenging but fair questions about the specified organism that test understanding of:
        1. Virulence factors and pathogenesis
        2. Clinical presentation and diagnosis
        3. Treatment and management
        4. Epidemiology and prevention
        
        Format each question clearly and ensure they require deep understanding rather than simple recall."""
        
        human_prompt = f"Generate educational questions about {organism} for medical students."
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
        
        response = self.llm.invoke(messages)
        
        # Parse the response into a list of questions
        questions = [q.strip() for q in response.content.split("\n") if q.strip() and "?" in q]
        
        # Ensure we have at least one question
        if not questions:
            questions = [f"What are the key virulence factors of {organism}?"]
            
        return questions

class EvaluateAnswerAction(BaseAction):
    def __init__(self):
        super().__init__(
            action_name="EvaluateAnswer",
            action_desc="Evaluate student's answer to a specific question",
            params_doc={
                "organism": "Name of the organism",
                "question": "The question asked",
                "student_answer": "Student's answer to evaluate",
                "key_concepts": "List of key concepts to reference in evaluation (optional)"
            }
        )
        # Initialize Azure OpenAI
        self.llm = AzureChatOpenAI(
            openai_api_type="azure",
            openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0.3
        )
    
    def __call__(self, **kwargs) -> Dict:
        organism = kwargs.get("organism", "")
        question = kwargs.get("question", "")
        student_answer = kwargs.get("student_answer", "")
        key_concepts = kwargs.get("key_concepts", [])
        
        if not organism or not question or not student_answer:
            return {
                "feedback": "I need more information to evaluate your answer.",
                "is_correct": False
            }
        
        # Create a prompt for the LLM to evaluate the answer
        from langchain.schema import SystemMessage, HumanMessage
        
        system_prompt = """You are an expert medical microbiologist evaluating student answers.
        Provide constructive feedback on the student's answer, highlighting strengths and areas for improvement.
        Be specific about what was correct and what was missing or incorrect.
        If key concepts are provided, reference them in your evaluation.
        
        Your feedback should be educational and encourage deeper understanding."""
        
        # Include key concepts if available
        key_concepts_text = ""
        if key_concepts:
            key_concepts_text = "Key concepts to reference:\n" + "\n".join([f"- {c}" for c in key_concepts])
        
        human_prompt = f"""
        Organism: {organism}
        Question: {question}
        Student Answer: {student_answer}
        
        {key_concepts_text}
        
        Evaluate the student's answer and provide constructive feedback.
        """
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
        
        response = self.llm.invoke(messages)
        
        # Determine if the answer is correct based on the feedback
        is_correct = "excellent" in response.content.lower() or "good" in response.content.lower() or "correct" in response.content.lower()
        
        return {
            "feedback": response.content.strip(),
            "is_correct": is_correct
        }

class ProvideExplanationAction(BaseAction):
    def __init__(self):
        super().__init__(
            action_name="ProvideExplanation",
            action_desc="Provide detailed explanation of a concept",
            params_doc={
                "organism": "Name of the organism",
                "concept": "Concept to explain",
                "key_concepts": "List of key concepts to reference in explanation (optional)"
            }
        )
        # Initialize Azure OpenAI
        self.llm = AzureChatOpenAI(
            openai_api_type="azure",
            openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0.3
        )
    
    def __call__(self, **kwargs) -> str:
        organism = kwargs.get("organism", "")
        concept = kwargs.get("concept", "")
        key_concepts = kwargs.get("key_concepts", [])
        
        if not organism or not concept:
            return "I need more information to provide an explanation."
        
        # Create a prompt for the LLM to provide an explanation
        from langchain.schema import SystemMessage, HumanMessage
        
        system_prompt = """You are an expert medical microbiologist providing educational explanations.
        Provide a detailed, clear explanation of the requested concept related to the specified organism.
        Include relevant clinical and microbiological details.
        If key concepts are provided, incorporate them into your explanation.
        
        Your explanation should be educational and encourage deeper understanding."""
        
        # Include key concepts if available
        key_concepts_text = ""
        if key_concepts:
            key_concepts_text = "Key concepts to incorporate:\n" + "\n".join([f"- {c}" for c in key_concepts])
        
        human_prompt = f"""
        Organism: {organism}
        Concept to explain: {concept}
        
        {key_concepts_text}
        
        Provide a detailed explanation of this concept.
        """
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
        
        response = self.llm.invoke(messages)
        
        return response.content.strip()

class KnowledgeAssessmentAgent(CustomAgentWrapper):
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.3):
        # Initialize LLM configuration
        llm_config = LLMConfig({"llm_name": model_name, "temperature": temperature})
        llm = get_llm_backend(llm_config)
        
        # Initialize custom actions
        actions = [
            LoadGuidingQuestionsAction(),
            LoadKeyConcepts(),
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
            
            I provide targeted questions and detailed feedback to ensure deep understanding.
            
            I can use pre-generated guiding questions and key concepts from the case to enhance the educational experience.""",
            llm=llm,
            actions=actions,
            reasoning_type="react"
        )
        
        self.current_organism = None
        self.current_stage = TutorStage.PRE_DIFFERENTIAL
        self.guiding_questions = []
        self.key_concepts = []
        
        # Add examples of successful interactions
        self._add_examples()
    
    def _add_examples(self):
        """Add comprehensive examples of successful agent interactions."""
        
        # Example 1: Starting knowledge assessment with RAG-generated questions
        task1 = TaskPackage(instruction="Begin assessment for N. meningitidis")
        action_chain1 = [
            (AgentAct(name="Think", params={"response": "Starting structured assessment of N. meningitidis knowledge. Let me first load any RAG-generated questions."}),
             "OK"),
            (AgentAct(name="LoadGuidingQuestions", params={"organism": "N. meningitidis"}),
             {"success": True, "message": "Loaded 15 questions for N. meningitidis", "questions": ["What are the key virulence factors of N. meningitidis?"]}),
            (AgentAct(name="LoadKeyConcepts", params={"organism": "N. meningitidis"}),
             {"success": True, "message": "Loaded 6 key concepts for N. meningitidis", "concepts": ["N. meningitidis has a polysaccharide capsule that helps evade phagocytosis"]}),
            (AgentAct(name="Finish", params={"response": "Let's discuss N. meningitidis. What are its key virulence factors and how do they contribute to pathogenesis?"}),
             "Task completed.")
        ]
        self.add_example(task1, action_chain1)

        # Example 2: Evaluating good answer about virulence using key concepts
        task2 = TaskPackage(instruction="N. meningitidis has a polysaccharide capsule that helps evade phagocytosis, and its endotoxin triggers inflammatory response")
        action_chain2 = [
            (AgentAct(name="Think", params={"response": "Student shows good understanding of key virulence factors. I'll evaluate using the key concepts we loaded."}),
             "OK"),
            (AgentAct(name="EvaluateAnswer", params={
                "organism": "N. meningitidis",
                "question": "virulence factors",
                "student_answer": "polysaccharide capsule for phagocytosis evasion, endotoxin for inflammation",
                "key_concepts": ["N. meningitidis has a polysaccharide capsule that helps evade phagocytosis"]
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

        # Example 3: Using a RAG-generated guiding question
        task3 = TaskPackage(instruction="What's the next question?")
        action_chain3 = [
            (AgentAct(name="Think", params={"response": "Student is asking for the next question. I'll use one of our RAG-generated guiding questions."}),
             "OK"),
            (AgentAct(name="Finish", params={"response": "How does N. meningitidis evade the host immune system, and what implications does this have for diagnosis and treatment?"}),
             "Task completed.")
        ]
        self.add_example(task3, action_chain3)

        # Example 4: Providing detailed explanation with key concepts
        task4 = TaskPackage(instruction="Can you explain more about meningococcal vaccines?")
        action_chain4 = [
            (AgentAct(name="Think", params={"response": "Student requesting detailed information about vaccination. I'll incorporate our key concepts."}),
             "OK"),
            (AgentAct(name="ProvideExplanation", params={
                "organism": "N. meningitidis",
                "concept": "vaccines",
                "key_concepts": ["N. meningitidis has a polysaccharide capsule that helps evade phagocytosis"]
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

        # Example 5: Fallback to generating questions when no RAG questions available
        task5 = TaskPackage(instruction="Let's discuss treatment for S. aureus")
        action_chain5 = [
            (AgentAct(name="Think", params={"response": "Student wants to discuss S. aureus treatment. Let me check if we have RAG-generated questions."}),
             "OK"),
            (AgentAct(name="LoadGuidingQuestions", params={"organism": "S. aureus"}),
             {"success": False, "message": "No question files found for S. aureus", "questions": []}),
            (AgentAct(name="GenerateQuestions", params={"organism": "S. aureus"}),
             ["What is the first-line empiric therapy for suspected S. aureus infections?", "How do you modify treatment once antibiotic susceptibilities are known?"]),
            (AgentAct(name="Finish", params={"response": "Let's discuss S. aureus treatment. What is the first-line empiric therapy for suspected S. aureus infections, and how would you modify it based on susceptibility results?"}),
             "Task completed.")
        ]
        self.add_example(task5, action_chain5)

    def __call__(self, task: TaskPackage) -> Dict:
        # Only proceed with knowledge assessment if in the right stage
        if self.current_stage != TutorStage.KNOWLEDGE_ASSESSMENT:
            return {
                "response": "Let's focus on gathering clinical information and forming a differential diagnosis before diving into detailed organism knowledge.",
                "agent": "knowledge_assessment"
            }
        
        # If we have an organism but haven't loaded questions yet, try to load them
        if self.current_organism and not self.guiding_questions:
            try:
                # Try to load guiding questions
                questions_result = self._execute_action(AgentAct(
                    name="LoadGuidingQuestions", 
                    params={"organism": self.current_organism}
                ))
                
                if isinstance(questions_result, dict) and questions_result.get("success", False):
                    self.guiding_questions = questions_result.get("questions", [])
                
                # Try to load key concepts
                concepts_result = self._execute_action(AgentAct(
                    name="LoadKeyConcepts", 
                    params={"organism": self.current_organism}
                ))
                
                if isinstance(concepts_result, dict) and concepts_result.get("success", False):
                    self.key_concepts = concepts_result.get("concepts", [])
            except Exception as e:
                print(f"Error loading RAG content: {str(e)}")
        
        # Process the task using the agent's reasoning
        response = self.llm_layer(task.instruction)
        
        return {
            "response": response,
            "agent": "knowledge_assessment"
        }
    
    def reset(self):
        """Reset the agent state."""
        self.current_organism = None
        self.current_stage = TutorStage.PRE_DIFFERENTIAL
        self.guiding_questions = []
        self.key_concepts = []