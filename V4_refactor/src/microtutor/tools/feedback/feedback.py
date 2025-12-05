"""
FeedbackTool - Feedback agent following ToolUniverse AgenticTool pattern.
"""

import logging
from typing import Dict, Any

from microtutor.schemas.tools.tool_models import AgenticTool
from microtutor.schemas.tools.tool_errors import ToolLLMError
from microtutor.core.llm.llm_router import chat_complete
from microtutor.prompts.final_feedback_agent_prompts import get_feedback_system_prompt
from microtutor.core.logging.logging_config import log_agent_context

logger = logging.getLogger(__name__)


class FeedbackTool(AgenticTool):
    """Provides comprehensive feedback on student performance throughout the case.
    
    Note: Feedback examples are passed via conversation history from TutorService,
    not retrieved directly by this tool.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize feedback tool."""
        super().__init__(config)
        self.interaction_counter = 0
    
    def _call_llm(self, prompt: str, **kwargs) -> str:
        """Call LLM to generate comprehensive feedback."""
        try:
            model = kwargs.get('model', self.llm_config.get('model', 'gpt-4'))
            case = kwargs.get('case', '')
            input_text = kwargs.get('input_text', '')
            conversation_history = kwargs.get('conversation_history', [])
            
            # Get system prompt template and format with case
            system_prompt_template = get_feedback_system_prompt()
            system_prompt = system_prompt_template.format(case=case)
            
            # Use conversation_history which already includes feedback at the end
            # Feedback was added to the last user message in tutor_service_v2.py
            # Prepare messages with system prompt (includes case) + conversation history (which includes feedback)
            from microtutor.utils.conversation_utils import prepare_llm_messages
            llm_messages = prepare_llm_messages(conversation_history, system_prompt)
            
            # Check if feedback is in the conversation history (last user message)
            feedback_in_history = False
            if conversation_history:
                last_user_msg = next((msg for msg in reversed(conversation_history) if msg.get("role") == "user"), None)
                if last_user_msg and "\n\n" in last_user_msg.get("content", ""):
                    # Feedback is typically appended with "\n\n" separator
                    feedback_in_history = True
            
            # Log agent context
            log_agent_context(
                agent_name="feedback",
                interaction_count=self.interaction_counter,
                user_input=input_text,
                case_context=case[:100] + "..." if len(case) > 100 else case,
                feedback_included=feedback_in_history
            )
            
            # Call LLM with prepared messages (includes system prompt + feedback from conversation_history)
            # Note: system_prompt is already in llm_messages, so we don't pass it separately
            response = chat_complete(
                system_prompt="",  # Not used when conversation_history is provided
                user_prompt="",  # Not used when conversation_history is provided
                model=model,
                conversation_history=llm_messages  # Includes system prompt + history with feedback
            )
            
            if not response:
                raise ToolLLMError("Empty response from LLM")
            
            self.interaction_counter += 1
            return response
            
        except Exception as e:
            logger.error(f"Feedback tool LLM call failed: {e}")
            raise ToolLLMError(f"LLM call failed: {e}")
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute feedback tool."""
        try:
            # Validate required parameters
            if 'input_text' not in kwargs:
                raise ValueError("Missing required parameter: input_text")
            if 'case' not in kwargs:
                raise ValueError("Missing required parameter: case")
            
            # Call LLM
            response = self._call_llm("", **kwargs)
            
            return {
                "success": True,
                "result": response,
                "metadata": {
                    "agent": "feedback",
                    "interaction_count": self.interaction_counter
                }
            }
            
        except Exception as e:
            logger.error(f"Feedback tool execution failed: {e}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }


# Legacy function wrapper for backward compatibility
def run_feedback(input_text: str, case: str, conversation_history: list = None, model: str = None) -> str:
    """Legacy function wrapper for feedback tool."""
    try:
        # Create tool instance with default config
        config = {
            "name": "feedback",
            "description": "Provides comprehensive feedback on student performance throughout the case",
            "type": "AgenticTool",
            "enable_feedback": True
        }
        
        tool = FeedbackTool(config)
        result = tool.execute(
            input_text=input_text,
            case=case,
            conversation_history=conversation_history or [],
            model=model
        )
        
        if result["success"]:
            return result["result"]
        else:
            return "I apologize, but I'm having trouble providing feedback right now. Could you please try again?"
            
    except Exception as e:
        logger.error(f"Legacy feedback function failed: {e}")
        return "I apologize, but I'm having trouble providing feedback right now. Could you please try again?"
