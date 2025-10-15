"""
PatientTool - Patient agent following ToolUniverse AgenticTool pattern.
"""

import logging
from typing import Dict, Any

from microtutor.models.tool_models import AgenticTool
from microtutor.models.tool_errors import ToolLLMError
from microtutor.core.llm_router import chat_complete
from microtutor.tools.prompts import get_patient_system_prompt, get_patient_user_prompt
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


class PatientTool(AgenticTool):
    """Simulates patient responses during case investigation."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize patient tool with optional feedback integration."""
        super().__init__(config)
        self.enable_feedback = config.get('enable_feedback', True) and FEEDBACK_AVAILABLE
        self.feedback_retriever = None
        self.interaction_counter = 0  # Track interaction count per tool instance
        
        if self.enable_feedback:
            try:
                feedback_dir = config.get('feedback_dir', 'data/feedback')
                self.feedback_retriever = create_feedback_retriever(feedback_dir)
                logger.info("Patient tool feedback integration enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize patient feedback retriever: {e}")
                self.enable_feedback = False
    
    def _call_llm(self, prompt: str, **kwargs) -> str:
        """Call LLM to generate patient response."""
        try:
            model = kwargs.get('model', self.llm_config.get('model', 'gpt-4'))
            case = kwargs.get('case', '')
            input_text = kwargs.get('input_text', '')
            conversation_history = kwargs.get('conversation_history', [])
            
            # Get base prompts without feedback
            system_prompt = get_patient_system_prompt()
            user_prompt = get_patient_user_prompt(case, input_text)
            
            # Append feedback examples to user prompt if available
            feedback_metadata = {}
            if self.enable_feedback and self.feedback_retriever:
                try:
                    feedback_examples = get_feedback_examples_for_tool(
                        user_input=input_text,
                        conversation_history=conversation_history,
                        tool_name="patient",
                        feedback_retriever=self.feedback_retriever,
                        include_feedback=True
                    )
                    if feedback_examples:
                        user_prompt += f"\n\n{feedback_examples}"
                        feedback_metadata = {
                            "feedback_enabled": True,
                            "feedback_examples_length": len(feedback_examples),
                            "enhanced_user_prompt_length": len(user_prompt),
                            "original_user_prompt_length": len(get_patient_user_prompt(case, input_text))
                        }
                        logger.info(f"[FEEDBACK] Retrieved {len(feedback_examples)} chars of feedback examples for patient")
                    else:
                        feedback_metadata = {"feedback_enabled": True, "feedback_examples_found": False}
                except Exception as e:
                    logger.warning(f"Could not retrieve feedback examples: {e}")
                    feedback_metadata = {"feedback_enabled": True, "feedback_error": str(e)}
            
            # Increment interaction counter and log agent context
            self.interaction_counter += 1
            case_id = kwargs.get('case_id', 'unknown')
            log_agent_context(
                case_id=case_id,
                agent_name="patient",
                interaction_id=self.interaction_counter,
                system_prompt=system_prompt,
                user_prompt=input_text,
                feedback_examples=feedback_examples if 'feedback_examples' in locals() else "",
                full_context=user_prompt,
                metadata={
                    "model": model,
                    "feedback_enabled": self.enable_feedback,
                    "case_length": len(case)
                }
            )
            
            response = chat_complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model
            )
            
            if not response or not response.strip():
                raise ToolLLMError("LLM returned empty response", tool_name=self.name)
            
            return response
            
        except Exception as e:
            logger.error(f"LLM call failed in {self.name}: {e}")
            raise ToolLLMError(f"Failed to generate patient response: {e}", tool_name=self.name)
    
    def _execute(self, arguments: Dict[str, Any]) -> str:
        """Execute patient tool."""
        return self._call_llm(
            "",
            case=arguments.get('case', ''),
            input_text=arguments.get('input_text', ''),
            conversation_history=arguments.get('conversation_history', []),
            model=arguments.get('model', 'gpt-4')
        )


# Legacy wrapper for backward compatibility
def run_patient(
    input_text: str,
    case: str,
    conversation_history: list = None,
    model: str = None
) -> str:
    """
    Legacy function - use PatientTool directly instead.
    Calls new tool system internally for backward compatibility.
    """
    from microtutor.tools.registry import get_tool_instance
    from pathlib import Path
    import json
    
    tool = get_tool_instance('patient')
    
    # Fallback: load config manually if not registered
    if not tool:
        logger.warning("Patient tool not registered, loading config manually")
        project_root = Path(__file__).parent.parent.parent.parent
        config_path = project_root / "config" / "tools" / "patient_tool.json"
        
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
            tool = PatientTool(config)
        else:
            raise RuntimeError("Patient tool not available and config not found")
    
    result = tool.run({
        'input_text': input_text,
        'case': case,
        'conversation_history': conversation_history or [],
        'model': model or 'gpt-4'
    })
    
    if result['success']:
        return result['result']
    else:
        raise RuntimeError(f"Patient tool failed: {result.get('error', {}).get('message', 'Unknown error')}")
