"""
TestsManagementTool - Helps students select diagnostic tests and develop management plans.

This tool focuses on:
- Guiding test selection based on differential diagnosis
- Interpreting test results in clinical context
- Developing evidence-based management plans
- Applying antimicrobial stewardship principles

Note: MCQ generation is handled by the separate PostCaseAssessmentTool.
"""

import logging
from typing import Dict, Any

from microtutor.schemas.tools.tool_models import AgenticTool
from microtutor.schemas.tools.tool_errors import ToolLLMError
from microtutor.core.llm.llm_router import chat_complete
from microtutor.prompts.tests_management_prompts import get_tests_management_system_prompt
from microtutor.core.logging.logging_config import log_agent_context
from microtutor.utils.conversation_utils import prepare_llm_messages

logger = logging.getLogger(__name__)


class TestsManagementTool(AgenticTool):
    """Helps students select appropriate diagnostic tests and develop management plans.
    
    This tool receives:
    - Case description
    - Conversation history (includes feedback from TutorService)
    - Optional guidelines context (from database, not ToolUniverse)
    
    Note: Feedback examples are passed via conversation history from TutorService,
    not retrieved directly by this tool.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize tests and management tool."""
        super().__init__(config)
        self.interaction_counter = 0
    
    def _call_llm(self, prompt: str, **kwargs) -> str:
        """Call LLM to generate tests and management guidance."""
        try:
            model = kwargs.get('model', self.llm_config.get('model', 'gpt-4'))
            case = kwargs.get('case', '')
            input_text = kwargs.get('input_text', '')
            conversation_history = kwargs.get('conversation_history', [])
            
            # Debug: Log conversation history length
            logger.info(f"[TESTS_MGMT] Received {len(conversation_history)} messages in conversation history")
            if conversation_history:
                # Log last few messages to verify context
                for msg in conversation_history[-3:]:
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')[:100]
                    logger.info(f"[TESTS_MGMT] Recent msg - {role}: {content}...")
            
            # Get guidelines context if provided (from database/service)
            guidelines_context = kwargs.get("guidelines_context", "")
            
            # Get system prompt template and format with case
            system_prompt_template = get_tests_management_system_prompt()
            system_prompt = system_prompt_template.format(case=case)
            
            # Add guidelines if available
            if guidelines_context:
                system_prompt += f"\n\n=== CLINICAL GUIDELINES ===\n{guidelines_context}"
                logger.info("Using guidelines context from service")
            
            # Prepare messages with system prompt + conversation history (which includes feedback)
            llm_messages = prepare_llm_messages(conversation_history, system_prompt)
            
            # Check if feedback is in the conversation history
            feedback_in_history = False
            if conversation_history:
                last_user_msg = next(
                    (msg for msg in reversed(conversation_history) if msg.get("role") == "user"), 
                    None
                )
                if last_user_msg and "\n\n" in last_user_msg.get("content", ""):
                    feedback_in_history = True
            
            # Log agent context
            log_agent_context(
                case_id="tests_management",
                agent_name="tests_management",
                interaction_id=self.interaction_counter,
                system_prompt=system_prompt[:200] + "..." if len(system_prompt) > 200 else system_prompt,
                user_prompt=input_text,
                feedback_examples="[From conversation_history]" if feedback_in_history else "",
                full_context=llm_messages[-1].get("content", "") if llm_messages else input_text,
                metadata={
                    "feedback_from_history": feedback_in_history,
                    "guidelines_included": bool(guidelines_context)
                }
            )
            
            # Call LLM
            response = chat_complete(
                system_prompt="",  # Already in llm_messages
                user_prompt="",    # Already in llm_messages
                model=model,
                conversation_history=llm_messages
            )
            
            if not response:
                raise ToolLLMError("Empty response from LLM")
            
            self.interaction_counter += 1
            return response
            
        except Exception as e:
            logger.error(f"Tests and management tool LLM call failed: {e}")
            raise ToolLLMError(f"LLM call failed: {e}")
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute tests and management tool.
        
        Args:
            input_text: Student's message
            case: Case description
            conversation_history: Previous messages (includes feedback)
            model: LLM model to use
            guidelines_context: Optional guidelines from database
            
        Returns:
            Dict with success status, result, and metadata
        """
        try:
            # Validate required parameters
            if 'input_text' not in kwargs:
                raise ValueError("Missing required parameter: input_text")
            if 'case' not in kwargs:
                raise ValueError("Missing required parameter: case")
            
            # Call LLM for guidance
            response = self._call_llm("", **kwargs)
            
            return {
                "success": True,
                "result": response,
                "metadata": {
                    "agent": "tests_management",
                    "interaction_count": self.interaction_counter,
                    "guidelines_included": bool(kwargs.get("guidelines_context"))
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
def run_tests_management(
    input_text: str, 
    case: str, 
    conversation_history: list = None, 
    model: str = None
) -> str:
    """Legacy function wrapper for tests and management tool."""
    try:
        config = {
            "name": "tests_management",
            "description": "Helps students select diagnostic tests and develop management plans",
            "type": "AgenticTool"
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
