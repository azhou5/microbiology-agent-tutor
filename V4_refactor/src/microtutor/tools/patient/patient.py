"""
PatientTool - Patient agent following ToolUniverse AgenticTool pattern.
"""

import logging
import re
from typing import Dict, Any, Optional

from microtutor.schemas.tools.tool_models import AgenticTool
from microtutor.schemas.tools.tool_errors import ToolLLMError
from microtutor.core.llm.llm_router import chat_complete
from microtutor.prompts.patient_prompts import get_patient_system_prompt
from microtutor.core.logging.logging_config import log_agent_context

# Import audio matcher for respiratory sounds
try:
    from microtutor.core.audio.sound_matcher import RespiratoryAudioMatcher
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    RespiratoryAudioMatcher = None

logger = logging.getLogger(__name__)


class PatientTool(AgenticTool):
    """Simulates patient responses during case investigation.
    
    Note: Feedback examples are passed via conversation history from TutorService,
    not retrieved directly by this tool.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize patient tool with optional audio integration."""
        super().__init__(config)
        self.enable_audio = config.get('enable_audio', True) and AUDIO_AVAILABLE
        self.audio_matcher = None
        self.interaction_counter = 0
        
        if self.enable_audio:
            try:
                self.audio_matcher = RespiratoryAudioMatcher()
                logger.info("Patient tool audio integration enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize audio matcher: {e}")
                self.enable_audio = False
    
    def _is_respiratory_exam_request(self, input_text: str) -> bool:
        """Check if the input is requesting a respiratory examination."""
        respiratory_keywords = [
            'listen', 'auscultate', 'lung sounds', 'breath sounds', 'chest exam',
            'respiratory exam', 'lungs', 'breathing', 'stethoscope', 'chest',
            'respiratory', 'pulmonary', 'auscultation', 'listen to', 'examine lungs',
            'check lungs', 'lung examination', 'breathing sounds'
        ]
        
        input_lower = input_text.lower()
        return any(keyword in input_lower for keyword in respiratory_keywords)
    
    def _get_organism_from_case(self, case: str) -> Optional[str]:
        """Extract organism name from case text."""
        # Common organism patterns in case text
        organism_patterns = [
            r'staphylococcus aureus',
            r'streptococcus pneumoniae', 
            r'escherichia coli',
            r'borrelia burgdorferi',
            r'nocardia species',
            r'hsv-1',
            r'influenza a',
            r'hiv',
            r'ebv',
            r'candida albicans',
            r'aspergillus fumigatus',
            r'plasmodium falciparum',
            r'taenia solium'
        ]
        
        case_lower = case.lower()
        for pattern in organism_patterns:
            if re.search(pattern, case_lower):
                return pattern.replace(' ', '_')
        
        return None
    
    def _get_audio_data(self, input_text: str, case: str) -> Optional[Dict[str, Any]]:
        """Get audio data for respiratory examination if applicable."""
        if not self.enable_audio or not self.audio_matcher:
            return None
        
        if not self._is_respiratory_exam_request(input_text):
            return None
        
        organism = self._get_organism_from_case(case)
        if not organism:
            logger.warning("Could not extract organism from case for audio matching")
            return None
        
        try:
            # Get HPI from case (first paragraph or section)
            hpi = case.split('\n')[0] if '\n' in case else case
            if len(hpi) > 500:  # Truncate very long cases
                hpi = hpi[:500] + "..."
            
            audio_data = self.audio_matcher.get_audio_for_respiratory_exam(organism, hpi)
            if audio_data:
                logger.info(f"Found audio match for {organism}: {audio_data['finding_type']}")
                return audio_data
            else:
                logger.info(f"No audio match found for {organism}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting audio data: {e}")
            return None
    
    def _call_llm(self, prompt: str, **kwargs) -> str:
        """Call LLM to generate patient response."""
        try:
            model = kwargs.get('model', self.llm_config.get('model', 'gpt-4'))
            case = kwargs.get('case', '')
            input_text = kwargs.get('input_text', '')
            conversation_history = kwargs.get('conversation_history', [])
            
            # Get system prompt template and format with case
            system_prompt_template = get_patient_system_prompt()
            system_prompt = system_prompt_template.format(case=case)
            
            # Use conversation_history which already includes feedback at the end
            # Feedback was added to the last user message in tutor_service_v2.py
            # Prepare messages with system prompt (includes case) + conversation history (which includes feedback)
            from microtutor.utils.conversation_utils import prepare_llm_messages
            llm_messages = prepare_llm_messages(conversation_history, system_prompt)
            
            # Increment interaction counter and log agent context
            self.interaction_counter += 1
            case_id = kwargs.get('case_id', 'unknown')
            
            # Check if feedback is in the conversation history (last user message)
            feedback_in_history = False
            if conversation_history:
                last_user_msg = next((msg for msg in reversed(conversation_history) if msg.get("role") == "user"), None)
                if last_user_msg and "\n\n" in last_user_msg.get("content", ""):
                    # Feedback is typically appended with "\n\n" separator
                    feedback_in_history = True
            
            log_agent_context(
                case_id=case_id,
                agent_name="patient",
                interaction_id=self.interaction_counter,
                system_prompt=system_prompt,
                user_prompt=input_text,
                feedback_examples="[Using feedback from conversation_history]" if feedback_in_history else "",
                full_context=llm_messages[-1].get("content", "") if llm_messages else input_text,
                metadata={
                    "model": model,
                    "feedback_from_history": feedback_in_history,
                    "case_length": len(case)
                }
            )
            
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
            raise ToolLLMError(f"Failed to generate patient response: {e}", tool_name=self.name)
    
    def _execute(self, arguments: Dict[str, Any]) -> str:
        """Execute patient tool."""
        input_text = arguments.get('input_text', '')
        case = arguments.get('case', '')
        
        # Get text response
        text_response = self._call_llm(
            "",
            case=case,
            input_text=input_text,
            conversation_history=arguments.get('conversation_history', []),
            model=arguments.get('model', 'gpt-4')
        )
        
        # Check for audio data
        audio_data = self._get_audio_data(input_text, case)
        
        if audio_data:
            # Return structured response with audio data
            import json
            return json.dumps({
                "response": text_response,
                "audio_data": audio_data,
                "has_audio": True
            })
        else:
            # Return simple text response
            return text_response


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
        config_path = Path(__file__).parent / "patient_tool.json"
        
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
