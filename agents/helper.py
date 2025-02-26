from typing import Dict
from custom_agent_wrapper import CustomAgentWrapper
from agentlite.llm.agent_llms import BaseLLM, get_llm_backend
from agentlite.llm.LLMConfig import LLMConfig
from agentlite.actions import BaseAction
from agentlite.actions.InnerActions import ThinkAction, FinishAction
from agentlite.commons import TaskPackage, AgentAct
import os
from langchain.schema import HumanMessage, SystemMessage
from agents.case_presenter import get_azure_llm

class ProvideGuidanceAction(BaseAction):
    def __init__(self):
        super().__init__(
            action_name="ProvideGuidance",
            action_desc="Provide contextual guidance to help students progress through the case",
            params_doc={
                "case_details": "Full case information",
                "conversation_history": "History of the interaction",
                "revealed_info": "Information already revealed",
                "differential_given": "Whether differential has been provided"
            }
        )
        # Initialize Azure OpenAI using the helper function
        self.llm = get_azure_llm("gpt-4o-mini", temperature=0.3)
    
    def __call__(self, **kwargs) -> str:
        case_details = kwargs.get("case_details", {}) or {}  # Handle None case
        conversation_history = kwargs.get("conversation_history", []) or []  # Handle None case
        revealed_info = kwargs.get("revealed_info", set()) or set()  # Handle None case
        differential_given = kwargs.get("differential_given", False)
        
        # Create conversation summary (last 3 interactions for context)
        conversation_summary = "\n".join([
            f"Student: {interaction['question']}\nTutor: {interaction['response']}"
            for interaction in conversation_history[-3:]
        ]) if conversation_history else "No previous interactions"
        
        # Get case text safely
        case_text = case_details.get('case_text', '') if isinstance(case_details, dict) else str(case_details)
        
        system_prompt = """You are an expert medical educator providing guidance to a student working through a clinical case.
Your role is to provide helpful hints without giving away the diagnosis.

Your guidance should:
1. Be specific enough to be helpful but not reveal the diagnosis
2. Encourage clinical reasoning and systematic thinking
3. Highlight key features they might have missed
4. Suggest areas of inquiry they haven't considered
5. Be concise (3-4 lines maximum)

If they ask a specific question about microbiology principles, answer it directly."""
        
        main_prompt = f"""Case Details: {case_text}

Conversation History:
{conversation_summary}

Information Already Revealed: {', '.join(revealed_info) if revealed_info else 'None'}
Differential Given: {differential_given}

Provide brief, targeted guidance to help the student move forward in their clinical reasoning."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=main_prompt)
        ]
        
        response = self.llm.invoke(messages)
        return {
            "response": response.content,
            "agent": "helper"
        }

class AnswerDirectQuestionAction(BaseAction):
    def __init__(self):
        super().__init__(
            action_name="AnswerDirectQuestion",
            action_desc="Answer direct educational questions not related to the current case",
            params_doc={
                "question": "The direct educational question",
                "case_details": "Full case information to check if question is related to case"
            }
        )
        # Initialize Azure OpenAI using the helper function - use a more capable model for educational content
        self.llm = get_azure_llm("gpt-4o", temperature=0.2)
    
    def __call__(self, **kwargs) -> str:
        question = kwargs.get("question", "")
        case_details = kwargs.get("case_details", {}) or {}
        
        # Get case text safely
        case_text = case_details.get('case_text', '') if isinstance(case_details, dict) else str(case_details)
        
        system_prompt = """You are an expert medical educator answering direct educational questions about microbiology, infectious diseases, and clinical medicine.

Your answers should be:
1. Accurate and evidence-based
2. Concise but comprehensive (4-6 sentences)
3. Educational and focused on key principles
4. Organized in a clear, structured format
5. Appropriate for medical students

