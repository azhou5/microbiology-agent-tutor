"""
Update Phase Tool - Simple tool for updating case phase state.

This tool allows the main tutor to update phase information as part of its
native function calling workflow.
"""

import logging
from typing import Dict, Any

from microtutor.models.tool_models import BaseTool

logger = logging.getLogger(__name__)


class UpdatePhaseTool(BaseTool):
    """Simple tool for updating phase state - no LLM calls needed."""
    
    def __init__(self, tool_config: Dict[str, Any]):
        super().__init__(tool_config)
        logger.info(f"Initialized {self.name}")
    
    def _execute(self, arguments: Dict[str, Any]) -> str:
        """Update phase state - this is handled by the tutor service."""
        current_phase = arguments.get('current_phase', 'information_gathering')
        phase_locked = arguments.get('phase_locked', False)
        phase_progress = arguments.get('phase_progress', 0.0)
        phase_guidance = arguments.get('phase_guidance', '')
        completion_criteria = arguments.get('completion_criteria', [])
        transition_reason = arguments.get('transition_reason', 'tutor_decision')
        
        logger.info(f"Phase update: {current_phase}, locked: {phase_locked}, progress: {phase_progress}")
        
        # Return structured phase information
        import json
        phase_data = {
            "current_phase": current_phase,
            "phase_locked": phase_locked,
            "phase_progress": phase_progress,
            "phase_guidance": phase_guidance,
            "completion_criteria": completion_criteria,
            "transition_reason": transition_reason
        }
        
        return json.dumps(phase_data)
