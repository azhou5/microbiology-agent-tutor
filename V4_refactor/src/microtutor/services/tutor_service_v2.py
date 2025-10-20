from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple, Protocol, Callable
from dataclasses import dataclass
from functools import lru_cache
from datetime import datetime
import logging
import os
import json
import asyncio

from microtutor.models.domain import TutorContext, TutorResponse, TutorState
from microtutor.core.logging_config import log_agent_context
from microtutor.tools import get_tool_engine
from microtutor.core.config_helper import config as global_config  # read-only
from microtutor.core.tutor_prompt import get_system_message_template
from microtutor.agents.case import get_case
from microtutor.core.llm_client import LLMClient
from microtutor.services.guidelines_cache import get_guidelines_cache

logger = logging.getLogger(__name__)

# -------- Collaborator Protocols (interfaces) --------

class ToolEngine(Protocol):
    def get_tool_schemas(self) -> List[Dict[str, Any]]: ...
    def list_tools(self) -> List[str]: ...
    def execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]: ...

class FeedbackClient(Protocol):
    def get_examples_for_tool(
        self,
        user_input: str,
        conversation_history: List[Dict[str, str]],
        tool_name: str,
        include_feedback: bool,
        similarity_threshold: Optional[float],
    ) -> str: ...
    def retrieve_feedback_examples(
        self,
        current_message: str,
        conversation_history: List[Dict[str, str]],
        message_type: str,
        k: int,
        similarity_threshold: Optional[float],
    ) -> List[Dict[str, Any]]: ...

# -------- Data configuration --------

@dataclass(frozen=True)
class ServiceConfig:
    model_name: str
    enable_feedback: bool = True
    direct_routing_agents: Tuple[str, ...] = ()
    fallback_model: str = "gpt-4.1"
    hpi_json_relpath: str = os.path.join("data", "cases", "cached", "ambiguous_with_ages.json")

# -------- Utilities --------

PHASE_DISPLAY_MAPPING = {
    "Information Gathering": TutorState.INFORMATION_GATHERING,
    "Differential Diagnosis": TutorState.DIFFERENTIAL_DIAGNOSIS,
    "Differential Diagnosis & Clinical Reasoning": TutorState.DIFFERENTIAL_DIAGNOSIS,
    "Tests & Management": TutorState.TESTS_MANAGEMENT,
    "Feedback": TutorState.FEEDBACK,
}
PHASE_AGENT_MAPPING = {
    TutorState.INFORMATION_GATHERING: "patient",
    TutorState.DIFFERENTIAL_DIAGNOSIS: "socratic",
    TutorState.TESTS_MANAGEMENT: "tests_management",
    TutorState.FEEDBACK: "feedback",
}
TOOL_TO_PHASE = {
    "patient": TutorState.INFORMATION_GATHERING,
    "socratic": TutorState.DIFFERENTIAL_DIAGNOSIS,
    "tests_management": TutorState.TESTS_MANAGEMENT,
    "feedback": TutorState.FEEDBACK,
}

