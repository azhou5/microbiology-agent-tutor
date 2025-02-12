from typing import Dict
from agentlite.agents import BaseAgent as AgentLiteBaseAgent
from agentlite.llm.agent_llms import BaseLLM, get_llm_backend
from agentlite.llm.LLMConfig import LLMConfig
from agentlite.actions import BaseAction
from agentlite.actions.InnerActions import ThinkAction, FinishAction
from agentlite.commons import TaskPackage, AgentAct

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
    
    def __call__(self, **kwargs) -> str:
        student_differential = kwargs.get("student_differential", "")
        case_details = kwargs.get("case_details", {})
        
        # Check if no differential was actually provided
        if not student_differential or student_differential == "Student's differential diagnosis":
            return {
                "feedback": "No differential diagnosis was provided. Please state your differential diagnosis, listing the possible causative organisms or conditions you're considering based on the clinical presentation.",
                "ready": False
            }
        
        # Create a comprehensive evaluation prompt
        evaluation_prompt = f"""Based on the case details:
        - Demographics: {case_details.get('demographics', {})}
        - Presenting Symptoms: {case_details.get('presenting_symptoms', [])}
        - Physical Exam: {case_details.get('physical_exam', {})}
        - Epidemiology: {case_details.get('epidemiology', '')}
        
        And the student's differential diagnosis:
        {student_differential}
        
        Provide constructive feedback considering:
        1. Are the proposed organisms/conditions reasonable given the clinical presentation?
        2. Are there any important pathogens they missed?
        3. What is the epidemiological and clinical reasoning supporting each possibility?
        4. What specific aspects of the case support or argue against each proposed pathogen?
        
        Then, guide them to consider specific diagnostic tests that would help distinguish between 
        these possibilities. Be specific about what tests would be most helpful and why.
        
        Format your response to be:
        1. Brief but specific feedback on their differential
        2. Any critical missing pathogens they should consider
        3. Guidance on what diagnostic tests would be most helpful
        """
        
        # Use the LLM to generate the evaluation
        response = kwargs.get("llm_response", evaluation_prompt)  # In real implementation, this would use the LLM
        
        return {
            "feedback": response,
            "is_appropriate": True  # You would want to actually evaluate this based on the response
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
    
    def __call__(self, **kwargs) -> str:
        case_details = kwargs.get("case_details", {})
        student_diagnosis = kwargs.get("student_diagnosis", "")
        previous_differential = kwargs.get("previous_differential", "")
        
        evaluation_prompt = f"""Based on:
        1. The case details
        2. The student's previous differential: {previous_differential}
        3. Their final diagnosis: {student_diagnosis}
        4. The available lab results: {case_details.get('initial_labs', {})}
        
        Evaluate their final diagnosis considering:
        1. Does it match the clinical presentation?
        2. Is it supported by the laboratory findings?
        3. How well did they use the diagnostic data to refine their differential?
        4. What key features of the case support this diagnosis?
        
        Provide:
        1. Specific feedback on their diagnostic reasoning
        2. Explanation of how the lab results support or refute their conclusion
        3. Any important learning points about this pathogen
        """
        
        # Use the LLM to generate the evaluation
        response = kwargs.get("llm_response", evaluation_prompt)  # In real implementation, this would use the LLM
        
        return {
            "feedback": response,
            "is_correct": True,  # This would be determined based on the actual evaluation
            "organism": student_diagnosis
        }

class ProvideHelpAction(BaseAction):
    def __init__(self):
        super().__init__(
            action_name="ProvideHelp",
            action_desc="Provide contextual hints and guidance to the student",
            params_doc={
                "case_details": "Full case information",
                "conversation_history": "History of the interaction",
                "revealed_info": "Information already revealed",
                "differential_given": "Whether differential has been provided"
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
            temperature=0.3
        )
    
    def __call__(self, **kwargs) -> str:
        case_details = kwargs.get("case_details", {})
        conversation_history = kwargs.get("conversation_history", [])
        revealed_info = kwargs.get("revealed_info", set())
        differential_given = kwargs.get("differential_given", False)
        
        # Create conversation summary
        conversation_summary = "\n".join([
            f"Student: {interaction['question']}\nTutor: {interaction['response']}"
            for interaction in conversation_history[-5:]  # Include last 5 interactions for context
        ])
        
        system_prompt = """You are an expert medical educator providing guidance to a student working through a clinical case.
        Your role is to provide helpful hints without giving away the diagnosis. Consider:

        1. The stage of the diagnostic process:
           - Initial information gathering
           - Pattern recognition
           - Differential diagnosis formation
           - Test selection
        
        2. Educational principles:
           - Guide don't tell
           - Highlight key features they might have missed
           - Encourage systematic thinking
           - Point out pattern recognition opportunities
        
        3. Clinical reasoning support:
           - Suggest areas of inquiry they haven't considered
           - Help them connect related symptoms
           - Guide them to think about epidemiological factors
           - Remind them of important physical exam components
        
        Provide a hint that:
        1. Is specific enough to be helpful
        2. Doesn't give away the diagnosis
        3. Encourages clinical reasoning
        4. Builds on what they already know
        """
        
        main_prompt = f"""Case Details:
{case_details.get('case_text', '')}

Conversation History:
{conversation_summary}

Information Already Revealed:
{', '.join(revealed_info) if revealed_info else 'None'}

Differential Given: {differential_given}

Based on where they are in the case, provide an appropriate hint that helps them move forward in their clinical reasoning.
Focus on helping them think through the case systematically without giving away key conclusions."""

        from langchain.schema import HumanMessage, SystemMessage
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=main_prompt)
        ]
        
        response = self.llm.invoke(messages)
        return {
            "hint": response.content,
            "type": "guidance"
        }

