from typing import Dict, Optional
from agentlite.agents import BaseAgent as AgentLiteBaseAgent
from agentlite.llm.agent_llms import BaseLLM, get_llm_backend
from agentlite.llm.LLMConfig import LLMConfig
from agentlite.actions import BaseAction
from agentlite.actions.InnerActions import ThinkAction, FinishAction
from agentlite.commons import TaskPackage, AgentAct
from .case_generator import CaseGeneratorAgent

class PresentCaseAction(BaseAction):
    def __init__(self):
        super().__init__(
            action_name="PresentCase",
            action_desc="Present a clinical case to the student",
            params_doc={"case": "The case data to present"}
        )
        # Initialize Azure OpenAI
        from langchain.chat_models import AzureChatOpenAI
        import os
        
        self.llm = AzureChatOpenAI(
            openai_api_type="azure",
            openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0.1
        )
    
    def __call__(self, **kwargs) -> str:
        case = kwargs.get("case", {})
        if not case:
            return {"error": "No valid case provided"}
        
        # Get the unstructured case text
        case_text = case.get("case_text", "")
        if not case_text:
            return {"error": "No case text provided"}
        
        # Create a prompt for the LLM to generate the initial presentation
        prompt = f"""Here is a clinical case:
{case_text}

Generate a one-line initial presentation of this case.
Focus on the patient's demographics and chief complaint.
Use this exact format, nothing else: "A [age] year old [sex] presents with [chief complaint]." """
        
        # Get the one-liner from LLM
        from langchain.schema import HumanMessage
        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages).content
        
        return {
            "case_presentation": response.strip(),
            "case_text": case_text
        }

class AssessReadinessAction(BaseAction):
    def __init__(self):
        super().__init__(
            action_name="AssessReadiness",
            action_desc="Assess if student has gathered enough information for differential",
            params_doc={
                "conversation_history": "History of student questions and responses",
                "case_details": "Current case details",
                "revealed_info": "Set of information categories already revealed"
            }
        )
        # Initialize Azure OpenAI
        from langchain.chat_models import AzureChatOpenAI
        import os
        
        self.llm = AzureChatOpenAI(
            openai_api_type="azure",
            openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0.1
        )
    
    def __call__(self, **kwargs) -> str:
        conversation_history = kwargs.get("conversation_history", [])
        case_details = kwargs.get("case_details", {})
        revealed_info = kwargs.get("revealed_info", set())
        
        # Create a summary of what information has been gathered
        conversation_summary = "\n".join([
            f"Student asked: {interaction['question']}\nRevealed: {interaction['response']}"
            for interaction in conversation_history
        ])
        
        system_prompt = """You are an experienced attending physician evaluating whether a medical student or resident 
        has gathered sufficient information to formulate a reasonable differential diagnosis. Consider:

        1. Key elements needed for any differential:
           - Chief complaint and its characteristics
           - Relevant associated symptoms
           - Basic vital signs
           - Pertinent physical exam findings
           - Key epidemiological factors
        
        2. Clinical reasoning principles:
           - Pattern recognition
           - Epidemiological risk factors
           - Key discriminating features
           - Red flag symptoms/signs
        
        Evaluate if enough critical information has been gathered to generate a meaningful differential diagnosis.
        Consider both breadth and depth of information gathering.
        
        Respond in this format:
        {
            "ready": true/false,
            "message": "Your explanation",
            "missing_critical_info": ["list", "of", "critical", "missing", "elements"] (if not ready)
        }
        """
        
        main_prompt = f"""Case Details:
{case_details.get('case_text', '')}

Information Gathered So Far:
{conversation_summary}

Categories of Information Revealed:
{', '.join(revealed_info) if revealed_info else 'None'}

Based on this information, assess if sufficient information has been gathered to formulate a reasonable differential diagnosis.
Consider what a well-trained physician would need to generate a meaningful differential.
"""
        
        from langchain.schema import HumanMessage, SystemMessage
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=main_prompt)
        ]
        
        response = self.llm.invoke(messages)
        
        try:
            import json
            evaluation = json.loads(response.content)
            return {
                "ready": evaluation["ready"],
                "message": evaluation["message"]
            }
        except:
            # Fallback if JSON parsing fails
            return {
                "ready": False,
                "message": "Unable to properly evaluate readiness. Please continue gathering key clinical information."
            }