@lru_cache(maxsize=1)
def _load_hpi_json(hpi_path: str) -> Dict[str, str]:
    try:
        with open(hpi_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("HPI JSON load failed: %s", e)
        return {}

def _system_message_for_case(case_text: str) -> str:
    tmpl = get_system_message_template()
    return tmpl.format(case=case_text, Examples_of_Good_and_Bad_Responses="")

def _ensure_system_message(context: TutorContext, case_text: str) -> None:
    # ensure a system message at index 0
    sys_idx = next((i for i, m in enumerate(context.conversation_history) if m.get("role") == "system"), None)
    if sys_idx is None:
        context.conversation_history.insert(0, {"role": "system", "content": _system_message_for_case(case_text)})
    elif sys_idx != 0:
        context.conversation_history.insert(0, context.conversation_history.pop(sys_idx))

def _determine_phase_from_tools(tools_used: List[str], current: TutorState) -> TutorState:
    if not tools_used:
        return current
    return TOOL_TO_PHASE.get(tools_used[0], current)

def _validate_phase_transition(phase_name: str) -> Tuple[bool, Optional[TutorState], Optional[str]]:
    if not phase_name or not isinstance(phase_name, str):
        return False, None, "Phase name must be a non-empty string"
    pn = phase_name.strip()
    if pn not in PHASE_DISPLAY_MAPPING:
        return False, None, f"Unknown phase '{pn}'. Available: {', '.join(PHASE_DISPLAY_MAPPING.keys())}"
    return True, PHASE_DISPLAY_MAPPING[pn], None

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

        # Guidelines pre-fetching service
        self.enable_guidelines_prefetch = enable_guidelines_prefetch
        if enable_guidelines_prefetch:
            self.guidelines_cache = get_guidelines_cache(use_tooluniverse=False)
            logger.info("Guidelines pre-fetching enabled")
        else:
            self.guidelines_cache = None

        self.interaction_counter = 0

        self._project_root = project_root or os.path.dirname(__file__)
        self._hpi_path = os.path.join(self._project_root, self.cfg.hpi_json_relpath)

        logger.info("TutorService init: tools=%s model=%s",
                    self.tool_engine.list_tools(), self.cfg.model_name)

    # ---------- Public API ----------

    async def start_case(
        self,
        organism: str,
        case_id: str,
        model_name: Optional[str] = None,
        use_hpi_only: bool = False,
    ) -> TutorResponse:
        t0 = datetime.now()
        model = model_name or self.cfg.model_name

        case_desc = get_case(organism, use_hpi_only=use_hpi_only)
        if not case_desc:
            raise ValueError(f"Could not load case for organism: {organism}")

        # Pre-fetch guidelines asynchronously (in background)
        guidelines_task = None
        if self.enable_guidelines_prefetch and self.guidelines_cache:
            guidelines_task = asyncio.create_task(
                self.guidelines_cache.prefetch_guidelines_for_organism(organism, case_desc)
            )

        # Always try cached HPI json first (unless explicitly disabled)
        response_text: str
        hpi = _load_hpi_json(self._hpi_path).get(organism.replace(" ", "_"))
        
        if hpi:
            # Use cached HPI data
            response_text = (
                "Welcome to today's case.\n\n"
                f"{hpi}\n\n"
                "Begin by asking a more detailed history, requesting specific physical exam findings, "
                "and ordering initial studies. Then we will move onto differential diagnosis, "
                "management and feedback."
            )
        else:
            # Fallback to LLM intro when cached data not available
            response_text = self._intro_via_llm(case_desc, model)

        # Wait for guidelines to complete (if started)
        guidelines = None
        if guidelines_task:
            try:
                guidelines = await guidelines_task
                logger.info(f"Guidelines pre-fetched for {organism}")
            except Exception as e:
                logger.warning(f"Failed to pre-fetch guidelines for {organism}: {e}")

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
                "guidelines_prefetched": guidelines is not None
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

        # 0) Always ensure case + system message first (before any routing)
        if not context.case_description:
            context.case_description = get_case(context.organism)
            if not context.case_description:
                raise ValueError(f"Could not load case for organism: {context.organism}")
        _ensure_system_message(context, context.case_description)
        
        # 0.5) Pre-fetch guidelines if not already done
        if (self.enable_guidelines_prefetch and 
            self.guidelines_cache and 
            not context.guidelines):
            try:
                context.guidelines = await self.guidelines_cache.prefetch_guidelines_for_organism(
                    context.organism, context.case_description
                )
                context.guidelines_fetched_at = datetime.now()
                logger.info(f"Guidelines fetched for {context.organism}")
            except Exception as e:
                logger.warning(f"Failed to fetch guidelines: {e}")

        # 1) Direct routing override
        if self.cfg.direct_routing_agents:
            agent = PHASE_AGENT_MAPPING.get(context.current_state)
            if agent and agent in self.cfg.direct_routing_agents:
                routed = await self._route_to_phase_agent(agent, message, context)
                if routed:
                    return self._finalize_response(routed, t0)

        # 2) Phase transition command (if present)
        if "Let's move onto phase:" in message:
            phase_name = message.split("Let's move onto phase:")[1].strip()
            ok, new_state, err = _validate_phase_transition(phase_name)
            if not ok:
                return self._finalize_response(
                    TutorResponse(content=f"Phase transition error: {err}", tools_used=[], metadata={"error": "invalid_phase_transition"}),
                    t0
                )
            context.current_state = new_state  # update and continue

        # 3) Normal phase routing (agent decides or fall through)
        agent = PHASE_AGENT_MAPPING.get(context.current_state)
        routed = await self._route_to_phase_agent(agent, message, context)
        if routed:
            return self._finalize_response(routed, t0)

        # 5) Optional feedback (no global mutations)
        use_feedback = (self.feedback_client is not None) if feedback_enabled is None else (feedback_enabled and self.feedback_client is not None)
        feedback_str, feedback_struct = ("", [])
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
                message_type="tutor",
                k=3,
                similarity_threshold=feedback_threshold,
            ) or []
            feedback_struct = retrieved

        # 6) Log & add user message
        self.interaction_counter += 1
        sys_msg = context.conversation_history[0]["content"]
        log_agent_context(
            case_id=context.case_id,
            agent_name="tutor",
            interaction_id=self.interaction_counter,
            system_prompt=sys_msg,
            user_prompt=message,
            feedback_examples=feedback_str,
            full_context=message + ("\n\n" + feedback_str if feedback_str else ""),
            metadata={"model": context.model_name, "feedback_enabled": bool(use_feedback), "organism": context.organism},
        )
        enhanced_message = message + ("\n\n" + feedback_str if feedback_str else "")
        context.conversation_history.append({"role": "user", "content": enhanced_message})

        # 7) LLM call with tools
        response = self.llm_client.generate(
            messages=context.conversation_history,
            model=context.model_name,
            tools=self.tool_engine.get_tool_schemas(),
            retries=4,
            fallback_model=self.cfg.fallback_model
        )

        # 8) Handle tool calls or direct text response
        tools_used: List[str] = []
        if isinstance(response, dict) and "tool_calls" in response:
            # Tool calling flow: execute ALL tools and return results directly
            # In our educational system, tools are agentic responses (patient, socratic, etc.)
            # that provide the final response - no synthesis needed
            result_text, tools_used = self._execute_all_tool_calls(response["tool_calls"], context)
        else:
            # Direct text response (no tools called)
            result_text = response if isinstance(response, str) else (response.get("content", "") if response else "")

        if not result_text:
            raise ValueError("LLM returned empty response.")

        # 9) Update convo + phase; return
        context.conversation_history.append({"role": "assistant", "content": result_text})
        new_state = _determine_phase_from_tools(tools_used, context.current_state)
        context.current_state = new_state

        return self._finalize_response(
            TutorResponse(
                content=result_text,
                tools_used=tools_used,
                metadata={"case_id": context.case_id, "state": new_state.value, "organism": context.organism},
                feedback_examples=feedback_struct,
            ),
            t0,
        )

    # ---------- Internals ----------

    def _intro_via_llm(self, case_desc: str, model: str) -> str:
        """Fallback to LLM for intro when cached HPI data not available."""
        sys = _system_message_for_case(case_desc)
        initial_prompt = (
            "Welcome the student and introduce the case. "
            "Present the initial chief complaint and basic demographics."
        )
        messages = [
            {"role": "system", "content": sys},
            {"role": "user", "content": initial_prompt}
        ]
        resp = self.llm_client.generate(
            messages=messages,
            model=model,
            tools=None,  # No tools needed for intro
            retries=4,
            fallback_model=self.cfg.fallback_model
        )
        if not resp:
            return "Welcome to today's case. I'm having trouble generating the case details right now. Please try starting a new case."
        return resp if isinstance(resp, str) else resp.get("content", "")

    async def _route_to_phase_agent(self, agent: Optional[str], message: str, context: TutorContext) -> Optional[TutorResponse]:
        if not agent:
            return None
        # Respect direct routing whitelist if set
        if self.cfg.direct_routing_agents and agent not in self.cfg.direct_routing_agents:
            return None

        try:
            result = self.tool_engine.execute_tool(agent, {
                "input_text": message,
                "case": context.case_description,
                "conversation_history": context.conversation_history or [],
                "model": context.model_name,
            })
            if not result.get("success"):
                logger.error("Phase agent %s failed: %s", agent, result.get("error"))
                return None

            content = str(result.get("result", ""))
            completion_token = {"tests_management": "[TESTS_MANAGEMENT_COMPLETE]", "feedback": "[FEEDBACK_COMPLETE]"}.get(agent)
            complete = bool(completion_token and completion_token in content)
            if complete and completion_token:
                content = content.replace(completion_token, "").strip()

            if complete:
                nxt = self._next_phase(context.current_state)
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

    def _execute_all_tool_calls(
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
            
            # Add guidelines to tool arguments if available and tool needs them
            if (context.guidelines and 
                tool_name in ["tests_management", "mcq_tool"] and 
                self.guidelines_cache):
                guidelines_context = self.guidelines_cache.format_guidelines_for_tool(
                    context.guidelines, tool_name
                )
                tool_args["guidelines_context"] = guidelines_context
            
            # Execute tool
            logger.info(f"Executing tool: {tool_name} with args={tool_args}")
            result = self.tool_engine.execute_tool(tool_name, tool_args)
            
            # Collect results
            if result.get("success"):
                results.append(str(result.get("result", "")))
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

    def _next_phase(self, current: TutorState) -> Optional[TutorState]:
        order = [
            TutorState.INFORMATION_GATHERING,
            TutorState.DIFFERENTIAL_DIAGNOSIS,
            TutorState.TESTS_MANAGEMENT,
            TutorState.FEEDBACK,
        ]
        try:
            i = order.index(current)
            return order[i + 1] if i + 1 < len(order) else None
        except ValueError:
            return None

    def _finalize_response(self, resp: TutorResponse, t0: datetime) -> TutorResponse:
        resp.processing_time_ms = (datetime.now() - t0).total_seconds() * 1000
        return resp