If the question is related to the current case, indicate that you'll focus on general principles without giving away case-specific answers."""
        
        main_prompt = f"""Case Details: {case_text}

Student Question: {question}

Provide a direct educational answer to this question. If it's closely related to the current case, mention that you'll focus on general principles without revealing case-specific information."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=main_prompt)
        ]
        
        response = self.llm.invoke(messages)
        return {
            "response": response.content,
            "agent": "educator"
        }

class HelperAgent(CustomAgentWrapper):
    def __init__(self, model_name: str = None, temperature: float = 0.3):
        # Initialize LLM configuration
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        if not deployment_name:
            raise ValueError("AZURE_OPENAI_DEPLOYMENT_NAME environment variable must be set")
            
        llm_config = LLMConfig({
            "llm_name": deployment_name,
            "temperature": temperature,
            "api_type": "azure"
        })
        llm = get_llm_backend(llm_config)
        
        # Initialize custom actions
        actions = [
            ProvideGuidanceAction(),
            AnswerDirectQuestionAction(),
            ThinkAction(),
            FinishAction()
        ]
        
        super().__init__(
            name="helper",
            role="""I am an expert medical educator specializing in guiding students through clinical cases.
            
I provide guidance by:
1. Assessing where students are in their diagnostic process
2. Identifying gaps in their information gathering
3. Suggesting relevant areas of inquiry
4. Helping them recognize important patterns
5. Encouraging systematic thinking

I keep my guidance concise and focused, providing just enough help to get students moving in the right direction without giving away answers.

For direct educational questions not related to the current case, I provide accurate, concise information as an educator.""",
            llm=llm,
            actions=actions,
            reasoning_type="react"
        )
        
        self.current_case = None
        self.conversation_history = []
        self.revealed_info = set()
        
        # Add examples of successful interactions
        self._add_examples()
    
    def determine_action(self, question: str) -> BaseAction:
        """
        Use an LLM to determine which action to take based on the question.
        
        Args:
            question: The student's question
            
        Returns:
            The appropriate action to handle the question
        """
        # Use a smaller model for action determination
        determine_action_llm = get_azure_llm("gpt-4o-mini", temperature=0.1)
        
        # Get case text safely
        case_text = ""
        if self.current_case:
            case_text = self.current_case.get('case_text', '') if isinstance(self.current_case, dict) else str(self.current_case)
        
        # Create a prompt for the LLM to help determine the appropriate action
        system_prompt = """You are an expert medical educator helping to determine which action to take based on a student's question.
        
Available actions are:
1. ProvideGuidance - For providing contextual guidance related to the current clinical case
2. AnswerDirectQuestion - For answering direct educational questions not related to the current case

ProvideGuidance is used when:
- The student is asking for help with the current case
- The question is about what to do next in the case
- The student is confused about the case
- The question is directly related to the patient or findings in the current case

AnswerDirectQuestion is used when:
- The student is asking a general educational question not specific to the case
- The question is about medical knowledge, microbiology, or clinical principles
- The question could be answered without knowing the details of the current case
- Examples: "What are the causes of traveler's diarrhea?", "How does penicillin work?", "What is the mechanism of action of fluoroquinolones?"

Respond with ONLY the action name, nothing else."""
        
        # Get the context from the question and case
        context = f"""Student question: {question}

Current case: {case_text if case_text else "No case loaded"}

