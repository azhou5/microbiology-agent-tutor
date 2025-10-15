"""
ProblemRepresentationTool - Problem representation agent following ToolUniverse AgenticTool pattern.
"""

import logging
from typing import Dict, Any

from microtutor.models.tool_models import AgenticTool
from microtutor.models.tool_errors import ToolLLMError
from microtutor.core.llm_router import chat_complete
from microtutor.tools.prompts import get_problem_representation_system_prompt, get_problem_representation_user_prompt
from microtutor.core.logging_config import log_agent_context

# Import feedback integration
try:
    from microtutor.feedback import create_feedback_retriever, get_feedback_examples_for_tool
    FEEDBACK_AVAILABLE = True
except ImportError:
    FEEDBACK_AVAILABLE = False
    def get_feedback_examples_for_tool(*args, **kwargs):
        return ""

logger = logging.getLogger(__name__)


class ProblemRepresentationTool(AgenticTool):
    """Helps students organize clinical information into a clear problem representation."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize problem representation tool with optional feedback integration."""
        super().__init__(config)
        self.enable_feedback = config.get('enable_feedback', True) and FEEDBACK_AVAILABLE
        self.feedback_retriever = None
        self.interaction_counter = 0  # Track interaction count per tool instance
        
        if self.enable_feedback:
            try:
                feedback_dir = config.get('feedback_dir', 'data/feedback')
                self.feedback_retriever = create_feedback_retriever(feedback_dir)
                logger.info("Problem representation tool feedback integration enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize problem representation feedback retriever: {e}")
                self.enable_feedback = False
    
    def _call_llm(self, prompt: str, **kwargs) -> str:
        """Call LLM to generate problem representation guidance."""
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
                        tool_name="problem_representation",
                        feedback_retriever=self.feedback_retriever
                    )
                except Exception as e:
                    logger.warning(f"Failed to get feedback examples: {e}")
            
            # Build system prompt with feedback
            system_prompt = get_problem_representation_system_prompt()
            if feedback_examples:
                system_prompt += f"\n\n=== EXPERT FEEDBACK EXAMPLES ===\n{feedback_examples}"
            
            # Build user prompt
            user_prompt = f"""Case: {case}

Student's question/input: {input_text}

{get_problem_representation_user_prompt()}"""
            
            # Log agent context
            log_agent_context(
                agent_name="problem_representation",
                interaction_count=self.interaction_counter,
                user_input=input_text,
                case_context=case[:100] + "..." if len(case) > 100 else case,
                feedback_included=bool(feedback_examples)
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
            logger.error(f"Problem representation tool LLM call failed: {e}")
            raise ToolLLMError(f"LLM call failed: {e}")
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute problem representation tool."""
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
                    "agent": "problem_representation",
                    "interaction_count": self.interaction_counter,
                    "feedback_enabled": self.enable_feedback
                }
            }
            
        except Exception as e:
            logger.error(f"Problem representation tool execution failed: {e}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }


# Legacy function wrapper for backward compatibility
def run_problem_representation(input_text: str, case: str, conversation_history: list = None, model: str = None) -> str:
    """Legacy function wrapper for problem representation tool."""
    try:
        # Create tool instance with default config
        config = {
            "name": "problem_representation",
            "description": "Helps students organize clinical information into a clear problem representation",
            "type": "AgenticTool",
            "enable_feedback": True
        }
        
        tool = ProblemRepresentationTool(config)
        result = tool.execute(
            input_text=input_text,
            case=case,
            conversation_history=conversation_history or [],
            model=model
        )
        
        if result["success"]:
            return result["result"]
        else:
            return "I apologize, but I'm having trouble helping with problem representation right now. Could you please try again?"
            
    except Exception as e:
        logger.error(f"Legacy problem representation function failed: {e}")
        return "I apologize, but I'm having trouble helping with problem representation right now. Could you please try again?"
