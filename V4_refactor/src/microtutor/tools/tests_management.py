"""
TestsManagementTool - Tests and management agent following ToolUniverse AgenticTool pattern.
"""

import logging
from typing import Dict, Any, Optional

from microtutor.models.tool_models import AgenticTool
from microtutor.models.tool_errors import ToolLLMError
from microtutor.core.llm_router import chat_complete
from microtutor.tools.prompts import get_tests_management_system_prompt, get_tests_management_user_prompt
from microtutor.core.logging_config import log_agent_context
from microtutor.tools.mcq_tool import MCQTool

# Import ToolUniverse for real-time guideline search
try:
    from tooluniverse import ToolUniverse
    TOOLUNIVERSE_AVAILABLE = True
except ImportError:
    TOOLUNIVERSE_AVAILABLE = False
    ToolUniverse = None

# Import feedback integration
try:
    from microtutor.feedback import create_feedback_retriever, get_feedback_examples_for_tool, FEEDBACK_AVAILABLE
except ImportError:
    FEEDBACK_AVAILABLE = False
    def create_feedback_retriever(*args, **kwargs):
        return None
    def get_feedback_examples_for_tool(*args, **kwargs):
        return ""

logger = logging.getLogger(__name__)


class TestsManagementTool(AgenticTool):
    """Helps students select appropriate diagnostic tests and develop management plans."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize tests and management tool with optional feedback integration and ToolUniverse."""
        super().__init__(config)
        self.enable_feedback = config.get('enable_feedback', True) and FEEDBACK_AVAILABLE
        self.feedback_retriever = None
        self.interaction_counter = 0  # Track interaction count per tool instance
        
        # Initialize ToolUniverse for guideline search
        self.tooluniverse = None
        self.enable_guidelines = config.get('enable_guidelines', True) and TOOLUNIVERSE_AVAILABLE
        
        if self.enable_guidelines:
            try:
                self.tooluniverse = ToolUniverse()
                self.tooluniverse.load_tools()
                logger.info("Tests and management tool ToolUniverse integration enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize ToolUniverse: {e}")
                self.enable_guidelines = False
        
        # Initialize MCQ tool for generating questions
        self.mcq_tool = MCQTool(config)
        
        if self.enable_feedback:
            try:
                feedback_dir = config.get('feedback_dir', 'data/feedback')
                self.feedback_retriever = create_feedback_retriever(feedback_dir)
                logger.info("Tests and management tool feedback integration enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize tests and management feedback retriever: {e}")
                self.enable_feedback = False
    
    def _search_treatment_guidelines(self, organism: str, case_description: str) -> str:
        """
        Search for latest treatment guidelines using ToolUniverse.
        
        Args:
            organism: The microorganism name
            case_description: The case description
            
        Returns:
            str: Formatted guideline information
        """
        if not self.enable_guidelines or not self.tooluniverse:
            return ""
        
        try:
            guidelines_info = []
            
            # Search for treatment guidelines
            search_queries = [
                f"{organism} treatment guidelines",
                f"{organism} antimicrobial therapy",
                f"{organism} clinical management",
                f"{organism} infection treatment"
            ]
            
            for query in search_queries:
                try:
                    # Search PubMed for guidelines
                    papers_result = self.tooluniverse.run({
                        "name": "PubMed_search_articles",
                        "arguments": {
                            "query": query,
                            "limit": 3,
                            "sort": "relevance"
                        }
                    })
                    
                    # Handle different response formats from ToolUniverse
                    papers = []
                    if isinstance(papers_result, dict) and papers_result.get('success'):
                        papers = papers_result.get('result', [])
                    elif isinstance(papers_result, list):
                        papers = papers_result
                    
                    for paper in papers[:2]:  # Limit to top 2 papers per query
                        if isinstance(paper, dict):
                            title = paper.get('title', '')
                            abstract = paper.get('abstract', '')
                            if 'guideline' in title.lower() or 'treatment' in title.lower():
                                guidelines_info.append(f"**{title}**\n{abstract[:300]}...\n")
                    
                    # Search for clinical guidelines
                    guidelines_result = self.tooluniverse.run({
                        "name": "EuropePMC_Guidelines_Search",
                        "arguments": {
                            "query": query,
                            "limit": 2
                        }
                    })
                    
                    # Handle different response formats from ToolUniverse
                    guidelines = []
                    if isinstance(guidelines_result, dict) and guidelines_result.get('success'):
                        guidelines = guidelines_result.get('result', [])
                    elif isinstance(guidelines_result, list):
                        guidelines = guidelines_result
                    
                    for guideline in guidelines[:2]:
                        if isinstance(guideline, dict):
                            title = guideline.get('title', '')
                            abstract = guideline.get('abstract', '')
                            guidelines_info.append(f"**Guideline: {title}**\n{abstract[:300]}...\n")
                            
                except Exception as e:
                    logger.warning(f"Error searching guidelines for query '{query}': {e}")
                    continue
            
            if guidelines_info:
                return f"\n\n=== LATEST TREATMENT GUIDELINES ===\n{''.join(guidelines_info[:4])}\n"
            else:
                return "\n\n=== GUIDELINE SEARCH ===\nNo recent guidelines found. Please consult current medical literature and institutional protocols.\n"
                
        except Exception as e:
            logger.error(f"Error in guideline search: {e}")
            return "\n\n=== GUIDELINE SEARCH ===\nUnable to retrieve current guidelines. Please consult current medical literature.\n"
    
    def _extract_organism_from_case(self, case_description: str) -> Optional[str]:
        """
        Extract organism name from case description for guideline search.
        
        Args:
            case_description: The case description
            
        Returns:
            str: Extracted organism name or None
        """
        if not case_description:
            return None
        
        # Common organism patterns to look for
        organism_patterns = [
            r'(\w+\s+\w+)\s+(?:infection|pneumonia|sepsis|bacteremia)',
            r'(?:caused by|due to|organism:)\s+(\w+\s+\w+)',
            r'(\w+\s+\w+)\s+(?:is|was)\s+(?:isolated|identified|found)',
            r'(?:gram\s+[+-]\s+)?(\w+\s+\w+)',
        ]
        
        import re
        case_lower = case_description.lower()
        
        for pattern in organism_patterns:
            match = re.search(pattern, case_lower)
            if match:
                organism = match.group(1).strip()
                # Filter out common false positives
                if organism not in ['patient has', 'case involves', 'clinical presentation']:
                    return organism
        
        return None
    
    def _should_generate_mcq(self, input_text: str) -> tuple[bool, str]:
        """
        Determine if the input suggests generating an MCQ and extract the topic.
        
        Args:
            input_text: The student's input
            
        Returns:
            tuple: (should_generate, topic) where should_generate is bool and topic is str
        """
        input_lower = input_text.lower()
        
        # Keywords that suggest MCQ generation
        mcq_keywords = [
            'generate a question', 'create a question', 'test me', 'quiz me',
            'multiple choice', 'mcq', 'question about', 'ask me about',
            'what would you ask', 'test my knowledge', 'check my understanding'
        ]
        
        # Check if any MCQ keywords are present
        for keyword in mcq_keywords:
            if keyword in input_lower:
                # Try to extract topic from the input
                topic = self._extract_topic_from_input(input_text)
                return True, topic
        
        return False, ""
    
    def _extract_topic_from_input(self, input_text: str) -> str:
        """
        Extract medical topic from input text for MCQ generation.
        
        Args:
            input_text: The student's input
            
        Returns:
            str: Extracted topic or default topic
        """
        # Common medical topics to look for
        topic_patterns = [
            r'(?:about|on|regarding)\s+([^?]+)',
            r'question\s+(?:about|on|regarding)\s+([^?]+)',
            r'test\s+(?:my\s+)?(?:knowledge\s+)?(?:about|on|regarding)\s+([^?]+)',
            r'ask\s+(?:me\s+)?(?:about|on|regarding)\s+([^?]+)',
        ]
        
        import re
        for pattern in topic_patterns:
            match = re.search(pattern, input_text.lower())
            if match:
                topic = match.group(1).strip()
                # Clean up the topic
                topic = re.sub(r'[?.,!]', '', topic)
                if len(topic) > 3:  # Ensure it's a meaningful topic
                    return topic
        
        # Default topics based on common medical areas
        if any(word in input_text.lower() for word in ['treatment', 'therapy', 'management']):
            return 'treatment guidelines'
        elif any(word in input_text.lower() for word in ['diagnosis', 'diagnostic', 'test']):
            return 'diagnostic approach'
        elif any(word in input_text.lower() for word in ['antibiotic', 'antimicrobial', 'drug']):
            return 'antimicrobial selection'
        elif any(word in input_text.lower() for word in ['infection', 'pathogen', 'organism']):
            return 'infectious disease management'
        else:
            return 'clinical guidelines'
    
    def _analyze_learning_focus(self, conversation_history: list, topic: str) -> Dict[str, Any]:
        """
        Analyze conversation history using LLM to determine learning focus and gaps.
        
        Args:
            conversation_history: Previous conversation messages
            topic: Current topic being discussed
            
        Returns:
            Dict containing learning focus analysis
        """
        if not conversation_history:
            return {
                "focus_areas": ["clinical_decision_making"],
                "knowledge_gaps": [],
                "difficulty_level": "intermediate",
                "recent_questions": [],
                "struggling_areas": []
            }
        
        # Prepare conversation context for LLM analysis
        conversation_text = "\n".join([
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" 
            for msg in conversation_history[-15:]  # Last 15 messages for context
        ])
        
        # Create LLM prompt for learning analysis
        analysis_prompt = f"""You are an expert medical educator analyzing a student's learning needs from their conversation history.

CONVERSATION HISTORY:
{conversation_text}

TOPIC: {topic}

Analyze this conversation to determine:
1. What learning focus areas the student needs (clinical_decision_making, pathophysiology, prioritization, diagnostic_approach, treatment_planning, etc.)
2. What knowledge gaps they have (conceptual_understanding, clinical_reasoning, factual_knowledge, complex_reasoning, etc.)
3. What difficulty level is appropriate (beginner, intermediate, advanced)
4. What specific questions they've been asking
5. What areas they seem to be struggling with

Return your analysis as a JSON object with this exact structure:
{{
    "focus_areas": ["area1", "area2"],
    "knowledge_gaps": ["gap1", "gap2"],
    "difficulty_level": "beginner|intermediate|advanced",
    "recent_questions": ["question1", "question2"],
    "struggling_areas": ["area1", "area2"],
    "reasoning": "Brief explanation of your analysis"
}}

Focus on identifying what the student specifically needs to learn about {topic} based on their conversation patterns, questions, and any struggles they've expressed."""

        try:
            # Call LLM for analysis
            response = chat_complete(
                system_prompt="You are an expert medical educator who analyzes student learning patterns and needs.",
                user_prompt=analysis_prompt,
                model=self.llm_config.get('model', 'gpt-4')
            )
            
            # Parse JSON response
            import json
            analysis = json.loads(response)
            
            # Validate and clean the response
            return {
                "focus_areas": analysis.get("focus_areas", ["clinical_decision_making"]),
                "knowledge_gaps": analysis.get("knowledge_gaps", []),
                "difficulty_level": analysis.get("difficulty_level", "intermediate"),
                "recent_questions": analysis.get("recent_questions", []),
                "struggling_areas": analysis.get("struggling_areas", []),
                "reasoning": analysis.get("reasoning", "")
            }
            
        except Exception as e:
            logger.warning(f"Failed to analyze learning focus with LLM: {e}")
            # Fallback to basic analysis
            return {
                "focus_areas": ["clinical_decision_making"],
                "knowledge_gaps": [],
                "difficulty_level": "intermediate",
                "recent_questions": [],
                "struggling_areas": []
            }
    
    def _call_llm(self, prompt: str, **kwargs) -> str:
        """Call LLM to generate tests and management guidance."""
        try:
            model = kwargs.get('model', self.llm_config.get('model', 'gpt-4'))
            case = kwargs.get('case', '')
            input_text = kwargs.get('input_text', '')
            conversation_history = kwargs.get('conversation_history', [])
            
            # Get feedback examples if available
            feedback_examples = ""
            if self.enable_feedback and self.feedback_retriever:
                try:
                    feedback_examples = get_feedback_examples_for_tool(
                        user_input=input_text,
                        conversation_history=conversation_history,
                        tool_name="tests_management",
                        feedback_retriever=self.feedback_retriever
                    )
                except Exception as e:
                    logger.warning(f"Failed to get feedback examples: {e}")
            
            # Search for treatment guidelines
            organism = self._extract_organism_from_case(case)
            guidelines_info = ""
            if organism:
                guidelines_info = self._search_treatment_guidelines(organism, case)
            
            # Build system prompt with feedback and guidelines
            system_prompt = get_tests_management_system_prompt()
            if feedback_examples:
                system_prompt += f"\n\n=== EXPERT FEEDBACK EXAMPLES ===\n{feedback_examples}"
            
            if guidelines_info:
                system_prompt += f"\n\n=== CURRENT GUIDELINES INTEGRATION ===\nWhen providing treatment recommendations, reference and incorporate the latest treatment guidelines provided below. Use this information to give evidence-based, up-to-date guidance.\n{guidelines_info}"
            
            # Build user prompt
            user_prompt = f"""Case: {case}

Student's question/input: {input_text}

{get_tests_management_user_prompt()}"""
            
            # Log agent context
            log_agent_context(
                case_id="tests_management_test",
                agent_name="tests_management",
                interaction_id=self.interaction_counter,
                system_prompt=system_prompt[:200] + "..." if len(system_prompt) > 200 else system_prompt,
                user_prompt=user_prompt[:200] + "..." if len(user_prompt) > 200 else user_prompt,
                feedback_examples=feedback_examples,
                full_context=case[:100] + "..." if len(case) > 100 else case,
                metadata={
                    "feedback_included": bool(feedback_examples),
                    "guidelines_included": bool(guidelines_info)
                }
            )
            
            # Call LLM
            response = chat_complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
                conversation_history=conversation_history
            )
            
            if not response:
                raise ToolLLMError("Empty response from LLM")
            
            self.interaction_counter += 1
            return response
            
        except Exception as e:
            logger.error(f"Tests and management tool LLM call failed: {e}")
            raise ToolLLMError(f"LLM call failed: {e}")
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute tests and management tool."""
        try:
            # Validate required parameters
            if 'input_text' not in kwargs:
                raise ValueError("Missing required parameter: input_text")
            if 'case' not in kwargs:
                raise ValueError("Missing required parameter: case")
            
            input_text = kwargs['input_text']
            case = kwargs['case']
            
            # Check if student wants to generate an MCQ
            should_generate_mcq, topic = self._should_generate_mcq(input_text)
            
            if should_generate_mcq:
                # Generate MCQ instead of regular response
                try:
                    # Analyze conversation for learning focus
                    learning_focus = self._analyze_learning_focus(kwargs.get('conversation_history', []), topic)
                    
                    mcq_result = self.mcq_tool.execute(
                        topic=topic,
                        case=case,
                        difficulty=kwargs.get('difficulty', 'intermediate'),
                        session_id=kwargs.get('session_id'),
                        conversation_history=kwargs.get('conversation_history', []),
                        learning_focus=learning_focus
                    )
                    
                    if mcq_result['success']:
                        return {
                            "success": True,
                            "result": mcq_result['result'],
                            "mcq_data": mcq_result.get('mcq_data'),
                            "metadata": {
                                "agent": "tests_management",
                                "interaction_count": self.interaction_counter,
                                "feedback_enabled": self.enable_feedback,
                                "guidelines_enabled": self.enable_guidelines,
                                "mcq_generated": True,
                                "topic": topic
                            }
                        }
                    else:
                        # Fall back to regular response if MCQ generation fails
                        logger.warning(f"MCQ generation failed, falling back to regular response: {mcq_result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    logger.warning(f"MCQ generation failed, falling back to regular response: {e}")
                    # Fall through to regular response
            
            # Regular tests and management response
            # Check if guidelines were searched
            guidelines_searched = False
            if self.enable_guidelines and 'case' in kwargs:
                organism = self._extract_organism_from_case(kwargs['case'])
                if organism:
                    guidelines_searched = True
            
            # Call LLM
            response = self._call_llm("", **kwargs)
            
            return {
                "success": True,
                "result": response,
                "metadata": {
                    "agent": "tests_management",
                    "interaction_count": self.interaction_counter,
                    "feedback_enabled": self.enable_feedback,
                    "guidelines_enabled": self.enable_guidelines,
                    "guidelines_searched": guidelines_searched,
                    "mcq_generated": False
                }
            }
            
        except Exception as e:
            logger.error(f"Tests and management tool execution failed: {e}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }


# Legacy function wrapper for backward compatibility
def run_tests_management(input_text: str, case: str, conversation_history: list = None, model: str = None) -> str:
    """Legacy function wrapper for tests and management tool."""
    try:
        # Create tool instance with default config
        config = {
            "name": "tests_management",
            "description": "Helps students select appropriate diagnostic tests and develop management plans",
            "type": "AgenticTool",
            "enable_feedback": True
        }
        
        tool = TestsManagementTool(config)
        result = tool.execute(
            input_text=input_text,
            case=case,
            conversation_history=conversation_history or [],
            model=model
        )
        
        if result["success"]:
            return result["result"]
        else:
            return "I apologize, but I'm having trouble helping with tests and management right now. Could you please try again?"
            
    except Exception as e:
        logger.error(f"Legacy tests and management function failed: {e}")
        return "I apologize, but I'm having trouble helping with tests and management right now. Could you please try again?"
