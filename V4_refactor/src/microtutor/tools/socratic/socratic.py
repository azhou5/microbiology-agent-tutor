"""
SocraticTool - Socratic dialogue agent following ToolUniverse AgenticTool pattern.
"""

import logging
from typing import Dict, Any

from microtutor.schemas.tools.tool_models import AgenticTool
from microtutor.schemas.tools.tool_errors import ToolLLMError
from microtutor.core.llm.llm_router import chat_complete
from microtutor.prompts.socratic_prompts import get_socratic_system_prompt

logger = logging.getLogger(__name__)


class SocraticTool(AgenticTool):
    """Guides clinical reasoning through Socratic questioning."""
    
    def __init__(self, tool_config: Dict[str, Any]):
        super().__init__(tool_config)
        self.completion_signal = self.metadata.get('completion_signal', '[SOCRATIC_COMPLETE]')
    
    def _call_llm(self, prompt: str, **kwargs) -> str:
        """Call LLM to generate Socratic response."""
        try:
            model = kwargs.get('model', self.llm_config.get('model', 'gpt-4'))
            case = kwargs.get('case', '')
            conversation_history = kwargs.get('conversation_history', [])
            
            # Get system prompt template and format with case
            system_prompt_template = get_socratic_system_prompt()
            system_prompt = system_prompt_template.format(case=case)
            
            # Use conversation_history which already includes feedback at the end
            # Feedback was added to the last user message in tutor_service_v2.py
            # Prepare messages with system prompt (includes case) + conversation history (which includes feedback)
            from microtutor.utils.conversation_utils import prepare_llm_messages
            llm_messages = prepare_llm_messages(conversation_history, system_prompt)
            
            # Call LLM with prepared messages (includes system prompt + feedback from conversation_history)
            # Note: system_prompt is already in llm_messages, so we don't pass it separately
            response = chat_complete(
                system_prompt="",  # Not used when conversation_history is provided
                user_prompt="",  # Not used when conversation_history is provided
                model=model,
                conversation_history=llm_messages  # Includes system prompt + history with feedback
            )
            
            if not response or not response.strip():
                raise ToolLLMError("LLM returned empty response", tool_name=self.name)
            
            return response
            
        except Exception as e:
            logger.error(f"LLM call failed in {self.name}: {e}")
            raise ToolLLMError(f"Failed to generate Socratic response: {e}", tool_name=self.name)
    
    def _execute(self, arguments: Dict[str, Any]) -> str:
        """Execute Socratic tool."""
        return self._call_llm(
            "",
            case=arguments.get('case', ''),
            input_text=arguments.get('input_text', ''),
            conversation_history=arguments.get('conversation_history', []),
            model=arguments.get('model', 'gpt-4')
        )


# Legacy wrapper for backward compatibility
def run_socratic(
    input_text: str,
    case: str,
    conversation_history: list = None,
    model: str = None
) -> str:
    """Legacy function - use SocraticTool directly instead."""
    from microtutor.tools.registry import get_tool_instance
    from pathlib import Path
    import json
    
    tool = get_tool_instance('socratic')
    
    if not tool:
        logger.warning("Socratic tool not registered, loading config manually")
        config_path = Path(__file__).parent / "socratic_tool.json"
        
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
            tool = SocraticTool(config)
        else:
            raise RuntimeError("Socratic tool not available and config not found")
    
    result = tool.run({
        'input_text': input_text,
        'case': case,
        'conversation_history': conversation_history or [],
        'model': model or 'gpt-4'
    })
    
    if result['success']:
        return result['result']
    else:
        raise RuntimeError(f"Socratic tool failed: {result.get('error', {}).get('message', 'Unknown error')}")
