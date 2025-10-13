"""
Tutor service - V4 with ToolUniverse-style tool system + native function calling.

Handles tutor business logic: starting cases, processing messages, managing tool calls.
"""

from typing import List, Dict, Any, Optional
import logging
import json
from datetime import datetime

from microtutor.tools import get_tool_engine
from microtutor.agents.case import get_case
from microtutor.core.llm_router import chat_complete, get_llm_client
from microtutor.core.tutor_prompt import get_system_message_template

try:
    from microtutor.Feedback.feedback_faiss import retrieve_similar_examples
except ImportError:
    def retrieve_similar_examples(*args, **kwargs):
        return []

from microtutor.models.domain import TutorContext, TutorResponse, TokenUsage, TutorState
from microtutor.core.config_helper import config

logger = logging.getLogger(__name__)

system_message_template = get_system_message_template()


class TutorService:
    """Tutor service with ToolUniverse-style tool engine and native function calling."""
    
    def __init__(
        self,
        output_tool_directly: bool = True,
        run_with_faiss: bool = False,
        reward_model_sampling: bool = False,
        model_name: Optional[str] = None
    ):
        """Initialize tutor service."""
        self.output_tool_directly = output_tool_directly
        self.run_with_faiss = run_with_faiss
        self.reward_model_sampling = reward_model_sampling
        self.model_name = model_name or config.API_MODEL_NAME
        
        # Initialize tool engine (ToolUniverse-style with native function calling)
        self.tool_engine = get_tool_engine()
        self.tool_schemas = self.tool_engine.get_tool_schemas()
        
        logger.info(
            f"TutorService initialized: tools={self.tool_engine.list_tools()}, "
            f"model={self.model_name}"
        )
    
    async def start_case(
        self,
        organism: str,
        case_id: str,
        model_name: Optional[str] = None,
        use_hpi_only: bool = False
    ) -> TutorResponse:
        """Start a new case.
        
        Args:
            organism: The microorganism name
            case_id: Unique case identifier
            model_name: Optional LLM model to use
            use_hpi_only: If True, use shorter HPI version
        """
        start_time = datetime.now()
        model = model_name or self.model_name
        
        logger.info(f"Starting case: organism={organism}, case_id={case_id}, use_hpi_only={use_hpi_only}")
        
        # Load case (full or HPI only)
        case_description = get_case(organism, use_hpi_only=use_hpi_only)
        if not case_description:
            raise ValueError(f"Could not load case for organism: {organism}")
        
        # Build system message (native function calling - no tool rules needed)
        system_message = system_message_template.format(
            case=case_description
        )
        
        # Generate initial message
        initial_prompt = (
            "Welcome the student and introduce the case. "
            "Present the initial chief complaint and basic demographics."
        )
        
        try:
            response_text = chat_complete(
                system_prompt=system_message,
                user_prompt=initial_prompt,
                model=model,
                tools=self.tool_schemas  # Native function calling
            )
            
            if not response_text:
                raise ValueError("LLM returned empty response")
                
        except Exception as e:
            logger.error(f"Error calling LLM: {e}", exc_info=True)
            raise ValueError(f"Failed to generate initial message: {e}")
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"Case started in {processing_time:.2f}ms")
        
        return TutorResponse(
            content=response_text,
            tools_used=[],
            processing_time_ms=processing_time,
            metadata={
                "case_id": case_id,
                "organism": organism,
                "state": TutorState.INFORMATION_GATHERING.value,
                "model": model
            }
        )
    
    async def process_message(
        self,
        message: str,
        context: TutorContext
    ) -> TutorResponse:
        """Process user message and return tutor response."""
        start_time = datetime.now()
        logger.info(f"Processing message for case_id={context.case_id}")
        
        # Load case if needed
        if not context.case_description:
            context.case_description = get_case(context.organism)
            if not context.case_description:
                raise ValueError(f"Could not load case for organism: {context.organism}")
        
        # Build system message (native function calling - no tool rules needed)
        system_message = system_message_template.format(
            case=context.case_description
        )
        
        # Update system message in history
        if context.conversation_history and context.conversation_history[0]["role"] == "system":
            context.conversation_history[0]["content"] = system_message
        else:
            context.conversation_history.insert(0, {"role": "system", "content": system_message})
        
        # Add user message
        context.conversation_history.append({"role": "user", "content": message})
        
        # Call LLM with native function calling
        try:
            response_text = self._call_tutor_with_tools(
                messages=context.conversation_history,
                case_description=context.case_description,
                model=context.model_name
            )
            
            if not response_text:
                raise ValueError("LLM returned empty response")
                
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            raise ValueError(f"Failed to process message: {e}")
        
        # Add assistant response
        context.conversation_history.append({"role": "assistant", "content": response_text})
        
        # Update state
        new_state = self._determine_state(response_text, context.current_state)
        context.current_state = new_state
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"Message processed in {processing_time:.2f}ms, state: {new_state}")
        
        return TutorResponse(
            content=response_text,
            tools_used=[],
            processing_time_ms=processing_time,
            metadata={
                "case_id": context.case_id,
                "state": new_state.value,
                "organism": context.organism
            }
        )
    
    def _call_tutor_with_tools(
        self,
        messages: List[Dict[str, str]],
        case_description: str,
        model: str
    ) -> str:
        """Call tutor LLM with native function calling support."""
        system_msg = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
        user_msg = messages[-1]["content"] if messages and messages[-1]["role"] == "user" else ""
        
        # Call LLM with tool schemas (native function calling)
        response = chat_complete(
            system_prompt=system_msg,
            user_prompt=user_msg,
            model=model,
            tools=self.tool_schemas
        )
        
        # Handle tool call (native function calling format)
        if isinstance(response, dict) and 'tool_calls' in response:
            tool_calls = response['tool_calls']
            
            if tool_calls and len(tool_calls) > 0:
                # Execute first tool call
                tool_call = tool_calls[0]
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                logger.info(f"Native function call: {tool_name}({list(tool_args.keys())})")
                
                # Add context to arguments
                tool_args.update({
                    'case': case_description,
                    'conversation_history': messages,
                    'model': model
                })
                
                # Execute via tool engine
                tool_result = self.tool_engine.execute_tool(tool_name, tool_args)
                
                if tool_result['success']:
                    return tool_result['result']
                else:
                    error = tool_result.get('error', {})
                    logger.error(f"Tool failed: {error.get('message', 'Unknown error')}")
                    return f"An error occurred while using the {tool_name} tool."
            
            # No tool calls, return content
            return response.get('content', '')
        
        # Normal text response
        return response
    
    def _determine_state(self, response: str, current_state: TutorState) -> TutorState:
        """Determine new state based on response content."""
        resp = response.lower()
        
        if "problem representation" in resp:
            return TutorState.PROBLEM_REPRESENTATION
        elif "differential" in resp or "ddx" in resp:
            return TutorState.DIFFERENTIAL_DIAGNOSIS
        elif any(x in resp for x in ["investigation", "test", "culture"]):
            return TutorState.INVESTIGATIONS
        elif any(x in resp for x in ["treatment", "management"]):
            return TutorState.TREATMENT
        elif "feedback" in resp and "conclusion" in resp:
            return TutorState.COMPLETED
        
        return current_state
