from typing import Dict, Optional
from agentlite.agents import ManagerAgent
from langchain.chat_models import AzureChatOpenAI
from agentlite.actions import BaseAction
from agentlite.actions.InnerActions import ThinkAction, FinishAction
from agentlite.commons import TaskPackage, AgentAct
from agents.case_presenter import CasePresenterAgent
from agents.case_generator import CaseGeneratorAgent
from agents.clinical_reasoning import ClinicalReasoningAgent
from agents.knowledge_assessment import KnowledgeAssessmentAgent
import os
from dotenv import load_dotenv
from langchain.schema import HumanMessage

# Load environment variables
load_dotenv()

# Verify Azure OpenAI configuration
if not os.getenv("AZURE_OPENAI_API_KEY") or not os.getenv("AZURE_OPENAI_ENDPOINT"):
    raise ValueError("Missing required Azure OpenAI environment variables")

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

class MedicalMicrobiologyTutor(ManagerAgent):
    def __init__(self, model_name: str = None, temperature: float = 0.1):
        # Use environment variables for model configuration
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
        self.case_generator = CaseGeneratorAgent(model_name=deployment_name, temperature=temperature)
        self.clinical_reasoning = ClinicalReasoningAgent(model_name=deployment_name, temperature=temperature)
        self.knowledge_assessment = KnowledgeAssessmentAgent(model_name=deployment_name, temperature=temperature)
        
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
            - Case Presenter: Presents cases and handles information gathering
            - Clinical Reasoning: Evaluates diagnostic thinking
            - Knowledge Assessment: Tests understanding of identified organisms
            
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
               - I route these to the case_presenter
               - The case_presenter tracks what information has been revealed
            
            3. For differential diagnosis attempts:
               - First check with case_presenter if enough info gathered
               - Then route to clinical_reasoning for evaluation
               - clinical_reasoning provides feedback and guides next steps
            
            4. For final diagnosis attempts:
               - Must have given differential first
               - Route to clinical_reasoning for evaluation
               - If correct, transition to knowledge_assessment
            
            5. For knowledge assessment questions:
               - Route to knowledge_assessment once in that phase
               - knowledge_assessment evaluates understanding of the pathogen
            
            I maintain state through my actions to ensure proper flow.""",
            actions=[TutorStateAction(), ThinkAction(), FinishAction()],
            TeamAgents=[self.case_presenter, self.case_generator, self.clinical_reasoning, self.knowledge_assessment],
            reasoning_type="planreact"
        )
        
        self.current_organism = None
        self.in_knowledge_assessment = False
        self.differential_given = False
        
        # Add examples of successful interactions
        self._add_examples()
    
    def _add_examples(self):
        """Add comprehensive examples of successful agent interactions."""
        
        # Example 1: Starting a new case
        task1 = TaskPackage(instruction="Start a new case")
        action_chain1 = [
            (AgentAct(name="Think", params={"response": "I will start a new case by having the case generator create it and the presenter introduce it."}), 
             "OK"),
            (AgentAct(name="case_generator", params={"Task": "Generate a new clinical case"}), 
             {
                "case_presentation": "A patient presents with fever and productive cough.",
                "full_case": {
                    "demographics": {"age": "56", "sex": "male", "occupation": "office worker"},
                    "presenting_symptoms": ["fever", "productive cough", "chest pain"],
                    "medical_history": "History of COPD",
                    "physical_exam": {
                        "vital_signs": {
                            "temperature": "38.9°C",
                            "blood_pressure": "130/80",
                            "heart_rate": "95",
                            "respiratory_rate": "22"
                        },
                        "relevant_findings": "Decreased breath sounds and crackles in right lower lobe"
                    },
                    "initial_labs": {
                        "WBC": "15,000/μL",
                        "CRP": "elevated"
                    },
                    "epidemiology": "Recent community pneumonia outbreak"
                }
             }),
            (AgentAct(name="UpdateState", params={"state_update": "reset_all", "state_value": "true"}),
             "State updated successfully"),
            (AgentAct(name="Finish", params={"response": "A patient presents with fever and productive cough."}),
             "Task completed.")
        ]
        self.add_example(task1, action_chain1)

        # Example 2: Information gathering phase - Route to case_presenter
        task2 = TaskPackage(instruction="What are the vital signs?")
        action_chain2 = [
            (AgentAct(name="Think", params={"response": "Student is gathering clinical information. Route to case presenter."}),
             "OK"),
            (AgentAct(name="case_presenter", params={"Task": "Evaluate question: What are the vital signs?"}),
             {"response": "Temperature 38.9°C, BP 130/80, HR 95, RR 22"}),
            (AgentAct(name="Finish", params={"response": "Temperature 38.9°C, BP 130/80, HR 95, RR 22"}),
             "Task completed.")
        ]
        self.add_example(task2, action_chain2)

        # Example 3: Premature lab request - Route to case_presenter for redirection
        task3 = TaskPackage(instruction="What are the lab results?")
        action_chain3 = [
            (AgentAct(name="Think", params={"response": "Student requesting labs before differential. Need to redirect."}),
             "OK"),
            (AgentAct(name="case_presenter", params={"Task": "Evaluate question: What are the lab results?"}),
             {"response": "Please provide your initial differential diagnosis based on the clinical presentation before requesting laboratory results."}),
            (AgentAct(name="Finish", params={"response": "Please provide your initial differential diagnosis based on the clinical presentation before requesting laboratory results."}),
             "Task completed.")
        ]
        self.add_example(task3, action_chain3)

        # Example 4: Initial differential diagnosis - Route to clinical_reasoning
        task4 = TaskPackage(instruction="I think this could be community-acquired pneumonia, possibly S. pneumoniae")
        action_chain4 = [
            (AgentAct(name="Think", params={"response": "Student providing initial differential. Check readiness then route to clinical reasoning."}),
             "OK"),
            (AgentAct(name="case_presenter", params={"Task": "ready for differential"}),
             {"ready": True, "message": "Sufficient information gathered for differential"}),
            (AgentAct(name="clinical_reasoning", params={"Task": "Evaluate differential: community-acquired pneumonia, S. pneumoniae"}),
             {"feedback": "Good thinking! Your differential diagnosis considers the common cause of community-acquired pneumonia...",
              "is_correct": True}),
            (AgentAct(name="UpdateState", params={"state_update": "differential_given", "state_value": "true"}),
             "State updated successfully"),
            (AgentAct(name="Finish", params={"response": "Good thinking! Your differential diagnosis considers the common cause of community-acquired pneumonia..."}),
             "Task completed.")
        ]
        self.add_example(task4, action_chain4)

        # Example 5: Post-differential lab request - Route to case_presenter
        task5 = TaskPackage(instruction="Now can I see the lab results?")
        action_chain5 = [
            (AgentAct(name="Think", params={"response": "Student requesting labs after differential. Approved to show."}),
             "OK"),
            (AgentAct(name="case_presenter", params={"Task": "Evaluate question: What are the lab results?"}),
             {"response": "WBC: 15,000/μL, CRP: elevated"}),
            (AgentAct(name="Finish", params={"response": "WBC: 15,000/μL, CRP: elevated"}),
             "Task completed.")
        ]
        self.add_example(task5, action_chain5)

        # Example 6: Final diagnosis - Route to clinical_reasoning then knowledge_assessment
        task6 = TaskPackage(instruction="Based on the labs and clinical presentation, this is S. pneumoniae pneumonia")
        action_chain6 = [
            (AgentAct(name="Think", params={"response": "Student providing final diagnosis. Route to clinical reasoning."}),
             "OK"),
            (AgentAct(name="clinical_reasoning", params={"Task": "Evaluate final diagnosis: S. pneumoniae pneumonia"}),
             {"feedback": "Excellent! This is indeed S. pneumoniae pneumonia...",
              "is_correct": True,
              "organism": "S. pneumoniae"}),
            (AgentAct(name="UpdateState", params={"state_update": "in_knowledge_assessment", "state_value": "true"}),
             "State updated successfully"),
            (AgentAct(name="knowledge_assessment", params={"Task": "Begin assessment", "organism": "S. pneumoniae"}),
             "Let's test your knowledge about S. pneumoniae..."),
            (AgentAct(name="Finish", params={"response": "Correct! Let's test your knowledge about S. pneumoniae..."}),
             "Task completed.")
        ]
        self.add_example(task6, action_chain6)

        # Example 7: Knowledge assessment phase - Route to knowledge_assessment
        task7 = TaskPackage(instruction="S. pneumoniae has a polysaccharide capsule that helps evade the immune system")
        action_chain7 = [
            (AgentAct(name="Think", params={"response": "Student in knowledge assessment phase. Route to knowledge assessment agent."}),
             "OK"),
            (AgentAct(name="knowledge_assessment", params={"Task": "Evaluate answer about S. pneumoniae virulence factors"}),
             {"feedback": "Excellent understanding of S. pneumoniae's key virulence factor..."}),
            (AgentAct(name="Finish", params={"response": "Excellent understanding of S. pneumoniae's key virulence factor..."}),
             "Task completed.")
        ]
        self.add_example(task7, action_chain7)

        # Example 8: Insufficient information for differential - Route to case_presenter
        task8 = TaskPackage(instruction="I think this is bacterial meningitis")
        action_chain8 = [
            (AgentAct(name="Think", params={"response": "Student attempting differential without sufficient information. Check with case presenter."}),
             "OK"),
            (AgentAct(name="case_presenter", params={"Task": "ready for differential"}),
             {"ready": False, "message": "More information needed. Consider asking about:\n1. Physical examination findings\n2. Medical history\n3. Epidemiological factors"}),
            (AgentAct(name="Finish", params={"response": "Before forming a differential, gather more information. Consider asking about:\n1. Physical examination findings\n2. Medical history\n3. Epidemiological factors"}),
             "Task completed.")
        ]
        self.add_example(task8, action_chain8)

        # Example 9: Incorrect final diagnosis - Route to clinical_reasoning
        task9 = TaskPackage(instruction="This is definitely viral pneumonia")
        action_chain9 = [
            (AgentAct(name="Think", params={"response": "Student providing incorrect final diagnosis. Route to clinical reasoning for feedback."}),
             "OK"),
            (AgentAct(name="clinical_reasoning", params={"Task": "Evaluate final diagnosis: viral pneumonia"}),
             {"feedback": "Let's reconsider this diagnosis. The elevated WBC count and CRP suggest a bacterial process. Additionally, the focal findings on chest exam are more typical of bacterial pneumonia. What specific findings support or argue against a viral etiology?",
              "is_correct": False}),
            (AgentAct(name="Finish", params={"response": "Let's reconsider this diagnosis. The elevated WBC count and CRP suggest a bacterial process. Additionally, the focal findings on chest exam are more typical of bacterial pneumonia. What specific findings support or argue against a viral etiology?"}),
             "Task completed.")
        ]
        self.add_example(task9, action_chain9)

        # Example 10: Knowledge assessment completion - Route to knowledge_assessment
        task10 = TaskPackage(instruction="Penicillin resistance in S. pneumoniae is due to alterations in penicillin-binding proteins")
        action_chain10 = [
            (AgentAct(name="Think", params={"response": "Student completing knowledge assessment. Route to knowledge assessment for final evaluation."}),
             "OK"),
            (AgentAct(name="knowledge_assessment", params={"Task": "Evaluate answer about S. pneumoniae resistance mechanisms"}),
             {"feedback": "Excellent! You've demonstrated thorough understanding of S. pneumoniae's resistance mechanisms. This completes our case discussion.",
              "complete": True}),
            (AgentAct(name="UpdateState", params={"state_update": "case_complete", "state_value": "true"}),
             "State updated successfully"),
            (AgentAct(name="Finish", params={"response": "Excellent! You've demonstrated thorough understanding of S. pneumoniae's resistance mechanisms. This completes our case discussion. Type 'new case' to start another case."}),
             "Task completed.")
        ]
        self.add_example(task10, action_chain10)

        # Example 11: Epidemiological questions - Route to case_presenter
        task11 = TaskPackage(instruction="Are there any similar cases in the community?")
        action_chain11 = [
            (AgentAct(name="Think", params={"response": "Student asking about epidemiological context. Route to case presenter."}),
             "OK"),
            (AgentAct(name="case_presenter", params={"Task": "Evaluate question: Are there any similar cases in the community?"}),
             {"response": "Yes, there has been a recent outbreak of community-acquired pneumonia in the area."}),
            (AgentAct(name="Finish", params={"response": "Yes, there has been a recent outbreak of community-acquired pneumonia in the area."}),
             "Task completed.")
        ]
        self.add_example(task11, action_chain11)

        # Example 12: Treatment questions during knowledge assessment - Route to knowledge_assessment
        task12 = TaskPackage(instruction="What is the recommended antibiotic treatment for S. pneumoniae?")
        action_chain12 = [
            (AgentAct(name="Think", params={"response": "Student asking about treatment during knowledge assessment phase. Route to knowledge assessment."}),
             "OK"),
            (AgentAct(name="knowledge_assessment", params={"Task": "Evaluate treatment knowledge for S. pneumoniae"}),
             {"feedback": "Let's discuss the treatment approach systematically:\n1. Empiric therapy typically includes a beta-lactam\n2. Once susceptibilities are known, therapy can be narrowed\n3. Duration typically 5-7 days for uncomplicated cases"}),
            (AgentAct(name="Finish", params={"response": "Let's discuss the treatment approach systematically:\n1. Empiric therapy typically includes a beta-lactam\n2. Once susceptibilities are known, therapy can be narrowed\n3. Duration typically 5-7 days for uncomplicated cases"}),
             "Task completed.")
        ]
        self.add_example(task12, action_chain12)

        # Example 13: Help request during information gathering - Route to case_presenter
        task13 = TaskPackage(instruction="im stuck")
        action_chain13 = [
            (AgentAct(name="Think", params={"response": "Student needs help during information gathering phase. Route to case presenter for guidance."}),
             "OK"),
            (AgentAct(name="case_presenter", params={"Task": "provide guidance", "phase": "information_gathering"}),
             {"response": "To help you gather key information systematically, consider asking about:\n1. Duration and progression of symptoms\n2. Associated symptoms beyond the chief complaint\n3. Past medical history and risk factors\n4. Physical examination findings\n5. Epidemiological context\nThis information will help build a complete clinical picture."}),
            (AgentAct(name="Finish", params={"response": "To help you gather key information systematically, consider asking about:\n1. Duration and progression of symptoms\n2. Associated symptoms beyond the chief complaint\n3. Past medical history and risk factors\n4. Physical examination findings\n5. Epidemiological context\nThis information will help build a complete clinical picture."}),
             "Task completed.")
        ]
        self.add_example(task13, action_chain13)

        # Example 14: Medication question during information gathering - Route to case_presenter
        task14 = TaskPackage(instruction="any medications?")
        action_chain14 = [
            (AgentAct(name="Think", params={"response": "Student asking about medications during information gathering phase. Route to case presenter for medical history."}),
             "OK"),
            (AgentAct(name="case_presenter", params={"Task": "Evaluate question: any medications?", "phase": "information_gathering"}),
             {"response": "The patient is not currently taking any medications. Consider asking about other aspects of the medical history or symptoms to help form your differential diagnosis."}),
            (AgentAct(name="Finish", params={"response": "The patient is not currently taking any medications. Consider asking about other aspects of the medical history or symptoms to help form your differential diagnosis."}),
             "Task completed.")
        ]
        self.add_example(task14, action_chain14)

        # Example 15: Help request during differential phase - Route to clinical_reasoning
        task15 = TaskPackage(instruction="im stuck with the differential")
        action_chain15 = [
            (AgentAct(name="Think", params={"response": "Student needs help forming differential diagnosis. Route to clinical reasoning for guidance."}),
             "OK"),
            (AgentAct(name="clinical_reasoning", params={"Task": "provide differential guidance"}),
             {"response": "Let's approach the differential diagnosis systematically:\n1. Consider the key symptoms: what syndromes do they suggest?\n2. Think about the patient demographics and risk factors\n3. What are common vs dangerous causes to consider?\n4. How does the epidemiological context inform your thinking?\nTry forming a differential based on these factors."}),
            (AgentAct(name="Finish", params={"response": "Let's approach the differential diagnosis systematically:\n1. Consider the key symptoms: what syndromes do they suggest?\n2. Think about the patient demographics and risk factors\n3. What are common vs dangerous causes to consider?\n4. How does the epidemiological context inform your thinking?\nTry forming a differential based on these factors."}),
             "Task completed.")
        ]
        self.add_example(task15, action_chain15)

        # Example 16: Treatment question during knowledge assessment - Route to knowledge_assessment
        task16 = TaskPackage(instruction="what is the treatment for this infection?")
        action_chain16 = [
            (AgentAct(name="Think", params={"response": "Student asking about treatment during knowledge assessment phase. Route to knowledge assessment."}),
             "OK"),
            (AgentAct(name="knowledge_assessment", params={"Task": "Evaluate treatment knowledge", "phase": "knowledge_assessment"}),
             {"response": "Let's discuss the treatment approach systematically:\n1. What is the first-line empiric therapy?\n2. How do you modify treatment based on susceptibility testing?\n3. What is the typical duration of therapy?\n4. Are there any special considerations for this patient population?"}),
            (AgentAct(name="Finish", params={"response": "Let's discuss the treatment approach systematically:\n1. What is the first-line empiric therapy?\n2. How do you modify treatment based on susceptibility testing?\n3. What is the typical duration of therapy?\n4. Are there any special considerations for this patient population?"}),
             "Task completed.")
        ]
        self.add_example(task16, action_chain16)

        # Example 17: Treatment question during information gathering - Route to case_presenter
        task17 = TaskPackage(instruction="what antibiotics is the patient on?")
        action_chain17 = [
            (AgentAct(name="Think", params={"response": "Student asking about current medications during information gathering. Route to case presenter."}),
             "OK"),
            (AgentAct(name="case_presenter", params={"Task": "Evaluate question: what antibiotics is the patient on?", "phase": "information_gathering"}),
             {"response": "The patient is not currently on any antibiotics. This is part of their medical history. Consider asking about other symptoms or risk factors to help form your differential diagnosis."}),
            (AgentAct(name="Finish", params={"response": "The patient is not currently on any antibiotics. This is part of their medical history. Consider asking about other symptoms or risk factors to help form your differential diagnosis."}),
             "Task completed.")
        ]
        self.add_example(task17, action_chain17)
    
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
            
            if not generator_response or not isinstance(generator_response, dict):
                print("Error: Case generator did not return a valid response.")
                return "Error generating case."
            
            # Use the unstructured case text from the generator response
            case_data = generator_response.get("case_text")
            if not case_data:
                print("Error: No case data in generator response.")
                return "Error generating case."
            
            # Have the case presenter present the case
            presentation_task = TaskPackage(
                instruction="present initial case",
                task_creator=self.id
            )
            
            # Present the case and store it in the presenter's state
            self.case_presenter.current_case = {"case_text": case_data}  
            self.clinical_reasoning.current_case = {"case_text": case_data}  
            presentation = self.case_presenter(presentation_task)
            
            if isinstance(presentation, dict):
                return presentation.get("case_presentation", "A patient presents for evaluation.")
            return presentation
            
        except Exception as e:
            print(f"Error starting case: {str(e)}")
            return "Error starting case."
    
    def reset(self):
        """Reset the tutor state."""
        self.case_presenter.reset()
        self.clinical_reasoning.reset()
        self.current_organism = None
        self.in_knowledge_assessment = False
        self.differential_given = False

    def llm_layer(self, prompt: str) -> str:
        """Input a prompt, llm generates a text."""
        # If the prompt is a string, convert it to a message
        if isinstance(prompt, str):
            messages = [HumanMessage(content=prompt)]
        else:
            # If it's already a list of messages, use it as is
            messages = prompt
            
        response = self.llm.predict_messages(messages)
        return response.content 