class ClinicalReasoningGraderAction(BaseAction):
    def __init__(self):
        super().__init__(
            action_name="GradeReasoning",
            action_desc="Evaluate the quality of clinical reasoning demonstrated in the case interaction",
            params_doc={
                "case_details": "Full case information",
                "conversation_history": "Complete history of the interaction",
                "differential_diagnosis": "Student's differential diagnosis",
                "revealed_info": "Information categories revealed during the interaction"
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
        case_details = kwargs.get("case_details", {})
        conversation_history = kwargs.get("conversation_history", [])
        differential_diagnosis = kwargs.get("differential_diagnosis", "")
        revealed_info = kwargs.get("revealed_info", set())
        
        # Create detailed interaction summary
        conversation_summary = "\n".join([
            f"Student: {interaction['question']}\nTutor: {interaction['response']}"
            for interaction in conversation_history
        ])
        
        system_prompt = """You are an expert medical educator evaluating a student's clinical reasoning process.
        Analyze their information gathering and differential diagnosis formation, considering:

        1. Information Gathering Efficiency:
           - Were questions targeted and relevant?
           - Did they gather essential information systematically?
           - Did they avoid unnecessary or redundant questions?
           - Did they recognize and follow up on key findings?

        2. Pattern Recognition:
           - Did they recognize important symptom clusters?
           - Did they consider epidemiological context?
           - Did they identify pertinent negative findings?
           - Did they connect related clinical features?

        3. Differential Diagnosis Formation:
           - Was their differential appropriately broad?
           - Did they consider common and dangerous causes?
           - Did they use epidemiology to refine probabilities?
           - Did they integrate all relevant findings?

        Provide a structured evaluation that:
        1. Highlights effective questions that helped narrow the differential
        2. Identifies missed opportunities or inefficient questioning
        3. Evaluates their clinical reasoning process
        4. Suggests specific areas for improvement

        Format your response as:
        {
            "effective_questions": ["list", "of", "good", "questions"],
            "inefficient_questions": ["list", "of", "unnecessary", "questions"],
            "reasoning_strengths": ["list", "of", "strengths"],
            "areas_for_improvement": ["list", "of", "suggestions"],
            "overall_feedback": "Detailed feedback message"
        }
        """
        
        main_prompt = f"""Case Details:
{case_details.get('case_text', '')}

Complete Interaction:
{conversation_summary}

Student's Differential Diagnosis:
{differential_diagnosis}

Information Categories Revealed:
{', '.join(revealed_info) if revealed_info else 'None'}

Evaluate the student's clinical reasoning process, focusing on both the quality of their information gathering and their differential diagnosis formation."""

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
                "evaluation": evaluation,
                "type": "feedback"
            }
        except:
            # Fallback if JSON parsing fails
            return {
                "evaluation": {
                    "overall_feedback": response.content
                },
                "type": "feedback"
            }

class ClinicalReasoningAgent(AgentLiteBaseAgent):
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.3):
        # Initialize LLM configuration
        llm_config = LLMConfig({"llm_name": model_name, "temperature": temperature})
        llm = get_llm_backend(llm_config)
        
        # Initialize custom actions
        actions = [
            EvaluateDifferentialAction(),
            EvaluateFinalDiagnosisAction(),
            ProvideHelpAction(),
            ClinicalReasoningGraderAction(),
            ThinkAction(),
            FinishAction()
        ]
        
        super().__init__(
            name="clinical_reasoning",
            role="""I am an expert medical microbiologist specializing in diagnostic reasoning and clinical case analysis.
            
            I guide students through the diagnostic process by:
            1. Evaluating differential diagnoses based on:
               - Epidemiological reasoning
               - Clinical pattern recognition
               - Host and pathogen factors
               - Evidence-based likelihood of different pathogens
            
            2. Providing constructive feedback that:
               - Acknowledges good reasoning
               - Identifies gaps in thinking
               - Suggests additional considerations
               - Guides test selection
            
            3. Assessing final diagnoses by:
               - Matching clinical features to pathogens
               - Evaluating use of laboratory data
               - Reinforcing key learning points
               - Highlighting diagnostic principles
            
            I maintain a structured educational approach:
            1. Require thorough information gathering before differential
            2. Guide test selection based on differential
            3. Ensure evidence-based final diagnoses
            4. Emphasize learning from the diagnostic process
            
            I also offer contextual hints when needed and assess the quality of clinical reasoning demonstrated in the case interaction.""",
            llm=llm,
            actions=actions,
            reasoning_type="react"
        )
        
        self.current_case = None
        self.current_differential = None
        self.differential_feedback_given = False
        self.conversation_history = []
        
        # Add examples of successful interactions
        self._add_examples()
    
    def __call__(self, task: TaskPackage) -> str:
        """Handle evaluation of student's diagnostic reasoning."""
        instruction = task.instruction.lower()
        
        # If this is a differential diagnosis attempt
        if any(phrase in instruction for phrase in [
            "differential", "diagnosis", "it could be", "suspect", "my guess",
            "it sounds like", "likely has", "probably has", "might be"
        ]):
            action = EvaluateDifferentialAction()
            self.current_differential = task.instruction
            result = action(
                student_differential=task.instruction,
                case_details=self.current_case,
                llm_response=self.llm_layer(task.instruction)
            )
            self.differential_feedback_given = True
            return result.get("feedback", str(result))
        
        # If this is a final diagnosis
        if "final" in instruction or "this is" in instruction:
            action = EvaluateFinalDiagnosisAction()
            result = action(
                student_diagnosis=task.instruction,
                case_details=self.current_case,
                previous_differential=self.current_differential,
                llm_response=self.llm_layer(task.instruction)
            )
            return result.get("feedback", str(result))
        
        return "Please provide either a differential diagnosis or a final diagnosis."
    
    def reset(self):
        """Reset the agent state."""
        self.current_case = None
        self.current_differential = None
        self.differential_feedback_given = False
        self.conversation_history = []

    def _add_examples(self):
        """Add comprehensive examples of successful agent interactions."""
        
        # Example 1: Evaluating good initial differential
        task1 = TaskPackage(instruction="The differential includes bacterial meningitis (N. meningitidis, S. pneumoniae) and viral meningitis given the headache, fever, and neck stiffness.")
        action_chain1 = [
            (AgentAct(name="Think", params={"response": "Student has provided a well-reasoned initial differential with appropriate organisms."}),
             "OK"),
            (AgentAct(name="EvaluateDifferential", params={
                "case_details": {
                    "presenting_symptoms": ["severe headache", "neck stiffness", "fever"],
                    "physical_exam": {"findings": "Positive Kernig's and Brudzinski's signs"},
                    "epidemiology": "Two other cases of meningitis in dormitory"
                },
                "student_differential": "bacterial meningitis (N. meningitidis, S. pneumoniae) and viral meningitis",
                "stage": "initial"
            }),
             {"feedback": """Excellent initial differential diagnosis! Your reasoning shows:
             1. Good pattern recognition of meningitis syndrome
             2. Appropriate consideration of both bacterial and viral etiologies
             3. Specific bacterial pathogens accurately identified
             4. Consideration of epidemiological context
             
             You may now proceed with requesting laboratory studies to narrow your differential.""",
              "is_appropriate": True}),
            (AgentAct(name="Finish", params={"response": "Excellent initial differential diagnosis! [...]"}),
             "Task completed.")
        ]
        self.add_example(task1, action_chain1)

        # Example 2: Evaluating incomplete differential
        task2 = TaskPackage(instruction="I think it's just a migraine headache")
        action_chain2 = [
            (AgentAct(name="Think", params={"response": "Student's differential is too narrow and misses key clinical features."}),
             "OK"),
            (AgentAct(name="EvaluateDifferential", params={
                "case_details": {
                    "presenting_symptoms": ["severe headache", "neck stiffness", "fever"],
                    "physical_exam": {"findings": "Positive Kernig's and Brudzinski's signs"},
                    "epidemiology": "Two other cases of meningitis in dormitory"
                },
                "student_differential": "migraine headache",
                "stage": "initial"
            }),
             {"feedback": """Your differential needs expansion. Consider:
             1. The presence of fever and neck stiffness
             2. Positive meningeal signs on exam
             3. The epidemiological context
             
             These features suggest more serious conditions that should be included in your differential.""",
              "is_appropriate": False}),
            (AgentAct(name="Finish", params={"response": "Your differential needs expansion. [...]"}),
             "Task completed.")
        ]
        self.add_example(task2, action_chain2)

        # Example 3: Evaluating correct final diagnosis
        task3 = TaskPackage(instruction="Based on the CSF showing gram-negative diplococci and the dormitory outbreak, this is N. meningitidis meningitis")
        action_chain3 = [
            (AgentAct(name="Think", params={"response": "Student has made correct final diagnosis with supporting evidence."}),
             "OK"),
            (AgentAct(name="EvaluateFinalDiagnosis", params={
                "case_details": {
                    "causative_organism": "N. meningitidis",
                    "labs": {"CSF": "Gram-negative diplococci"},
                    "epidemiology": "Two other cases of meningitis in dormitory"
                },
                "student_diagnosis": "N. meningitidis meningitis"
            }),
             {"feedback": """Excellent final diagnosis! Your conclusion is well-supported by:
             1. Classic CSF findings of gram-negative diplococci
             2. Epidemiological context of dormitory outbreak
             3. Typical clinical presentation
             
             Let's proceed to discuss key aspects of N. meningitidis infection.""",
              "is_correct": True,
              "organism": "N. meningitidis"}),
            (AgentAct(name="Finish", params={"response": "Excellent final diagnosis! [...]"}),
             "Task completed.")
        ]
        self.add_example(task3, action_chain3)

        # Example 4: Evaluating incorrect final diagnosis
        task4 = TaskPackage(instruction="This is viral meningitis")
        action_chain4 = [
            (AgentAct(name="Think", params={"response": "Student's final diagnosis conflicts with key laboratory findings."}),
             "OK"),
            (AgentAct(name="EvaluateFinalDiagnosis", params={
                "case_details": {
                    "causative_organism": "N. meningitidis",
                    "labs": {"CSF": "Gram-negative diplococci"},
                    "epidemiology": "Two other cases of meningitis in dormitory"
                },
                "student_diagnosis": "viral meningitis"
            }),
             {"feedback": """Your diagnosis needs revision. Consider:
             1. The CSF shows gram-negative diplococci, which indicates bacterial infection
             2. The outbreak pattern in a dormitory setting
             3. The severity of presentation
             
             These findings strongly suggest which specific bacterial pathogen?""",
              "is_correct": False}),
            (AgentAct(name="Finish", params={"response": "Your diagnosis needs revision. [...]"}),
             "Task completed.")
        ]
        self.add_example(task4, action_chain4)

        # Example 5: Providing a hint
        task5 = TaskPackage(instruction="I'm not sure what to think about the CSF findings")
        action_chain5 = [
            (AgentAct(name="Think", params={"response": "Student needs guidance interpreting laboratory findings."}),
             "OK"),
            (AgentAct(name="ProvideHint", params={
                "case_details": {
                    "labs": {"CSF": "Gram-negative diplococci"}
                },
                "current_reasoning": "Uncertain about CSF interpretation"
            }),
             "Think about which common meningitis pathogen appears as gram-negative diplococci on microscopy. This morphology is quite characteristic."),
            (AgentAct(name="Finish", params={"response": "Think about which common meningitis pathogen appears as gram-negative diplococci on microscopy. This morphology is quite characteristic."}),
             "Task completed.")
        ]
        self.add_example(task5, action_chain5)

    def provide_help(self, case_details: Dict, conversation_history: list, revealed_info: set, differential_given: bool) -> str:
        """Provide contextual hints to the student."""
        action = ProvideHelpAction()
        result = action(
            case_details=case_details,
            conversation_history=conversation_history,
            revealed_info=revealed_info,
            differential_given=differential_given
        )
        return result.get("hint", "Consider what additional information would help narrow your differential diagnosis.")
    
    def grade_reasoning(self, case_details: Dict, conversation_history: list, differential_diagnosis: str, revealed_info: set) -> Dict:
        """Evaluate the quality of the student's clinical reasoning."""
        action = ClinicalReasoningGraderAction()
        result = action(
            case_details=case_details,
            conversation_history=conversation_history,
            differential_diagnosis=differential_diagnosis,
            revealed_info=revealed_info
        )
        return result.get("evaluation", {"overall_feedback": "Unable to evaluate clinical reasoning at this time."})
