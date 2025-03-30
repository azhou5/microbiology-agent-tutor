from typing import Dict, Optional
from custom_agent_wrapper import CustomAgentWrapper
from agentlite.llm.agent_llms import BaseLLM, get_llm_backend
from agentlite.llm.LLMConfig import LLMConfig
from agentlite.actions import BaseAction
from agentlite.actions.InnerActions import ThinkAction, FinishAction
from agentlite.commons import TaskPackage, AgentAct
from .case_generator_RAG import CaseGeneratorRAGAgent
import os
from langchain.chat_models import AzureChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from shared_definitions import TutorStage  # Import the stage enum from shared_definitions

"""
Case Presenter Agent Module

This module implements a medical case presenter agent that simulates a clinical instructor
presenting cases to medical students and evaluating their diagnostic reasoning.

Key Components:
- PresentCaseAction: Presents initial clinical case information to students
- PhysicalExamAction: Provides physical examination findings based on student requests
- EvaluateDifferentialAction: Evaluates student's differential diagnosis
- EvaluateDifferentialReasoningAction: Conducts interactive Socratic dialogue to evaluate reasoning
- EvaluateFinalDiagnosisAction: Evaluates student's final diagnosis
- CasePresenterAgent: Main agent class that orchestrates the clinical case workflow

The module uses Azure OpenAI services to generate responses and evaluate student reasoning.
It supports a structured educational approach that guides students through:
1. Initial case presentation
2. Information gathering through history and physical examination
3. Differential diagnosis formulation and reasoning
4. Final diagnosis and evaluation

The agent tracks revealed information, conversation history, and student progress through
different stages of the diagnostic process.
"""

# Helper function to create Azure OpenAI LLM instance
def get_azure_llm(deployment_name=None, temperature=0.1):
    """
    Create and return an Azure OpenAI LLM instance with the specified parameters.
    
    Args:
        deployment_name (str, optional): The Azure deployment name to use. Defaults to environment variable.
        temperature (float, optional): The temperature parameter for generation. Defaults to 0.1.
        
    Returns:
        AzureChatOpenAI: Configured Azure OpenAI client
        
    Raises:
        ValueError: If required environment variables are not set
    """
    if not deployment_name:
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        if not deployment_name:
            raise ValueError("AZURE_OPENAI_DEPLOYMENT_NAME environment variable must be set")
    
    return AzureChatOpenAI(
        openai_api_type="azure",
        openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        deployment_name=deployment_name,
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        temperature=temperature
    )

class PresentCaseAction(BaseAction):
    """
    Action that presents a clinical case to the student.
    
    Generates a concise one-line initial presentation focusing on patient 
    demographics and chief complaint using the format:
    "A [age] year old [sex] presents with [chief complaint]."
    
    Returns:
        dict: Contains the case presentation, full case details, and metadata
    """
    def __init__(self):
        super().__init__(
            action_name="PresentCase",
            action_desc="Present a clinical case to the student",
            params_doc={"case": "The case data to present"}
        )
        # Initialize Azure OpenAI
        self.llm = get_azure_llm("gpt-4o-mini")
    
    def __call__(self, **kwargs) -> str:
        case = kwargs.get("case", {})
        if not case:
            return {"error": "No valid case provided", "agent": "case_presenter"}
        
        # Get the unstructured case text
        case_text = case.get("case_text", "")
        if not case_text:
            return {"error": "No case text provided", "agent": "case_presenter"}
        
        # Create a prompt for the LLM to generate the initial presentation
        prompt = f"""Here is a clinical case:
{case_text}

Generate a one-line initial presentation of this case.
Focus on the patient's demographics and chief complaint.
Use this exact format, nothing else: "A [age] year old [sex] presents with [chief complaint]." """
        
        # Get the one-liner from LLM
        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)
        
        return {
            "case_presentation": response.content.strip(),
            "full_case": {"case_text": case_text},
            "case_text": case_text,
            "agent": "case_presenter"
        }

