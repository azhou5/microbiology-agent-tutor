"""
PatientTool - Patient agent following ToolUniverse AgenticTool pattern.
"""

import logging
from typing import Dict, Any

from microtutor.models.tool_models import AgenticTool
from microtutor.models.tool_errors import ToolLLMError
from microtutor.core.llm_router import chat_complete
from microtutor.tools.prompts import get_patient_system_prompt, get_patient_user_prompt

logger = logging.getLogger(__name__)


class PatientTool(AgenticTool):
    """Simulates patient responses during case investigation."""
    
    def _call_llm(self, prompt: str, **kwargs) -> str:
        """Call LLM to generate patient response."""
        try:
            model = kwargs.get('model', self.llm_config.get('model', 'gpt-4'))
            
            system_prompt = get_patient_system_prompt()
            user_prompt = get_patient_user_prompt(
                kwargs.get('case', ''),
                kwargs.get('input_text', '')
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
