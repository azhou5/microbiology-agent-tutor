"""
MCQ Tool for MicroTutor V4

Tool for generating and managing multiple choice questions based on clinical guidelines.
Integrates with the tests_and_management agent to provide MCQ-based learning.
"""

import logging
from typing import Dict, Any, Optional
import asyncio

from microtutor.models.tool_models import AgenticTool
from microtutor.models.tool_errors import ToolLLMError
from microtutor.services.mcq_service import MCQService
from microtutor.core.logging_config import log_agent_context

logger = logging.getLogger(__name__)


class MCQTool(AgenticTool):
    """Tool for generating MCQs based on clinical guidelines and case context."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize MCQ tool with MCQ service."""
        super().__init__(config)
        self.mcq_service = MCQService(config)
        self.interaction_counter = 0
    
    def _call_llm(self, prompt: str, **kwargs) -> str:
        """MCQ tool doesn't use LLM directly - delegates to MCQ service."""
        # This method is required by AgenticTool but not used
        return ""
    
    def _generate_mcq_prompt(self, topic: str, case_context: str = None, difficulty: str = "intermediate") -> str:
        """
        Generate a prompt for MCQ generation based on topic and case context.
        
        Args:
            topic: Medical topic for the question
            case_context: Optional case context
            difficulty: Question difficulty level
            
        Returns:
            str: Formatted prompt for MCQ generation
        """
        prompt = f"""Based on the current case and clinical guidelines, I'd like to generate a multiple choice question to test your understanding of {topic}.

CASE CONTEXT:
{case_context if case_context else "General clinical scenario"}

TOPIC: {topic}
DIFFICULTY: {difficulty}

This will help reinforce your learning through evidence-based questions derived from current treatment guidelines."""
        
        return prompt
    
    def _format_mcq_for_display(self, mcq) -> str:
        """
        Format MCQ for display in the chat interface.
        
        Args:
            mcq: MCQ object to format
            
        Returns:
            str: Formatted MCQ for display
        """
        if not mcq:
            return "I apologize, but I couldn't generate a question at this time."
        
        formatted = f"""**Question: {mcq.question_text}**

"""
        
        for option in mcq.options:
            formatted += f"{option.letter.upper()}) {option.text}\n"
        
        formatted += f"""
**Instructions:** Click on your answer choice (a, b, c, or d) to submit your response.

*This question is based on current clinical guidelines for {mcq.topic}.*"""
        
        return formatted
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute MCQ tool to generate questions based on guidelines."""
        try:
            # Validate required parameters
            if 'topic' not in kwargs:
                raise ValueError("Missing required parameter: topic")
            
            topic = kwargs['topic']
            case_context = kwargs.get('case', '')
            difficulty = kwargs.get('difficulty', 'intermediate')
            session_id = kwargs.get('session_id')
            
            # Generate MCQ using the service
            try:
                # Get additional context for personalized MCQ generation
                conversation_history = kwargs.get('conversation_history', [])
                learning_focus = kwargs.get('learning_focus', {})
                
                # Use thread pool to run async function from sync context
                import concurrent.futures
                import threading
                
                def run_async_in_thread():
                    # Create new event loop in thread
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        return loop.run_until_complete(
                            self.mcq_service.generate_mcq(
                                topic=topic,
                                case_context=case_context,
                                difficulty=difficulty,
                                session_id=session_id,
                                conversation_history=conversation_history,
                                learning_focus=learning_focus
                            )
                        )
                    finally:
                        loop.close()
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_async_in_thread)
                    mcq = future.result(timeout=30)  # 30 second timeout
            except Exception as e:
                logger.error(f"Failed to generate MCQ: {e}")
                return {
                    "success": False,
                    "error": {
                        "type": "MCQGenerationError",
                        "message": f"Failed to generate MCQ: {str(e)}"
                    }
                }
            
            # Format MCQ for display
            formatted_mcq = self._format_mcq_for_display(mcq)
            
            # Log interaction
            log_agent_context(
                case_id=session_id or "mcq_test",
                agent_name="mcq_tool",
                interaction_id=self.interaction_counter,
                system_prompt="MCQ Generation",
                user_prompt=f"Generate MCQ for topic: {topic}",
                feedback_examples="",
                full_context=case_context[:100] + "..." if len(case_context) > 100 else case_context,
                metadata={"guidelines_included": True}
            )
            
            self.interaction_counter += 1
            
            return {
                "success": True,
                "result": formatted_mcq,
                "mcq_data": {
                    "question_id": mcq.question_id,
                    "question_text": mcq.question_text,
                    "options": [
                        {
                            "letter": opt.letter,
                            "text": opt.text,
                            "is_correct": opt.is_correct
                        } for opt in mcq.options
                    ],
                    "correct_answer": mcq.correct_answer,
                    "explanation": mcq.explanation,
                    "topic": mcq.topic,
                    "difficulty": mcq.difficulty,
                    "source_guidelines": mcq.source_guidelines
                },
                "metadata": {
                    "agent": "mcq_tool",
                    "interaction_count": self.interaction_counter,
                    "topic": topic,
                    "difficulty": difficulty,
                    "guidelines_based": True
                }
            }
            
        except Exception as e:
            logger.error(f"MCQ tool execution failed: {e}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
    
    def process_response(self, mcq_data: Dict[str, Any], selected_answer: str, session_id: str = None) -> Dict[str, Any]:
        """
        Process a student's response to an MCQ.
        
        Args:
            mcq_data: The MCQ data from a previous generation
            selected_answer: The letter of the selected answer
            session_id: Optional session ID
            
        Returns:
            Dict containing feedback on the response
        """
        try:
            # Reconstruct MCQ object from data
            from microtutor.models.domain import MCQ, MCQOption
            
            options = [
                MCQOption(
                    letter=opt['letter'],
                    text=opt['text'],
                    is_correct=opt['is_correct']
                ) for opt in mcq_data['options']
            ]
            
            mcq = MCQ(
                question_id=mcq_data['question_id'],
                question_text=mcq_data['question_text'],
                options=options,
                correct_answer=mcq_data['correct_answer'],
                explanation=mcq_data['explanation'],
                topic=mcq_data['topic'],
                difficulty=mcq_data['difficulty'],
                source_guidelines=mcq_data.get('source_guidelines', [])
            )
            
            # Process the response
            feedback = self.mcq_service.process_mcq_response(mcq, selected_answer, session_id)
            
            # Format feedback for display
            feedback_text = f"""**Your Answer: {selected_answer.upper()}**

