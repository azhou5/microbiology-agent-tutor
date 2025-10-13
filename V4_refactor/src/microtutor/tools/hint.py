"""
HintTool - Hint generation agent following ToolUniverse AgenticTool pattern.
"""

import logging
from typing import Dict, Any

from microtutor.models.tool_models import AgenticTool
from microtutor.models.tool_errors import ToolLLMError
from microtutor.core.llm_router import chat_complete
from microtutor.tools.prompts import get_hint_system_prompt, get_hint_user_prompt

logger = logging.getLogger(__name__)


class HintTool(AgenticTool):
    """Provides strategic hints to guide investigation."""
    
    def _call_llm(self, prompt: str, **kwargs) -> str:
        """Call LLM to generate hint."""
        try:
            model = kwargs.get('model', self.llm_config.get('model', 'gpt-4'))
            
            system_prompt = get_hint_system_prompt()
            user_prompt = get_hint_user_prompt(
                kwargs.get('case', ''),
                kwargs.get('input_text', ''),
                kwargs.get('covered_topics', [])
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
            raise ToolLLMError(f"Failed to generate hint: {e}", tool_name=self.name)
    
    def _execute(self, arguments: Dict[str, Any]) -> str:
        """Execute hint tool."""
        return self._call_llm(
            "",
            case=arguments.get('case', ''),
            input_text=arguments.get('input_text', ''),
            covered_topics=arguments.get('covered_topics', []),
            model=arguments.get('model', 'gpt-4')
        )


# Legacy wrapper for backward compatibility
def run_hint(
    input_text: str,
    case: str,
    conversation_history: list = None,
    model: str = None
) -> str:
    """Legacy function - use HintTool directly instead."""
    from microtutor.tools.registry import get_tool_instance
    from pathlib import Path
    import json
    
    tool = get_tool_instance('hint')
    
    if not tool:
        logger.warning("Hint tool not registered, loading config manually")
        project_root = Path(__file__).parent.parent.parent.parent
        config_path = project_root / "config" / "tools" / "hint_tool.json"
        
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
            tool = HintTool(config)
        else:
            raise RuntimeError("Hint tool not available and config not found")
    
    # Extract covered topics from conversation history
    covered_topics = []
    if conversation_history:
        for msg in conversation_history:
            if msg.get('role') == 'user':
                content = msg.get('content', '').lower()
                if 'fever' in content:
                    covered_topics.append('fever')
                if 'cough' in content:
                    covered_topics.append('cough')
                # Add more topic extraction as needed
    
    result = tool.run({
        'input_text': input_text,
        'case': case,
        'covered_topics': covered_topics,
        'model': model or 'gpt-4'
    })
    
    if result['success']:
        return result['result']
    else:
        raise RuntimeError(f"Hint tool failed: {result.get('error', {}).get('message', 'Unknown error')}")