Based on the question and case details, which action should be taken?"""
        
        # Use LLM to determine action
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=context)
        ]
        
        response = determine_action_llm.invoke(messages)
        action_name = response.content.strip()
        
        # Map the action name to the actual action
        for action in self.actions:
            if action.action_name == action_name:
                return action
            
        # Default to ProvideGuidance if no clear match
        return next(action for action in self.actions if isinstance(action, ProvideGuidanceAction))
    
    def __call__(self, task: TaskPackage) -> str:
        """Handle requests for guidance and help."""
        question = task.instruction
        
        # Use LLM to determine which action to take
        action = self.determine_action(question)
        
        # Execute the appropriate action
        if isinstance(action, AnswerDirectQuestionAction):
            return action(
                question=question,
                case_details=self.current_case
            )
        else:  # Default to ProvideGuidance
            return action(
                case_details=self.current_case,
                conversation_history=self.conversation_history,
                revealed_info=self.revealed_info,
                differential_given=False  # This will be updated when integrated with the tutor
            )
    
    def reset(self):
        """Reset the agent state."""
        self.current_case = None
        self.conversation_history = []
        self.revealed_info = set()

    def _add_examples(self):
        """Add examples of successful guidance interactions."""
        
        # Example 1: Early case guidance with no case loaded
        task1 = TaskPackage(instruction="I'm not sure where to start")
        action_chain1 = [
            (AgentAct(name="Think", params={"response": "No case loaded yet."}),
             "OK"),
            (AgentAct(name="Finish", params={"response": {
                "response": "I notice you're asking for help, but I don't have access to the current case details. Please make sure a case has been started first.",
                "agent": "helper"
            }}),
             "Task completed.")
        ]
        self.add_example(task1, action_chain1)

        # Example 2: Early case guidance with case loaded
        task2 = TaskPackage(instruction="I'm not sure where to start with this case")
        action_chain2 = [
            (AgentAct(name="Think", params={"response": "Student needs initial guidance on case approach."}),
             "OK"),
            (AgentAct(name="ProvideGuidance", params={
                "case_details": {"case_text": "Patient presents with fever and cough"},
                "conversation_history": [],
                "revealed_info": [],
                "differential_given": False
            }),
             {"response": "Let's approach this systematically. Consider characterizing the main symptoms, understanding their timeline, and identifying any risk factors. What would you like to know about the presenting symptoms?",
              "agent": "helper"}),
            (AgentAct(name="Finish", params={"response": {
                "response": "Let's approach this systematically...",
                "agent": "helper"
            }}),
             "Task completed.")
        ]
        self.add_example(task2, action_chain2)

        # Example 3: Mid-case guidance
        task3 = TaskPackage(instruction="What should I ask next?")
        action_chain3 = [
            (AgentAct(name="Think", params={"response": "Student needs guidance on next steps."}),
             "OK"),
            (AgentAct(name="ProvideGuidance", params={
                "case_details": {"case_text": "Patient with fever, cough for 3 days"},
                "conversation_history": [
                    {"question": "How long have you been sick?", "response": "3 days"},
                    {"question": "What symptoms do you have?", "response": "Fever and cough"}
                ],
                "revealed_info": ["symptoms", "duration"],
                "differential_given": False
            }),
             {"response": "You've gathered basic symptom information. Consider exploring associated symptoms, risk factors or exposures, and relevant past medical history. Which area interests you most?",
              "agent": "helper"}),
            (AgentAct(name="Finish", params={"response": {
                "response": "You've gathered basic symptom information...",
                "agent": "helper"
            }}),
             "Task completed.")
        ]
        self.add_example(task3, action_chain3)
        
        # Example 4: Direct educational question
        task4 = TaskPackage(instruction="What are the causes of traveler's diarrhea in third world countries?")
        action_chain4 = [
            (AgentAct(name="Think", params={"response": "This is a direct educational question not related to the current case."}),
             "OK"),
            (AgentAct(name="AnswerDirectQuestion", params={
                "question": "What are the causes of traveler's diarrhea in third world countries?",
                "case_details": {"case_text": "Patient with fever, cough for 3 days"}
            }),
             {"response": "Traveler's diarrhea in developing countries is primarily caused by enterotoxigenic E. coli (ETEC), which accounts for about 50% of cases. Other bacterial pathogens include Campylobacter, Salmonella, and Shigella. Viral causes include norovirus and rotavirus, while parasitic agents like Giardia lamblia and Cryptosporidium are less common but important in certain regions. Risk factors include consuming contaminated food or water, with prevention focusing on careful selection of food and beverages and proper hand hygiene.",
              "agent": "educator"}),
            (AgentAct(name="Finish", params={"response": {
                "response": "Traveler's diarrhea in developing countries is primarily caused by...",
                "agent": "educator"
            }}),
             "Task completed.")
        ]
        self.add_example(task4, action_chain4) 