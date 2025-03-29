from typing import Dict, Optional
from custom_agent_wrapper import CustomAgentWrapper
from agentlite.llm.agent_llms import BaseLLM, get_llm_backend
from agentlite.llm.LLMConfig import LLMConfig
from agentlite.actions import BaseAction
from agentlite.actions.InnerActions import ThinkAction, FinishAction
from agentlite.commons import TaskPackage, AgentAct
import os
from langchain.chat_models import AzureChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from shared_definitions import TutorStage  # Import the stage enum from shared_definitions

class RespondToQuestionAction(BaseAction):
    def __init__(self):
        super().__init__(
            action_name="RespondToQuestion",
            action_desc="Respond to student's question as the patient",
            params_doc={
                "question": "Student's question",
                "case_details": "Full case information",
                "conversation_history": "Previous interactions",
                "revealed_info": "Information already revealed",
                "current_stage": "Current stage of the tutor"
            }
        )
        # Initialize Azure OpenAI
        self.llm = AzureChatOpenAI(
            openai_api_type="azure",
            model="gpt-4o",
            openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0.5
        )
    
    def __call__(self, **kwargs) -> str:
        question = kwargs.get("question", "")
        case_details = kwargs.get("case_details", {})
        conversation_history = kwargs.get("conversation_history", [])
        revealed_info = kwargs.get("revealed_info", set())
        current_stage = kwargs.get("current_stage", TutorStage.PRE_DIFFERENTIAL)
        
        # Create conversation context
        conversation_summary = "\n".join([
            f"Doctor: {interaction['question']}\nMe: {interaction['response']}"
            for interaction in conversation_history[-3:]  # Include last 3 interactions for context
        ])
        
        system_prompt = """You are a patient in a clinical setting. You should:
        1. Respond naturally to questions about your symptoms, history, and condition
        2. Maintain consistency with previously revealed information
        3. Only reveal information that is specifically asked about
        4. Use lay person's terms unless repeating medical terms used by the doctor
        5. Show appropriate levels of concern, discomfort, or anxiety based on your condition
        6. Maintain the personality and background defined in your case
        
        Remember:
        - You are not a medical expert - don't use technical terms unless the doctor used them first
        - Express symptoms as you experience them, not in medical terminology
        - Be consistent with your previous answers
        - Only answer what is asked - don't volunteer additional information
        - Show appropriate emotional responses to your condition
        - Stay in character as the patient described in the case
        """
        
        main_prompt = f"""Your case details:
{case_details.get('case_text', '')}

Previous conversation:
{conversation_summary}

Information already revealed:
{', '.join(revealed_info) if revealed_info else 'None'}

The doctor asks: {question}

Respond naturally as the patient, keeping in mind:
1. Only reveal information specifically asked about
2. Use lay person's terms
3. Show appropriate emotion/concern
4. Stay consistent with previous answers
5. Don't volunteer additional information"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=main_prompt)
        ]
        
        response = self.llm.invoke(messages)
        
        # Determine what category of information was revealed
        revealed_category = None
        if any(word in question.lower() for word in ["symptom", "feel", "pain", "hurt", "bother", "sick"]):
            revealed_category = "symptoms"
        elif any(word in question.lower() for word in ["exam", "check", "vital", "temperature", "pressure", "heart", "breathing"]):
            revealed_category = "physical_exam"
        elif any(word in question.lower() for word in ["contact", "travel", "exposure", "others", "sick", "family", "work", "home", "job", "occupation", "employ", "profession"]):
            revealed_category = "epidemiology"
        elif any(word in question.lower() for word in ["history", "medical", "past", "condition", "problem", "medication", "allergy"]):
            revealed_category = "medical_history"
            
        return {
            "response": response.content,
            "revealed_category": revealed_category,
            "agent": "patient"
        }

class ElaborateResponseAction(BaseAction):
    def __init__(self):
        super().__init__(
            action_name="ElaborateResponse",
            action_desc="Provide more detail about a previously discussed topic",
            params_doc={
                "topic": "The topic to elaborate on",
                "case_details": "Full case information",
                "conversation_history": "Previous interactions"
            }
        )
        # Initialize Azure OpenAI
        self.llm = AzureChatOpenAI(
            openai_api_type="azure",
            openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0.5
        )
    
    def __call__(self, **kwargs) -> str:
        topic = kwargs.get("topic", "")
        case_details = kwargs.get("case_details", {})
        conversation_history = kwargs.get("conversation_history", [])
        
        # Find previous mentions of this topic
        relevant_interactions = [
            interaction for interaction in conversation_history
            if topic.lower() in interaction["question"].lower() or topic.lower() in interaction["response"].lower()
        ]
        
        topic_history = "\n".join([
            f"Doctor: {interaction['question']}\nMe: {interaction['response']}"
            for interaction in relevant_interactions
        ])
        
        system_prompt = """You are a patient elaborating on a previously discussed aspect of your condition.
        Provide more detail while:
        1. Maintaining consistency with previous responses
        2. Using lay person's terms
        3. Showing appropriate emotion/concern
        4. Staying in character
        5. Only elaborating on the specific topic asked about"""
        
        main_prompt = f"""Your case details:
{case_details.get('case_text', '')}

