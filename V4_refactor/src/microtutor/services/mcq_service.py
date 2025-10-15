"""
MCQ Generation Service for MicroTutor V4

Generates multiple choice questions based on clinical guidelines and case context.
Integrates with ToolUniverse for real-time guideline access.
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from microtutor.models.domain import MCQ, MCQOption, MCQResponse, MCQFeedback
from microtutor.core.llm_router import chat_complete
from microtutor.core.logging_config import log_agent_context

# Import ToolUniverse for guideline search
try:
    from tooluniverse import ToolUniverse
    TOOLUNIVERSE_AVAILABLE = True
except ImportError:
    TOOLUNIVERSE_AVAILABLE = False
    ToolUniverse = None

logger = logging.getLogger(__name__)


class MCQService:
    """Service for generating and managing MCQs based on clinical guidelines."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize MCQ service with optional ToolUniverse integration."""
        self.config = config or {}
        self.enable_guidelines = self.config.get('enable_guidelines', True) and TOOLUNIVERSE_AVAILABLE
        self.tooluniverse = None
        
        if self.enable_guidelines:
            try:
                self.tooluniverse = ToolUniverse()
                self.tooluniverse.load_tools()
                logger.info("MCQ service ToolUniverse integration enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize ToolUniverse for MCQ service: {e}")
                self.enable_guidelines = False
    
    def _search_guidelines_for_topic(self, topic: str, case_context: str = None, conversation_history: list = None) -> str:
        """
        Search for guidelines related to a specific topic, tailored to the case and conversation.
        
        Args:
            topic: The medical topic to search for
            case_context: Patient case context for targeted search
            conversation_history: Previous conversation to understand learning needs
            
        Returns:
            str: Formatted guideline information
        """
        if not self.enable_guidelines or not self.tooluniverse:
            return ""
        
        try:
            guidelines_info = []
            
            # Extract key clinical details from case context
            clinical_details = self._extract_clinical_details(case_context)
            
            # Extract learning gaps from conversation history
            learning_focus = self._extract_learning_focus(conversation_history, topic)
            
            # Build highly targeted search queries
            search_queries = self._build_targeted_queries(topic, clinical_details, learning_focus)
            
            for query in search_queries:
                try:
                    # Search PubMed for guidelines
                    papers_result = self.tooluniverse.run({
                        "name": "PubMed_search_articles",
                        "arguments": {
                            "query": query,
                            "limit": 2,
                            "sort": "relevance"
                        }
                    })
                    
                    # Handle different response formats from ToolUniverse
                    papers = []
                    if isinstance(papers_result, dict) and papers_result.get('success'):
                        papers = papers_result.get('result', [])
                    elif isinstance(papers_result, list):
                        papers = papers_result
                    
                    for paper in papers[:1]:  # Limit to top paper per query
                        if isinstance(paper, dict):
                            title = paper.get('title', '')
                            abstract = paper.get('abstract', '')
                            if 'guideline' in title.lower() or 'recommendation' in title.lower():
                                guidelines_info.append(f"**{title}**\n{abstract[:200]}...\n")
                    
                    # Search for clinical guidelines
                    guidelines_result = self.tooluniverse.run({
                        "name": "EuropePMC_Guidelines_Search",
                        "arguments": {
                            "query": query,
                            "limit": 1
                        }
                    })
                    
                    # Handle different response formats from ToolUniverse
                    guidelines = []
                    if isinstance(guidelines_result, dict) and guidelines_result.get('success'):
                        guidelines = guidelines_result.get('result', [])
                    elif isinstance(guidelines_result, list):
                        guidelines = guidelines_result
                    
                    for guideline in guidelines[:1]:
                        if isinstance(guideline, dict):
                            title = guideline.get('title', '')
                            abstract = guideline.get('abstract', '')
                            guidelines_info.append(f"**Guideline: {title}**\n{abstract[:200]}...\n")
                            
                except Exception as e:
                    logger.warning(f"Error searching guidelines for query '{query}': {e}")
                    continue
            
            if guidelines_info:
                return f"\n\n=== RELEVANT GUIDELINES ===\n{''.join(guidelines_info[:3])}\n"
            else:
                return ""
                
        except Exception as e:
            logger.error(f"Error in guideline search for MCQ generation: {e}")
            return ""
    
    def _extract_clinical_details(self, case_context: str) -> Dict[str, Any]:
        """
        Extract key clinical details from case context using LLM analysis.
        
        Args:
            case_context: Patient case description
            
        Returns:
            Dict containing extracted clinical details
        """
        if not case_context:
            return {}
        
        # Use LLM to extract clinical details
        analysis_prompt = f"""You are an expert clinician analyzing a patient case to extract key clinical details for targeted guideline search.

CASE CONTEXT:
{case_context}

Extract the following clinical details and return as JSON:
{{
    "age_group": "neonate|pediatric|adult|elderly",
    "setting": "icu|inpatient|outpatient|emergency",
    "severity": "mild|moderate|severe",
    "comorbidities": ["list", "of", "comorbidities"],
    "symptoms": ["list", "of", "symptoms"],
    "vital_signs": ["list", "of", "vital", "signs"],
    "lab_findings": ["list", "of", "lab", "findings"],
    "imaging": ["list", "of", "imaging", "findings"],
    "key_clinical_factors": ["most", "important", "clinical", "factors"]
}}

Focus on details that would be most relevant for guideline search and MCQ generation."""

        try:
            from microtutor.core.llm_router import chat_complete
            response = chat_complete(
                system_prompt="You are an expert clinician who extracts key clinical details from patient cases.",
                user_prompt=analysis_prompt,
                model=self.config.get('model', 'gpt-4')
            )
            
            import json
            details = json.loads(response)
            return details
            
        except Exception as e:
            logger.warning(f"Failed to extract clinical details with LLM: {e}")
            return {}
    
    def _extract_learning_focus(self, conversation_history: list, topic: str) -> Dict[str, Any]:
        """
        Extract learning focus and gaps from conversation history.
        
        Args:
            conversation_history: Previous conversation messages
            topic: Current topic being discussed
            
        Returns:
            Dict containing learning focus areas
        """
        if not conversation_history:
            return {"focus_areas": [], "knowledge_gaps": [], "difficulty_level": "intermediate"}
        
        focus_areas = []
        knowledge_gaps = []
        difficulty_level = "intermediate"
        
        # Analyze conversation for learning patterns
        for message in conversation_history:
            content = message.get("content", "").lower()
            role = message.get("role", "")
            
            if role == "user":
                # Look for questions or uncertainties
                if any(phrase in content for phrase in ["don't know", "unsure", "confused", "not sure"]):
                    knowledge_gaps.append("conceptual_understanding")
                
                if any(phrase in content for phrase in ["what should", "how do i", "which is better"]):
                    focus_areas.append("clinical_decision_making")
                
                if any(phrase in content for phrase in ["why", "explain", "reasoning"]):
                    focus_areas.append("pathophysiology")
                
                if any(phrase in content for phrase in ["first", "next step", "immediate"]):
                    focus_areas.append("prioritization")
            
            elif role == "assistant":
                # Look for areas where student struggled
                if any(phrase in content for phrase in ["incorrect", "not quite", "consider"]):
                    knowledge_gaps.append("clinical_reasoning")
        
        # Determine difficulty based on conversation complexity
        if any(area in focus_areas for area in ["pathophysiology", "complex_management"]):
            difficulty_level = "advanced"
        elif any(gap in knowledge_gaps for gap in ["basic_concepts", "fundamental_principles"]):
            difficulty_level = "beginner"
        
        return {
            "focus_areas": list(set(focus_areas)),
            "knowledge_gaps": list(set(knowledge_gaps)),
            "difficulty_level": difficulty_level
        }
    
    def _build_targeted_queries(self, topic: str, clinical_details: Dict[str, Any], learning_focus: Dict[str, Any]) -> List[str]:
        """
        Build highly targeted search queries based on case and learning needs.
        
        Args:
            topic: Medical topic
            clinical_details: Extracted clinical details
            learning_focus: Learning focus areas
            
        Returns:
            List of targeted search queries
        """
        queries = []
        
        # Base topic queries
        queries.append(f"{topic} guidelines")
        
        # Add age-specific queries
        if clinical_details.get("age_group"):
            age_group = clinical_details["age_group"]
            queries.append(f"{topic} {age_group} guidelines")
            queries.append(f"{topic} {age_group} management")
        
        # Add setting-specific queries
        if clinical_details.get("setting"):
            setting = clinical_details["setting"]
            queries.append(f"{topic} {setting} guidelines")
            queries.append(f"{topic} {setting} management")
        
        # Add severity-specific queries
        if clinical_details.get("severity"):
            severity = clinical_details["severity"]
            queries.append(f"{topic} {severity} guidelines")
            queries.append(f"{topic} {severity} management")
        
        # Add comorbidity-specific queries
        for comorbidity in clinical_details.get("comorbidities", []):
            queries.append(f"{topic} {comorbidity} guidelines")
            queries.append(f"{topic} {comorbidity} management")
        
        # Add learning focus queries
        for focus_area in learning_focus.get("focus_areas", []):
            if focus_area == "clinical_decision_making":
                queries.append(f"{topic} clinical decision making guidelines")
            elif focus_area == "pathophysiology":
                queries.append(f"{topic} pathophysiology guidelines")
            elif focus_area == "prioritization":
                queries.append(f"{topic} treatment prioritization guidelines")
        
        # Add knowledge gap queries
        for gap in learning_focus.get("knowledge_gaps", []):
            if gap == "conceptual_understanding":
                queries.append(f"{topic} basic principles guidelines")
            elif gap == "clinical_reasoning":
                queries.append(f"{topic} clinical reasoning guidelines")
        
        # Add symptom-specific queries
        for symptom in clinical_details.get("symptoms", []):
            queries.append(f"{topic} {symptom} guidelines")
        
        # Remove duplicates and limit to most relevant
        unique_queries = list(dict.fromkeys(queries))  # Preserve order while removing duplicates
        return unique_queries[:8]  # Limit to 8 most targeted queries
    
    def _generate_mcq_with_llm(
        self, 
        topic: str, 
        case_context: str = None, 
        difficulty: str = "intermediate",
        guidelines_info: str = "",
        conversation_history: list = None,
        learning_focus: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Generate personalized MCQ using LLM based on topic, guidelines, and learning needs.
        
        Args:
            topic: Medical topic for the question
            case_context: Patient case context
            difficulty: Question difficulty level
            guidelines_info: Guidelines information to base question on
            conversation_history: Previous conversation for context
            learning_focus: Analysis of student's learning needs
            
        Returns:
            Dict containing the generated MCQ data
        """
        # Prepare conversation context
        conversation_text = ""
        if conversation_history:
            conversation_text = "\n".join([
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" 
                for msg in conversation_history[-10:]  # Last 10 messages
            ])
        
        # Prepare learning focus context
        focus_context = ""
        if learning_focus:
            focus_areas = learning_focus.get('focus_areas', [])
            knowledge_gaps = learning_focus.get('knowledge_gaps', [])
            struggling_areas = learning_focus.get('struggling_areas', [])
            recent_questions = learning_focus.get('recent_questions', [])
            
            focus_context = f"""
LEARNING FOCUS ANALYSIS:
- Focus Areas: {', '.join(focus_areas) if focus_areas else 'General clinical decision making'}
- Knowledge Gaps: {', '.join(knowledge_gaps) if knowledge_gaps else 'None identified'}
- Struggling Areas: {', '.join(struggling_areas) if struggling_areas else 'None identified'}
- Recent Questions: {'; '.join(recent_questions) if recent_questions else 'None'}
- Difficulty Level: {learning_focus.get('difficulty_level', difficulty)}
"""

        system_prompt = f"""You are an expert medical educator creating personalized multiple choice questions based on clinical guidelines and student learning needs.

TASK: Generate a single, well-crafted MCQ that tests understanding of {topic} while addressing the student's specific learning needs.

QUESTION REQUIREMENTS:
- Base the question on current clinical guidelines and evidence-based practice
- Make it clinically relevant and practical to the specific case
- Test understanding, not just memorization
- Use clear, unambiguous language
- Ensure only one correct answer
- Make distractors plausible but clearly incorrect
- Target the student's identified learning gaps and focus areas
- Match the appropriate difficulty level for this student

FORMAT: Return a JSON object with this exact structure:
{{
    "question_text": "Clear, specific question about {topic} that addresses the student's learning needs",
    "options": [
        {{"letter": "a", "text": "First option", "is_correct": false}},
        {{"letter": "b", "text": "Second option", "is_correct": false}},
        {{"letter": "c", "text": "Third option", "is_correct": true}},
        {{"letter": "d", "text": "Fourth option", "is_correct": false}}
    ],
    "correct_answer": "c",
    "explanation": "Detailed explanation of why the correct answer is right and others are wrong, tailored to address the student's learning gaps",
    "topic": "{topic}",
    "difficulty": "{difficulty}"
}}

GUIDELINES TO REFERENCE:
{guidelines_info if guidelines_info else "Use current medical literature and evidence-based practices."}

CASE CONTEXT:
{case_context if case_context else "General clinical scenario"}

{focus_context}

CONVERSATION CONTEXT:
{conversation_text if conversation_text else "No previous conversation context"}

Focus on creating a question that will help this specific student learn and address their identified knowledge gaps while being clinically relevant to their case."""

        user_prompt = f"""Generate a personalized MCQ about {topic} that addresses this student's specific learning needs and is appropriate for their current understanding level. The question should be clinically relevant to their case and help them learn the areas they need to focus on."""

        try:
            response = chat_complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=self.config.get('model', 'gpt-4')
            )
            
            # Parse JSON response
            import json
            mcq_data = json.loads(response)
            
            # Validate required fields
            required_fields = ['question_text', 'options', 'correct_answer', 'explanation', 'topic']
            for field in required_fields:
                if field not in mcq_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate options
            if len(mcq_data['options']) != 4:
                raise ValueError("Must have exactly 4 options")
            
            # Ensure correct answer is marked
            correct_answer = mcq_data['correct_answer']
            for option in mcq_data['options']:
                if option['letter'] == correct_answer:
                    option['is_correct'] = True
                else:
                    option['is_correct'] = False
            
            return mcq_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse MCQ JSON response: {e}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")
        except Exception as e:
            logger.error(f"Error generating MCQ with LLM: {e}")
            raise
    
    async def generate_mcq(
        self, 
        topic: str, 
        case_context: str = None, 
        difficulty: str = "intermediate",
        session_id: str = None,
        conversation_history: list = None,
        learning_focus: Dict[str, Any] = None
    ) -> MCQ:
        """
        Generate a new MCQ based on topic and guidelines.
        
        Args:
            topic: Medical topic for the question
            case_context: Optional case context for more targeted questions
            difficulty: Question difficulty level
            session_id: Optional session ID for tracking
            
        Returns:
            MCQ: Generated multiple choice question
        """
        try:
            # Search for relevant guidelines
            guidelines_info = self._search_guidelines_for_topic(topic, case_context, conversation_history)
            
            # Generate MCQ using LLM
            mcq_data = self._generate_mcq_with_llm(
                topic=topic,
                case_context=case_context,
                difficulty=difficulty,
                guidelines_info=guidelines_info,
                conversation_history=conversation_history,
                learning_focus=learning_focus
            )
            
            # Create MCQ object
            question_id = str(uuid.uuid4())
            
            # Convert options to MCQOption objects
            options = []
            for opt_data in mcq_data['options']:
                option = MCQOption(
                    letter=opt_data['letter'],
                    text=opt_data['text'],
                    is_correct=opt_data['is_correct']
                )
                options.append(option)
            
            # Extract source guidelines from the guidelines_info
            source_guidelines = []
            if guidelines_info:
                # Simple extraction - could be improved
                lines = guidelines_info.split('\n')
                for line in lines:
                    if line.startswith('**') and line.endswith('**'):
                        source_guidelines.append(line.strip('*'))
            
            mcq = MCQ(
                question_id=question_id,
                question_text=mcq_data['question_text'],
                options=options,
                correct_answer=mcq_data['correct_answer'],
                explanation=mcq_data['explanation'],
                source_guidelines=source_guidelines,
                difficulty=difficulty,
                topic=topic,
                metadata={
                    'session_id': session_id,
                    'case_context': case_context,
                    'generated_at': datetime.now().isoformat()
                }
            )
            
            logger.info(f"Generated MCQ {question_id} for topic: {topic}")
            return mcq
            
        except Exception as e:
            logger.error(f"Failed to generate MCQ for topic {topic}: {e}")
            raise
    
    def process_mcq_response(self, mcq: MCQ, selected_answer: str, session_id: str = None) -> MCQFeedback:
        """
        Process a student's response to an MCQ and provide feedback.
        
        Args:
            mcq: The MCQ that was answered
            selected_answer: The letter of the selected answer
            session_id: Optional session ID
            
        Returns:
            MCQFeedback: Feedback on the response
        """
        try:
            is_correct = selected_answer.lower() == mcq.correct_answer.lower()
            
            # Generate additional guidance based on the response
            if is_correct:
                additional_guidance = "Excellent! You correctly identified the answer based on current guidelines."
                next_question_suggestion = f"Would you like to explore another aspect of {mcq.topic}?"
            else:
                additional_guidance = f"Not quite right. The correct answer is {mcq.correct_answer.upper()}. Review the explanation to understand why this is the best choice based on current guidelines."
                next_question_suggestion = f"Let's review the guidelines for {mcq.topic} and try a similar question."
            
            feedback = MCQFeedback(
                question_id=mcq.question_id,
                is_correct=is_correct,
                explanation=mcq.explanation,
                additional_guidance=additional_guidance,
                next_question_suggestion=next_question_suggestion
            )
            
            logger.info(f"Processed MCQ response for {mcq.question_id}: {'correct' if is_correct else 'incorrect'}")
            return feedback
            
        except Exception as e:
            logger.error(f"Failed to process MCQ response: {e}")
            raise
    
    def is_available(self) -> bool:
        """Check if MCQ service is available."""
        return True  # Service is always available, guidelines are optional