class EvaluateQuestionAction(BaseAction):
    def __init__(self):
        super().__init__(
            action_name="EvaluateQuestion",
            action_desc="Evaluate and respond to student's question about the case",
            params_doc={
                "question": "Student's question", 
                "case_details": "Current case details",
                "conversation_history": "List of previous interactions",
                "revealed_info": "Set of information categories already revealed"
            }
        )
        # Initialize Azure OpenAI for main responses
        from langchain.chat_models import AzureChatOpenAI
        import os
        
        self.llm = AzureChatOpenAI(
            openai_api_type="azure",
            openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0.1
        )
        
        # Initialize GPT-4 mini for diagnostic question checking
        self.diagnostic_checker = AzureChatOpenAI(
            openai_api_type="azure",
            openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),  # Use your GPT-4 mini deployment
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0.0  # Keep temperature low for consistent classification
        )
    
    def is_diagnostic_question(self, question: str) -> bool:
        """Use LLM to determine if the question is asking for diagnostic information."""
        from langchain.schema import HumanMessage, SystemMessage
        
        system_prompt = """You are a medical education expert who determines if questions are asking for diagnostic information.
        Diagnostic information includes:
        1. Laboratory test results
        2. Imaging studies (X-rays, CT, MRI, etc.)
        3. Microbiology results (cultures, gram stains, etc.)
        4. Other diagnostic procedures
        
        Respond with ONLY 'true' if the question is asking for diagnostic information, or 'false' if it is not.
        Do not provide any other text in your response."""
        
        prompt = f"""Question: "{question}"
        Is this question asking for diagnostic information (lab results, imaging, cultures, etc.)?
        Remember to respond with ONLY 'true' or 'false'."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        
        response = self.diagnostic_checker.invoke(messages).content.lower().strip()
        return response == 'true'
    
    def __call__(self, **kwargs) -> str:
        question = kwargs.get("question", "").lower()
        case_details = kwargs.get("case_details", {})
        differential_given = kwargs.get("differential_given", False)
        conversation_history = kwargs.get("conversation_history", [])
        revealed_info = kwargs.get("revealed_info", set())
        
        # Check if this is a diagnostic question using LLM
        if self.is_diagnostic_question(question) and not differential_given:
            return {
                "response": """I notice you're asking about diagnostic information. In clinical practice, it's important to form an initial differential diagnosis based on the history and physical examination before ordering tests. This helps us:
                1. Focus on the most relevant diagnostic tests
                2. Avoid unnecessary testing
                3. Develop strong clinical reasoning skills
                
                We can move to diagnostic tests after you provide your differential diagnosis.""",
                "revealed_category": None
            }
        
        # Create the system prompt
        system_prompt = """You are an expert medical microbiology tutor. Your role is to present clinical cases and 
        guide students through the diagnostic process in specific phases:
        1. Initial information gathering (history and physical examination) - minimum 3 questions
        2. Differential diagnosis with feedback and discussion
        3. Laboratory/diagnostic testing to refine differential
        4. Final diagnosis
        
        Format your responses concisely and clearly, as they will be read directly by the student.
        Present information progressively, revealing only what is asked.
        Don't give too much information to the student or suggest what to ask next.   
        Do not reveal laboratory or diagnostic test results until after a differential diagnosis is provided.
        
        Current case state:
        - Information revealed so far: {revealed_categories}
        - Differential diagnosis given: {differential_status}
        """
        
        # Create the conversation context
        conversation_context = "\n".join([
            f"Student: {interaction['question']}\nTutor: {interaction['response']}"
            for interaction in conversation_history[-3:]  # Include last 3 interactions for context
        ])
        
        # Create the main prompt
        prompt = f"""Case Details:
{case_details.get('case_text', '')}

Conversation History:
{conversation_context}

Current Question: {question}

Please respond to the student's question following these rules:
1. If they're asking about labs/tests before giving a differential diagnosis, redirect them to provide a differential first
2. Only reveal information that is specifically asked about
3. If they've given a differential diagnosis, you can reveal lab results if requested
4. Format your response concisely and clearly
5. If they need more information gathering, suggest specific areas they should ask about
Don't give too much information to the student or suggest what to ask next.   