Previous discussion of this topic:
{topic_history}

The doctor wants more detail about: {topic}

Elaborate naturally as the patient, while:
1. Being consistent with previous answers
2. Using lay person's terms
3. Showing appropriate emotion/concern
4. Only elaborating on this specific topic"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=main_prompt)
        ]
        
        response = self.llm.invoke(messages)
        return {
            "response": response.content,
            "type": "elaboration"
        }

class PatientAgent(CustomAgentWrapper):
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.3):
        # Initialize LLM configuration
        llm_config = LLMConfig({"llm_name": model_name, "temperature": temperature})
        llm = get_llm_backend(llm_config)
        
        # Initialize custom actions
        actions = [
            RespondToQuestionAction(),
            ElaborateResponseAction(),
            ThinkAction(),
            FinishAction()
        ]
        
        super().__init__(
            name="patient",
            role="""I am a patient in a clinical setting, responding to questions from medical students and doctors.
            
            I respond naturally to questions by:
            1. Using lay person's terms unless repeating medical terms used by the doctor
            2. Expressing symptoms as I experience them
            3. Showing appropriate emotional responses
            4. Maintaining consistency with my case details
            5. Only revealing information that is specifically asked about
            
            I help the learning process by:
            1. Providing realistic patient responses
            2. Maintaining character consistency
            3. Showing appropriate health literacy
            4. Expressing natural concerns and emotions
            5. Giving accurate but non-technical descriptions
            
            I maintain the educational value by:
            1. Only revealing information when asked
            2. Staying true to the case details
            3. Providing consistent responses
            4. Showing realistic patient behavior
            5. Expressing appropriate concerns""",
            llm=llm,
            actions=actions,
            reasoning_type="react"
        )
        
        self.current_case = None
        self.conversation_history = []
        self.revealed_info = set()
        self.current_stage = TutorStage.PRE_DIFFERENTIAL
        
        # Add examples of successful interactions
        self._add_examples()
    
    def __call__(self, task: TaskPackage) -> str:
        """Handle questions from the student/doctor."""
        instruction = task.instruction.lower()
        
        # Check if this is a lab/test result request
        if any(word in instruction for word in ["lab", "test", "xray", "scan", "culture", "blood"]):
            if self.current_stage == TutorStage.PRE_DIFFERENTIAL:
                return {
                    "response": "The doctor hasn't told me about any test results yet. They mentioned they wanted to hear what you think might be going on first.",
                    "agent": "patient"
                }
        
        # Check if this is a request for elaboration
        if "tell me more about" in instruction or "can you elaborate" in instruction:
            action = ElaborateResponseAction()
            topic = instruction.replace("tell me more about", "").replace("can you elaborate on", "").strip()
            result = action(
                topic=topic,
                case_details=self.current_case,
                conversation_history=self.conversation_history
            )
            response = result.get("response", str(result))
            self.conversation_history.append({
                "question": task.instruction,
                "response": response
            })
            return {
                "response": response,
                "agent": "patient"
            }
        
        # Handle regular questions
        action = RespondToQuestionAction()
        result = action(
            question=task.instruction,
            case_details=self.current_case,
            conversation_history=self.conversation_history,
            revealed_info=self.revealed_info,
            current_stage=self.current_stage
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
            return {
                "response": response,
                "agent": "patient"
            }
        
        return str(result)
    
    def reset(self):
        """Reset the agent state."""
        self.current_case = None
        self.conversation_history = []
        self.revealed_info = set()
        self.current_stage = TutorStage.PRE_DIFFERENTIAL

    def _add_examples(self):
        """Add comprehensive examples of successful agent interactions."""
        
        # Example 1: Basic symptom question
        task1 = TaskPackage(instruction="What brings you to the hospital today?")
        action_chain1 = [
            (AgentAct(name="Think", params={"response": "Patient will describe chief complaint in natural terms."}),
             "OK"),
            (AgentAct(name="RespondToQuestion", params={
                "case_details": {
                    "presenting_symptoms": ["fever", "productive cough", "chest pain"],
                    "duration": "3 days"
                },
                "question": "What brings you to the hospital today?"
            }),
             {"response": "I've been feeling really awful for the past 3 days. I've got this bad cough that's bringing up yellow stuff, and my chest hurts, especially when I breathe. I've also been running a fever.",
              "revealed_category": "symptoms"}),
            (AgentAct(name="Finish", params={"response": "I've been feeling really awful for the past 3 days..."}),
             "Task completed.")
        ]
        self.add_example(task1, action_chain1)

        # Example 2: Follow-up symptom question
        task2 = TaskPackage(instruction="Can you tell me more about the cough?")
        action_chain2 = [
            (AgentAct(name="Think", params={"response": "Patient will elaborate on previously mentioned symptom."}),
             "OK"),
            (AgentAct(name="ElaborateResponse", params={
                "topic": "cough",
                "case_details": {
                    "symptoms": {
                        "cough": "productive with yellow sputum, worse at night, causes chest pain"
                    }
                }
            }),
             {"response": "Well, it's a really deep cough, and when I cough stuff comes up - it's thick and yellow. It seems to get worse at night when I'm trying to sleep. Every time I cough, I get this sharp pain in my chest. It's really been keeping me up.",
              "type": "elaboration"}),
            (AgentAct(name="Finish", params={"response": "Well, it's a really deep cough..."}),
             "Task completed.")
        ]
        self.add_example(task2, action_chain2)

        # Example 3: Medical history question
        task3 = TaskPackage(instruction="Do you have any medical conditions?")
        action_chain3 = [
            (AgentAct(name="Think", params={"response": "Patient will discuss medical history in lay terms."}),
             "OK"),
            (AgentAct(name="RespondToQuestion", params={
                "case_details": {
                    "medical_history": "History of COPD, well-controlled hypertension"
                },
                "question": "Do you have any medical conditions?"
            }),
             {"response": "Yes, I have COPD - the doctor called it that. I also take medicine for my blood pressure. Both have been pretty well controlled with my medications.",
              "revealed_category": "medical_history"}),
            (AgentAct(name="Finish", params={"response": "Yes, I have COPD..."}),
             "Task completed.")
        ]
        self.add_example(task3, action_chain3)

        # Example 4: Epidemiological question
        task4 = TaskPackage(instruction="Has anyone around you been sick?")
        action_chain4 = [
            (AgentAct(name="Think", params={"response": "Patient will describe relevant exposures naturally."}),
             "OK"),
            (AgentAct(name="RespondToQuestion", params={
                "case_details": {
                    "epidemiology": "Several coworkers with similar symptoms in past week"
                },
                "question": "Has anyone around you been sick?"
            }),
             {"response": "Now that you mention it, a few people at work have been out sick this past week. I think they had similar symptoms - one of my colleagues was complaining about a bad cough before she took sick leave.",
              "revealed_category": "epidemiology"}),
            (AgentAct(name="Finish", params={"response": "Now that you mention it..."}),
             "Task completed.")
        ]
        self.add_example(task4, action_chain4)

        # Example 5: Physical exam response
        task5 = TaskPackage(instruction="I'm going to listen to your lungs now. Take a deep breath.")
        action_chain5 = [
            (AgentAct(name="Think", params={"response": "Patient will respond to physical exam appropriately."}),
             "OK"),
            (AgentAct(name="RespondToQuestion", params={
                "case_details": {
                    "physical_exam": {
                        "lungs": "Decreased breath sounds and crackles in right lower lobe",
                        "symptoms": "chest pain with deep breathing"
                    }
                },
                "question": "I'm going to listen to your lungs now. Take a deep breath."
            }),
             {"response": "*Tries to take a deep breath but winces* Ouch, it hurts when I breathe in deeply, especially on the right side. *Coughs*",
              "revealed_category": "physical_exam"}),
            (AgentAct(name="Finish", params={"response": "*Tries to take a deep breath but winces*..."}),
             "Task completed.")
        ]
        self.add_example(task5, action_chain5) 