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

from microtutor.models.domain import TutorContext, TutorResponse, TokenUsage, TutorState
from microtutor.models.phase_models import PhaseState, PhaseConfidence, PhaseTransitionReason, TutorStructuredResponse
from microtutor.core.config_helper import config
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

system_message_template = get_system_message_template()


class TutorService:
    """Tutor service with ToolUniverse-style tool engine and native function calling."""
    
    def __init__(
        self,
        output_tool_directly: bool = True,
        run_with_faiss: bool = False,
        reward_model_sampling: bool = False,
        model_name: Optional[str] = None,
        enable_feedback: bool = True,
        feedback_dir: Optional[str] = None
    ):
        """Initialize tutor service."""
        self.output_tool_directly = output_tool_directly
        self.run_with_faiss = run_with_faiss
        self.reward_model_sampling = reward_model_sampling
        self.model_name = model_name or config.API_MODEL_NAME
        self.enable_feedback = enable_feedback and FEEDBACK_AVAILABLE
        
        # Initialize tool engine (ToolUniverse-style with native function calling)
        self.tool_engine = get_tool_engine()
        self.tool_schemas = self.tool_engine.get_tool_schemas()
        
        # Initialize feedback retriever if available
        self.feedback_retriever = None
        self.interaction_counter = 0  # Track interaction count per service instance
        
        # Phase management state (similar to V3 socratic mode)
        self.current_phase = TutorState.INFORMATION_GATHERING
        self.phase_locked = False  # Whether we're locked in current phase
        
        # Socratic routing state (from V3)
        self.socratic_mode = False
        self.socratic_conversation_count = 0
        self.phase_progress = {}  # Track progress within each phase
        self.phase_transition_history = []  # Track phase transitions
        self.phase_completion_signals = {
            'information_gathering': '[PHASE_COMPLETE: information_gathering]',
            'problem_representation': '[PHASE_COMPLETE: problem_representation]',
            'differential_diagnosis': '[PHASE_COMPLETE: differential_diagnosis]',
            'tests': '[PHASE_COMPLETE: tests]',
            'management': '[PHASE_COMPLETE: management]',
            'feedback': '[PHASE_COMPLETE: feedback]'
        }
        
        # Phase-specific validation rules
        self.phase_validation_rules = {
            TutorState.INFORMATION_GATHERING: {
                'min_messages': 3,
                'required_keywords': ['history', 'symptoms', 'exam', 'physical', 'vital'],
                'completion_threshold': 0.6
            },
            TutorState.PROBLEM_REPRESENTATION: {
                'min_messages': 2,
                'required_keywords': ['problem', 'representation', 'illness', 'script', 'reasoning'],
                'completion_threshold': 0.5
            },
            TutorState.DIFFERENTIAL_DIAGNOSIS: {
                'min_messages': 2,
                'required_keywords': ['differential', 'diagnosis', 'ddx', 'consider', 'suspect'],
                'completion_threshold': 0.5
            },
            TutorState.TESTS: {
                'min_messages': 2,
                'required_keywords': ['test', 'investigation', 'culture', 'lab', 'imaging'],
                'completion_threshold': 0.5
            },
            TutorState.MANAGEMENT: {
                'min_messages': 2,
                'required_keywords': ['treatment', 'management', 'therapy', 'medication'],
                'completion_threshold': 0.5
            }
        }
        
        if self.enable_feedback:
            try:
                feedback_path = feedback_dir or config.get('FEEDBACK_DIR', 'data/feedback')
                self.feedback_retriever = create_feedback_retriever(feedback_path)
                logger.info("Feedback integration enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize feedback retriever: {e}")
                self.enable_feedback = False
        
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
        
        # Reset socratic mode state for new case
        self.socratic_mode = False
        self.socratic_conversation_count = 0
        
        logger.info(f"Starting case: organism={organism}, case_id={case_id}, use_hpi_only={use_hpi_only}")
        
        # Load case (full or HPI only)
        case_description = get_case(organism, use_hpi_only=use_hpi_only)
        if not case_description:
            raise ValueError(f"Could not load case for organism: {organism}")
        
        # Build system message (native function calling - no tool rules needed)
        # No feedback needed for initial case introduction
        system_message = system_message_template.format(
            case=case_description,
            Examples_of_Good_and_Bad_Responses=""
        )
        
        # Use HPI data for initial presentation instead of LLM call
        try:
            import json
            import os
            
            # Load ambiguous case data for concise initial presentations
            hpi_file = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'Case_Outputs', 'ambiguous_with_ages.json')
            with open(hpi_file, 'r') as f:
                hpi_data = json.load(f)
            
            # Get HPI for this organism (convert spaces to underscores for key matching)
            organism_key = organism.replace(' ', '_')
            hpi_text = hpi_data.get(organism_key)
            if not hpi_text:
                logger.warning(f"No HPI data for organism: {organism}")
                # Fallback to LLM if no HPI data
                initial_prompt = (
                    "Welcome the student and introduce the case. "
                    "Present the initial chief complaint and basic demographics."
                )
                response_text = chat_complete(
                    system_prompt=system_message,
                    user_prompt=initial_prompt,
                    model=model,
                    tools=self.tool_schemas,
                    fallback_model="gpt-4.1"
                )
                if not response_text:
                    # Fallback message if LLM fails after all retries
                    response_text = "Welcome to today's case. I'm having trouble generating the case details right now. Please try starting a new case."
            else:
                # Use ambiguous case data directly for initial presentation
                response_text = f"Welcome to today's case.\n\n{hpi_text}\n\n Begin by asking a more detailed history, requesting specific physical exam findings, and ordering initial studies. Then we will move onto problem representation, differential diagnosis, management and feedback."
                logger.info(f"Using ambiguous case data for initial presentation: {organism}")
                
        except Exception as e:
            logger.error(f"Error generating initial message: {e}", exc_info=True)
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
        context: TutorContext,
        feedback_enabled: Optional[bool] = None,
        feedback_threshold: Optional[float] = None
    ) -> TutorResponse:
        """Process user message and return tutor response."""
        start_time = datetime.now()
        logger.info(f"Processing message for case_id={context.case_id}")
        
        # Check if we're in socratic mode and should route directly to socratic agent
        if self.socratic_mode:
            logger.info("In socratic mode, routing directly to socratic agent")
            # Ensure phase is set to differential diagnosis when in socratic mode
            if context.current_state != TutorState.DIFFERENTIAL_DIAGNOSIS:
                context.current_state = TutorState.DIFFERENTIAL_DIAGNOSIS
                logger.info("Setting phase to differential_diagnosis for socratic mode")
            return await self._handle_socratic_direct_route(message, context)
        
        # Check for phase transition messages and update context
        if "Let's move onto phase:" in message:
            # Extract phase name from message
            phase_name = message.split("Let's move onto phase:")[1].strip()
            # Map phase name to TutorState
            phase_mapping = {
                "Information Gathering": TutorState.INFORMATION_GATHERING,
                "Problem Representation": TutorState.PROBLEM_REPRESENTATION,
                "Differential Diagnosis": TutorState.DIFFERENTIAL_DIAGNOSIS,
                "Tests": TutorState.TESTS,
                "Management": TutorState.MANAGEMENT,
                "Feedback": TutorState.FEEDBACK
            }
            if phase_name in phase_mapping:
                context.current_state = phase_mapping[phase_name]
                logger.info(f"[PHASE] Updated context state to: {context.current_state}")
                
                # Immediately route to the phase-specific agent for phase transitions
                phase_agent_response = await self._handle_phase_specific_routing(
                    f"Let's start the {phase_name} phase", context
                )
                if phase_agent_response:
                    return phase_agent_response
        
        # Check if we should route to phase-specific agent
        phase_agent_response = await self._handle_phase_specific_routing(message, context)
        if phase_agent_response:
            return phase_agent_response
        
        # Load case if needed
        if not context.case_description:
            context.case_description = get_case(context.organism)
            if not context.case_description:
                raise ValueError(f"Could not load case for organism: {context.organism}")
        
        # Get feedback examples for tutor and append to user message
        enhanced_message = message
        feedback_examples = ""
        retrieved_feedback_examples = []
        
        # Use provided feedback settings or fall back to service defaults
        use_feedback = feedback_enabled if feedback_enabled is not None else self.enable_feedback
        logger.info(f"[FEEDBACK] use_feedback={use_feedback}, feedback_retriever={self.feedback_retriever is not None}")
        
        if use_feedback and self.feedback_retriever:
            try:
                # Temporarily update threshold if provided
                if feedback_threshold is not None:
                    from microtutor.core.config_helper import config
                    original_threshold = config.FEEDBACK_SIMILARITY_THRESHOLD
                    config.FEEDBACK_SIMILARITY_THRESHOLD = feedback_threshold
                    logger.info(f"[FEEDBACK] Updated threshold from {original_threshold} to {feedback_threshold}")
                
                feedback_examples = get_feedback_examples_for_tool(
                    user_input=message,
                    conversation_history=context.conversation_history,
                    tool_name="tutor",
                    feedback_retriever=self.feedback_retriever,
                    include_feedback=True
                )
                
                # Get the actual feedback examples for the response
                current_threshold = config.FEEDBACK_SIMILARITY_THRESHOLD
                logger.info(f"[FEEDBACK] Using threshold: {current_threshold}")
                retrieved_feedback_examples = self.feedback_retriever.retrieve_feedback_examples(
                    current_message=message,
                    conversation_history=context.conversation_history,
                    message_type="tutor",
                    k=3
                )
                logger.info(f"[FEEDBACK] Retrieved {len(retrieved_feedback_examples)} feedback examples")
                
                # Convert to serializable format
                retrieved_feedback_examples = [
                    {
                        "similarity_score": float(example.similarity_score),
                        "is_positive_example": example.is_positive_example,
                        "is_negative_example": example.is_negative_example,
                        "entry": {
                            "rating": example.entry.rating,
                            "organism": example.entry.organism,
                            "case_id": example.entry.case_id,
                            "rated_message": example.entry.rated_message,
                            "feedback_text": example.entry.feedback_text,
                            "replacement_text": example.entry.replacement_text,
                            "chat_history": example.entry.chat_history
                        },
                        "text": example.text
                    }
                    for example in retrieved_feedback_examples
                ]
                
                if feedback_examples:
                    enhanced_message = f"{message}\n\n{feedback_examples}"
                
                # Restore original threshold
                if feedback_threshold is not None:
                    config.FEEDBACK_SIMILARITY_THRESHOLD = original_threshold
                    
            except Exception as e:
                logger.warning(f"Could not retrieve feedback examples: {e}")
        
        # Ensure system message is present and at the beginning
        # Check if system message exists anywhere in the conversation history
        has_system_message = any(
            msg.get("role") == "system" for msg in context.conversation_history
        )
        
        if not has_system_message:
            # No system message found, add it at the beginning
            system_message = system_message_template.format(
                case=context.case_description
            )
            context.conversation_history.insert(0, {"role": "system", "content": system_message})
            logger.info(f"[SYSTEM] Added system message to conversation history")
        elif context.conversation_history[0]["role"] != "system":
            # System message exists but not at the beginning, move it to the front
            system_msg = None
            for i, msg in enumerate(context.conversation_history):
                if msg.get("role") == "system":
                    system_msg = context.conversation_history.pop(i)
                    break
            
            if system_msg:
                context.conversation_history.insert(0, system_msg)
                logger.info(f"[SYSTEM] Moved system message to beginning of conversation history")
            else:
                # Fallback: create new system message
                system_message = system_message_template.format(
                    case=context.case_description
                )
                context.conversation_history.insert(0, {"role": "system", "content": system_message})
                logger.info(f"[SYSTEM] Created new system message as fallback")
        
        # Log conversation history state for debugging
        logger.info(f"[CONVERSATION] History length: {len(context.conversation_history)}")
        logger.info(f"[CONVERSATION] First message role: {context.conversation_history[0]['role'] if context.conversation_history else 'None'}")
        logger.info(f"[CONVERSATION] Last message role: {context.conversation_history[-1]['role'] if context.conversation_history else 'None'}")
        
        # Increment interaction counter and log agent context
        self.interaction_counter += 1
        system_message = context.conversation_history[0]["content"]
        log_agent_context(
            case_id=context.case_id,
            agent_name="tutor",
            interaction_id=self.interaction_counter,
            system_prompt=system_message,
            user_prompt=message,
            feedback_examples=feedback_examples,
            full_context=enhanced_message,
            metadata={
                "model": context.model_name,
                "feedback_enabled": self.enable_feedback,
                "organism": context.organism
            }
        )
        
        # Add enhanced user message
        context.conversation_history.append({"role": "user", "content": enhanced_message})
        
        # Call LLM with native function calling
        try:
            response_text, phase_data, tools_used = self._call_tutor_with_tools_and_phase(
                messages=context.conversation_history,
                case_description=context.case_description,
                model=context.model_name,
                use_azure=context.use_azure
            )
            
            if not response_text:
                raise ValueError("LLM returned empty response after all retries")
                
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            raise ValueError(f"Failed to process message: {e}")
        
        # Add assistant response
        context.conversation_history.append({"role": "assistant", "content": response_text})
        
        # Update phase state - either from tool call or automatic detection
        if phase_data:
            # Phase data from LLM tool call
            new_state = TutorState(phase_data['current_phase'])
            self.current_phase = new_state
            self.phase_locked = phase_data.get('phase_locked', False)
            context.current_state = new_state
            logger.info(f"[PHASE] Updated via LLM tool: {phase_data['current_phase']}, locked: {self.phase_locked}")
        else:
            # Automatic phase detection as fallback
            new_state = self._determine_state(response_text, context.current_state)
            context.current_state = new_state
            logger.info(f"[PHASE] Auto-detected: {new_state}")
            
            # Force phase update tool call for consistency
            self._force_phase_update(context, response_text, message)
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"Message processed in {processing_time:.2f}ms, state: {new_state}")
        
        return TutorResponse(
            content=response_text,
            tools_used=tools_used,
            processing_time_ms=processing_time,
            metadata={
                "case_id": context.case_id,
                "state": new_state.value,
                "organism": context.organism,
                "phase_locked": self.phase_locked,
                "current_phase": self.current_phase.value
            },
            feedback_examples=retrieved_feedback_examples
        )
    
    async def _handle_socratic_direct_route(self, message: str, context: TutorContext) -> TutorResponse:
        """
        Handle direct routing to socratic agent when in socratic mode.
        
        Args:
            message: The user's message
            context: Tutor context
            
        Returns:
            TutorResponse: The socratic agent's response
        """
        logger.info(f"Handling direct socratic route for: {message}")
        
        # Get socratic agent response
        socratic_response = await self._call_socratic_agent(message, context)
        
        # Check for completion signal
        completion_signal = "[SOCRATIC_COMPLETE]"
        is_complete = completion_signal in socratic_response
        
        # Clean the response - remove completion signal
        cleaned_response = socratic_response
        if completion_signal in cleaned_response:
            cleaned_response = cleaned_response.replace(completion_signal, "").strip()
        
        # Increment conversation count
        self.socratic_conversation_count += 1
        
        # Check if socratic section is complete based on signal
        if is_complete:
            logger.info("Socratic section complete (signal detected), exiting socratic mode")
            self.socratic_mode = False
            self.socratic_conversation_count = 0
        
        # Create metadata
        metadata = {
            "socratic_mode": True,
            "socratic_conversation_count": self.socratic_conversation_count,
            "socratic_complete": is_complete,
            "agent": "socratic",
            "state": "differential_diagnosis",
            "current_phase": "differential_diagnosis"
        }
        
        return TutorResponse(
            content=cleaned_response,
            tools_used=["socratic"],
            metadata=metadata,
            feedback_examples=[]
        )
    
    async def _call_socratic_agent(self, message: str, context: TutorContext) -> str:
        """Call the socratic agent directly."""
        from microtutor.agents.socratic import run_socratic
        
        # Prepare conversation history for socratic agent
        conversation_history = []
        if hasattr(context, 'conversation_history') and context.conversation_history:
            conversation_history = context.conversation_history
        
        # Call socratic agent
        socratic_response = run_socratic(
            input_text=message,
            case=context.case_description,
            history=conversation_history,
            model=context.model_name
        )
        
        return socratic_response
    
    async def _handle_phase_specific_routing(self, message: str, context: TutorContext) -> Optional[TutorResponse]:
        """
        Handle routing to phase-specific agents based on current phase.
        
        Args:
            message: The user's message
            context: Tutor context
            
        Returns:
            TutorResponse if routed to phase-specific agent, None otherwise
        """
        current_phase = context.current_state
        
        # Map phases to their corresponding agents
        phase_agent_map = {
            TutorState.INFORMATION_GATHERING: "patient",
            TutorState.PROBLEM_REPRESENTATION: "problem_representation", 
            TutorState.DIFFERENTIAL_DIAGNOSIS: "socratic",
            TutorState.TESTS: "tests_management",
            TutorState.MANAGEMENT: "tests_management",
            TutorState.FEEDBACK: "feedback"
        }
        
        agent_name = phase_agent_map.get(current_phase)
        if not agent_name:
            logger.info(f"No phase-specific agent for phase: {current_phase}")
            return None
        
        logger.info(f"Routing to phase-specific agent: {agent_name} for phase: {current_phase}")
        
        try:
            # Execute the phase-specific agent
            result = self.tool_engine.execute_tool(agent_name, {
                'input_text': message,
                'case': context.case_description,
                'conversation_history': context.conversation_history or [],
                'model': context.model_name
            })
            
            if result['success']:
                response_content = result['result']
                
                # Check for completion signals and handle phase transitions
                completion_signals = {
                    'problem_representation': '[PROBLEM_REPRESENTATION_COMPLETE]',
                    'tests_management': '[TESTS_MANAGEMENT_COMPLETE]',
                    'feedback': '[FEEDBACK_COMPLETE]'
                }
                
                completion_signal = completion_signals.get(agent_name)
                is_complete = completion_signal and completion_signal in response_content
                
                # Clean response if completion signal present
                if is_complete and completion_signal:
                    response_content = response_content.replace(completion_signal, "").strip()
                
                # Handle phase transitions based on completion
                if is_complete:
                    next_phase = self._get_next_phase(current_phase)
                    if next_phase:
                        context.current_state = next_phase
                        logger.info(f"Phase transition: {current_phase} -> {next_phase}")
                
                # Create metadata
                metadata = {
                    "phase_agent": agent_name,
                    "current_phase": current_phase.value,
                    "phase_complete": is_complete,
                    "agent": agent_name
                }
                
                return TutorResponse(
                    content=response_content,
                    tools_used=[agent_name],
                    metadata=metadata,
                    feedback_examples=[]
                )
            else:
                logger.error(f"Phase-specific agent {agent_name} failed: {result.get('error', 'Unknown error')}")
                return None
                
        except Exception as e:
            logger.error(f"Error in phase-specific routing for {agent_name}: {e}")
            return None
    
    def _get_next_phase(self, current_phase: TutorState) -> Optional[TutorState]:
        """Get the next phase in the sequence."""
        phase_sequence = [
            TutorState.INFORMATION_GATHERING,
            TutorState.PROBLEM_REPRESENTATION,
            TutorState.DIFFERENTIAL_DIAGNOSIS,
            TutorState.TESTS,
            TutorState.MANAGEMENT,
            TutorState.FEEDBACK
        ]
        
        try:
            current_index = phase_sequence.index(current_phase)
            if current_index < len(phase_sequence) - 1:
                return phase_sequence[current_index + 1]
        except ValueError:
            pass
        
        return None
    
    def _call_tutor_with_tools_and_phase(
        self,
        messages: List[Dict[str, str]],
        case_description: str,
        model: str,
        use_azure: Optional[bool] = None
    ) -> tuple[str, Optional[Dict[str, Any]], List[str]]:
        """Call tutor LLM with native function calling and phase management."""
        # When conversation_history is provided, chat_complete uses that instead of system_prompt/user_prompt
        # So we only need to pass the conversation history for proper context
        response = chat_complete(
            system_prompt="",  # Not used when conversation_history is provided
            user_prompt="",    # Not used when conversation_history is provided
            model=model,
            tools=self.tool_schemas,
            conversation_history=messages,  # Pass full conversation history for proper context
            fallback_model="gpt-4.1",  # Use GPT-4.1 as fallback
            use_azure=use_azure
        )
        
        phase_data = None
        tools_used = []
        
        # Handle None response (all retries failed)
        if response is None:
            logger.error("LLM returned None after all retries")
            # Try a simpler fallback approach
            try:
                # Extract the last user message for fallback
                last_user_msg = ""
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        last_user_msg = msg.get("content", "")
                        break
                
                simple_response = chat_complete(
                    system_prompt="You are a helpful microbiology tutor. Provide a brief, helpful response.",
                    user_prompt=last_user_msg,
                    model="gpt-4.1",  # Use reliable fallback
                    max_retries=3
                )
                if simple_response and simple_response.strip():
                    return simple_response, phase_data, tools_used
            except Exception as e:
                logger.error(f"Fallback response also failed: {e}")
            
            return "I apologize, but I'm having trouble processing your request right now. Could you please try again?", phase_data, tools_used
        
        # Handle tool calls (native function calling format)
        if isinstance(response, dict) and 'tool_calls' in response:
            tool_calls = response['tool_calls']
            
            if tool_calls and len(tool_calls) > 0:
                # Execute all tool calls
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    logger.info(f"Native function call: {tool_name}({list(tool_args.keys())})")
                    
                    # Track tool usage
                    tools_used.append(tool_name)
                
                # Add context to arguments
                tool_args.update({
                    'case': case_description,
                    'conversation_history': messages,
                    'model': model
                })
                
                # Execute via tool engine
                tool_result = self.tool_engine.execute_tool(tool_name, tool_args)
                
                if tool_result['success']:
                        # Check if this is a phase update tool
                        if tool_name == 'update_phase':
                            try:
                                phase_data = json.loads(tool_result['result'])
                                logger.info(f"[PHASE] Phase update tool called: {phase_data['current_phase']}")
                            except json.JSONDecodeError:
                                logger.warning("Failed to parse phase data from update_phase tool")
                        elif tool_name == 'socratic':
                            # Set socratic mode to True when socratic tool is called
                            self.socratic_mode = True
                            self.socratic_conversation_count = 1
                            # Set phase to differential diagnosis for socratic mode
                            self.current_phase = TutorState.DIFFERENTIAL_DIAGNOSIS
                            logger.info("Entering socratic mode - future messages will route directly to socratic agent")
                            logger.info("Setting phase to differential_diagnosis for socratic mode")
                        else:
                            # Regular tool - return its result
                            return tool_result['result'], phase_data, tools_used
                else:
                    error = tool_result.get('error', {})
                    logger.error(f"Tool failed: {error.get('message', 'Unknown error')}")
                    return f"An error occurred while using the {tool_name} tool.", phase_data, tools_used
            
            # No tool calls, return content
            content = response.get('content', '')
            if not content.strip():
                content = "I apologize, but I'm having trouble processing your request right now. Could you please try again?"
            return content, phase_data, tools_used
        
        # Normal text response
        if not response.strip():
            response = "I apologize, but I'm having trouble processing your request right now. Could you please try again?"
        return response, phase_data, tools_used
    
    def _force_phase_update(self, context: TutorContext, response_text: str, user_message: str) -> None:
        """Force a phase update when LLM doesn't call the update_phase tool."""
        try:
            # Determine phase based on content
            current_phase = self._determine_state(response_text, context.current_state)
            
            # Calculate progress based on conversation length and content
            progress = self._calculate_phase_progress(context.conversation_history, current_phase)
            
            # Generate phase guidance
            guidance = self._generate_phase_guidance(current_phase, progress)
            
            # Create phase data
            phase_data = {
                'current_phase': current_phase.value,
                'phase_locked': self.phase_locked,
                'confidence': 'medium',
                'transition_reason': 'content_analysis',
                'phase_progress': progress,
                'phase_guidance': guidance,
                'completion_criteria': self._get_completion_criteria(current_phase),
                'reasoning': f"Auto-detected phase from content analysis",
                'suggestions': self._get_phase_suggestions(current_phase)
            }
            
            # Update internal state
            self.current_phase = current_phase
            context.current_state = current_phase
            
            logger.info(f"[PHASE] Forced update: {current_phase.value}, progress: {progress:.2f}")
            
        except Exception as e:
            logger.error(f"Error in forced phase update: {e}", exc_info=True)
    
    def _calculate_phase_progress(self, conversation: List[Dict[str, str]], phase: TutorState) -> float:
        """Calculate progress within current phase based on conversation content."""
        if phase == TutorState.INFORMATION_GATHERING:
            # Count history and exam-related questions and responses
            info_indicators = ['symptom', 'history', 'pain', 'fever', 'cough', 'breathing', 'exam', 'physical', 'vital']
            count = sum(1 for msg in conversation 
                       if any(indicator in msg.get('content', '').lower() 
                             for indicator in info_indicators))
            return min(count * 0.1, 1.0)
        
        elif phase == TutorState.DIFFERENTIAL_DIAGNOSIS:
            # Count differential mentions
            diff_indicators = ['differential', 'diagnosis', 'consider', 'rule out', 'likely']
            count = sum(1 for msg in conversation 
                       if any(indicator in msg.get('content', '').lower() 
                             for indicator in diff_indicators))
            return min(count * 0.2, 1.0)
        
        elif phase == TutorState.TESTS:
            # Count test mentions
            test_indicators = ['test', 'lab', 'x-ray', 'ct', 'mri', 'blood', 'urine']
            count = sum(1 for msg in conversation 
                       if any(indicator in msg.get('content', '').lower() 
                             for indicator in test_indicators))
            return min(count * 0.15, 1.0)
        
        elif phase == TutorState.MANAGEMENT:
            # Count treatment mentions
            treatment_indicators = ['treatment', 'medication', 'therapy', 'antibiotic', 'dose']
            count = sum(1 for msg in conversation 
                       if any(indicator in msg.get('content', '').lower() 
                             for indicator in treatment_indicators))
            return min(count * 0.2, 1.0)
        
        return 0.0
    
    def _generate_phase_guidance(self, phase: TutorState, progress: float) -> str:
        """Generate specific guidance for the current phase."""
        if phase == TutorState.INFORMATION_GATHERING:
            if progress < 0.3:
                return "Start by gathering the chief complaint and history of present illness."
            elif progress < 0.7:
                return "Continue asking about symptoms, duration, and associated factors. Include physical examination findings."
            else:
                return "Complete the information gathering with past medical history, social history, and vital signs."
        
        elif phase == TutorState.DIFFERENTIAL_DIAGNOSIS:
            if progress < 0.5:
                return "Present your differential diagnoses with supporting evidence."
            else:
                return "Refine your differentials and explain your reasoning."
        
        elif phase == TutorState.TESTS:
            return "Request appropriate diagnostic tests and explain their rationale."
        
        elif phase == TutorState.MANAGEMENT:
            return "Propose a treatment plan with specific medications and dosages."
        
        return "Continue working through the case systematically."
    
    def _get_completion_criteria(self, phase: TutorState) -> List[str]:
        """Get completion criteria for the current phase."""
        if phase == TutorState.INFORMATION_GATHERING:
            return [
                "Chief complaint identified",
                "History of present illness gathered",
                "Physical examination findings documented",
                "Key symptoms and vital signs recorded"
            ]
        elif phase == TutorState.DIFFERENTIAL_DIAGNOSIS:
            return [
                "At least 3-5 differential diagnoses proposed",
                "Supporting evidence for each diagnosis",
                "Most likely diagnosis identified"
            ]
        elif phase == TutorState.TESTS:
            return [
                "Relevant diagnostic tests identified",
                "Rationale for each test explained",
                "Test results interpreted"
            ]
        elif phase == TutorState.MANAGEMENT:
            return [
                "Treatment plan proposed",
                "Specific medications and dosages",
                "Follow-up plan established"
            ]
        return []
    
    def _get_phase_suggestions(self, phase: TutorState) -> List[str]:
        """Get suggestions for the current phase."""
        if phase == TutorState.INFORMATION_GATHERING:
            return [
                "Ask about symptom onset and progression",
                "Inquire about associated symptoms",
                "Gather past medical history",
                "Perform physical examination"
            ]
        elif phase == TutorState.DIFFERENTIAL_DIAGNOSIS:
            return [
                "Consider common vs. rare diagnoses",
                "Think about red flag symptoms",
                "Use the VINDICATE mnemonic"
            ]
        elif phase == TutorState.TESTS:
            return [
                "Start with basic labs",
                "Consider imaging if indicated",
                "Think about cost-effectiveness"
            ]
        elif phase == TutorState.MANAGEMENT:
            return [
                "Consider patient allergies",
                "Think about drug interactions",
                "Plan for follow-up"
            ]
        return []
    
    def _call_tutor_with_tools(
        self,
        messages: List[Dict[str, str]],
        case_description: str,
        model: str
    ) -> str:
        """Call tutor LLM with native function calling support (legacy method)."""
        response_text, _ = self._call_tutor_with_tools_and_phase(messages, case_description, model)
        return response_text
    
    def _detect_phase_transition(self, response: str, user_message: str, conversation_history: List[Dict[str, str]]) -> Optional[TutorState]:
        """Robust phase transition detection using multiple signals and context analysis."""
        response_lower = response.lower()
        user_lower = user_message.lower()
        
        # 1. Check for explicit phase completion signals in tutor response
        for phase, signal in self.phase_completion_signals.items():
            if signal in response:
                logger.info(f"[PHASE] Completion signal detected: {signal}")
                return self._get_next_phase(phase)
        
        # 2. Check for user transition requests with context validation
        transition_phrases = [
            "let's move on", "move on", "continue", "next phase", "proceed",
            "let's continue", "back to the case", "done with", "finished with",
            "ready for the next", "let's go to", "transition to", "next step",
            "move forward", "let's proceed", "ready to move on"
        ]
        
        if any(phrase in user_lower for phrase in transition_phrases):
            # Validate that user has made sufficient progress in current phase
            if self._validate_phase_completion(user_message, self.current_phase, conversation_history):
                logger.info(f"[PHASE] User transition request validated: {user_message}")
                return self._get_next_phase(self.current_phase.value)
            else:
                logger.info(f"[PHASE] User transition request rejected - insufficient progress")
                return None
        
        # 3. Analyze conversation content for implicit phase transitions
        content_based_transition = self._analyze_content_for_phase_transition(response, user_message)
        if content_based_transition:
            logger.info(f"[PHASE] Content-based transition detected: {content_based_transition}")
            return content_based_transition
        
        return None
    
    def _validate_phase_completion(self, user_message: str, current_phase: TutorState, conversation_history: List[Dict[str, str]]) -> bool:
        """Robust validation that user has made sufficient progress to transition from current phase."""
        if current_phase not in self.phase_validation_rules:
            return True  # Allow transition from completed phase
        
        rules = self.phase_validation_rules[current_phase]
        
        # Check minimum message count
        user_messages = [msg for msg in conversation_history if msg.get("role") == "user"]
        if len(user_messages) < rules['min_messages']:
            logger.info(f"[PHASE] Insufficient messages for phase completion: {len(user_messages)} < {rules['min_messages']}")
            return False
        
        # Analyze recent conversation for phase-relevant content
        recent_messages = conversation_history[-10:] if len(conversation_history) >= 10 else conversation_history
        recent_text = " ".join([msg.get("content", "") for msg in recent_messages]).lower()
        
        # Calculate keyword coverage
        required_keywords = rules['required_keywords']
        found_keywords = [kw for kw in required_keywords if kw in recent_text]
        keyword_coverage = len(found_keywords) / len(required_keywords)
        
        # Check if coverage meets threshold
        meets_threshold = keyword_coverage >= rules['completion_threshold']
        
        # Additional validation: check for phase-specific completion patterns
        completion_patterns = self._get_phase_completion_patterns(current_phase)
        has_completion_pattern = any(pattern in recent_text for pattern in completion_patterns)
        
        # Log validation details
        logger.info(f"[PHASE] Validation for {current_phase}: coverage={keyword_coverage:.2f}, "
                   f"threshold={rules['completion_threshold']}, pattern={has_completion_pattern}")
        
        return meets_threshold or has_completion_pattern
    
    def _get_phase_completion_patterns(self, phase: TutorState) -> List[str]:
        """Get completion patterns specific to each phase."""
        patterns = {
            TutorState.INFORMATION_GATHERING: [
                "sufficient history", "enough information", "gathered enough",
                "complete history", "thorough exam", "comprehensive history"
            ],
            TutorState.PROBLEM_REPRESENTATION: [
                "problem representation", "illness script", "clinical reasoning",
                "key findings", "presentation summary", "case summary"
            ],
            TutorState.DIFFERENTIAL_DIAGNOSIS: [
                "differential diagnosis", "differentials", "ddx complete",
                "considered all", "comprehensive differentials"
            ],
            TutorState.INVESTIGATIONS: [
                "sufficient evidence", "enough tests", "investigation complete",
                "diagnostic workup", "test results"
            ],
            TutorState.TREATMENT: [
                "treatment plan", "management plan", "therapeutic approach",
                "treatment strategy", "management strategy"
            ]
        }
        return patterns.get(phase, [])
    
    def _analyze_content_for_phase_transition(self, response: str, user_message: str) -> Optional[TutorState]:
        """Analyze conversation content to detect implicit phase transitions."""
        combined_text = f"{response} {user_message}".lower()
        
        # Define phase transition indicators
        phase_indicators = {
            TutorState.PROBLEM_REPRESENTATION: [
                "problem representation", "illness script", "clinical reasoning",
                "summarize", "key findings", "presentation"
            ],
            TutorState.DIFFERENTIAL_DIAGNOSIS: [
                "differential diagnosis", "differentials", "ddx", "consider",
                "suspect", "think it's", "most likely"
            ],
            TutorState.INVESTIGATIONS: [
                "investigation", "test", "culture", "lab work", "imaging",
                "order", "request", "check"
            ],
            TutorState.TREATMENT: [
                "treatment", "management", "therapy", "medication", "antibiotic",
                "treat", "manage", "prescribe"
            ],
            TutorState.COMPLETED: [
                "feedback", "conclusion", "summary", "review", "performance",
                "well done", "excellent work"
            ]
        }
        
        # Check for strong indicators of phase transition
        for phase, indicators in phase_indicators.items():
            if any(indicator in combined_text for indicator in indicators):
                # Additional validation: check if this is a natural progression
                if self._is_valid_phase_progression(self.current_phase, phase):
                    return phase
        
        return None
    
    def _is_valid_phase_progression(self, current_phase: TutorState, target_phase: TutorState) -> bool:
        """Validate that phase progression follows logical sequence."""
        phase_order = [
            TutorState.INFORMATION_GATHERING,
            TutorState.PROBLEM_REPRESENTATION,
            TutorState.DIFFERENTIAL_DIAGNOSIS,
            TutorState.INVESTIGATIONS,
            TutorState.TREATMENT,
            TutorState.COMPLETED
        ]
        
        try:
            current_index = phase_order.index(current_phase)
            target_index = phase_order.index(target_phase)
            return target_index > current_index  # Can only move forward
        except ValueError:
            return False
    
    
    def _get_next_phase(self, current_phase: str) -> TutorState:
        """Get the next phase in sequence."""
        phase_sequence = [
            TutorState.INFORMATION_GATHERING,
            TutorState.PROBLEM_REPRESENTATION,
            TutorState.DIFFERENTIAL_DIAGNOSIS,
            TutorState.INVESTIGATIONS,
            TutorState.TREATMENT,
            TutorState.COMPLETED
        ]
        
        try:
            current_index = phase_sequence.index(TutorState(current_phase))
            if current_index < len(phase_sequence) - 1:
                return phase_sequence[current_index + 1]
            else:
                return TutorState.COMPLETED
        except (ValueError, IndexError):
            logger.warning(f"[PHASE] Unknown phase: {current_phase}")
            return TutorState.INFORMATION_GATHERING
    
    def _determine_state(self, response: str, current_state: TutorState) -> TutorState:
        """Determine new state based on response content (fallback method)."""
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
