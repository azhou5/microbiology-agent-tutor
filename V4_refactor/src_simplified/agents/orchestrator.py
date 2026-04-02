import hashlib
import json
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any

from ..utils.llm import chat_complete
from ..utils.case_loader import CaseLoader
from ..tools.csv_tool import CSVTool
from queue import Queue, Empty

from ..config.config import config
from ..prompts import (
    HISTORY_DEBRIEF_PROMPT,
    FEEDBACK_SYSTEM_PROMPT,
    CASE_SUMMARY_PROMPT,
    CHECKLIST_GENERATION_PROMPT,
    CHECKLIST_UPDATE_PROMPT,
    EMR_NOTE_EXTRACTION_PROMPT,
    EMR_FULL_REBUILD_PROMPT,
)
from .patient_agent import PatientAgent
from .ddx_agent import DdxAgent
from .tx_agent import TxAgent
from .pathophys_epi_agent import PathophysEpiAgent
from .quiz_agent import QuizAgent
from .feedback_agent import FeedbackAgent

logger = logging.getLogger(__name__)

# Canonical ordering when the user selects multiple modules.
MODULE_ORDER = ["history_taking", "ddx_deep_dive", "tx_deep_dive", "pathophys_epi"]

MODULE_LABEL_TO_ID: dict[str, str] = {
    "history taking": "history_taking",
    "history": "history_taking",
    "ddx deep dive": "ddx_deep_dive",
    "differential diagnosis deep dive": "ddx_deep_dive",
    "ddx": "ddx_deep_dive",
    "management deep dive": "tx_deep_dive",
    "tx deep dive": "tx_deep_dive",
    "treatment": "tx_deep_dive",
    "management": "tx_deep_dive",
    "pathophys epi": "pathophys_epi",
    "pathophys & epi": "pathophys_epi",
    "pathophys and epi": "pathophys_epi",
    "pathophysiology": "pathophys_epi",
    "feedback": "feedback",
}

MODULE_FRIENDLY_NAME: dict[str, str] = {
    "history_taking": "History Taking",
    "ddx_deep_dive": "DDx Deep Dive",
    "tx_deep_dive": "Management Deep Dive",
    "pathophys_epi": "Pathophys & Epi Deep Dive",
    "feedback": "Feedback",
}


