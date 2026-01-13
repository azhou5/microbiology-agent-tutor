from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging
import os
import json

from microtutor.schemas.domain.domain import TutorContext, TutorResponse, TutorState
from microtutor.core.logging.logging_config import log_agent_context
from microtutor.tools import get_tool_engine
from microtutor.core.config.config_helper import config as global_config  # read-only
from microtutor.prompts.tutor_prompt import (
    get_first_pt_sentence_generation_system_prompt,
    get_first_pt_sentence_generation_user_prompt
)
from microtutor.services.case import get_case
from microtutor.core.llm.llm_client import LLMClient
from microtutor.services.guideline.cache import get_guidelines_cache
from microtutor.utils.conversation_utils import (
    filter_system_messages,
    prepare_llm_messages,
    get_cached_first_pt_sentence,
    has_cached_case
)
from microtutor.utils.phase_utils import (
    PHASE_AGENT_MAPPING,
    determine_phase_from_tools,
    validate_phase_transition,
    get_next_phase,
    get_completion_token,
    is_phase_complete,
    is_forward_transition
)
from microtutor.prompts.tutor_prompt import get_system_message_template
from microtutor.utils.protocols import ToolEngine, FeedbackClient

logger = logging.getLogger(__name__)

# -------- Data configuration --------

@dataclass(frozen=True)
class ServiceConfig:
    model_name: str
    enable_feedback: bool = True
    fallback_model: str = "gpt-5"
    first_pt_sentence_json_relpath: str = os.path.join("data", "cases", "cached", "ambiguous_with_ages.json")

# -------- TutorService --------