{feedback.explanation}

{feedback.additional_guidance}

{feedback.next_question_suggestion}"""
            
            return {
                "success": True,
                "result": feedback_text,
                "is_correct": feedback.is_correct,
                "feedback": {
                    "question_id": feedback.question_id,
                    "is_correct": feedback.is_correct,
                    "explanation": feedback.explanation,
                    "additional_guidance": feedback.additional_guidance,
                    "next_question_suggestion": feedback.next_question_suggestion
                },
                "metadata": {
                    "agent": "mcq_tool",
                    "response_processed": True,
                    "correct": feedback.is_correct
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to process MCQ response: {e}")
            return {
                "success": False,
                "error": {
                    "type": "MCQResponseError",
                    "message": f"Failed to process response: {str(e)}"
                }
            }


# Legacy function wrapper for backward compatibility
def run_mcq_tool(topic: str, case: str = None, difficulty: str = "intermediate", session_id: str = None) -> str:
    """Legacy function wrapper for MCQ tool."""
    try:
        # Create tool instance with default config
        config = {
            "name": "mcq_tool",
            "description": "Generates MCQs based on clinical guidelines",
            "type": "AgenticTool",
            "enable_guidelines": True
        }
        
        tool = MCQTool(config)
        result = tool.execute(
            topic=topic,
            case=case,
            difficulty=difficulty,
            session_id=session_id
        )
        
        if result["success"]:
            return result["result"]
        else:
            return "I apologize, but I'm having trouble generating a question right now. Could you please try again?"
            
    except Exception as e:
        logger.error(f"Legacy MCQ tool function failed: {e}")
        return "I apologize, but I'm having trouble generating a question right now. Could you please try again?"
