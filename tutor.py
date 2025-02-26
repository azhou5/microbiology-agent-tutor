from typing import Dict, Optional
from agentlite.agents import ManagerAgent
from langchain.chat_models import AzureChatOpenAI
from agentlite.actions import BaseAction, FinishAction
from agentlite.actions.InnerActions import ThinkAction
from agentlite.commons import TaskPackage, AgentAct
from agents.case_presenter import CasePresenterAgent
from agents.case_generator_RAG import CaseGeneratorRAGAgent
from agents.knowledge_assessment import KnowledgeAssessmentAgent
from agents.helper import HelperAgent
from agents.patient import PatientAgent
import os
from dotenv import load_dotenv
from langchain.schema import HumanMessage
from shared_definitions import TutorStage

# Load environment variables
load_dotenv()

# Verify Azure OpenAI configuration
if not os.getenv("AZURE_OPENAI_API_KEY") or not os.getenv("AZURE_OPENAI_ENDPOINT"):
    raise ValueError("Missing required Azure OpenAI environment variables")

# Validate Azure OpenAI deployment configuration
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
if not deployment_name:
    raise ValueError("AZURE_OPENAI_DEPLOYMENT_NAME must be set to your Azure OpenAI deployment name")

class TutorStateAction(BaseAction):
    """Action to update and check tutor state."""
    def __init__(self):
        super().__init__(
            action_name="UpdateState",
            action_desc="Update and check the tutor's state based on the current interaction",
            params_doc={
                "state_update": "State to update",
                "state_value": "Value to set"
            }
        )
    
    def __call__(self, **kwargs) -> str:
        return "State updated successfully"

class AgentTrackingFinishAction(FinishAction):
    """Action to finish a task while preserving agent information."""
    def __init__(self):
        super().__init__()
    
    def __call__(self, **kwargs) -> str:
        # First, call the parent class's __call__ method with only the parameters it expects
        response_param = kwargs.get("response", "")
        response = super().__call__(response=response_param)
        
        # Now, handle the agent tracking separately
        agent = kwargs.get("agent", "tutor") if "agent" in kwargs else "tutor"
        
        # If the response is already a dict with agent info, return it as is
        if isinstance(response, dict) and "response" in response and "agent" in response:
            return response
            
        # Otherwise, wrap the response with agent info
        return {
            "response": str(response),
            "agent": agent
        }