class TutorService:
    def __init__(
        self,
        *,
        cfg: Optional[ServiceConfig] = None,
        tool_engine: Optional[ToolEngine] = None,
        llm_client: Optional[LLMClient] = None,  # Now using concrete LLMClient, not protocol
        feedback_client: Optional[FeedbackClient] = None,
        project_root: Optional[str] = None,
        enable_guidelines_prefetch: bool = True,  # Enable async guideline pre-fetching
    ):
        self.cfg = cfg or ServiceConfig(model_name=global_config.API_MODEL_NAME, enable_feedback=True)
        self.tool_engine: ToolEngine = tool_engine or get_tool_engine()
        self.llm_client = llm_client or LLMClient(model=self.cfg.model_name)
        self.feedback_client = feedback_client if self.cfg.enable_feedback else None
        self.enable_guidelines_prefetch = enable_guidelines_prefetch

        self.interaction_counter = 0

        # Resolve project root: go up 3 levels from services/ to V4_refactor/
        # __file__ is at: V4_refactor/src/microtutor/services/tutor/service.py
        # V4_refactor is at: service.py -> tutor -> services -> microtutor -> src -> V4_refactor (5 levels up)
        if project_root:
            self._project_root = project_root
        else:
            # Go up 5 levels: tutor -> services -> microtutor -> src -> V4_refactor
            self._project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
        
        print(f"[DEBUG] TutorService project_root: {self._project_root}")
        
        # Guidelines cache service (always available, but only used when requested)
        self.guidelines_cache = get_guidelines_cache(project_root=str(self._project_root))
        logger.info("Guidelines cache service initialized")
        self._first_pt_sentence_path = os.path.join(self._project_root, self.cfg.first_pt_sentence_json_relpath)
        self._cached_cases_dir = os.path.join(self._project_root, "data", "cases", "cached")
        
        # Log the resolved paths for debugging
        logger.info(f"TutorService first patient sentence path resolved to: {self._first_pt_sentence_path}")
        logger.info(f"TutorService cached cases directory: {self._cached_cases_dir}")

        logger.info("TutorService init: tools=%s model=%s",
                    self.tool_engine.list_tools(), self.cfg.model_name)

    # ---------- Public API ----------


    def _generate_first_pt_sentence_via_llm(self, case_description: str, model: str) -> str:
        """Generate first patient sentence via LLM in the format of ambiguous_with_ages.json.
        
        The generated sentence should be a brief, ambiguous initial presentation
        similar to the cached examples (e.g., "45-year-old man reports fatigue and expanding skin rash.").
        
        Args:
            case_description: Full case description
            model: Model name to use
            
        Returns:
            Generated first patient sentence
        """
        system_prompt = get_first_pt_sentence_generation_system_prompt()
        user_prompt = get_first_pt_sentence_generation_user_prompt(case_description)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self.llm_client.generate(
            messages=messages,
            model=model,
            tools=None,
            retries=4,
            fallback_model=self.cfg.fallback_model
        )
        
        if not response:
            return "A patient presents with concerning symptoms."
        
        sentence = response if isinstance(response, str) else response.get("content", "")
        # Clean up any extra formatting
        sentence = sentence.strip().strip('"').strip("'")
        
        logger.info(f"Generated first patient sentence via LLM: {sentence[:50]}...")
        return sentence


    async def start_case(
        self,
        organism: str,
        case_id: str,
        model_name: Optional[str] = None,
        enable_guidelines: bool = False,
    ) -> TutorResponse:
        """Start a new case for the given organism.
        
        Flow:
        a) Organism has cached case AND cached first_pt_sentence → use cached sentence
        b) Organism has cached case BUT no cached first_pt_sentence → generate sentence via LLM
        c) Organism has NO cached case → generate case via QDRANT RAG, then generate first_pt_sentence
        
        Args:
            organism: The microorganism name
            case_id: Unique case identifier
            model_name: Optional LLM model to use
            
        Returns:
            TutorResponse with initial welcome message
        """
        t0 = datetime.now()
        model = model_name or self.cfg.model_name

        # Check if organism has cached case (get in-memory cache if available)
        from microtutor.services.case import CaseGeneratorRAGAgent
        case_generator = CaseGeneratorRAGAgent()
        organism_has_cached_case = has_cached_case(
            organism,
            self._cached_cases_dir,
            case_generator_cache=case_generator.case_cache
        )
        
        # Get or generate case description
        case_desc = get_case(organism)
        if not case_desc:
            raise ValueError(f"Could not load or generate case for organism: {organism}")

        # Get first patient sentence
        # a) Check for cached first_pt_sentence
        first_pt_sentence = get_cached_first_pt_sentence(organism, self._first_pt_sentence_path)
        
        if not first_pt_sentence:
            # b) or c) Generate first_pt_sentence via LLM (using the case description)
            logger.info("Generating first patient sentence via LLM")
            first_pt_sentence = self._generate_first_pt_sentence_via_llm(case_desc, model)

        # Format welcome message
        response_text = (
            "Welcome to today's case.\n\n"
            f"{first_pt_sentence}\n\n"
            "Begin by asking a more detailed history, requesting specific physical exam findings, "
            "and ordering initial studies. Then we will move onto differential diagnosis, "
            "management and feedback."
        )

        # Reset guidelines cache for this session if enabled
        if self.enable_guidelines_prefetch and self.guidelines_cache:
            # We don't need to clear the whole cache, just ensure we're starting fresh
            # The client should clear its local state, but we can log it here
            logger.info(f"Starting new case {case_id} - guidelines prefetch enabled: {enable_guidelines}")

        # Return immediately (guidelines load in background)
        dt_ms = (datetime.now() - t0).total_seconds() * 1000
        return TutorResponse(
            content=response_text,
            tools_used=[],
            processing_time_ms=dt_ms,
            metadata={
                "case_id": case_id, 
                "organism": organism, 
                "state": TutorState.INFORMATION_GATHERING.value, 
                "model": model,
                "guidelines_prefetching": self.enable_guidelines_prefetch and self.guidelines_cache is not None,
                "case_source": "cached" if organism_has_cached_case else "generated"
            },
        )

    async def process_message(
        self,
        message: str,
        context: TutorContext,
        feedback_enabled: Optional[bool] = None,
        feedback_threshold: Optional[float] = None,
    ) -> TutorResponse:
        t0 = datetime.now()
        logger.info("process_message: case_id=%s", context.case_id)

        # 0) Filter out any system messages from incoming history (chat history should be clean)
        context.conversation_history = filter_system_messages(context.conversation_history)
        
        # 0.5) Load case description if not already set (needed for agentic tools)
        if not context.case_description and context.organism:
            from microtutor.services.case import get_case
            context.case_description = get_case(context.organism)
            logger.info(f"Loaded case description for organism: {context.organism}")
        
        # 1) Phase transition command (if present) - acts as tool call to activate specific agent
        if "Let's move onto phase:" in message:
            phase_name = message.split("Let's move onto phase:")[1].strip()
            ok, new_state, err = validate_phase_transition(phase_name)
            if not ok:
                return self._finalize_response(
                    TutorResponse(content=f"Phase transition error: {err}", tools_used=[], metadata={"error": "invalid_phase_transition"}),
                    t0
                )
            
            # Enforce forward-only transition
            if not is_forward_transition(context.current_state, new_state):
                return self._finalize_response(
                    TutorResponse(
                        content="We need to complete the current section before moving back. Let's focus on moving forward!", 
                        tools_used=[], 
                        metadata={"error": "backward_phase_transition"}
                    ),
                    t0
                )
            
            # Generate summary if moving forward
            summary = ""
            if new_state != context.current_state:
                summary = await self._generate_section_summary(context, context.current_state)
                
            # Update state and route to the agent for that phase
            context.current_state = new_state
            agent = PHASE_AGENT_MAPPING.get(new_state)
            if agent:
                # IMPORTANT: phase transitions are part of the real conversation.
                # Persist the user's phase-transition command and the phase agent's response
                # so subsequent turns have full continuity (no "restart" feeling).
                if not context.conversation_history:
                    context.conversation_history = []
                if not (
                    context.conversation_history
                    and context.conversation_history[-1].get("role") == "user"
                    and context.conversation_history[-1].get("content") == message
                ):
                    context.conversation_history.append({"role": "user", "content": message})

                # Inject summary into message for the next agent
                routed_message = message
                if summary:
                    routed_message += f"\n\n[SYSTEM] The student has skipped previous sections. Here is a summary of what they skipped:\n{summary}"
                    
                routed = await self._route_to_phase_agent(agent, routed_message, context)
                if routed:
                    # Persist the assistant response from the phase agent into the main history
                    if not (
                        context.conversation_history
                        and context.conversation_history[-1].get("role") == "assistant"
                        and context.conversation_history[-1].get("content") == routed.content
                    ):
                        context.conversation_history.append({"role": "assistant", "content": routed.content})
                    if summary:
                        routed.content = f"**Summary of Skipped Sections:**\n{summary}\n\n---\n\n{routed.content}"
                    return self._finalize_response(routed, t0)
            # If no agent found for phase, continue to LLM routing

        # 2) Optional feedback (no global mutations)
        use_feedback = (self.feedback_client is not None) if feedback_enabled is None else (feedback_enabled and self.feedback_client is not None)
        feedback_str, feedback_struct = ("", [])
        
        # Debug logging for feedback
        logger.info(f"[FEEDBACK_DEBUG] feedback_enabled={feedback_enabled}, feedback_client={self.feedback_client is not None}, use_feedback={use_feedback}")
        
        if use_feedback:
            feedback_str = self.feedback_client.get_examples_for_tool(
                user_input=message,
                conversation_history=context.conversation_history,
                tool_name="tutor",
                include_feedback=True,
                similarity_threshold=feedback_threshold,
            ) or ""
            retrieved = self.feedback_client.retrieve_feedback_examples(
                current_message=message,
                conversation_history=context.conversation_history,
                message_type="all",  # Use "all" to get all feedback types
                k=3,  # Increase to get more examples
                similarity_threshold=feedback_threshold,
            ) or []
            feedback_struct = retrieved
            
            # Debug logging for feedback retrieval
            logger.info(f"[FEEDBACK_DEBUG] Retrieved {len(feedback_struct)} feedback examples")
            if feedback_struct:
                first = feedback_struct[0]
                # Support both dict payloads (adapter) and objects (direct retriever)
                first_text = (
                    (first.get("text", "") if isinstance(first, dict) else getattr(first, "text", ""))
                )
                logger.info(f"[FEEDBACK_DEBUG] First example: {first_text[:50]}...")
            else:
                logger.warning(f"[FEEDBACK_DEBUG] No feedback examples retrieved")

        # 3) Log & add user message to chat history
        self.interaction_counter += 1
        enhanced_message = message + ("\n\n" + feedback_str if feedback_str else "")
        # Avoid duplicate/near-duplicate user messages if the client already included
        # the latest turn in history.
        #
        # Common problematic case:
        # - Client includes the raw `message` as the last user item in history.
        # - Server appends feedback examples to form `enhanced_message`.
        # If we naively append, we end up with two consecutive user turns that are
        # semantically the same, which can confuse routing/tools.
        if context.conversation_history and context.conversation_history[-1].get("role") == "user":
            last_content = context.conversation_history[-1].get("content", "")
            if last_content == enhanced_message:
                pass  # already present
            elif last_content == message and enhanced_message != message:
                # Upgrade the last user message in-place to include feedback context
                context.conversation_history[-1]["content"] = enhanced_message
            else:
                context.conversation_history.append({"role": "user", "content": enhanced_message})
        else:
            context.conversation_history.append({"role": "user", "content": enhanced_message})
        
        # Get system prompt for logging (not stored in history)
        tutor_system_prompt = get_system_message_template().format(
            case=context.case_description, 
            Examples_of_Good_and_Bad_Responses=""
        )
        log_agent_context(
            case_id=context.case_id,
            agent_name="tutor",
            interaction_id=self.interaction_counter,
            system_prompt=tutor_system_prompt,
            user_prompt=message,
            feedback_examples=feedback_str,
            full_context=message + ("\n\n" + feedback_str if feedback_str else ""),
            metadata={"model": context.model_name, "feedback_enabled": bool(use_feedback), "organism": context.organism},
        )

        # 4) LLM call with tools - tutor decides which tool to call
        llm_messages = prepare_llm_messages(context.conversation_history, tutor_system_prompt)
        response = self.llm_client.generate(
            messages=llm_messages,
            model=context.model_name,
            tools=self.tool_engine.get_tool_schemas(),
            retries=4,
            fallback_model=self.cfg.fallback_model
        )

        # 5) Handle tool calls or direct text response
        tools_used: List[str] = []
        if isinstance(response, dict) and "tool_calls" in response:
            # Tool calling flow: execute ALL tools and return results directly
            # In our educational system, tools are agentic responses (patient, socratic, etc.)
            # that provide the final response - no synthesis needed
            result_text, tools_used = await self._execute_all_tool_calls(response["tool_calls"], context)
        else:
            # Direct text response (no tools called)
            result_text = response if isinstance(response, str) else (response.get("content", "") if response else "")

        if not result_text:
            raise ValueError("LLM returned empty response.")

        # 6) Update convo + phase; return
        # Ensure we're not duplicating the assistant's message if it was already added by a tool
        # In this architecture, the tool output IS the assistant's message, so we append it here.
        if not (
            context.conversation_history
            and context.conversation_history[-1].get("role") == "assistant"
            and context.conversation_history[-1].get("content") == result_text
        ):
            context.conversation_history.append({"role": "assistant", "content": result_text})
        
        # Determine new phase based on tools used
        proposed_state = determine_phase_from_tools(tools_used, context.current_state)
        
        # Enforce forward-only for implicit transitions too
        # If tool tries to go back, we stay in current state (or we could warn)
        if not is_forward_transition(context.current_state, proposed_state):
            logger.warning(f"Prevented backward transition from {context.current_state} to {proposed_state} triggered by tools {tools_used}")
            new_state = context.current_state
        else:
            new_state = proposed_state
            
        context.current_state = new_state

        return self._finalize_response(
            TutorResponse(
                content=result_text,
                tools_used=tools_used,
                metadata={
                    "case_id": context.case_id, 
                    "state": new_state.value, 
                    "organism": context.organism,
                    "guidelines_loaded": bool(context.guidelines)
                },
                feedback_examples=feedback_struct,
            ),
            t0,
        )

    async def _generate_section_summary(self, context: TutorContext, phase: TutorState) -> str:
        """Generate a summary of the key points from the completed phase.
        
        Args:
            context: Current tutor context
            phase: The phase that was just completed
            
        Returns:
            String summary of the phase
        """
        try:
            # Filter history to get relevant messages (simple heuristic: last 10 messages or since start)
            # In a real system, we might want to tag messages with phases
            relevant_history = context.conversation_history[-10:] if len(context.conversation_history) > 10 else context.conversation_history
            
            prompt = f"""
            The student is skipping the remainder of the {phase.value} section.
            Please acknowledge that we are skipping ahead, and provide a concise summary of the key clinical information that would have been covered in the skipped sections (e.g. Information Gathering, Differential Diagnosis) for a patient with {context.organism}.
            
            IMPORTANT: Do NOT include information from the section we are skipping TO (e.g. do not include tests or management if we are skipping to Tests & Management). Only summarize the history and exam findings.
            
            Structure the summary clearly:
            - **Skipped Information Summary:** [Concise summary of history/exam/DDx]
            - **Key Takeaways:** [Most critical points to carry forward]
            
            Keep it concise (2-3 sentences max per section) and easy to read at a glance.
            """
            
            messages = prepare_llm_messages(relevant_history, prompt)
            
            response = self.llm_client.generate(
                messages=messages,
                model=context.model_name,
                tools=None, # No tools for summarization
                retries=2
            )
            
            summary = response if isinstance(response, str) else response.get("content", "")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating phase summary: {e}")
            return ""

    # ---------- Internals ----------

    async def _load_and_format_guidelines(
        self,
        context: TutorContext,
        tool_name: str,
        tool_args: Dict[str, Any]
    ) -> Optional[str]:
        """Load guidelines and inject into tool args. Returns debug text if loaded."""
        if not self.guidelines_cache:
            return None

        try:
            # Always load for management/MCQ tools
            if not context.guidelines:
                context.guidelines = await self.guidelines_cache.prefetch_guidelines_for_organism(
                    context.organism, context.case_description
                )
                context.guidelines_fetched_at = datetime.now()
                logger.info(f"Guidelines loaded for {context.organism} (requested by {tool_name})")

            # Format and add to tool args
            if context.guidelines:
                guidelines_context = self.guidelines_cache.format_guidelines_for_tool(
                    context.guidelines, tool_name
                )
                tool_args["guidelines_context"] = guidelines_context
                
                # Generate debug text for UI
                found_items = context.guidelines.get("found_guidelines", [])
                if found_items:
                    debug_lines = ["\n\n**[DEBUG] Auto-loaded Guidelines:**"]
                    for i, item in enumerate(found_items, 1):
                        title = item.get("title", "Unknown Source")
                        score = item.get("score", "N/A") # Score might not be in item directly depending on implementation
                        debug_lines.append(f"{i}. {title}")
                    return "\n".join(debug_lines)
                    
        except Exception as e:
            logger.warning(f"Failed to load guidelines: {e}")
            
        return None

    async def _route_to_phase_agent(self, agent: Optional[str], message: str, context: TutorContext) -> Optional[TutorResponse]:
        """
        Route message directly to a phase-specific agent.
        
        Used for phase transition commands where user explicitly requests a phase change.
        
        Args:
            agent: Agent name to route to
            message: User message
            context: Current conversation context
            
        Returns:
            TutorResponse if routing succeeds, None otherwise
        """
        if not agent:
            return None

        try:
            # Pass filtered history (no system prompts) to tools
            # Tools will add their own system prompt when calling LLM
            filtered_history = filter_system_messages(context.conversation_history or [])
            
            tool_args = {
                "input_text": message,
                "case": context.case_description,
                "conversation_history": filtered_history,
                "model": context.get_model_name(),
            }
            
            # Auto-load guidelines for management phase
            guidelines_debug = None
            if agent == "tests_management":
                guidelines_debug = await self._load_and_format_guidelines(context, agent, tool_args)
            
            result = self.tool_engine.execute_tool(agent, tool_args)
            if not result.get("success"):
                logger.error("Phase agent %s failed: %s", agent, result.get("error"))
                return None

            content = str(result.get("result", ""))
            
            # Append debug info if available
            if guidelines_debug:
                content += guidelines_debug

            completion_token = get_completion_token(agent)
            complete = is_phase_complete(content, agent)
            if complete and completion_token:
                content = content.replace(completion_token, "").strip()

            if complete:
                nxt = get_next_phase(context.current_state)
                if nxt:
                    context.current_state = nxt
                    logger.info("Phase auto-transition: %s -> %s", context.current_state, nxt)

            return TutorResponse(
                content=content,
                tools_used=[agent],
                metadata={"phase_agent": agent, "current_phase": context.current_state.value, "phase_complete": complete},
            )
        except Exception as e:
            logger.error("Phase routing error (%s): %s", agent, e)
            return None

    async def _execute_all_tool_calls(
        self, 
        tool_calls: List[Any],
        context: TutorContext
    ) -> Tuple[str, List[str]]:
        """
        Execute all tool calls and return results directly.
        
        In our educational system, tools are agentic responses (patient, socratic, etc.)
        that provide complete responses to the student. Unlike standard tool calling patterns,
        we DON'T feed results back to the LLM for synthesis - the tool output IS the response.
        
        This follows ToolUniverse's pattern of handling multiple tool calls but adapted
        for our human-in-the-loop educational interaction model.
        
        Args:
            tool_calls: List of tool calls from LLM
            context: Current conversation context
            
        Returns:
            Tuple of (combined_response_text, list_of_tool_names_used)
        """
        if not tool_calls:
            return "", []
        
        tools_used = []
        results = []
        
        # Execute ALL tool calls (not just first)
        for tool_call in tool_calls:
            # Extract tool info
            if hasattr(tool_call, 'function'):
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments
            else:
                tool_name = tool_call["function"]["name"]
                tool_args = tool_call["function"]["arguments"]
            
            # Parse JSON arguments
            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse tool arguments for {tool_name}: {e}")
                    tool_args = {}
            
            # Load and add guidelines if tool needs them (Management or MCQ)
            guidelines_debug = None
            if tool_name in ["tests_management", "mcq_tool"]:
                guidelines_debug = await self._load_and_format_guidelines(context, tool_name, tool_args)
            
            # Augment tool args with context for agentic tools
            # These tools need case, conversation_history, model to function properly
            if tool_name in ["patient", "socratic", "tests_management", "feedback", "mcq_tool", "post_case_assessment"]:
                tool_args["case"] = context.case_description or ""
                tool_args["conversation_history"] = context.conversation_history or []
                tool_args["model"] = context.model_name or global_config.API_MODEL_NAME or "gpt-5"
                tool_args["case_id"] = context.case_id or ""
            elif tool_name == "hint":
                # Hint tool does NOT get the full case - only conversation history
                # This prevents leaking undiscovered case information
                tool_args["case"] = ""  # No case access
                tool_args["conversation_history"] = context.conversation_history or []
                tool_args["model"] = context.model_name or global_config.API_MODEL_NAME or "gpt-5"
                tool_args["case_id"] = context.case_id or ""
            
            # Execute tool
            hist_len = len(context.conversation_history or [])
            logger.info(
                f"Executing tool: {tool_name} with args keys={list(tool_args.keys())} history_len={hist_len}"
            )
            if hist_len:
                try:
                    last = context.conversation_history[-1]
                    logger.info(
                        f"[TOOL_CTX] last_msg role={last.get('role')} content={str(last.get('content',''))[:120]}..."
                    )
                except Exception:
                    pass
            result = self.tool_engine.execute_tool(tool_name, tool_args)
            
            # Collect results
            if result.get("success"):
                res_content = str(result.get("result", ""))
                # If guidelines were loaded and debug info is available, append it to the response
                if guidelines_debug:
                    res_content += f"\n\n{guidelines_debug}"
                results.append(res_content)
            else:
                error = result.get("error", {})
                error_msg = f"Tool {tool_name} failed: {error.get('message', 'Unknown error')}"
                logger.error(error_msg)
                results.append(error_msg)
            
            tools_used.append(tool_name)
        
        # Combine results if multiple tools were called
        # In practice, we typically only call one agentic tool at a time,
        # but this handles the general case
        combined_result = "\n\n---\n\n".join(results) if len(results) > 1 else (results[0] if results else "")
        
        return combined_result, tools_used

    def _finalize_response(self, resp: TutorResponse, t0: datetime) -> TutorResponse:
        resp.processing_time_ms = (datetime.now() - t0).total_seconds() * 1000
        return resp