class PhysicalExamAction(BaseAction):
    """
    Action that provides physical examination findings based on student requests.
    
    Generates realistic and clinically appropriate physical exam findings
    that are consistent with the underlying pathology in the case.
    
    Returns:
        dict: Contains the physical exam findings and metadata
    """
    def __init__(self):
        super().__init__(
            action_name="PhysicalExam",
            action_desc="Provide physical examination findings based on the student's specific request",
            params_doc={
                "exam_request": "The specific physical exam request from the student",
                "case_details": "Full case information"
            }
        )
        # Initialize Azure OpenAI
        self.llm = get_azure_llm("gpt-4o-mini")
    
    def __call__(self, **kwargs) -> str:
        exam_request = kwargs.get("exam_request", "")
        case_details = kwargs.get("case_details", {})
        
        # Get the case text
        case_text = case_details.get("case_text", "")
        if not case_text:
            return {"error": "No case details available", "agent": "case_presenter"}
        
        system_prompt = """You are an expert physician conducting a physical examination on a patient.
        Based on the case details and the specific examination request from the medical student,
        provide realistic and clinically appropriate physical exam findings.
        
        Your response should:
        1. Be concise and focused on the specific exam requested
        2. Include both positive and negative findings as appropriate
        3. Use proper medical terminology
        4. Be consistent with the underlying pathology in the case
        5. Format your response as if you (the physician) are directly telling the student what you observe
        
        For example:
        - For lung exam: "On auscultation, there are crackles in the right lower lobe with decreased breath sounds. No wheezing is appreciated."
        - For abdominal exam: "The abdomen is soft and non-tender. No hepatosplenomegaly. Normal bowel sounds."
        
        Do not provide any additional information or commentary, such as potential diagnoses or differentials.
        Keep your response brief and focused on objective findings."""
        
        main_prompt = f"""Case Details:
{case_text}

Student's Physical Exam Request:
{exam_request}

Provide appropriate physical examination findings for this specific request, consistent with the underlying pathology."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=main_prompt)
        ]
        
        response = self.llm.invoke(messages)
        
        return {
            "response": response.content.strip(),
            "exam_type": "physical_exam",
            "agent": "case_presenter"
        }
    


class EvaluateDifferentialAction(BaseAction):
    """
    Action that evaluates a student's differential diagnosis.
    
    Assesses the appropriateness of proposed conditions, use of clinical findings,
    consideration of epidemiological factors, and pattern recognition.
    
    Returns:
        dict: Contains feedback, assessment of appropriateness, and metadata
    """
    def __init__(self):
        super().__init__(
            action_name="EvaluateDifferential",
            action_desc="Evaluate student's differential diagnosis",
            params_doc={
                "case_details": "Full case information",
                "student_differential": "Student's differential diagnosis"
            }
        )
        # Initialize Azure OpenAI
        self.llm = get_azure_llm()
    
    def __call__(self, **kwargs) -> str:
        student_differential = kwargs.get("student_differential", "")
        case_details = kwargs.get("case_details", {})
        
        system_prompt = """You are an expert medical educator evaluating a student's differential diagnosis.
        Consider:
        1. Appropriateness of proposed organisms/conditions
        2. Use of clinical findings to support reasoning
        3. Consideration of epidemiological factors
        4. Pattern recognition and syndrome identification
        
        Provide feedback that:
        1. Acknowledges good reasoning
        2. Identifies gaps or missed pathogens
        3. Guides further diagnostic workup
        4. Reinforces key clinical principles
        
        Format your response as:
        {
            "feedback": "Detailed feedback message",
            "is_appropriate": true/false,
            "missing_pathogens": ["list", "of", "missed", "organisms"],
            "suggested_tests": ["list", "of", "appropriate", "tests"]
        }"""
        
        main_prompt = f"""Case Details:
{case_details.get('case_text', '')}

Student's Differential:
{student_differential}

Evaluate their differential diagnosis, considering:
1. Clinical presentation
2. Epidemiological factors
3. Pattern recognition
4. Key discriminating features"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=main_prompt)
        ]
        
        response = self.llm.invoke(messages)
        
        try:
            import json
            evaluation = json.loads(response.content)
            return {
                "feedback": evaluation["feedback"],
                "is_appropriate": evaluation["is_appropriate"],
                "agent": "case_presenter"
            }
        except:
            return {
                "feedback": response.content,
                "is_appropriate": True,
                "agent": "case_presenter"
            }

