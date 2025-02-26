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

# Helper function to create Azure OpenAI LLM instance
def get_azure_llm(deployment_name=None, temperature=0.1):
    """Create and return an Azure OpenAI LLM instance with the specified parameters."""
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
        
        # Add the examined area to revealed info
        exam_category = self._categorize_exam_request(exam_request)
        
        return {
            "response": response.content.strip(),
            "exam_type": exam_category,
            "agent": "case_presenter"
        }
    
    def _categorize_exam_request(self, request):
        """Categorize the exam request into a standard category for tracking."""
        request_lower = request.lower()
        
        if any(term in request_lower for term in ["lung", "chest", "breath", "respiratory", "auscultation"]):
            return "respiratory_exam"
        elif any(term in request_lower for term in ["heart", "cardiac", "pulse", "cardiovascular"]):
            return "cardiac_exam"
        elif any(term in request_lower for term in ["abdomen", "belly", "stomach", "bowel"]):
            return "abdominal_exam"
        elif any(term in request_lower for term in ["neuro", "neurological", "mental", "consciousness"]):
            return "neurological_exam"
        elif any(term in request_lower for term in ["skin", "rash", "lesion"]):
            return "skin_exam"
        elif any(term in request_lower for term in ["lymph", "node", "spleen", "liver"]):
            return "lymphatic_exam"
        elif any(term in request_lower for term in ["ear", "nose", "throat", "mouth"]):
            return "ent_exam"
        elif any(term in request_lower for term in ["eye", "vision", "pupil"]):
            return "eye_exam"
        elif any(term in request_lower for term in ["musculoskeletal", "joint", "muscle", "bone"]):
            return "musculoskeletal_exam"
        else:
            return "general_physical_exam"

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
        self.llm = get_azure_llm("gpt-4o-mini")
    
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

        
        Evaluate if enough critical information has been gathered to generate a meaningful differential diagnosis.
        Consider both breadth and depth of information gathering.
        You will receive the case details and the information that has been revealed so far.
        
        You must respond with ONLY a JSON object in this exact format:
        {
            "ready": false,
            "message": "Explanation of what information is still needed",
            "missing_critical_info": ["list", "of", "critical", "missing", "elements"]
        }
        
        OR if ready:
        {
            "ready": true,
            "message": "Explanation of why sufficient information has been gathered"
        }

        Do not include any other text outside the JSON object."""
        
        main_prompt = f"""Case Details:
{case_details.get('case_text', '')}

Information Gathered So Far:
{conversation_summary}

Categories of Information Revealed:
{', '.join(revealed_info) if revealed_info else 'None'}

Based on this information, assess if sufficient information has been gathered to formulate a reasonable differential diagnosis. Consider what
diseases would be on your differential at this point. If it is reasonably narrow, the student is ready, but if the student didn't gather information 
to narrow it down, they are not ready. 
Consider what a well-trained physician would need to generate a meaningful differential.
"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=main_prompt)
        ]
        
        response = self.llm.invoke(messages)
        
        try:
            import json
            # Strip any potential whitespace or extra text
            response_text = response.content.strip()
            # Find the first { and last } to extract just the JSON
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = response_text[start:end]
                evaluation = json.loads(json_str)
                return {
                    "ready": evaluation.get("ready", False),
                    "message": evaluation.get("message", "Please continue gathering key clinical information."),
                    "missing_info": evaluation.get("missing_critical_info", []) if not evaluation.get("ready", False) else None
                }
            raise ValueError("No valid JSON found in response")
        except Exception as e:
            print(f"Error parsing readiness evaluation: {str(e)}")  # Debug log
            print(f"Response content: {response.content}")  # Debug log
            return {
                "ready": False,
                "message": "Please continue gathering key clinical information about the patient's symptoms, vital signs, and relevant history."
            }

class EvaluateDifferentialAction(BaseAction):
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