Your response should be natural and educational, but avoid revealing information not specifically requested."""

        from langchain.schema import HumanMessage, SystemMessage
        messages = [
            SystemMessage(content=system_prompt.format(
                revealed_categories=", ".join(revealed_info) if revealed_info else "None",
                differential_status="Yes" if differential_given else "No"
            )),
            HumanMessage(content=prompt)
        ]
        
        response = self.llm.invoke(messages)
        
        # Determine what category of information was revealed
        revealed_category = None
        if any(word in question for word in ["lab", "test", "xray", "ct", "mri", "culture"]) and differential_given:
            revealed_category = "labs"
        elif any(word in question for word in ["symptom", "complain", "feel", "pain", "fever", "cough"]):
            revealed_category = "symptoms"
        elif any(word in question for word in ["exam", "vital", "temperature", "temp", "bp", "pulse", "breathing"]):
            revealed_category = "physical_exam"
        elif any(word in question for word in ["exposure", "contact", "travel", "risk", "epidemiology", "sick", "outbreak"]):
            revealed_category = "epidemiology"
        elif "history" in question or "medical" in question or "past" in question:
            revealed_category = "medical_history"
            
        return {
            "response": response.content,
            "revealed_category": revealed_category
        }

class CasePresenterAgent(AgentLiteBaseAgent):
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.3):
        # Initialize LLM configuration
        llm_config = LLMConfig({"llm_name": model_name, "temperature": temperature})
        llm = get_llm_backend(llm_config)
        
        # Initialize the case generator
        self.case_generator = CaseGeneratorAgent(model_name=model_name, temperature=temperature)
        
        # Initialize custom actions
        actions = [
            PresentCaseAction(),
            AssessReadinessAction(),
            EvaluateQuestionAction(),
            ThinkAction(),
            FinishAction()
        ]
        
        super().__init__(
            name="case_presenter",
            role="""I am an expert medical case presenter. I:
            1. Present clinical cases progressively
            2. Evaluate student questions and reveal appropriate information
            3. Track what information has been revealed
            4. Assess readiness for differential diagnosis""",
            llm=llm,
            actions=actions,
            reasoning_type="react"
        )
        
        self.current_case = None
        self.revealed_info = set()  # Track what information has been revealed
        self.differential_given = False
        self.diagnostic_tests_revealed = False
        self.conversation_history = []  # Track conversation history
    
    def __call__(self, task: TaskPackage) -> str:
        """Handle case generation, presentation, and student questions using LLM-driven responses."""
        instruction = task.instruction.lower()
        
        # Handle initial case presentation explicitly
        if instruction == "present initial case":
            action = PresentCaseAction()
            # Get case from task context if it exists, otherwise use current_case
            case_data = getattr(task, 'context', {}).get('case', {}) or self.current_case
            result = action(case=case_data)
            if isinstance(result, dict):
                self.current_case = result.get("full_case", {})
                response = result.get("case_presentation", "A patient presents for evaluation.")
                self.conversation_history.append({
                    "question": "present initial case",
                    "response": response
                })
                return response
            return str(result)
        
        # Handle readiness check
        if instruction == "ready for differential":
            action = AssessReadinessAction()
            result = action(
                conversation_history=self.conversation_history,
                case_details=self.current_case,
                revealed_info=self.revealed_info
            )
            response = result.get("message") if isinstance(result, dict) else str(result)
            self.conversation_history.append({
                "question": instruction,
                "response": response
            })
            return response
        
        # For all other queries, treat as a question about the case
        action = EvaluateQuestionAction()
        result = action(
            question=task.instruction,
            case_details=self.current_case,
            stage="post_differential" if self.differential_given else "initial",
            differential_given=self.differential_given,
            conversation_history=self.conversation_history,
            revealed_info=self.revealed_info
        )
        
        # Update revealed info if applicable
        if isinstance(result, dict):
            if result.get("revealed_category"):
                self.revealed_info.add(result["revealed_category"])
            response = result.get("response", str(result))
            self.conversation_history.append({
                "question": task.instruction,
                "response": response
            })
            return response
        
        return str(result)
    
    def reset(self):
        """Reset the agent state."""
        self.current_case = None
        self.revealed_info = set()
        self.differential_given = False
        self.diagnostic_tests_revealed = False
        self.conversation_history = []  # Reset conversation history