class EvaluateDifferentialReasoningAction(BaseAction):
    """
    Action that conducts an interactive Socratic dialogue to evaluate a student's
    clinical reasoning process.
    
    Implements a two-stage approach:
    1. Clarification stage: Determines if reasoning is already included in the differential
    2. Interactive evaluation stage: Engages in dialogue to probe reasoning
    
    Identifies student failure modes (information gathering vs. knowledge gaps)
    and provides appropriate guidance without giving away answers.
    
    Returns:
        dict: Contains response, reasoning assessment, and completion status
    """
    def __init__(self):
        super().__init__(
            action_name="EvaluateDifferentialReasoning",
            action_desc="Evaluate student's reasoning for their differential diagnosis",
            params_doc={
                "case_details": "Full case information",
                "student_differential": "Student's differential diagnosis",
                "student_reasoning": "Student's current reasoning statement",
                "is_initial_response": "Whether this is the first response to the differential",
                "full_case_conversation": "Full conversation history from the entire case including reasoning dialogue",
                "revealed_info": "Set of information categories already revealed to the student"
            }
        )
        # Initialize Azure OpenAI for different tasks
        self.clarify_llm = get_azure_llm("gpt-4o-mini")  # Lighter model for clarification
        self.evaluate_llm = get_azure_llm("gpt-4o")      # More powerful model for evaluation
        
        # Track conversation state
        self.last_response_type = None
        self.discussed_findings = set()
    
    def __call__(self, **kwargs) -> str:
        student_differential = kwargs.get("student_differential", "")
        student_reasoning = kwargs.get("student_reasoning", "")
        case_details = kwargs.get("case_details", {})
        is_initial_response = kwargs.get("is_initial_response", True)
        full_case_conversation = kwargs.get("full_case_conversation", "")
        revealed_info = kwargs.get("revealed_info", set())
        
        # If this is the initial differential diagnosis, use it as both the differential and reasoning
        if is_initial_response and not student_reasoning and student_differential:
            student_reasoning = student_differential
        
        # Check if the input is a doctor/tutor message
        is_doctor_message = False
        if student_reasoning:
            lower_reasoning = student_reasoning.lower()
            if lower_reasoning.startswith("doctor:") or lower_reasoning.startswith("tutor:"):
                is_doctor_message = True
                # For doctor messages, we'll return a special response indicating not to count this as student reasoning
                print(f"DEBUG - Detected doctor message in reasoning evaluation: '{student_reasoning}'")
                return {
                    "response": "This appears to be a message from the doctor/tutor, not student reasoning.",
                    "reasoning_complete": False,
                    "is_doctor_message": True,
                    "agent": "case_presenter"
                }
        
        # STAGE 1: CLARIFICATION STAGE
        # If this is the first response to the differential, check if reasoning is already included
        if is_initial_response:
            # Use a lighter model to determine if reasoning is already included
            system_prompt = """You are analyzing a student's differential diagnosis to determine if it already includes reasoning.
            Respond with a JSON object in this format:
            {
                "includes_reasoning": true/false,
                "next_question": "The question to ask the student next",
                "identified_findings": ["list", "of", "clinical", "findings", "mentioned"]
            }
            
            If the student's response includes "because", "due to", "as a result of", "given that", or similar phrases
            followed by clinical reasoning, set includes_reasoning to true.
            
            Extract any clinical findings or observations the student mentions and include them in identified_findings.
            
            If includes_reasoning is true, the next_question should ask about additional factors they haven't mentioned.
            If includes_reasoning is false, ask them to explain their reasoning."""
            
            main_prompt = f"""Student's differential diagnosis: {student_differential}

            Determine if this already includes reasoning for the diagnosis."""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=main_prompt)
            ]
            
            response = self.clarify_llm.invoke(messages)
            
            try:
                import json
                response_text = response.content.strip()
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                if start >= 0 and end > start:
                    analysis = json.loads(response_text[start:end])
                    
                    # Track findings mentioned
                    if "identified_findings" in analysis:
                        self.discussed_findings.update(analysis["identified_findings"])
                    
                    if analysis.get("includes_reasoning", False):
                        self.last_response_type = "probe_further"
                        return {
                            "response": analysis.get("next_question", "Any other clinical findings or epidemiological factors that support your differential?"),
                            "includes_reasoning": True,
                            "agent": "case_presenter"
                        }
                    else:
                        self.last_response_type = "request_reasoning"
                        return {
                            "response": analysis.get("next_question", "Why do you think these are the most likely diagnoses? What specific findings support your differential?"),
                            "includes_reasoning": False,
                            "agent": "case_presenter"
                        }
            except:
                # Default to asking why if we can't parse the response
                self.last_response_type = "request_reasoning"
                return {
                    "response": "Why do you think these are the most likely diagnoses? What specific findings support your differential?",
                    "includes_reasoning": False,
                    "agent": "case_presenter"
                }
        
        # STAGE 2: INTERACTIVE EVALUATION STAGE
        # This is the continuous back-and-forth evaluation of reasoning
        else:
            # Add the current reasoning to the conversation for continuity
            full_case_with_current = full_case_conversation 
            if full_case_with_current and student_reasoning:
                full_case_with_current += f"\nStudent: {student_reasoning}"
            elif student_reasoning:
                full_case_with_current = f"Student: {student_reasoning}"
            
            system_prompt = """You are an expert medical educator engaging in a Socratic dialogue with a student about their differential diagnosis.
            
            Your goal is to:
            1. Evaluate the strength and accuracy of their reasoning
            2. Identify failure modes of the students 
            3. Provide feedback based on the failure mode
            4. Help them arrive at a well-reasoned conclusion
            
            Students are likely to have two main failure modes: 
            1. The reasoning for the information they have collected up to that point is correct, but they did not collect enough/the right information to come to the correct conclusion. This is a failure of information gathering. 
            2. The reasoning for the information they have collected up to that point is incorrect. This is a failure of knowledge. 

            EVALUATE BOTH:
            1. Whether the student has done sufficient information gathering before reaching their differential diagnosis
            2. Whether their reasoning about the information they collected is correct
            
            When analyzing their information gathering, review the FULL case conversation provided to determine what questions they asked and what information they obtained.
            
            Return a JSON object with:
            {
                "reasoning_complete": true/false,
                "response_type": "probe_further|correct_misconception|challenge_with_information|acknowledge_good_reasoning",
                "response": "Your response to the student",
                "reasoning_quality": "strong|adequate|needs_improvement|flawed",
                "identified_findings": ["list", "of", "clinical", "findings", "mentioned"],
                "next_steps": ["suggested", "areas", "to", "explore"]
            }
            
            IMPORTANT:
            1. Never repeat the exact same question
            2. Acknowledge what the student has said before asking the next question
            3. If they mention a finding, probe deeper about its significance
            4. If they miss key findings, guide them to consider those areas
            5. Make your responses feel like a natural conversation"""
            
            # Format revealed_info to be more readable
            formatted_revealed_info = []
            info_mapping = {
                "symptoms": "Symptoms and complaints",
                "physical_exam": "Physical examination findings",
                "epidemiology": "Epidemiological information", 
                "medical_history": "Medical history",
                "respiratory_exam": "Respiratory examination",
                "cardiac_exam": "Cardiac examination",
                "abdominal_exam": "Abdominal examination",
                "neurological_exam": "Neurological examination",
                "skin_exam": "Skin examination",
                "lymphatic_exam": "Lymphatic examination",
                "ent_exam": "ENT examination",
                "eye_exam": "Eye examination",
                "musculoskeletal_exam": "Musculoskeletal examination",
                "general_physical_exam": "General physical examination"
            }
            
            for info in revealed_info:
                readable_name = info_mapping.get(info, info.replace("_", " ").title())
                formatted_revealed_info.append(readable_name)
                
            revealed_info_text = ", ".join(formatted_revealed_info) if formatted_revealed_info else "No specific information categories gathered yet"
            
            main_prompt = f"""Case Details:
{case_details.get('case_text', '')}

Student's Differential Diagnosis:
{student_differential}

Student's Latest Response:
{student_reasoning}

Previously Discussed Findings:
{', '.join(self.discussed_findings) if self.discussed_findings else "None"}

Last Response Type:
{self.last_response_type if self.last_response_type else "None"}

Full Case Conversation:
{full_case_with_current if full_case_with_current else "[No prior conversation recorded]"}

Information Categories Gathered:
{revealed_info_text}
This part is crucial. This is the only information that the student has gathered. Please do not reference any information outside of this. 

If the student has not gathered enough information to make the differential diagnosis in your judgement, you should tell them to gather more information. 

Based on this exchange, determine if the student's reasoning is complete and accurate enough to move forward, or if further questioning would be beneficial for their learning.
If you need to probe further, don't give away the answers - ask questions that lead them to discover insights themselves.

When evaluating, consider BOTH:
1. Did they ask sufficient questions to gather appropriate information before making their differential diagnosis?
2. Is their reasoning about the information they gathered correct?"""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=main_prompt)
            ]
            
            response = self.evaluate_llm.invoke(messages)
            
            try:
                import json
                response_text = response.content.strip()
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                if start >= 0 and end > start:
                    evaluation = json.loads(response_text[start:end])
                    
                    # Update tracking
                    self.last_response_type = evaluation.get("response_type", "probe_further")
                    if "identified_findings" in evaluation:
                        self.discussed_findings.update(evaluation["identified_findings"])
                    
                    # Be more explicit about reasoning completion
                    # If the response type indicates acknowledgment of good reasoning or reasoning quality is strong,
                    # we should consider reasoning complete even if not explicitly marked
                    is_reasoning_complete = evaluation.get("reasoning_complete", False)
                    if not is_reasoning_complete:
                        response_type = evaluation.get("response_type", "")
                        reasoning_quality = evaluation.get("reasoning_quality", "")
                        
                        if response_type == "acknowledge_good_reasoning" or reasoning_quality == "strong":
                            is_reasoning_complete = True
                            print(f"DEBUG - EvaluateDifferentialReasoningAction: Forcing reasoning_complete=True based on response_type={response_type} and reasoning_quality={reasoning_quality}")
                    
                    return {
                        "response": evaluation.get("response", "Could you elaborate on your reasoning?"),
                        "reasoning_complete": is_reasoning_complete,
                        "reasoning_quality": evaluation.get("reasoning_quality", "needs_improvement"),
                        "response_type": evaluation.get("response_type", "probe_further"),
                        "agent": "case_presenter"
                    }
                
                raise ValueError("No valid JSON found in response")
                
            except Exception as e:
                print(f"Error evaluating reasoning: {str(e)}")
                # Default to a generic follow-up question that acknowledges their input
                self.last_response_type = "probe_further"
                return {
                    "response": f"I see you mentioned {student_reasoning}. Could you elaborate on how this connects to your differential diagnoses?",
                    "reasoning_complete": False,
                    "reasoning_quality": "needs_improvement",
                    "response_type": "probe_further",
                    "agent": "case_presenter"
                }