class MedicalMicrobiologyTutor(ManagerAgent):
    def __init__(self, model_name: str = None, temperature: float = 0.1):
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        if not deployment_name:
            raise ValueError("AZURE_OPENAI_DEPLOYMENT_NAME environment variable must be set")
        print(f"Using Azure OpenAI deployment: {deployment_name}")
        
        # Initialize Azure OpenAI through LangChain
        self.llm = AzureChatOpenAI(
            openai_api_type="azure",
            openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            deployment_name=deployment_name,
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=temperature,
            streaming=True,
        )
        
        # Initialize specialized agents with the same deployment name
        self.case_presenter = CasePresenterAgent(model_name=deployment_name, temperature=temperature)
        self.case_generator = CaseGeneratorRAGAgent(model_name=deployment_name, temperature=temperature)
        self.knowledge_assessment = KnowledgeAssessmentAgent(model_name=deployment_name, temperature=temperature)
        self.patient = PatientAgent(model_name=deployment_name, temperature=temperature)
        self.helper = HelperAgent(model_name=deployment_name, temperature=temperature)
        
        # Initialize manager agent with specialized agents as team members
        super().__init__( 
            llm=self.llm,
            name="MedicalMicrobiologyTutor",
            role="""I am an expert medical microbiology tutor that coordinates between specialized agents to guide students through clinical cases.
            
            I follow these educational principles:
            1. Start with case presentation and information gathering
            2. Require a differential diagnosis before final diagnosis
            3. Only reveal lab results after differential diagnosis
            4. Test knowledge after correct diagnosis
            
            I coordinate these specialized agents:
            - Case Generator: Creates new cases
            - Case Presenter: Handles case flow, clinical reasoning, and diagnostic evaluation
            - Knowledge Assessment: Tests understanding of identified organisms
            - Patient: Provides realistic patient responses during information gathering
            - Helper: Provides guidance when students are stuck
            
            I maintain the educational flow by:
            1. Tracking the current phase (case presentation, differential, final diagnosis, knowledge assessment)
            2. Ensuring prerequisites are met before advancing
            3. Routing student interactions to appropriate agents
            4. Managing transitions between phases
            
            Here is how I route different types of interactions:
            1. For new case requests (e.g. "start new case", "begin case"):
               - I use the case_generator to create a case
               - Then have the case_presenter introduce it
            
            2. For information gathering (questions about symptoms, exam, history):
               - First check with case_presenter if it's a diagnostic question
               - If not diagnostic, route to the patient agent for natural responses
               - The patient agent tracks what information has been revealed
            
            3. For physical examination questions:
               - If directed at the patient (e.g., "Can you take a deep breath?"), route to patient agent
               - If asking for doctor's findings (e.g., "What do you hear in the lungs?"), route to case_presenter
               - If asking for vital signs or exam results, route to case_presenter
               - The case_presenter tracks what physical exam information has been revealed
            
            4. For readiness assessment and differential diagnosis:
               - When students ask if they have enough information, route to case_presenter
               - Case presenter evaluates readiness and differential attempts
               - Only after readiness confirmed, proceed with differential evaluation
            
            5. For final diagnosis attempts:
               - Must have given differential first
               - Route to case_presenter for evaluation
               - If correct, transition to knowledge_assessment
            
            6. For knowledge assessment questions:
               - Route to knowledge_assessment once in that phase
               - knowledge_assessment evaluates understanding of the pathogen
            
            7. When the student is unsure or needs guidance:
               - Route to the helper agent for contextual hints
            
            I maintain state through my actions to ensure proper flow.""",
            actions=[TutorStateAction(), ThinkAction(), AgentTrackingFinishAction()],
            TeamAgents=[self.case_presenter, self.case_generator, self.knowledge_assessment, self.patient, self.helper],
            reasoning_type="planreact"
        )
        
        self.current_organism = None
        self.in_knowledge_assessment = False
        self.differential_given = False
        self._last_agent = None
        self.current_stage = TutorStage.PRE_DIFFERENTIAL
        
        # Add examples of successful interactions
        self._add_examples()
    
    def _add_examples(self):
        """Add comprehensive examples of successful agent interactions and routing."""
        
        # Example 1: Starting a new case
        task1 = TaskPackage(instruction="Can we start a new case?")
        action_chain1 = [
            (AgentAct(name="Think", params={"response": "Student wants to start a new case. I will generate one and have it presented."}),
             "OK"),
            (AgentAct(name="case_generator", params={"Task": "Generate a new clinical case"}),
             {"case_text": "A 45-year-old male presents with fever and productive cough for 3 days..."}),
            (AgentAct(name="case_presenter", params={"Task": "present initial case"}),
             "A 45-year-old male presents with fever and productive cough."),
            (AgentAct(name="Finish", params={"response": "A 45-year-old male presents with fever and productive cough."}),
             "Task completed.")
        ]
        self.add_example(task1, action_chain1)

        # Example 2: Basic history question
        task2 = TaskPackage(instruction="How long have you been feeling sick?")
        action_chain2 = [
            (AgentAct(name="Think", params={"response": "This is a history-gathering question. Route to patient for response."}),
             "OK"),
            (AgentAct(name="patient", params={"Task": "How long have you been feeling sick?"}),
             {"response": "I started feeling really bad about 3 days ago. It came on pretty suddenly.", "agent": "patient"}),
            (AgentAct(name="Finish", params={"response": {"response": "I started feeling really bad about 3 days ago. It came on pretty suddenly.", "agent": "patient"}}),
             "Task completed.")
        ]
        self.add_example(task2, action_chain2)

        # Example 3: Diagnostic test question before differential
        task3 = TaskPackage(instruction="What do the blood tests show?")
        action_chain3 = [
            (AgentAct(name="Think", params={"response": "This is a question about test results before differential. Route to patient for basic response."}),
             "OK"),
            (AgentAct(name="patient", params={"Task": "What do the blood tests show?"}),
             {"response": "The doctor hasn't told me about any blood test results yet.", "agent": "patient"}),
            (AgentAct(name="Finish", params={"response": {"response": "The doctor hasn't told me about any blood test results yet.", "agent": "patient"}}),
             "Task completed.")
        ]
        self.add_example(task3, action_chain3)

        # Example 3a: Diagnostic test question after differential
        task3a = TaskPackage(instruction="Can you show me the chest x-ray?")
        action_chain3a = [
            (AgentAct(name="Think", params={"response": "Student has given differential and is now asking about imaging. Route to patient for detailed results."}),
             "OK"),
            (AgentAct(name="UpdateState", params={"state_update": "diagnostic_tests_revealed", "state_value": "true"}),
             "State updated successfully"),
            (AgentAct(name="patient", params={"Task": "Can you show me the chest x-ray?"}),
             {"response": "The chest x-ray shows a dense consolidation in the right lower lobe with air bronchograms. There is a small right-sided pleural effusion. The left lung is clear.", "agent": "patient"}),
            (AgentAct(name="Finish", params={"response": {"response": "The chest x-ray shows a dense consolidation in the right lower lobe with air bronchograms. There is a small right-sided pleural effusion. The left lung is clear.", "agent": "patient"}}),
             "Task completed.")
        ]
        self.add_example(task3a, action_chain3a)

        # Example 3b: Lab results after differential
        task3b = TaskPackage(instruction="What are the blood test results?")
        action_chain3b = [
            (AgentAct(name="Think", params={"response": "Student has given differential and is asking about labs. Route to patient for detailed results."}),
             "OK"),
            (AgentAct(name="patient", params={"Task": "What are the blood test results?"}),
             {"response": "The blood tests show: WBC 15,000 with 85% neutrophils, Hgb 13.5, Platelets 250,000. CRP is elevated at 85. Blood cultures are pending.", "agent": "patient"}),
            (AgentAct(name="Finish", params={"response": {"response": "The blood tests show: WBC 15,000 with 85% neutrophils, Hgb 13.5, Platelets 250,000. CRP is elevated at 85. Blood cultures are pending.", "agent": "patient"}}),
             "Task completed.")
        ]
        self.add_example(task3b, action_chain3b)

        # Example 4: Readiness check
        task4 = TaskPackage(instruction="Do I have enough information for a differential?")
        action_chain4 = [
            (AgentAct(name="Think", params={"response": "Student asking about readiness for differential. Route to case presenter."}),
             "OK"),
            (AgentAct(name="case_presenter", params={"Task": "Do I have enough information for a differential?"}),
             {"ready": True, "message": "Yes, you've gathered sufficient information including symptoms, vital signs, and key physical findings. You may now provide your differential diagnosis.", "agent": "case_presenter"}),
            (AgentAct(name="Finish", params={"response": {"response": "Yes, you've gathered sufficient information including symptoms, vital signs, and key physical findings. You may now provide your differential diagnosis.", "agent": "case_presenter"}}),
             "Task completed.")
        ]
        self.add_example(task4, action_chain4)

        # Example 5: Differential diagnosis attempt
        task5 = TaskPackage(instruction="is it croup?")
        action_chain5 = [
            (AgentAct(name="Think", params={"response": "Student is providing a potential diagnosis. Route to case presenter for evaluation."}),
             "OK"),
            (AgentAct(name="case_presenter", params={"Task": "is it croup?"}),
             {"feedback": "I see you're considering croup. Let's think about this systematically. What specific symptoms and findings made you consider this diagnosis? Can you walk me through your reasoning?", "is_appropriate": False, "agent": "case_presenter"}),
            (AgentAct(name="Finish", params={"response": {"response": "I see you're considering croup. Let's think about this systematically. What specific symptoms and findings made you consider this diagnosis? Can you walk me through your reasoning?", "agent": "case_presenter"}}),
             "Task completed.")
        ]
        self.add_example(task5, action_chain5)

        # Example 5a: More detailed differential diagnosis attempt
        task5a = TaskPackage(instruction="Given the fever and cough, this could be bacterial pneumonia, possibly Streptococcus pneumoniae")
        action_chain5a = [
            (AgentAct(name="Think", params={"response": "Student is providing a detailed differential with reasoning. Route to case presenter for evaluation."}),
             "OK"),
            (AgentAct(name="case_presenter", params={"Task": "Given the fever and cough, this could be bacterial pneumonia, possibly Streptococcus pneumoniae"}),
             {"feedback": "Good thinking! The combination of acute fever, productive cough, and focal findings supports your consideration of bacterial pneumonia. S. pneumoniae is indeed a common cause. Would you like to see the relevant diagnostic tests now?", "is_appropriate": True, "agent": "case_presenter"}),
            (AgentAct(name="UpdateState", params={"state_update": "differential_given", "state_value": "true"}),
             "State updated successfully"),
            (AgentAct(name="Finish", params={"response": {"response": "Good thinking! The combination of acute fever, productive cough, and focal findings supports your consideration of bacterial pneumonia. S. pneumoniae is indeed a common cause. Would you like to see the relevant diagnostic tests now?", "agent": "case_presenter"}}),
             "Task completed.")
        ]
        self.add_example(task5a, action_chain5a)

        # Example 6: Help request
        task6 = TaskPackage(instruction="I'm not sure what to ask next")
        action_chain6 = [
            (AgentAct(name="Think", params={"response": "Student needs guidance. Route to helper agent."}),
             "OK"),
            (AgentAct(name="helper", params={"Task": "I'm not sure what to ask next"}),
             {"response": "Let's think about what information would help narrow your differential. Consider asking about:\n1. Risk factors for specific pathogens\n2. Specific characteristics of the symptoms\n3. Any sick contacts or exposures", "agent": "helper"}),
            (AgentAct(name="Finish", params={"response": {"response": "Let's think about what information would help narrow your differential. Consider asking about:\n1. Risk factors for specific pathogens\n2. Specific characteristics of the symptoms\n3. Any sick contacts or exposures", "agent": "helper"}}),
             "Task completed.")
        ]
        self.add_example(task6, action_chain6)

        # Example 7: Knowledge assessment
        task7 = TaskPackage(instruction="What virulence factors does S. pneumoniae possess?")
        action_chain7 = [
            (AgentAct(name="Think", params={"response": "This is a knowledge assessment question. Route to knowledge assessment agent."}),
             "OK"),
            (AgentAct(name="knowledge_assessment", params={"Task": "What virulence factors does S. pneumoniae possess?"}),
             {"response": "Let's discuss S. pneumoniae's key virulence factors. Can you tell me about its polysaccharide capsule and its role in pathogenesis?", "agent": "knowledge_assessment"}),
            (AgentAct(name="Finish", params={"response": {"response": "Let's discuss S. pneumoniae's key virulence factors. Can you tell me about its polysaccharide capsule and its role in pathogenesis?", "agent": "knowledge_assessment"}}),
             "Task completed.")
        ]
        self.add_example(task7, action_chain7)

        # Example 8: Physical exam question directed to patient
        task8 = TaskPackage(instruction="Can you take a deep breath for me?")
        action_chain8 = [
            (AgentAct(name="Think", params={"response": "This is a physical exam instruction directed at the patient. Route to patient for response."}),
             "OK"),
            (AgentAct(name="patient", params={"Task": "Can you take a deep breath for me?"}),
             {"response": "*Takes a deep breath but winces* It hurts when I breathe in deeply, especially on my right side.", "agent": "patient"}),
            (AgentAct(name="Finish", params={"response": {"response": "*Takes a deep breath but winces* It hurts when I breathe in deeply, especially on my right side.", "agent": "patient"}}),
             "Task completed.")
        ]
        self.add_example(task8, action_chain8)

        # Example 8a: Physical exam question for doctor's findings
        task8a = TaskPackage(instruction="What do you hear when you listen to the patient's lungs?")
        action_chain8a = [
            (AgentAct(name="Think", params={"response": "This is a physical exam question asking for doctor's findings. Route to case presenter."}),
             "OK"),
            (AgentAct(name="case_presenter", params={"Task": "What do you hear when you listen to the patient's lungs?"}),
             {"response": "On auscultation, there are crackles in the right lower lobe with decreased breath sounds. No wheezing is appreciated in either lung field.", "agent": "case_presenter"}),
            (AgentAct(name="Finish", params={"response": {"response": "On auscultation, there are crackles in the right lower lobe with decreased breath sounds. No wheezing is appreciated in either lung field.", "agent": "case_presenter"}}),
             "Task completed.")
        ]
        self.add_example(task8a, action_chain8a)

        # Example 8b: Another physical exam question for doctor's findings
        task8b = TaskPackage(instruction="Can you examine the patient's abdomen?")
        action_chain8b = [
            (AgentAct(name="Think", params={"response": "This is a physical exam request for the doctor to perform. Route to case presenter."}),
             "OK"),
            (AgentAct(name="case_presenter", params={"Task": "Can you examine the patient's abdomen?"}),
             {"response": "The abdomen is soft and non-tender. There is no hepatosplenomegaly. Normal bowel sounds are present in all four quadrants.", "agent": "case_presenter"}),
            (AgentAct(name="Finish", params={"response": {"response": "The abdomen is soft and non-tender. There is no hepatosplenomegaly. Normal bowel sounds are present in all four quadrants.", "agent": "case_presenter"}}),
             "Task completed.")
        ]
        self.add_example(task8b, action_chain8b)

        # Example 8c: Vital signs request
        task8c = TaskPackage(instruction="What are the patient's vital signs?")
        action_chain8c = [
            (AgentAct(name="Think", params={"response": "This is a request for vital signs. Route to case presenter."}),
             "OK"),
            (AgentAct(name="case_presenter", params={"Task": "What are the patient's vital signs?"}),
             {"response": "Temperature: 38.5°C, Blood pressure: 120/80 mmHg, Heart rate: 88 bpm, Respiratory rate: 20 breaths per minute, Oxygen saturation: 94% on room air.", "agent": "case_presenter"}),
            (AgentAct(name="Finish", params={"response": {"response": "Temperature: 38.5°C, Blood pressure: 120/80 mmHg, Heart rate: 88 bpm, Respiratory rate: 20 breaths per minute, Oxygen saturation: 94% on room air.", "agent": "case_presenter"}}),
             "Task completed.")
        ]
        self.add_example(task8c, action_chain8c)

        # Example 9: Final diagnosis
        task9 = TaskPackage(instruction="Based on all the findings, I believe this is S. pneumoniae pneumonia")
        action_chain9 = [
            (AgentAct(name="Think", params={"response": "Student providing final diagnosis. Route to case presenter for evaluation."}),
             "OK"),
            (AgentAct(name="case_presenter", params={"Task": "Based on all the findings, I believe this is S. pneumoniae pneumonia"}),
             {"feedback": "Excellent! You've correctly identified S. pneumoniae as the causative organism. The clinical presentation, laboratory findings, and radiographic changes are indeed classic for pneumococcal pneumonia.", "is_correct": True, "organism": "S. pneumoniae", "agent": "case_presenter"}),
            (AgentAct(name="UpdateState", params={"state_update": "in_knowledge_assessment", "state_value": "true"}),
             "State updated successfully"),
            (AgentAct(name="Finish", params={"response": {"response": "Excellent! You've correctly identified S. pneumoniae as the causative organism. The clinical presentation, laboratory findings, and radiographic changes are indeed classic for pneumococcal pneumonia.", "agent": "case_presenter"}}),
             "Task completed.")
        ]
        self.add_example(task9, action_chain9)
    
    def start_new_case(self) -> str:
        """Start a new case session by first generating a case, then having the case presenter provide a one-liner presentation."""
        # Reset the tutor state for the new case
        self.reset()
        
        try:
            # Generate the new case using the case generator
            generator_response = self.case_generator(TaskPackage(
                instruction="Generate a new clinical case",
                task_creator=self.id
            ))
            
            # Extract the case text
            case_data = generator_response.get("case_text", "")
            if not case_data:
                print("Warning: No case data in generator response, using default case.")
                case_data = "A 45-year-old male presents with fever and productive cough for 3 days."
            
            # Store the case in both case presenter and patient agents
            self.case_presenter.current_case = {"case_text": case_data}  
            self.patient.current_case = {"case_text": case_data}
            
            # Have the case presenter present the case
            presentation = self.case_presenter(TaskPackage(
                instruction="present initial case",
                task_creator=self.id
            ))
            
            # Extract the presentation text
            if isinstance(presentation, dict):
                return presentation.get("response", "A patient presents for evaluation.")
            return presentation
            
        except Exception as e:
            print(f"Error starting case: {str(e)}")
            return "Error starting case. Please try again."
    
    def reset(self):
        """Reset the tutor state."""
        self.case_presenter.reset()
        self.patient.reset()
        self.current_organism = None
        self.in_knowledge_assessment = False
        self.differential_given = False
        self.current_stage = TutorStage.PRE_DIFFERENTIAL

    def llm_layer(self, prompt: str) -> str:
        """Override the llm_layer method to use the correct LangChain API."""
        # If the prompt is a string, convert it to a message
        if isinstance(prompt, str):
            messages = [HumanMessage(content=prompt)]
        else:
            # If it's already a list of messages, use it as is
            messages = prompt
            
        response = self.llm.predict_messages(messages)
        return response.content

    def __call__(self, task: TaskPackage) -> str:
        """Handle task requests by routing to appropriate agents."""
        # Create a task package for the manager agent
        task = TaskPackage(
            instruction=task.instruction,
            task_creator=self.id
        )
        
        # Let the manager agent handle the routing based on examples
        response = super().__call__(task)
        
        # Check if the response contains a correct diagnosis
        if isinstance(response, dict) and response.get("agent") == "case_presenter":
            # If the case presenter indicates a correct diagnosis, update the knowledge assessment agent
            if "is_correct" in response and response.get("is_correct") == True and "organism" in response:
                organism = response.get("organism")
                self.current_organism = organism
                self.knowledge_assessment.current_organism = organism
                self.current_stage = TutorStage.KNOWLEDGE_ASSESSMENT
                self.knowledge_assessment.current_stage = TutorStage.KNOWLEDGE_ASSESSMENT
                print(f"Diagnosis correct! Moving to knowledge assessment for {organism}")
        
        # If the response is from an agent's action, preserve the agent information
        if isinstance(response, dict) and "response" in response and "agent" in response:
            return response
            
        # For other responses, wrap them appropriately
        if isinstance(response, str):
            # Check if this was the last agent that handled the task
            last_agent = getattr(self, '_last_agent', None)
            if last_agent:
                return {
                    "response": response,
                    "agent": last_agent
                }
        
        return response

    def _execute_action(self, action: AgentAct) -> str:
        """Execute an action and track which agent handled it."""
        # Track which specialized agent is handling this action
        if action.name in ["patient", "case_presenter", "knowledge_assessment", "helper"]:
            self._last_agent = action.name
            
        # Store the agent parameter for later use
        agent_param = None
        if action.name == "Finish" and "agent" in action.params:
            agent_param = action.params.pop("agent")  # Remove it from params
            
        # Execute the action using the parent class method
        response = super()._execute_action(action)
        
        # If this was a Finish action and we had an agent parameter or last_agent, add it to the response
        if action.name == "Finish":
            if isinstance(response, str):
                # Use the stored agent param or last_agent
                agent = agent_param or self._last_agent or "tutor"
                response = {
                    "response": response,
                    "agent": agent
                }
                self._last_agent = None  # Reset after using
            
        return response

    def forward(self, task: TaskPackage, agent_act: AgentAct) -> str:
        """Override the forward method to handle the 'agent' parameter for FinishAction."""
        # If this is a Finish action and it has an agent parameter, save it and remove it from params
        agent_param = None
        if agent_act.name == "Finish" and "agent" in agent_act.params:
            agent_param = agent_act.params.pop("agent")  # Remove it from params
        
        # Call the parent forward method
        response = super().forward(task, agent_act)
        
        # If this was a Finish action and we have agent info, add it to the response
        if agent_act.name == "Finish" and (agent_param or self._last_agent):
            if isinstance(response, str):
                # Use the stored agent param or last_agent
                agent = agent_param or self._last_agent or "tutor"
                response = {
                    "response": response,
                    "agent": agent
                }
                self._last_agent = None  # Reset after using
        
        return response 