class EvaluateFinalDiagnosisAction(BaseAction):
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
            PresentCaseAction(),
            PhysicalExamAction(),  # Add the new physical exam action
            AssessReadinessAction(),
            EvaluateDifferentialAction(),
            EvaluateFinalDiagnosisAction(),
            ThinkAction(),
            FinishAction()
        ]
        
        super().__init__(
            name="case_presenter",
            role="""I am an expert medical case presenter and clinical reasoning coach. I:
            1. Present clinical cases and guide information gathering
            2. Provide physical examination findings when requested
            3. Assess readiness for differential diagnosis
            4. Evaluate differential diagnoses and clinical reasoning
            5. Assess final diagnoses and provide feedback
            6. Track case progression and information revealed
            
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
    
    def determine_action(self, task: TaskPackage) -> BaseAction:
        """Determine which action to use based on the task instruction."""
        instruction = task.instruction.lower()
        
        # Use a smaller model for action determination
        determine_action_llm = get_azure_llm("gpt-4o-mini")
        
        # Create a prompt for the LLM to help determine the appropriate action
        system_prompt = """You are an expert medical case presenter helping to determine which action to take based on a student's input.
        Available actions are:
        1. PresentCase - For presenting initial case information
        2. PhysicalExam - For providing physical examination findings when the student asks for specific exam components
        3. AssessReadiness - For checking if student has gathered enough info for differential
        4. EvaluateDifferential - For evaluating a proposed differential diagnosis
        5. EvaluateFinalDiagnosis - For evaluating a final diagnosis
        
        PresentCase is only used when the case is just started, to give the initial one-liner.

        PhysicalExam is used when the student asks for specific physical examination findings, such as:
        - "What do you hear when you listen to the lungs?"
        - "Can you check the patient's abdomen?"
        - "What do the vital signs show?"
        - "Are there any skin findings?"
        - "What do you see in the throat?"
        
        AssessReadiness is used to check if the student has gathered enough information to give a differential diagnosis.

        EvaluateDifferential is used to evaluate a proposed differential diagnosis.

        EvaluateFinalDiagnosis is used to evaluate a final diagnosis (after the differential).
        
        Respond with ONLY the action name, nothing else."""
        
        # Get the context from the task
        context = f"""Task instruction: {instruction}
        Current state:
        - Differential given: {self.differential_given}
        - Information revealed: {', '.join(self.revealed_info) if self.revealed_info else 'None'}
        """
        
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
            
        # Default to EvaluateDifferential if no clear match
        return next(action for action in self.actions if isinstance(action, EvaluateDifferentialAction))
    
    def __call__(self, task: TaskPackage) -> str:
        """Handle case presentation, clinical reasoning, and diagnostic evaluation."""
        # Determine which action to use
        action = self.determine_action(task)
        
        # Handle each action type
        if isinstance(action, PresentCaseAction):
            case_data = getattr(task, 'context', {}).get('case', {}) or self.current_case
            result = action(case=case_data)
            if isinstance(result, dict):
                if result.get("full_case"):
                    self.current_case = result.get("full_case")
                elif result.get("case_text"):
                    self.current_case = {"case_text": result.get("case_text")}
                
                response = result.get("case_presentation", "A patient presents for evaluation.")
                self.conversation_history.append({
                    "question": task.instruction,
                    "response": response
                })
                return {
                    "response": response,
                    "agent": "case_presenter"
                }
            return str(result)
        
        elif isinstance(action, PhysicalExamAction):
            result = action(
                exam_request=task.instruction,
                case_details=self.current_case
            )
            if isinstance(result, dict):
                # Add the exam type to revealed info
                exam_type = result.get("exam_type")
                if exam_type:
                    self.revealed_info.add(exam_type)
                
                response = result.get("response", "No significant findings.")
                self.conversation_history.append({
                    "question": task.instruction,
                    "response": response
                })
                return {
                    "response": response,
                    "agent": "case_presenter"
                }
            return str(result)
        
        elif isinstance(action, AssessReadinessAction):
            result = action(
                conversation_history=self.conversation_history,
                case_details=self.current_case,
                revealed_info=self.revealed_info
            )
            response = result.get("message") if isinstance(result, dict) else str(result)
            self.conversation_history.append({
                "question": task.instruction,
                "response": response
            })
            return response
        
        elif isinstance(action, EvaluateDifferentialAction):
            self.current_differential = task.instruction
            result = action(
                student_differential=task.instruction,
                case_details=self.current_case
            )
            if isinstance(result, dict) and result.get("is_appropriate", False):
                self.differential_given = True
                self.current_stage = TutorStage.POST_DIFFERENTIAL
            response = result.get("feedback", str(result))
            self.conversation_history.append({
                "question": task.instruction,
                "response": response
            })
            return response
            
        elif isinstance(action, EvaluateFinalDiagnosisAction):
            result = action(
                student_diagnosis=task.instruction,
                case_details=self.current_case,
                previous_differential=self.current_differential
            )
            if isinstance(result, dict) and result.get("is_correct", False):
                self.current_stage = TutorStage.KNOWLEDGE_ASSESSMENT
            
            # Extract response and organism
            response = result.get("feedback", str(result))
            organism = result.get("organism", "Unknown organism")
            is_correct = result.get("is_correct", False)
            
            self.conversation_history.append({
                "question": task.instruction,
                "response": response
            })
            
            # Return the full result including organism if correct
            if is_correct:
                return {
                    "response": response,
                    "is_correct": True,
                    "organism": organism,
                    "agent": "case_presenter"
                }
            else:
                return {
                    "response": response,
                    "agent": "case_presenter"
                }
        
        # For any other action type, just execute it
        return str(action(task=task.instruction))
    
    def reset(self):
        """Reset the agent state."""
        self.current_case = None
        self.revealed_info = set()
        self.differential_given = False
        self.current_differential = None
        self.diagnostic_tests_revealed = False
        self.conversation_history = []
        self.current_stage = TutorStage.PRE_DIFFERENTIAL
