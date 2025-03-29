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

class EvaluateDifferentialReasoningAction(BaseAction):
    def __init__(self):
        super().__init__(
            action_name="EvaluateDifferentialReasoning",
            action_desc="Evaluate student's reasoning for their differential diagnosis",
            params_doc={
                "case_details": "Full case information",
                "student_differential": "Student's differential diagnosis",
                "student_reasoning": "Student's current reasoning statement",
                "is_initial_response": "Whether this is the first response to the differential",
                "full_case_conversation": "Full conversation history from the entire case including reasoning dialogue"
            }
        )
        # Initialize Azure OpenAI for different tasks
        self.clarify_llm = get_azure_llm("gpt-4o-mini")  # Lighter model for clarification
        self.evaluate_llm = get_azure_llm("gpt-4o")      # More powerful model for evaluation
    
    def __call__(self, **kwargs) -> str:
        student_differential = kwargs.get("student_differential", "")
        student_reasoning = kwargs.get("student_reasoning", "")
        case_details = kwargs.get("case_details", {})
        is_initial_response = kwargs.get("is_initial_response", True)
        full_case_conversation = kwargs.get("full_case_conversation", "")
        
        # If this is the initial differential diagnosis, use it as both the differential and reasoning
        if is_initial_response and not student_reasoning and student_differential:
            student_reasoning = student_differential
        
        # STAGE 1: CLARIFICATION STAGE
        # If this is the first response to the differential, check if reasoning is already included
        if is_initial_response:
            # Use a lighter model to determine if reasoning is already included in the differential
            system_prompt = """You are analyzing a student's differential diagnosis to determine if it already includes reasoning.
            Respond with a JSON object in this format:
            {
                "includes_reasoning": true/false,
                "next_question": "The question to ask the student next"
            }
            
            If the student's response includes "because", "due to", "as a result of", "given that", or similar phrases
            followed by clinical reasoning, set includes_reasoning to true.
            
            If includes_reasoning is true, the next_question should ask for additional factors.
            If includes_reasoning is false, the next_question should ask why they think this is the diagnosis."""
            
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
                    
                    if analysis.get("includes_reasoning", False):
                        # If reasoning is included, ask for additional factors
                        return {
                            "response": "Any other clinical findings or epidemiological factors that support your differential?",
                            "includes_reasoning": True,
                            "agent": "case_presenter"
                        }
                    else:
                        # If no reasoning is provided, ask why
                        return {
                            "response": "Why do you think this is the most likely diagnosis? What specific findings support your differential?",
                            "includes_reasoning": False,
                            "agent": "case_presenter"
                        }
            except:
                # Default to asking why if we can't parse the response
                return {
                    "response": "Why do you think this is the most likely diagnosis? What specific findings support your differential?",
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
            
            When analyzing their information gathering, review the FULL case conversation provided to determine what questions they asked and what information they obtained. Did they miss important history, physical exam findings, or necessary tests? Did they fail to explore important epidemiological factors?
            
            **If the failure mode is information gathering (aka, the reasoning is STRONG but INCOMPLETE)**:
                => ask about specific missing elements they should consider!! 
            
            EXAMPLES:

            Student reason given: "staph epidermidis lives on the skin so it's a likely bug to cause infection. probably the patient got a small cut somehow and then it got bad."
            Doctor: However, in this case, the microbiological analysis specifically identified Staphylococcus aureus, not Staphylococcus epidermidis.
            => don't just say "well actually it's staph aureus" - that's not helpful! Also the micro analysis was in the case conversation up to that point, so the student wouldn't have know about it!
            => Instead, ask: "That's a good thought, but if I told you this is incorrect, what question or investigation would help you get to the right answer?"
            ⸻ 
            Fever, night sweats, weight loss → Tuberculosis
            But ask about:
            New information 1: What if I told you the patient had a cat that recently scratched them? → Bartonella henselae
            New information 2: What if I told you the patient is a healthy 22-year-old and their lymph nodes are fluctuant with overlying redness? → Bartonella
            ⸻
            Pneumonia with cavitation → Tuberculosis
            But ask about:
            New information 1: What if I told you they have very poor dentition and recently had a tooth extracted? → Anaerobic lung abscess
            New information 2: What if I told you they also have chronic sinus issues and new hematuria? → Granulomatosis with polyangiitis
            ⸻
            Fever + travel to sub-Saharan Africa → Malaria
            But ask about:
            New information 1: What if I told you they went swimming in Lake Victoria? → Acute schistosomiasis
            New information 2: What if I told you they remember pulling off a tick after a hike through the grasslands? → African tick-bite fever
            ⸻
            Monoarthritis + fever → Septic arthritis
            But ask about:
            New information 1: What if I told you they had some small pustular lesions on their palms and their knee pain started after shoulder and wrist pain? → Disseminated gonococcal infection
            New information 2: What if I told you they had unprotected sex with a new partner two weeks ago? → DGI
            ⸻
            Meningitis in an immunocompromised patient → TB meningitis
            But ask about:
            New information 1: What if I told you they live in a shelter with a large pigeon population nearby? → Cryptococcal meningitis
            New information 2: What if I told you they’re HIV-positive with a CD4 count of 45? → Cryptococcus
            ⸻
            Fever, rash, myalgia after travel to Southeast Asia → Dengue
            But ask about:
            New information 1: What if I told you they have a black crusted lesion on their abdomen and had hiked through tall grass? → Scrub typhus
            New information 2: What if I told you they’re now confused and have a stiff neck? → Japanese encephalitis
            ⸻
            Febrile returning traveler → Malaria
            But ask about:
            New information 1: What if I told you they took mefloquine prophylaxis the whole trip and their eosinophil count is elevated? → Strongyloides or schistosomiasis
            New information 2: What if I told you they went rafting in a river? → Acute schistosomiasis
            ⸻
            Diarrhea after antibiotics → Clostridioides difficile
            But ask about:
            New information 1: What if I told you their colonoscopy shows deep ulcerations and they’re also having visual floaters? → CMV colitis
            New information 2: What if I told you they were recently hospitalized in India? → Multidrug-resistant enteric infection
            ⸻
            Red, swollen leg → Cellulitis
            But ask about:
            New information 1: What if I told you the pain is excruciating and spreads over hours despite IV antibiotics? → Necrotizing fasciitis
            New information 2: What if I told you they went hunting last week and now have a black eschar? → Tularemia or anthrax
            ⸻
            Fever + new murmur → Endocarditis
            But ask about:
            New information 1: What if I told you they were just diagnosed with iron deficiency anemia and their colonoscopy showed a mass? → Strep gallolyticus endocarditis
            New information 2: What if I told you they inject heroin and have septic pulmonary emboli? → Tricuspid valve S. aureus endocarditis

           
            **If the failure mode is knowledge (aka, the reasoning is INCORRECT)**: 
                => gently correct them to help them reroute them into the correct direction

            EXAMPLES: 
            Case: “Patient presents with monoarthritis of the knee and fever. I think it’s gout, since he has a history of elevated uric acid.”
            Failure mode: Misunderstanding that gout = non-infectious, and that septic arthritis can coexist with high uric acid
            Correction:
            “It’s true that hyperuricemia can point toward gout, but remember that it doesn’t rule out septic arthritis — especially in the setting of fever and an acutely inflamed joint. What would help you definitively distinguish between the two here?”
            → (Joint aspiration)
            ⸻
            Case: “This returning traveler with fever, chills, and low platelets must have typhoid — they were in India last month.”
            Failure mode: Overrelying on geography, missing malaria as the most urgent r/o
            Correction:
            “Typhoid is definitely endemic in India, but before you settle there — which diagnosis would you want to rule out first, given how quickly it can deteriorate and how treatable it is if caught early?”
            → (Malaria with thick/thin smear)
            ⸻
            Case: “This patient has a cough and night sweats — so I think it’s bacterial pneumonia.”
            Failure mode: Not recognizing chronicity and constitutional symptoms suggest something else
            Correction:
            “Interesting — bacterial pneumonia is often more acute. Does anything about the time course or those night sweats make you think of a more chronic or systemic process?”
            → (Consider TB, fungal infection, malignancy)
            ⸻
            Case: “The patient has fever and a diastolic murmur — it’s aortic stenosis.”
            Failure mode: Misidentifying murmur type, missing the red flag of fever + murmur
            Correction:
            “Aortic stenosis is a good thought for a murmur, but it usually causes a systolic sound. With a diastolic murmur and fever, what serious diagnosis should we prioritize?”
            → (Endocarditis with aortic regurg)
            ⸻
            Case: “They have HIV and are coughing — it’s PCP pneumonia.”
            Failure mode: Anchoring on HIV without considering CD4 count or OI timeline
            Correction:
            “PCP is certainly common in HIV, but not every patient with HIV is equally vulnerable. What kind of immune status would make you more concerned for that?”
            → (PCP usually if CD4 < 200)
            ⸻
            Case: “This elderly patient has fever and flank pain — must be appendicitis.”
            Failure mode: Anchoring on abdominal pain without considering age-adjusted prevalence
            Correction:
            “Appendicitis is common, but in someone older, are there other intra-abdominal or urologic sources you’d want to think about, especially with flank pain?”
            → (Consider pyelonephritis, diverticulitis)
            ⸻
            Case: “The patient has diarrhea after antibiotics — must be a foodborne bug like Salmonella.”
            Failure mode: Missing the classic iatrogenic cause
            Correction:
            “Salmonella’s definitely on the list — but if they were recently on antibiotics, is there another cause that’s directly related to that exposure?”
            → (C. difficile)
            ⸻
            Case: “This patient has fever and a systolic murmur — probably rheumatic fever.”
            Failure mode: Misunderstanding of rheumatic fever epidemiology and murmur acuity
            Correction:
            “Interesting pick — rheumatic fever is more common in younger patients and developing regions. In an adult with new fever and murmur, what more urgent infectious cause should we consider?”
            → (Infective endocarditis)

            Keep asking questions until you are confident about the accuracy of reasoning OR if the student asks to move on. Then you should conclude the reasoning phase: reasoning_complete = true. 

            Return a JSON object with:
            {
                "reasoning_complete": true/false,
                "response_type": "probe_further|correct_misconception|challenge_with_information|acknowledge_good_reasoning",
                "response": "Your response to the student",
                "reasoning_quality": "strong|adequate|needs_improvement|flawed"
            }"""
            
            main_prompt = f"""Case Details:
{case_details.get('case_text', '')}

Student's Differential Diagnosis:
{student_differential}

Full Case Conversation (all questions asked and answers received):
{full_case_with_current if full_case_with_current else "[No prior conversation recorded]"}

Case-relevant information that the student has already gathered:
{self.revealed_info}

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
                    
                    return {
                        "response": evaluation.get("response", "Could you elaborate on your reasoning?"),
                        "reasoning_complete": evaluation.get("reasoning_complete", False),
                        "reasoning_quality": evaluation.get("reasoning_quality", "needs_improvement"),
                        "response_type": evaluation.get("response_type", "probe_further"),
                        "agent": "case_presenter"
                    }
                
                raise ValueError("No valid JSON found in response")
                
            except Exception as e:
                print(f"Error evaluating reasoning: {str(e)}")
                # Default to a generic follow-up question
                return {
                    "response": "Interesting. Could you elaborate more on the connection between your observations and your diagnosis?",
                    "reasoning_complete": False,
                    "reasoning_quality": "needs_improvement",
                    "response_type": "probe_further",
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
            PhysicalExamAction(),  # Add the new physical exam action
            EvaluateDifferentialAction(),  # Keep both for A/B testing
            EvaluateDifferentialReasoningAction(), # Add the new reasoning evaluation action
            EvaluateFinalDiagnosisAction(),
            ThinkAction(),
            FinishAction()
        ]
        ##3. Assess readiness for differential diagnosis, 4. Assess final diagnoses and provide feedback
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
    
    def determine_action(self, task: TaskPackage) -> BaseAction:
        """Determine which action to use based on the task instruction."""
        instruction = task.instruction.lower()
        
        # Use a smaller model for action determination
        determine_action_llm = get_azure_llm("gpt-4o")
        
        # Debug state
        print(f"DEBUG - determine_action - awaiting_reasoning: {self.awaiting_reasoning}, pending_differential: {self.pending_differential}")
        
        # If we're awaiting reasoning, this is likely the reasoning response
        if self.awaiting_reasoning:
            print(f"DEBUG - Already awaiting reasoning, using EvaluateDifferentialReasoningAction")
            return next(action for action in self.actions if isinstance(action, EvaluateDifferentialReasoningAction))
        
        # For A/B testing, the decision is controlled by the class variable
        # If we're determining action for a differential diagnosis input, return the appropriate action
        if "diagnosis" in instruction or "differential" in instruction or "ddx" in instruction:
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
        
        # Create a prompt for the LLM to help determine the appropriate action
        system_prompt = """You are an expert medical case presenter helping to determine which action to take based on a student's input.
        Available actions are:
        1. PresentCase - For presenting initial case information
        2. PhysicalExam - For providing physical examination findings when the student asks for specific exam components
        3. EvaluateDifferential - For evaluating a proposed differential diagnosis without interactive reasoning
        4. EvaluateDifferentialReasoning - For evaluating differential diagnoses with an interactive reasoning process 
        5. EvaluateFinalDiagnosis - For evaluating a final diagnosis
        
        PresentCase is only used when the case is just started, to give the initial one-liner.

        PhysicalExam is used when the student asks for specific physical examination findings, such as:
        - "What do you hear when you listen to the lungs?"
        - "Can you check the patient's abdomen?"
        - "What do the vital signs show?"
        - "Are there any skin findings?"
        - "What do you see in the throat?"

        EvaluateDifferential is used when the student proposes a differential diagnosis and you want to evaluate it directly without the interactive reasoning process.

        EvaluateDifferentialReasoning is used when the student proposes a differential diagnosis and you want to engage in an interactive reasoning process.

        EvaluateFinalDiagnosis is used to evaluate a definitive final diagnosis (after the differential).
        
        IMPORTANT: EvaluateDifferential and EvaluateDifferentialReasoning are two different approaches. Do not confuse them.
        
        Respond with ONLY the action name, nothing else."""
        
        # Get the context from the task
        context = f"""Task instruction: {instruction}
        Current state:
        - Differential given: {self.differential_given}
        - Information revealed: {', '.join(self.revealed_info) if self.revealed_info else 'None'}
        """
        
        # Use LLM to determine action for non-differential inputs
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
        
        # Default to first action if no match
        return self.actions[0]
    
    def __call__(self, task: TaskPackage) -> str:
        """Handle case presentation, clinical reasoning, and diagnostic evaluation."""
        # Determine which action to use
        print(f"DEBUG - __call__ - Starting with instruction: {task.instruction}")
        print(f"DEBUG - __call__ - State before action: awaiting_reasoning={self.awaiting_reasoning}, pending_differential={self.pending_differential}")
        
        # Check for full conversation history in the context
        full_conversation_history = None
        if hasattr(task, 'context') and task.context and 'full_conversation_history' in task.context:
            full_conversation_history = task.context['full_conversation_history']
            print(f"DEBUG - __call__ - Received full conversation history with {len(full_conversation_history)} entries")
        
        action = self.determine_action(task)
        
        print(f"DEBUG - __call__ - Selected action: {action.action_name}")
        
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
        
        # Handle EvaluateDifferentialAction directly (non-interactive approach)
        elif isinstance(action, EvaluateDifferentialAction):
            # Store the differential for future reference
            self.pending_differential = task.instruction
            self.current_differential = task.instruction
            
            # Add to differential history if it's not already there
            if task.instruction not in self.differential_history:
                self.differential_history.append(task.instruction)
                print(f"DEBUG - Added to differential history (non-interactive): {task.instruction}")
            
            # Process using the original non-interactive approach
            result = action(
                student_differential=task.instruction,
                case_details=self.current_case
            )
            
            # Extract and store information
            if isinstance(result, dict):
                response = result.get("feedback", str(result))
                is_appropriate = result.get("is_appropriate", False)
                
                # Update state if the differential is appropriate
                if is_appropriate:
                    self.differential_given = True
                    self.current_stage = TutorStage.POST_DIFFERENTIAL
                
                self.conversation_history.append({
                    "question": task.instruction,
                    "response": response
                })
                
                return {
                    "response": response,
                    "agent": "case_presenter"
                }
            return str(result)
        
        # Handle EvaluateDifferentialReasoningAction (interactive approach)
        elif isinstance(action, EvaluateDifferentialReasoningAction):
            # Store the differential if this is the first interaction
            if not self.awaiting_reasoning:
                print(f"DEBUG - EvaluateDifferentialReasoningAction - Setting pending_differential: {task.instruction}")
                self.pending_differential = task.instruction
                self.awaiting_reasoning = True
                self.reasoning_evaluation_started = False
            
            # Check if we have a pending differential to evaluate
            if not self.pending_differential:
                print(f"DEBUG - EvaluateDifferentialReasoningAction - No pending_differential found!")
                # If no differential, ask for one
                response = "Please provide a differential diagnosis first."
                self.conversation_history.append({
                    "question": task.instruction,
                    "response": response
                })
                return {
                    "response": response,
                    "agent": "case_presenter"
                }
            
            # Determine if this is the initial response or a follow-up
            is_initial_response = not self.reasoning_evaluation_started
            print(f"DEBUG - EvaluateDifferentialReasoningAction - is_initial_response: {is_initial_response}")
            self.reasoning_evaluation_started = True
            
            # Format the full conversation history into a readable string if available
            full_conversation_string = ""
            if full_conversation_history:
                print(f"DEBUG - Using full conversation history with {len(full_conversation_history)} entries")
                for entry in full_conversation_history:
                    question = entry.get("question", "")
                    response = entry.get("response", "")
                    agent = entry.get("agent", "unknown")
                    agent_label = "Doctor" if agent == "case_presenter" else "Patient"
                    
                    if question:
                        full_conversation_string += f"Student: {question}\n"
                    if response:
                        full_conversation_string += f"{agent_label}: {response}\n\n"
            
            # Debug information
            print(f"DEBUG - Current case: {self.current_case}")
            
            # Evaluate the reasoning
            result = action(
                student_differential=self.pending_differential,
                student_reasoning=task.instruction if not is_initial_response else self.pending_differential,
                is_initial_response=is_initial_response,
                full_case_conversation=full_conversation_string,
                case_details=self.current_case
            )
            
            # Get the response
            response = result.get("response", "Please elaborate on your reasoning.")
            
            # Store in conversation history
            self.conversation_history.append({
                "question": task.instruction,
                "response": response
            })
            
            # If reasoning is complete, update status
            if result.get("reasoning_complete", False):
                self.awaiting_reasoning = False
                self.differential_given = True
                self.current_stage = TutorStage.POST_DIFFERENTIAL
                print(f"DEBUG - Reasoning complete for differential: {self.pending_differential}")
            
            return {
                "response": response,
                "agent": "case_presenter"
            }
        
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
        
        # Reset interactive reasoning variables
        self.awaiting_reasoning = False
        self.reasoning_evaluation_started = False
        self.pending_differential = None
        
        # Reset differential tracking
        self.differential_history = []


    