class Orchestrator:
    """Routes messages through user-selected learning modules."""

    def __init__(
        self,
        organism_name: str,
        selected_modules: list[str] | None = None,
        enable_mcqs: bool = False,
        enable_emr_notes: bool = True,
        enable_checklist: bool = True,
        module_models: dict[str, str] | None = None,
    ):
        self.case_loader = CaseLoader()
        self.csv_tool = CSVTool()
        normalized = (organism_name or "").strip().lower()

        if normalized in {"staphylococcus aureus", "staph aureus", "mssa", "mrsa"}:
            organism_name = "Case_07011"

        if organism_name in self.case_loader.manual_cases:
            self.case_id = organism_name
            case_data = self.case_loader.get_case_data(organism_name)
            self.case_data: str = case_data["content"]
            self.images: list[str] = case_data["images"]
            self.image_path: str | None = case_data["path"]
            if organism_name == "Case_07011":
                self.organism_name = "staphylococcus aureus"
            else:
                self.organism_name = organism_name
        else:
            self.case_id = None
            self.organism_name = organism_name
            self.case_data = self.case_loader.get_case(organism_name)
            self.images = []
            self.image_path = None

        # --- module pipeline --------------------------------------------------
        if not selected_modules:
            selected_modules = list(MODULE_ORDER)
        self.module_queue: list[str] = [
            m for m in MODULE_ORDER if m in selected_modules
        ]
        if not self.module_queue:
            self.module_queue = list(MODULE_ORDER)
        # Always append feedback at the end
        self.module_queue.append("feedback")

        self.enable_mcqs = enable_mcqs
        self.enable_emr_notes = enable_emr_notes
        self.enable_checklist = enable_checklist
        self.module_models: dict[str, str] = module_models or {}
        self.current_module_idx: int = 0
        self.current_module: str = self.module_queue[0]
        self.multi_module: bool = len(self.module_queue) > 2  # >1 real + feedback

        # --- state bookkeeping ------------------------------------------------
        self.conversation_history: list[dict[str, str]] = []
        self.module_logs: dict[str, list[dict[str, str]]] = {
            m: [] for m in self.module_queue
        }
        self.revealed_images: set[str] = set()
        self.pinned_images: list[str] = []  # URLs shown so far (for UI pinning)

        # --- synthesis step (transition from history_taking) ----------------
        self._awaiting_synthesis: str | None = None
        self.student_differentials: str | None = None
        factors = self.csv_tool.get_crucial_factors(self.organism_name)
        self.csv_guidance = ", ".join(factors) if factors else "None identified"

        # --- case summary (generated lazily for non-history modules) ---------
        self.case_summary: str | None = None

        # --- findings checklist (history_taking only) -------------------------
        self.findings_checklist: dict[str, list[dict]] | None = None
        self.checked_findings: dict[str, dict] = {}
        self.findings_progress: dict[str, dict[str, int]] = {
            "history_exam": {"checked": 0, "total": 0},
            "investigations": {"checked": 0, "total": 0},
        }
        self._checklist_lock = threading.Lock()
        if self.enable_checklist and "history_taking" in self.module_queue:
            threading.Thread(
                target=self._generate_findings_checklist, daemon=True
            ).start()

        # --- EMR notes (structured clinical notes from conversation) ----------
        self.emr_notes: list[dict[str, str]] = []
        self._emr_notes_lock = threading.Lock()
        self._emr_queue: Queue[tuple[str, str, str | None]] = Queue()
        self._emr_busy = threading.Event()
        self._emr_worker = threading.Thread(
            target=self._emr_extraction_worker, daemon=True
        )
        self._emr_worker.start()

        # --- agents -----------------------------------------------------------
        self._agents: dict[str, Any] = {}
        self._init_agents()
        self.quiz_agent = QuizAgent(self.case_data)

    # ------------------------------------------------------------------
    # Agent initialisation (lazy-ish: only modules the user selected)
    # ------------------------------------------------------------------
    def _init_agents(self) -> None:
        default_teaching_model = config.TEACHING_MODEL_NAME
        default_patient_model = config.MODEL_NAME

        for mod in self.module_queue:
            model = self.module_models.get(mod)

            if mod == "history_taking":
                self._agents[mod] = PatientAgent(
                    self.case_data, model=model or default_patient_model,
                )
            elif mod == "ddx_deep_dive":
                self._agents[mod] = DdxAgent(
                    self.case_data, self.organism_name, self.csv_tool,
                    model=model or default_teaching_model,
                )
            elif mod == "tx_deep_dive":
                self._agents[mod] = TxAgent(
                    self.case_data, self.organism_name, self.csv_tool,
                    model=model or default_teaching_model,
                )
            elif mod == "pathophys_epi":
                self._agents[mod] = PathophysEpiAgent(
                    self.case_data, self.organism_name, self.csv_tool,
                    model=model or default_teaching_model,
                )
            elif mod == "feedback":
                self._agents[mod] = FeedbackAgent(self.case_data)

        models_used = {
            m: self._agents[m].model
            for m in self.module_queue
            if hasattr(self._agents.get(m), "model")
        }
        logger.info("Agent models: %s", models_used)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def process_message(self, user_message: str) -> dict[str, Any]:
        self.conversation_history.append({"role": "user", "content": user_message})
        self._log_to_module("user", user_message)

        # Check for explicit module-jump request from the frontend
        requested_module = self._extract_requested_module_transition(user_message)

        # --- Handle synthesis response (student answered DDx question) ---
        if self._awaiting_synthesis:
            if requested_module:
                # Student skipped synthesis — jump directly
                self._awaiting_synthesis = None
                self._advance_to_module(requested_module)
            else:
                return self._handle_synthesis_response(user_message)

        # --- Module transition ---
        if requested_module and requested_module != self.current_module:
            # Synthesis step: ask for differentials when leaving history_taking
            if (
                self.current_module == "history_taking"
                and requested_module != "feedback"
            ):
                return self._inject_synthesis_question(requested_module)
            self._advance_to_module(requested_module)

        # --- feedback module: generate combined debrief + MCQs ---
        if self.current_module == "feedback" and requested_module == "feedback":
            return self._generate_feedback_bundle()

        # --- route to active agent ---
        active_agent = self._agents.get(self.current_module)
        if not active_agent:
            return self._error_response("No agent for current module.")

        routed_message = user_message
        # If we just transitioned, give the agent a synthetic kickoff prompt
        if requested_module and requested_module == self.current_module:
            routed_message = (
                "This is the start of the module. Introduce the case briefly "
                "(the student can see the full case summary above) and give "
                "your first teaching question."
            )

        response = active_agent.chat(routed_message)
        response, agent_requested_figure = self._parse_display_figure_tool_call(response)

        # --- image handling ---
        image_url = self._resolve_image(
            response, routed_message, agent_requested_figure
        )

        # --- record assistant turn ---
        self.conversation_history.append({"role": "assistant", "content": response})
        self._log_to_module("assistant", response)

        # --- background tasks for history-taking ---
        if self.current_module == "history_taking" and not requested_module:
            if self.enable_checklist and self.findings_checklist:
                threading.Thread(
                    target=self._update_findings_checklist,
                    args=(user_message, response),
                    daemon=True,
                ).start()
            if self.enable_emr_notes:
                self._emr_queue.put((user_message, response, image_url))

        return {
            "response": response,
            "subagent_response": response,
            "subagent_name": self.current_module,
            "image_url": image_url,
            "pinned_images": list(self.pinned_images),
            "findings_checklist": self._get_findings_snapshot(),
            "emr_notes": self._get_emr_notes_snapshot(),
            "metadata": {
                "current_module": self.current_module,
                "module_queue": self.module_queue,
                "module_index": self.current_module_idx,
                "modules_remaining": self.module_queue[self.current_module_idx + 1 :],
                "enable_mcqs": self.enable_mcqs,
            },
        }

    # ------------------------------------------------------------------
    # Synthesis step (DDx challenge when leaving history_taking)
    # ------------------------------------------------------------------
    _SYNTHESIS_QUESTION = (
        "Great work gathering the clinical information! Before we move on "
        "— based on everything you've gathered from the history, examination, "
        "and investigations, what are your **top 3–5 differential diagnoses**?"
        "\n\nFor each, briefly list the key features that support it."
    )

    def _inject_synthesis_question(self, target_module: str) -> dict[str, Any]:
        """Return a synthesis question instead of transitioning immediately."""
        self._awaiting_synthesis = target_module
        msg = self._SYNTHESIS_QUESTION

        self.conversation_history.append({"role": "assistant", "content": msg})
        self._log_to_module("assistant", msg)

        return {
            "response": msg,
            "subagent_response": msg,
            "subagent_name": "synthesis",
            "image_url": None,
            "pinned_images": list(self.pinned_images),
            "findings_checklist": self._get_findings_snapshot(),
            "emr_notes": self._get_emr_notes_snapshot(),
            "metadata": {
                "current_module": target_module,
                "module_queue": self.module_queue,
                "module_index": self.current_module_idx,
                "modules_remaining": self.module_queue[self.current_module_idx + 1 :],
                "enable_mcqs": self.enable_mcqs,
            },
        }

    def _handle_synthesis_response(self, user_message: str) -> dict[str, Any]:
        """Process the student's differentials and kick off the target module."""
        target = self._awaiting_synthesis
        self._awaiting_synthesis = None
        self.student_differentials = user_message

        self._advance_to_module(target)

        active_agent = self._agents.get(self.current_module)
        if not active_agent:
            return self._error_response("No agent for current module.")

        if self.current_module == "ddx_deep_dive":
            kickoff = (
                f"The student just completed history taking and proposed these "
                f"differential diagnoses:\n\n{user_message}\n\n"
                f"Start by engaging with their proposed differentials — "
                f"acknowledge what they identified well, point out important "
                f"diagnoses they may have missed, and explain briefly why. "
                f"Then transition into your first systematic teaching question."
            )
        else:
            kickoff = (
                f"The student completed history taking and proposed these "
                f"differentials:\n{user_message}\n\n"
                f"This is the start of the module. Introduce the case briefly "
                f"(the student can see the full case summary above) and give "
                f"your first teaching question."
            )

        response = active_agent.chat(kickoff)
        response, agent_requested_figure = self._parse_display_figure_tool_call(response)
        image_url = self._resolve_image(response, kickoff, agent_requested_figure)

        self.conversation_history.append({"role": "assistant", "content": response})
        self._log_to_module("assistant", response)

        return {
            "response": response,
            "subagent_response": response,
            "subagent_name": self.current_module,
            "image_url": image_url,
            "pinned_images": list(self.pinned_images),
            "findings_checklist": self._get_findings_snapshot(),
            "emr_notes": self._get_emr_notes_snapshot(),
            "metadata": {
                "current_module": self.current_module,
                "module_queue": self.module_queue,
                "module_index": self.current_module_idx,
                "modules_remaining": self.module_queue[self.current_module_idx + 1 :],
                "enable_mcqs": self.enable_mcqs,
            },
        }

    # ------------------------------------------------------------------
    # Module transition helpers
    # ------------------------------------------------------------------
    def _advance_to_next_module(self) -> None:
        if self.current_module_idx < len(self.module_queue) - 1:
            self.current_module_idx += 1
            self.current_module = self.module_queue[self.current_module_idx]
            logger.info(f"Advanced to module: {self.current_module}")

    def _advance_to_module(self, target_module: str) -> None:
        """Jump to a specific module (for explicit UI transitions)."""
        if target_module in self.module_queue:
            idx = self.module_queue.index(target_module)
            self.current_module_idx = idx
            self.current_module = target_module
            logger.info(f"Jumped to module: {self.current_module}")

    def _extract_requested_module_transition(self, user_message: str) -> str | None:
        if not user_message:
            return None
        text = user_message.strip().lower()

        cmd_match = re.search(r"let'?s move onto (?:phase|module):\s*(.+)$", text)
        if cmd_match:
            label = cmd_match.group(1).strip()
            return MODULE_LABEL_TO_ID.get(label)

        skip_match = re.search(
            r"\b(?:skip|jump|move|start|switch)\s+(?:ahead\s+)?(?:to|into)?\s*"
            r"(history taking|ddx deep dive|differential diagnosis deep dive|"
            r"management deep dive|tx deep dive|treatment|management|"
            r"pathophys(?:iology)?(?:\s*(?:&|and)\s*epi)?|feedback)\b",
            text,
        )
        if skip_match:
            label = re.sub(r"\s+", " ", skip_match.group(1)).strip().replace("&", "and")
            return MODULE_LABEL_TO_ID.get(label)
        return None

    # ------------------------------------------------------------------
    # Module review generation (called explicitly via feedback endpoint)
    # ------------------------------------------------------------------
    def generate_module_review(self, module_id: str | None = None) -> str | None:
        """Generate a review/debrief for the given module (defaults to current)."""
        mod = module_id or self.current_module
        log = self.module_logs.get(mod, [])
        if not log:
            return None

        conversation_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in log
        )

        if mod == "history_taking":
            return self._generate_history_debrief(conversation_text)

        if mod in ("ddx_deep_dive", "tx_deep_dive", "pathophys_epi") and self.enable_mcqs:
            return self._generate_module_mcqs(mod, conversation_text)

        return None

    def _generate_history_debrief(self, conversation_text: str) -> str | None:
        prompt = HISTORY_DEBRIEF_PROMPT.format(
            case=self.case_data,
            conversation=conversation_text,
        )
        try:
            return chat_complete([{"role": "user", "content": prompt}])
        except Exception as e:
            logger.error(f"History debrief generation failed: {e}")
            return None

    def _generate_module_mcqs(self, module_id: str, conversation_text: str) -> str | None:
        friendly = MODULE_FRIENDLY_NAME.get(module_id, module_id)
        try:
            quiz_data = self.quiz_agent.generate_quiz(
                conversation_text=conversation_text,
                module_name=friendly,
            )
            return json.dumps(quiz_data, indent=2)
        except Exception as e:
            logger.error(f"MCQ generation for {module_id} failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Feedback bundle (end-of-case: debrief + MCQs)
    # ------------------------------------------------------------------
    def _generate_feedback_bundle(self) -> dict[str, Any]:
        """Generate combined feedback when entering the feedback module.

        Includes:
        - History-taking debrief (if that module was completed)
        - A summary of all completed modules

        MCQs are handled separately by the frontend MCQ system.
        """
        parts: list[str] = []

        # History-taking debrief (if that module was used)
        ht_log = self.module_logs.get("history_taking", [])
        if ht_log:
            ht_text = "\n".join(f"{m['role']}: {m['content']}" for m in ht_log)
            debrief = self._generate_history_debrief(ht_text)
            if debrief:
                parts.append(debrief)

        # General feedback from the feedback agent for the overall session
        completed = [
            MODULE_FRIENDLY_NAME.get(m, m)
            for m in self.module_queue
            if m != "feedback" and self.module_logs.get(m)
        ]
        if not parts and not completed:
            response = "No modules completed yet — try completing some modules first."
        else:
            if not parts:
                all_text = "\n\n".join(
                    "\n".join(f"{e['role']}: {e['content']}" for e in self.module_logs[m])
                    for m in self.module_queue
                    if m != "feedback" and self.module_logs.get(m)
                )
                agent = self._agents.get("feedback")
                if agent:
                    response = agent.chat(
                        f"Here is the full conversation from the student's session:\n\n{all_text}"
                    )
                    parts.append(response)

            response = "\n\n".join(parts)

        self.conversation_history.append({"role": "assistant", "content": response})
        self._log_to_module("assistant", response)

        return {
            "response": response,
            "subagent_response": response,
            "subagent_name": "feedback",
            "image_url": None,
            "pinned_images": list(self.pinned_images),
            "findings_checklist": self._get_findings_snapshot(),
            "emr_notes": self._get_emr_notes_snapshot(),
            "metadata": {
                "current_module": self.current_module,
                "module_queue": self.module_queue,
                "module_index": self.current_module_idx,
                "modules_remaining": [],
                "enable_mcqs": self.enable_mcqs,
            },
        }

    # ------------------------------------------------------------------
    # Per-module logging
    # ------------------------------------------------------------------
    def _log_to_module(self, role: str, content: str) -> None:
        log = self.module_logs.get(self.current_module)
        if log is not None:
            log.append({"role": role, "content": content})

    # ------------------------------------------------------------------
    # Image handling  (preserved from original)
    # ------------------------------------------------------------------
    def _resolve_image(
        self,
        response: str,
        user_message: str,
        agent_requested_figure: str | None,
    ) -> str | None:
        """Resolve a figure number to an image URL.

        Priority: agent-emitted marker > explicit "Figure N" in response text.
        """
        image_url = None
        if agent_requested_figure:
            image_url = self.display_image(agent_requested_figure)
        else:
            mentioned = self._extract_figure_reference(response)
            if mentioned:
                image_url = self.display_image(mentioned)

        if image_url and image_url not in self.pinned_images:
            self.pinned_images.append(image_url)
        return image_url

    def display_image(self, figure_num: str) -> str | None:
        if not self.images or not self.case_id:
            return None
        clean_num = re.sub(r"[^0-9]", "", str(figure_num))
        if not clean_num:
            return None
        for img in self.images:
            if f"figure{clean_num}" in img.lower():
                self.revealed_images.add(img)
                return f"/images/{self.case_id}/{img}"
        return None

    def _parse_display_figure_tool_call(self, response: str) -> tuple[str, str | None]:
        """Strip all display_figure markers from assistant text; return first figure id if any."""
        if not response:
            return response, None
        text = (
            response.replace("\uFF3B", "[")
            .replace("\uFF3D", "]")
            .replace("\uFF1A", ":")
        )
        bracket_re = re.compile(
            r"\[\[\s*display_figure\s*:\s*(\d+)\s*\]\]", re.IGNORECASE
        )
        paren_re = re.compile(r"\bdisplay_figure\s*\(\s*(\d+)\s*\)", re.IGNORECASE)

        first_fig: str | None = None
        m = bracket_re.search(text)
        if m:
            first_fig = m.group(1)
        if first_fig is None:
            m2 = paren_re.search(text)
            if m2:
                first_fig = m2.group(1)

        cleaned = bracket_re.sub("", text)
        cleaned = paren_re.sub("", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        return cleaned, first_fig

    def _extract_figure_reference(self, text: str) -> str | None:
        """Fallback: detect explicit 'Figure N' mentions in agent text."""
        if not text:
            return None
        match = re.search(r"\bfig(?:ure)?\.?\s*(\d+)\b", text, re.IGNORECASE)
        return match.group(1) if match else None

    # ------------------------------------------------------------------
    # First message
    # ------------------------------------------------------------------
    def get_first_message(self) -> dict[str, str]:
        """Return the opening message and the speaker identity.

        For history_taking the patient agent provides a one-liner and
        fires the async EMR / checklist tasks on it.
        For any other module the specialist agent is asked to introduce itself
        so there is **no** MainTutor wrapper message.
        """
        first_mod = self.module_queue[0]
        if first_mod == "history_taking":
            agent = self._agents.get("history_taking")
            if isinstance(agent, PatientAgent):
                msg = agent.first_sentence
                self._fire_background_tasks_for_first_message(msg)
                return {"speaker": "patient", "message": msg}
            return {"speaker": "patient", "message": "Hello, I'm your patient today."}

        agent = self._agents.get(first_mod)
        if agent:
            kickoff = agent.chat(
                "This is the start of the module. Introduce the case briefly "
                "(the student can see the full case summary above) and give "
                "your first teaching question."
            )
            self.conversation_history.append({"role": "assistant", "content": kickoff})
            self._log_to_module("assistant", kickoff)
            speaker_map = {
                "ddx_deep_dive": "ddx_tutor",
                "tx_deep_dive": "tx_tutor",
                "pathophys_epi": "pathophys_epi_tutor",
                "feedback": "feedback",
            }
            return {"speaker": speaker_map.get(first_mod, "tutor"), "message": kickoff}

        friendly = MODULE_FRIENDLY_NAME.get(first_mod, first_mod)
        return {"speaker": "maintutor", "message": f"Let's begin **{friendly}**."}

    def _fire_background_tasks_for_first_message(self, first_msg: str) -> None:
        """Kick off EMR notes + checklist on the patient's opening greeting.

        The checklist may still be generating in another thread, so the
        checklist updater waits up to 30 s for it to become available.
        """
        synthetic_student = "(Patient introduces themselves)"

        def _checklist_when_ready() -> None:
            for _ in range(30):
                if self.findings_checklist:
                    self._update_findings_checklist(synthetic_student, first_msg)
                    return
                time.sleep(1)

        if self.enable_checklist:
            threading.Thread(target=_checklist_when_ready, daemon=True).start()
        if self.enable_emr_notes:
            self._emr_queue.put((synthetic_student, first_msg, None))

    # ------------------------------------------------------------------
    # Case summary (rounds-style, for non-history modules)
    # ------------------------------------------------------------------
    def generate_case_summary(self) -> str:
        """Return a concise clinical rounds-style summary of the case.

        The summary is generated once via LLM and cached on the instance.
        """
        if self.case_summary:
            return self.case_summary

        prompt = CASE_SUMMARY_PROMPT.format(case=self.case_data)
        try:
            self.case_summary = chat_complete(
                [{"role": "user", "content": prompt}]
            )
        except Exception as e:
            logger.error(f"Case summary generation failed: {e}")
            self.case_summary = self.case_data[:800] + "\n\n*(Summary generation failed -- showing truncated case text.)*"

        return self.case_summary

    # ------------------------------------------------------------------
    # EMR note extraction  (sequential queue-based worker with batching)
    # ------------------------------------------------------------------
    def _emr_extraction_worker(self) -> None:
        """Background worker: process EMR extraction jobs sequentially.

        If multiple turns queue up while one is being processed, they are
        batched into a single LLM call to reduce latency and improve
        consistency (each call sees up-to-date existing notes).
        """
        while True:
            first = self._emr_queue.get()
            batch: list[tuple[str, str, str | None]] = [first]
            # Drain any additional queued items into the same batch
            while True:
                try:
                    batch.append(self._emr_queue.get_nowait())
                except Empty:
                    break

            self._emr_busy.set()
            try:
                self._extract_emr_notes_batch(batch)
            except Exception as e:
                logger.error("EMR extraction worker error: %s", e)
            finally:
                self._emr_busy.clear()
                for _ in batch:
                    self._emr_queue.task_done()

    def _extract_emr_notes_batch(
        self, batch: list[tuple[str, str, str | None]]
    ) -> None:
        """Run a single LLM call to extract notes from one or more exchanges."""
        exchanges = "\n\n".join(
            f"--- Exchange {i+1} ---\nStudent: {q}\nPatient: {a}"
            for i, (q, a, _) in enumerate(batch)
        )
        image_urls = [url for _, _, url in batch if url]

        with self._emr_notes_lock:
            existing = list(self.emr_notes)

        existing_text = (
            json.dumps(existing, indent=2) if existing else "None yet."
        )
        prompt = EMR_NOTE_EXTRACTION_PROMPT.format(
            student_question=exchanges,
            patient_response="(see exchanges above)",
            existing_notes=existing_text,
        )
        try:
            raw = chat_complete(
                [{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            data = json.loads(raw)
            new_notes = data.get("notes", [])
            if not isinstance(new_notes, list):
                return

            img_idx = 0
            with self._emr_notes_lock:
                for note in new_notes:
                    if not (
                        isinstance(note, dict)
                        and note.get("section")
                        and note.get("content")
                    ):
                        continue
                    if img_idx < len(image_urls):
                        note["image_url"] = image_urls[img_idx]
                        img_idx += 1
                    self.emr_notes.append(note)

            logger.info(
                "EMR notes extracted: %d new (batch of %d exchanges)",
                len(new_notes), len(batch),
            )
        except Exception as e:
            logger.error("EMR note extraction failed: %s", e)

    def rebuild_emr_notes(self) -> list[dict[str, str]]:
        """Full re-extraction from the entire conversation history.

        Replaces all existing EMR notes with a fresh extraction.
        Returns the new notes list.
        """
        self._emr_busy.set()
        try:
            turns = []
            hist = list(self.conversation_history)
            for i in range(0, len(hist) - 1, 2):
                if hist[i]["role"] == "user" and hist[i + 1]["role"] == "assistant":
                    turns.append(
                        f"Student: {hist[i]['content']}\nPatient: {hist[i+1]['content']}"
                    )
            if not turns:
                return []

            conversation_text = "\n\n".join(turns)
            prompt = EMR_FULL_REBUILD_PROMPT.format(conversation=conversation_text)

            raw = chat_complete(
                [{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            data = json.loads(raw)
            new_notes = data.get("notes", [])
            if not isinstance(new_notes, list):
                return self._get_emr_notes_snapshot()

            valid = [
                n for n in new_notes
                if isinstance(n, dict) and n.get("section") and n.get("content")
            ]

            with self._emr_notes_lock:
                self.emr_notes = valid

            logger.info("EMR full rebuild: %d notes from %d turns", len(valid), len(turns))
            return valid
        except Exception as e:
            logger.error("EMR rebuild failed: %s", e)
            return self._get_emr_notes_snapshot()
        finally:
            self._emr_busy.clear()

    def is_emr_busy(self) -> bool:
        """Return True if the EMR worker is currently processing."""
        return self._emr_busy.is_set() or not self._emr_queue.empty()

    def _get_emr_notes_snapshot(self) -> list[dict[str, str]]:
        """Return a thread-safe copy of the accumulated EMR notes."""
        with self._emr_notes_lock:
            return list(self.emr_notes)

    # ------------------------------------------------------------------
    # Findings checklist
    # ------------------------------------------------------------------
    _CHECKLIST_CACHE_DIR = Path("data/cases/cached/checklists")

    def _checklist_cache_path(self) -> Path:
        """Return a deterministic cache file path based on case data content."""
        digest = hashlib.sha256(self.case_data.encode()).hexdigest()[:16]
        return self._CHECKLIST_CACHE_DIR / f"{digest}.json"

    def _generate_findings_checklist(self) -> None:
        """Generate the structured checklist from case data (runs once at init).

        Checks a disk cache first; falls back to an LLM call and saves the
        result for subsequent runs.
        """
        cache_path = self._checklist_cache_path()
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text())
                self._apply_checklist(data)
                logger.info(
                    "Findings checklist loaded from cache: %d history_exam, %d investigations",
                    self.findings_progress["history_exam"]["total"],
                    self.findings_progress["investigations"]["total"],
                )
                return
            except Exception as e:
                logger.warning(f"Checklist cache read failed, regenerating: {e}")

        prompt = CHECKLIST_GENERATION_PROMPT.format(case=self.case_data)
        try:
            raw = chat_complete(
                [{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("Expected JSON object from checklist generation")

            self._apply_checklist(data)

            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(data, indent=2))
            logger.info(
                "Findings checklist generated & cached: %d history_exam, %d investigations",
                self.findings_progress["history_exam"]["total"],
                self.findings_progress["investigations"]["total"],
            )
        except Exception as e:
            logger.error(f"Findings checklist generation failed: {e}")
            self.findings_checklist = None

    def _apply_checklist(self, data: dict) -> None:
        """Apply parsed checklist data to instance state."""
        self.findings_checklist = {
            "history_exam": data.get("history_exam", []),
            "investigations": data.get("investigations", []),
        }
        self.findings_progress = {
            "history_exam": {
                "checked": 0,
                "total": len(self.findings_checklist["history_exam"]),
            },
            "investigations": {
                "checked": 0,
                "total": len(self.findings_checklist["investigations"]),
            },
        }

    def _update_findings_checklist(
        self, user_message: str, agent_response: str
    ) -> None:
        """Check which items were revealed (runs in a background thread)."""
        if not self.findings_checklist:
            return

        with self._checklist_lock:
            checked_ids = set(self.checked_findings.keys())

        unchecked: list[dict] = []
        for group in ("history_exam", "investigations"):
            for item in self.findings_checklist.get(group, []):
                if item["id"] not in checked_ids:
                    unchecked.append(item)

        if not unchecked:
            return

        unchecked_text = json.dumps(unchecked, indent=2)
        prompt = CHECKLIST_UPDATE_PROMPT.format(
            unchecked_items=unchecked_text,
            student_question=user_message,
            agent_response=agent_response,
        )
        try:
            raw = chat_complete(
                [{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            data = json.loads(raw)
            newly_checked = data.get("checked", [])
            if not isinstance(newly_checked, list):
                return

            item_lookup: dict[str, dict] = {}
            for group in ("history_exam", "investigations"):
                for item in self.findings_checklist.get(group, []):
                    item_lookup[item["id"]] = item

            with self._checklist_lock:
                for entry in newly_checked:
                    item_id = entry.get("id", "")
                    if item_id in item_lookup and item_id not in self.checked_findings:
                        self.checked_findings[item_id] = {
                            "label": item_lookup[item_id].get("label", ""),
                            "category": item_lookup[item_id].get("category", ""),
                            "summary": entry.get("summary", item_lookup[item_id].get("detail", "")),
                        }

                self._recompute_progress()

        except Exception as e:
            logger.error(f"Findings checklist update failed: {e}")

    def _recompute_progress(self) -> None:
        """Recount checked items per group. Must be called with _checklist_lock held."""
        if not self.findings_checklist:
            return
        for group in ("history_exam", "investigations"):
            items = self.findings_checklist.get(group, [])
            total = len(items)
            checked = sum(1 for it in items if it["id"] in self.checked_findings)
            self.findings_progress[group] = {"checked": checked, "total": total}

    def _get_findings_snapshot(self) -> dict | None:
        """Return a thread-safe snapshot of the checklist state for the response."""
        if not self.findings_checklist:
            return None
        with self._checklist_lock:
            return {
                "progress": dict(self.findings_progress),
                "gathered": dict(self.checked_findings),
            }

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    @property
    def current_state(self) -> str:
        """Backward-compatible alias used by app.py."""
        return self.current_module

    def _error_response(self, msg: str) -> dict[str, Any]:
        return {
            "response": msg,
            "subagent_response": msg,
            "subagent_name": self.current_module,
            "image_url": None,
            "pinned_images": list(self.pinned_images),
            "findings_checklist": self._get_findings_snapshot(),
            "emr_notes": self._get_emr_notes_snapshot(),
            "metadata": {
                "current_module": self.current_module,
                "module_queue": self.module_queue,
                "module_index": self.current_module_idx,
                "modules_remaining": [],
                "enable_mcqs": self.enable_mcqs,
            },
        }