class EvaluateFinalDiagnosisAction(BaseAction):
    """
    Action that evaluates a student's final diagnosis.
    
    Assesses diagnostic accuracy, supporting/refuting evidence, and extracts
    the identified pathogen when correct.
    
    Returns:
        dict: Contains feedback, correctness assessment, identified organism, and metadata
    """
    def __init__(self):
        super().__init__(
            action_name="EvaluateFinalDiagnosis",
            action_desc="Evaluate student's final diagnosis",
            params_doc={
                "case_details": "Full case information",
                "student_diagnosis": "Student's final diagnosis",
                "previous_differential": "Student's previous differential diagnosis"
            }
        )
        # Initialize Azure OpenAI
        self.llm = get_azure_llm(temperature=0.3)
    
    def __call__(self, **kwargs) -> str:
        case_details = kwargs.get("case_details", {})
        student_diagnosis = kwargs.get("student_diagnosis", "")
        previous_differential = kwargs.get("previous_differential", "")
        
        system_prompt = """You are an expert medical educator evaluating a student's final diagnosis.
        Consider:
        1. Match with clinical presentation
        2. Support from laboratory findings
        3. Use of diagnostic data
        4. Clinical reasoning process
        
        Provide feedback that:
        1. Evaluates diagnostic accuracy
        2. Explains supporting/refuting evidence
        3. Highlights learning points
        4. Reinforces diagnostic principles
        
        Format your response as:
        {
            "feedback": "Detailed feedback message",
            "is_correct": true/false,
            "organism": "identified pathogen",
            "key_learning_points": ["list", "of", "important", "points"]
        }"""
        
        main_prompt = f"""Case Details:
{case_details.get('case_text', '')}

Previous Differential:
{previous_differential}

Final Diagnosis:
{student_diagnosis}

Evaluate their final diagnosis, considering:
1. Clinical presentation
2. Laboratory findings
3. Diagnostic reasoning
4. Key supporting features

IMPORTANT: If the diagnosis is correct, make sure to extract and return the specific organism name in the "organism" field.
For example, if the student says "This is Streptococcus pneumoniae pneumonia", the organism should be "Streptococcus pneumoniae".
"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=main_prompt)
        ]
        
        response = self.llm.invoke(messages)
        
        try:
            import json
            evaluation = json.loads(response.content)
            
            # Extract organism from the student's diagnosis if not provided in the evaluation
            if evaluation.get("is_correct", False) and not evaluation.get("organism"):
                # Try to extract organism from student diagnosis
                import re
                # Look for common organism patterns
                organism_patterns = [
                    r"(?i)(streptococcus|staphylococcus|neisseria|escherichia|klebsiella|pseudomonas|haemophilus|mycobacterium|candida|aspergillus|pneumocystis|legionella|bordetella|listeria|salmonella|shigella|clostridium|bacteroides|enterococcus|proteus|serratia|acinetobacter|stenotrophomonas|burkholderia|moraxella|corynebacterium|actinomyces|nocardia|rhodococcus|mycoplasma|chlamydia|rickettsia|coxiella|bartonella|borrelia|treponema|leptospira|brucella|francisella|yersinia|vibrio|campylobacter|helicobacter|gardnerella|prevotella|fusobacterium|peptostreptococcus|propionibacterium|bacillus|enterobacter|citrobacter|morganella|providencia|hafnia|edwardsiella|ewingella|kluyvera|rahnella|yokenella|cedecea|tatumella|plesiomonas|aeromonas|chryseobacterium|elizabethkingia|flavobacterium|sphingobacterium|chryseomonas|flavimonas|ralstonia|achromobacter|alcaligenes|bordetella|comamonas|delftia|methylobacterium|ochrobactrum|oligella|psychrobacter|roseomonas|sphingomonas|weeksella|kingella|cardiobacterium|eikenella|capnocytophaga|dysgonomonas|suttonella|streptobacillus|pasteurella|mannheimia|actinobacillus|aggregatibacter|haemophilus|histophilus|mannheimia|pasteurella|abiotrophia|aerococcus|alloiococcus|dolosicoccus|dolosigranulum|facklamia|gemella|globicatella|helcococcus|ignavigranum|lactococcus|leuconostoc|pediococcus|tetragenococcus|vagococcus|weissella)\s+([a-z]+)",
                    r"(?i)(e\.\s*coli|c\.\s*diff|s\.\s*aureus|s\.\s*pneumoniae|h\.\s*influenzae|n\.\s*meningitidis|m\.\s*tuberculosis|p\.\s*aeruginosa|k\.\s*pneumoniae)"
                ]
                
                for pattern in organism_patterns:
                    match = re.search(pattern, student_diagnosis)
                    if match:
                        if match.group(1).lower() in ["e.", "c.", "s.", "h.", "n.", "m.", "p.", "k."]:
                            # Handle abbreviated forms
                            evaluation["organism"] = match.group(0)
                        else:
                            # Handle full genus + species
                            evaluation["organism"] = f"{match.group(1)} {match.group(2)}"
                        break
                
                # If still no organism, use a more general approach
                if not evaluation.get("organism"):
                    # Extract organism from case text
                    case_text = case_details.get('case_text', '')
                    if "Organism" in case_text:
                        organism_section = case_text.split("Organism")[1].split("\n\n")[0].strip()
                        evaluation["organism"] = organism_section
            
            return {
                "feedback": evaluation["feedback"],
                "is_correct": evaluation["is_correct"],
                "organism": evaluation.get("organism", "Unknown organism"),
                "agent": "case_presenter"
            }
        except Exception as e:
            print(f"Error parsing diagnosis evaluation: {str(e)}")
            # Try to extract organism from student diagnosis
            import re
            organism = "Unknown organism"
            
            # Look for common organism patterns
            organism_patterns = [
                r"(?i)(streptococcus|staphylococcus|neisseria|escherichia|klebsiella|pseudomonas|haemophilus|mycobacterium|candida|aspergillus|pneumocystis|legionella|bordetella|listeria|salmonella|shigella|clostridium|bacteroides|enterococcus|proteus|serratia|acinetobacter|stenotrophomonas|burkholderia|moraxella|corynebacterium|actinomyces|nocardia|rhodococcus|mycoplasma|chlamydia|rickettsia|coxiella|bartonella|borrelia|treponema|leptospira|brucella|francisella|yersinia|vibrio|campylobacter|helicobacter|gardnerella|prevotella|fusobacterium|peptostreptococcus|propionibacterium|bacillus|enterobacter|citrobacter|morganella|providencia|hafnia|edwardsiella|ewingella|kluyvera|rahnella|yokenella|cedecea|tatumella|plesiomonas|aeromonas|chryseobacterium|elizabethkingia|flavobacterium|sphingobacterium|chryseomonas|flavimonas|ralstonia|achromobacter|alcaligenes|bordetella|comamonas|delftia|methylobacterium|ochrobactrum|oligella|psychrobacter|roseomonas|sphingomonas|weeksella|kingella|cardiobacterium|eikenella|capnocytophaga|dysgonomonas|suttonella|streptobacillus|pasteurella|mannheimia|actinobacillus|aggregatibacter|haemophilus|histophilus|mannheimia|pasteurella|abiotrophia|aerococcus|alloiococcus|dolosicoccus|dolosigranulum|facklamia|gemella|globicatella|helcococcus|ignavigranum|lactococcus|leuconostoc|pediococcus|tetragenococcus|vagococcus|weissella)\s+([a-z]+)",
                r"(?i)(e\.\s*coli|c\.\s*diff|s\.\s*aureus|s\.\s*pneumoniae|h\.\s*influenzae|n\.\s*meningitidis|m\.\s*tuberculosis|p\.\s*aeruginosa|k\.\s*pneumoniae)"
            ]
            
            for pattern in organism_patterns:
                match = re.search(pattern, student_diagnosis)
                if match:
                    if match.group(1).lower() in ["e.", "c.", "s.", "h.", "n.", "m.", "p.", "k."]:
                        # Handle abbreviated forms
                        organism = match.group(0)
                    else:
                        # Handle full genus + species
                        organism = f"{match.group(1)} {match.group(2)}"
                    break
            
            # If still no organism, extract from case text
            if organism == "Unknown organism":
                case_text = case_details.get('case_text', '')
                if "Organism" in case_text:
                    organism_section = case_text.split("Organism")[1].split("\n\n")[0].strip()
                    organism = organism_section
            
            return {
                "feedback": response.content,
                "is_correct": True,
                "organism": organism,
                "agent": "case_presenter"
            }

class CasePresenterAgent(CustomAgentWrapper):
    """
    Main agent class that orchestrates the clinical case presentation workflow.
    
    Manages the progression through different stages of the diagnostic process:
    1. PRE_DIFFERENTIAL: Initial case presentation and information gathering
    2. POST_DIFFERENTIAL: Evaluation of differential diagnosis and reasoning
    3. KNOWLEDGE_ASSESSMENT: Final diagnosis evaluation
    
    Tracks revealed information categories, conversation history, and supports
    both direct evaluation and interactive reasoning approaches.
    
    Methods:
        determine_action: Selects appropriate action based on student input
        __call__: Processes student input and returns appropriate response
        _classify_physical_exam: Categorizes physical exam requests by body system
        reset: Resets the agent state for a new case
    """
    def __init__(self, model_name: str = None, temperature: float = 0.3):
        # A/B Testing configuration
        # Set this to True to use the interactive reasoning approach,
        # or False to use the direct evaluation approach
        self.use_interactive_reasoning = True
        
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
            PresentCaseAction(),
            PhysicalExamAction(),
            EvaluateDifferentialAction(),
            EvaluateDifferentialReasoningAction(),
            EvaluateFinalDiagnosisAction(),
            ThinkAction(),
            FinishAction()
        ]
        
        super().__init__(
            name="case_presenter",
            role="""I am an expert medical case presenter and clinical reasoning coach. I:
            1. Present clinical cases and guide information gathering
            2. Provide physical examination findings when requested
            3. Evaluate differential diagnoses and clinical reasoning
            4. Track case progression and information revealed
            
            I maintain a structured educational approach:
            1. Require thorough information gathering before differential
            2. Guide test selection based on differential
            3. Ensure evidence-based final diagnoses
            4. Emphasize learning from the diagnostic process""",
            llm=llm,
            actions=actions,
            reasoning_type="react"
        )
        
        self.current_case = None
        self.revealed_info = set()
        self.differential_given = False
        self.current_differential = None
        self.diagnostic_tests_revealed = False
        self.conversation_history = []
        self.current_stage = TutorStage.PRE_DIFFERENTIAL
        
        # Variables for the interactive reasoning approach
        self.awaiting_reasoning = False
        self.reasoning_evaluation_started = False
        self.reasoning_conversation = None
        self.pending_differential = None
        
        # Track all differential diagnoses presented by the student over time
        self.differential_history = []
        
        # Add a counter to limit the number of reasoning turns
        self.reasoning_turn_count = 0
        self.max_reasoning_turns = 5  # Maximum number of back-and-forth exchanges for reasoning
    
    def determine_action(self, task: TaskPackage) -> BaseAction:
        """Determine which action to use based on the task instruction."""
        instruction = task.instruction.lower()
        
        # Use a smaller model for action determination
        determine_action_llm = get_azure_llm("gpt-4o-mini")
        
        # Debug state
        print(f"DEBUG - determine_action - awaiting_reasoning: {self.awaiting_reasoning}, pending_differential: {self.pending_differential}")
        
        # Check for doctor/tutor messages
        is_doctor_message = instruction.startswith("doctor:") or instruction.startswith("tutor:")
        
        # If we're awaiting reasoning and this is not a doctor message, treat it as a reasoning response
        if self.awaiting_reasoning and not is_doctor_message:
            print(f"DEBUG - Already awaiting reasoning, using EvaluateDifferentialReasoningAction")
            return next(action for action in self.actions if isinstance(action, EvaluateDifferentialReasoningAction))
        
        # Create a prompt for the LLM to classify the request type
        system_prompt = """You are an expert medical educator helping to classify student requests during a case-based learning session.

        Analyze the student's request and classify it into one of these categories:
        1. DIAGNOSTIC_REQUEST - Any request for test results, imaging, cultures, or other diagnostic information
        2. DIFFERENTIAL_DIAGNOSIS - Student providing or discussing their differential diagnosis
        3. PHYSICAL_EXAM - Request for physical examination findings
        4. PRESENT_CASE - Request for initial case presentation
        5. FINAL_DIAGNOSIS - Student providing their final diagnosis
        6. OTHER - Any other type of request

        Consider the full context of medical education when classifying. For example:
        - "What do the labs show?" -> DIAGNOSTIC_REQUEST
        - "I think this could be pneumonia" -> DIFFERENTIAL_DIAGNOSIS
        - "Can you check their lungs?" -> PHYSICAL_EXAM
        - "What's the case?" -> PRESENT_CASE
        - "My final diagnosis is S. aureus infection" -> FINAL_DIAGNOSIS
        
        Respond with ONLY the category name, nothing else."""
        
        # Get the context from the task
        context = f"""Student request: {instruction}
        Current state:
        - Differential given: {self.differential_given}
        - Information revealed: {', '.join(self.revealed_info) if self.revealed_info else 'None'}
        """
        
        # Use LLM to classify the request type
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=context)
        ]
        
        request_type = determine_action_llm.invoke(messages).content.strip()
        
        # Handle diagnostic requests before differential
        if request_type == "DIAGNOSTIC_REQUEST" and not self.differential_given:
            # Return the ThinkAction object itself, not the result of calling it
            return next(action for action in self.actions if isinstance(action, ThinkAction))
        
        # Handle differential diagnosis requests
        if request_type == "DIFFERENTIAL_DIAGNOSIS":
            # If this appears to be a new differential diagnosis, store it
            if not self.awaiting_reasoning:
                print(f"DEBUG - Detected differential diagnosis: {instruction}")
                self.pending_differential = task.instruction
                
                # Add to differential history if it's not already in the list
                if task.instruction not in self.differential_history:
                    self.differential_history.append(task.instruction)
                    print(f"DEBUG - Added to differential history: {task.instruction}")
                
                # For interactive approach, we'll set awaiting_reasoning to True
                if self.use_interactive_reasoning:
                    print(f"DEBUG - Setting awaiting_reasoning to True for interactive approach")
                    self.awaiting_reasoning = True
                    self.reasoning_evaluation_started = False
            
            # Return the appropriate action based on the A/B testing flag
            if self.use_interactive_reasoning:
                return next(action for action in self.actions if isinstance(action, EvaluateDifferentialReasoningAction))
            else:
                return next(action for action in self.actions if isinstance(action, EvaluateDifferentialAction))
        
        # For other request types, use another LLM call to determine the specific action
        action_system_prompt = """You are an expert medical case presenter helping to determine which action to take based on a student's input.
        Available actions are:
        1. PresentCase - For presenting initial case information
        2. PhysicalExam - For providing physical examination findings when the student asks for specific exam components
        3. EvaluateDifferential - For evaluating a proposed differential diagnosis without interactive reasoning
        4. EvaluateDifferentialReasoning - For evaluating differential diagnoses with an interactive reasoning process 
        5. EvaluateFinalDiagnosis - For evaluating a final diagnosis
        
        The request has been classified as: {request_type}
        
        Based on this classification and the following guidelines, determine the appropriate action:
        
        - PHYSICAL_EXAM requests should use PhysicalExam action
        - PRESENT_CASE requests should use PresentCase action
        - FINAL_DIAGNOSIS requests should use EvaluateFinalDiagnosis action
        - For OTHER requests, choose the most appropriate action based on context
        
        Respond with ONLY the action name, nothing else."""
        
        messages = [
            SystemMessage(content=action_system_prompt),
            HumanMessage(content=context)
        ]
        
        action_name = determine_action_llm.invoke(messages).content.strip()
        
        # Map the action name to the actual action
        for action in self.actions:
            if action.action_name == action_name:
                return action
        
        # Default to first action if no match
        return self.actions[0]

    def __call__(self, task: TaskPackage) -> str:
        """Handle case presentation, clinical reasoning, and diagnostic evaluation."""
        # Determine which action to use
        print(f"DEBUG - __call__ - Starting with instruction: {task.instruction}")
        print(f"DEBUG - __call__ - State before action: awaiting_reasoning={self.awaiting_reasoning}, pending_differential={self.pending_differential}")
        
        # Process doctor/tutor messages to extract actual content
        instruction = task.instruction
        original_instruction = instruction
        is_doctor_message = False
        
        # Extract content if it's a doctor message
        if instruction.lower().startswith("doctor:") or instruction.lower().startswith("tutor:"):
            is_doctor_message = True
            # Extract the content after "Doctor:" or "Tutor:"
            split_msg = instruction.split(":", 1)
            if len(split_msg) > 1:
                instruction = split_msg[1].strip()
                print(f"DEBUG - Extracted doctor message content: '{instruction}'")
        
        # Update the task with the processed instruction
        modified_task = TaskPackage(
            instruction=instruction,
            context=getattr(task, 'context', {}),
            task_creator=getattr(task, 'task_creator', None)
        )
        
        # Check for full conversation history in the context
        full_conversation_history = None
        if hasattr(task, 'context') and task.context and 'full_conversation_history' in task.context:
            full_conversation_history = task.context['full_conversation_history']
            print(f"DEBUG - __call__ - Received full conversation history with {len(full_conversation_history)} entries")
        
        action = self.determine_action(modified_task)
        
        print(f"DEBUG - __call__ - Selected action: {action.action_name}")
        
        # Handle each action type
        if isinstance(action, PresentCaseAction):
            case_data = getattr(modified_task, 'context', {}).get('case', {}) or self.current_case
            result = action(case=case_data)
            if isinstance(result, dict):
                if result.get("full_case"):
                    self.current_case = result.get("full_case")
                elif result.get("case_text"):
                    self.current_case = {"case_text": result.get("case_text")}
                
                # Add to revealed info
                self.revealed_info.add("initial_presentation")
                
                response = result.get("case_presentation", "A patient presents for evaluation.")
                self.conversation_history.append({
                    "question": original_instruction,
                    "response": response
                })
                return {
                    "response": response,
                    "agent": "case_presenter"
                }
            return str(result)
        
        elif isinstance(action, PhysicalExamAction):
            result = action(
                exam_request=modified_task.instruction,
                case_details=self.current_case
            )
            if isinstance(result, dict):
                # Simply track that a physical exam was performed
                self.revealed_info.add("physical_exam")
                
                response = result.get("response", "No significant findings.")
                self.conversation_history.append({
                    "question": original_instruction,
                    "response": response
                })
                return {
                    "response": response,
                    "agent": "case_presenter"
                }
            return str(result)
        
        elif isinstance(action, EvaluateDifferentialAction) or isinstance(action, EvaluateDifferentialReasoningAction):
            if isinstance(action, EvaluateDifferentialAction):
                result = action(
                    student_differential=modified_task.instruction,
                    case_details=self.current_case
                )
            else:
                result = action(
                    student_differential=self.pending_differential,
                    student_reasoning=modified_task.instruction if not self.reasoning_evaluation_started else modified_task.instruction,
                    is_initial_response=not self.reasoning_evaluation_started,
                    full_case_conversation=full_conversation_history,
                    case_details=self.current_case,
                    revealed_info=self.revealed_info
                )
            
            if isinstance(result, dict):
                # Check if this was a doctor message that was erroneously routed
                if result.get("is_doctor_message", False):
                    print(f"DEBUG - Detected doctor message in reasoning evaluation, not counting as student reasoning")
                    # Process the doctor's message with the appropriate action
                    # We'll need to figure out what the doctor is asking and route accordingly
                    # For now, we'll just return a generic response
                    response = "I'll help evaluate the student's reasoning when they respond."
                    self.conversation_history.append({
                        "question": original_instruction if 'original_instruction' in locals() else task.instruction,
                        "response": response
                    })
                    return {
                        "response": response,
                        "agent": "case_presenter"
                    }
                
                # Increment the reasoning turn counter if this is a student response
                # Check if this is a doctor message from the original instruction
                is_doctor_message = False
                if 'original_instruction' in locals() and original_instruction:
                    is_doctor_message = original_instruction.lower().startswith("doctor:") or original_instruction.lower().startswith("tutor:")
                
                if not is_doctor_message and not result.get("is_doctor_message", False):
                    self.reasoning_turn_count += 1
                    print(f"DEBUG - Incremented reasoning turn count to {self.reasoning_turn_count}")
                
                # Check if we've exceeded the maximum number of reasoning turns
                if self.reasoning_turn_count >= self.max_reasoning_turns:
                    print(f"DEBUG - Reached maximum reasoning turns ({self.max_reasoning_turns}), marking reasoning as complete")
                    self.awaiting_reasoning = False
                    self.reasoning_evaluation_started = False
                    self.reasoning_turn_count = 0
                    self.differential_given = True
                    self.current_stage = TutorStage.POST_DIFFERENTIAL
                    self.revealed_info.add("differential_diagnosis")
                    
                    # Create a completion response
                    completion_response = "Thank you for explaining your reasoning. Based on your differential and reasoning, let's proceed with the next steps in evaluating this case."
                    self.conversation_history.append({
                        "question": original_instruction if 'original_instruction' in locals() else task.instruction,
                        "response": completion_response
                    })
                    return {
                        "response": completion_response,
                        "reasoning_complete": True,
                        "agent": "case_presenter"
                    }
                
                # Update state based on differential evaluation
                if result.get("reasoning_complete", False) or result.get("is_appropriate", False):
                    self.differential_given = True
                    self.current_stage = TutorStage.POST_DIFFERENTIAL
                    self.revealed_info.add("differential_diagnosis")
                    # Reset awaiting_reasoning flag when reasoning is complete
                    self.awaiting_reasoning = False
                    self.reasoning_evaluation_started = False
                    self.reasoning_turn_count = 0  # Reset the counter
                    print(f"DEBUG - Reasoning complete, resetting awaiting_reasoning to False")
                
                # Track that we've started the reasoning evaluation process
                if not self.reasoning_evaluation_started and not result.get("reasoning_complete", False):
                    self.reasoning_evaluation_started = True
                    print(f"DEBUG - Started reasoning evaluation process")
                
                response = result.get("response", "Please elaborate on your reasoning.")
                self.conversation_history.append({
                    "question": original_instruction if 'original_instruction' in locals() else task.instruction,
                    "response": response
                })
                
                # Log the current state after processing
                print(f"DEBUG - After processing reasoning: awaiting_reasoning={self.awaiting_reasoning}, reasoning_evaluation_started={self.reasoning_evaluation_started}")
                return result
            return str(result)
        
        elif isinstance(action, EvaluateFinalDiagnosisAction):
            result = action(
                student_diagnosis=modified_task.instruction,
                case_details=self.current_case,
                previous_differential=self.current_differential
            )
            if isinstance(result, dict):
                if result.get("is_correct", False):
                    self.current_stage = TutorStage.KNOWLEDGE_ASSESSMENT
                    self.revealed_info.add("final_diagnosis")
                
                response = result.get("feedback", str(result))
                self.conversation_history.append({
                    "question": original_instruction,
                    "response": response
                })
                return result
            return str(result)
        
        # For any other action type, just execute it
        if isinstance(action, ThinkAction):
            # Special case for ThinkAction - likely for diagnostic request before differential
            result = "Before we look at diagnostic tests, I'd like to hear your differential diagnosis based on the history and physical examination findings. What conditions are you considering?"
        else:
            result = str(action(task=modified_task.instruction))
            
        self.conversation_history.append({
            "question": original_instruction,
            "response": result
        })
        return {
            "response": result,
            "agent": "case_presenter"
        }


    def reset(self):
        """Reset the agent state."""
        self.current_case = None
        self.revealed_info = set()
        self.differential_given = False
        self.current_differential = None
        self.diagnostic_tests_revealed = False
        self.conversation_history = []
        self.current_stage = TutorStage.PRE_DIFFERENTIAL
        
        # Reset interactive reasoning variables
        self.awaiting_reasoning = False
        self.reasoning_evaluation_started = False
        self.pending_differential = None
        self.reasoning_turn_count = 0
        
        # Reset differential tracking
        self.differential_history = []


    
