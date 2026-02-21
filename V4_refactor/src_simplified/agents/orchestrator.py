import json
import logging
import re
from typing import Dict, Any, List, Optional

from ..utils.llm import chat_complete
from ..utils.case_loader import CaseLoader
from ..tools.csv_tool import CSVTool
from ..prompts import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    MANAGER_DIFFERENTIAL_SYSTEM_PROMPT,
)
from .patient_agent import PatientAgent
from .deeper_dive_agent import DeeperDiveAgent
from .tests_agent import TestsAgent
from .feedback_agent import FeedbackAgent
from .quiz_agent import QuizAgent

logger = logging.getLogger(__name__)

class Orchestrator:
    PHASE_ORDER = [
        "information_gathering",
        "differential_diagnosis",
        "tests_management",
        "deeper_dive",
        "post_case_mcq",
        "feedback",
    ]

    PHASE_LABEL_TO_STATE = {
        "information gathering": "information_gathering",
        "differential diagnosis": "differential_diagnosis",
        "tests & management": "tests_management",
        "tests and management": "tests_management",
        "tests management": "tests_management",
        "deeper dive": "deeper_dive",
        "post-case mcq": "post_case_mcq",
        "post case mcq": "post_case_mcq",
        "assessment mcqs": "post_case_mcq",
        "assessment": "post_case_mcq",
        "feedback": "feedback",
    }

    PHASE_SUMMARY_TIPS = {
        "information_gathering": "Key history/exam clues were gathered before narrowing the diagnosis.",
        "differential_diagnosis": "The differential should rank top causes and justify each with case clues.",
        "tests_management": "High-yield diagnostics and interpretation should confirm the diagnosis and guide treatment.",
        "deeper_dive": "Advanced mechanism-level and organism-specific learning points are covered here.",
        "post_case_mcq": "MCQs consolidate weak spots and reinforce key reasoning points.",
        "feedback": "Final reflection covers strengths, gaps, and practical takeaways.",
    }

    def __init__(self, organism_name: str):
        self.case_loader = CaseLoader()
        self.csv_tool = CSVTool()
        normalized = (organism_name or "").strip().lower()

        # Route staph selection to curated ID case for image-first workflow.
        if normalized in {"staphylococcus aureus", "staph aureus", "mssa", "mrsa"}:
            organism_name = "Case_07011"
        
        # Check if it's a manual case ID
        if organism_name in self.case_loader.manual_cases:
            self.case_id = organism_name
            case_data = self.case_loader.get_case_data(organism_name)
            self.case_data = case_data["content"]
            self.images = case_data["images"]
            self.image_path = case_data["path"]
            
            # Map Case ID to Organism for CSV lookup
            if organism_name == "Case_07011":
                self.organism_name = "staphylococcus aureus"
            else:
                self.organism_name = organism_name # Fallback
        else:
            self.case_id = None
            self.organism_name = organism_name
            self.case_data = self.case_loader.get_case(organism_name)
            self.images = []
            self.image_path = None
        
        self.current_state = "information_gathering"
        self.conversation_history = []
        self.revealed_images: set[str] = set()
        self.figure_captions = self._extract_figure_captions(self.case_data)
        factors = self.csv_tool.get_crucial_factors(self.organism_name)
        self.csv_guidance = ", ".join(factors) if factors else "None identified"
        
        # Initialize subagents
        self.agents = {
            "information_gathering": PatientAgent(self.case_data),
            "tests_management": TestsAgent(self.case_data),
            "deeper_dive": DeeperDiveAgent(self.case_data, self.organism_name),
            "post_case_mcq": QuizAgent(self.case_data),
            "feedback": FeedbackAgent(self.case_data)
        }

    def process_message(self, user_message: str) -> Dict[str, Any]:
        # 1. Update history
        self.conversation_history.append({"role": "user", "content": user_message})

        # 2. Determine state (Orchestrator Logic)
        requested_state = self._extract_requested_phase_transition(user_message)
        transition_msg = None
        display_image_figure = ""
        routed_user_message = user_message

        if requested_state:
            new_state = requested_state
            transition_msg = self._build_skipped_sections_summary(self.current_state, requested_state)
            routed_user_message = (
                f"The learner skipped ahead to {requested_state}. "
                "Give a concise phase kickoff and ask one focused next-step question."
            )
        else:
            new_state_info = self._determine_state(user_message)
            new_state = new_state_info.get("state", self.current_state)
            transition_msg = new_state_info.get("transition_message")
            display_image_figure = str(new_state_info.get("display_image_figure", "")).strip()
        
        # Handle state transition
        if new_state != self.current_state:
            logger.info(f"Transitioning from {self.current_state} to {new_state}")
            self.current_state = new_state

        # 3. Route to active agent
        active_agent = self.agents.get(self.current_state)
        if self.current_state == "differential_diagnosis":
            response = self._manager_phase_chat()
        elif not active_agent:
            return {"response": "Error: Invalid state."}

        # Special handling for Quiz Agent
        if self.current_state == "post_case_mcq" and "mcq" not in routed_user_message.lower():
             if not active_agent.get_history():
                 quiz_data = active_agent.generate_quiz(self.conversation_history)
                 response = json.dumps(quiz_data, indent=2)
             else:
                 response = active_agent.chat(routed_user_message)
        elif self.current_state != "differential_diagnosis":
            response = active_agent.chat(routed_user_message)

        response, agent_requested_figure = self._parse_display_figure_tool_call(response)

        orchestrator_message = transition_msg.strip() if transition_msg else None

        # 4. Update history with separated assistant turns
        if orchestrator_message:
            self.conversation_history.append({"role": "assistant", "content": orchestrator_message})
        self.conversation_history.append({"role": "assistant", "content": response})

        # 5. Orchestrator-controlled image tool call
        image_url = None
        if display_image_figure:
            image_url = self.display_image(display_image_figure)
        elif agent_requested_figure:
            image_url = self.display_image(agent_requested_figure)
        else:
            mentioned_figure = self._extract_figure_reference(response)
            if mentioned_figure:
                image_url = self.display_image(mentioned_figure)
            elif self._should_proactively_display_image(routed_user_message):
                proactive_figure = self._select_proactive_figure(routed_user_message)
                if proactive_figure:
                    image_url = self.display_image(proactive_figure)

        return {
            "response": response,
            "subagent_response": response,
            "orchestrator_message": orchestrator_message,
            "subagent_name": self.current_state,
            "image_url": image_url
        }

    def _extract_requested_phase_transition(self, user_message: str) -> Optional[str]:
        """Parse explicit phase-jump requests from UI command or natural language."""
        if not user_message:
            return None
        text = user_message.strip().lower()

        cmd_match = re.search(r"let'?s move onto phase:\s*(.+)$", text)
        if cmd_match:
            label = cmd_match.group(1).strip()
            return self.PHASE_LABEL_TO_STATE.get(label)

        skip_match = re.search(
            r"\b(skip|jump|move)\s+(ahead\s+)?(to|into)?\s*(information gathering|differential diagnosis|tests(?:\s*&|\s+and)?\s*management|deeper dive|post[-\s]?case mcq|assessment(?:\s*mcqs)?|feedback)\b",
            text,
        )
        if skip_match:
            label = skip_match.group(4)
            label = re.sub(r"\s+", " ", label).strip()
            label = label.replace("&", "and")
            if label == "assessment":
                label = "assessment mcqs"
            return self.PHASE_LABEL_TO_STATE.get(label)
        return None

    def _build_skipped_sections_summary(self, from_state: str, to_state: str) -> Optional[str]:
        """Summarize sections skipped when learner jumps forward."""
        try:
            from_idx = self.PHASE_ORDER.index(from_state)
            to_idx = self.PHASE_ORDER.index(to_state)
        except ValueError:
            return None

        if to_idx <= from_idx + 1:
            return None

        skipped = self.PHASE_ORDER[from_idx + 1:to_idx]
        if not skipped:
            return None

        generated = self._generate_case_grounded_skip_summary(skipped)
        if generated:
            return generated

        bullets = []
        for state in skipped:
            tip = self.PHASE_SUMMARY_TIPS.get(state)
            if tip:
                label = state.replace("_", " ").title()
                bullets.append(f"- {label}: {tip}")
        if not bullets:
            return None
        return "Quick recap of skipped sections:\n" + "\n".join(bullets)

    def _generate_case_grounded_skip_summary(self, skipped_states: List[str]) -> Optional[str]:
        """Use case content to generate concrete recap points for skipped phases."""
        if not skipped_states:
            return None

        readable_labels = [s.replace("_", " ").title() for s in skipped_states]
        prompt = (
            "You are creating a concise recap for a learner who skipped sections in a clinical microbiology case.\n"
            "Use concrete details from the case text, not generic study advice.\n\n"
            f"Skipped sections: {', '.join(readable_labels)}\n\n"
            "Output format (strict):\n"
            "Quick recap of skipped sections:\n"
            "- <Section>: <1 sentence with concrete case details>\n"
            "- <Section>: <1 sentence with concrete case details>\n\n"
            "Rules:\n"
            "- One bullet per skipped section.\n"
            "- Include specific findings/symptoms/results when available.\n"
            "- Keep each bullet <= 25 words.\n"
            "- Do not include recommendations, only recap what was covered/critical.\n\n"
            f"Case text:\n{self.case_data}"
        )
        try:
            recap = chat_complete(
                [
                    {"role": "system", "content": "You produce faithful, concise case-grounded summaries."},
                    {"role": "user", "content": prompt},
                ]
            )
            cleaned = (recap or "").strip()
            if cleaned.lower().startswith("quick recap"):
                return cleaned
            if cleaned:
                return f"Quick recap of skipped sections:\n{cleaned}"
            return None
        except Exception as e:
            logger.warning(f"Case-grounded skip summary failed: {e}")
            return None

    def _manager_phase_chat(self) -> str:
        """Main orchestrator directly handles DDx tutoring."""
        system_prompt = MANAGER_DIFFERENTIAL_SYSTEM_PROMPT.format(
            case=self.case_data,
            csv_guidance=self.csv_guidance,
        )

        messages = [{"role": "system", "content": system_prompt}] + self.conversation_history[-10:]
        try:
            return chat_complete(messages)
        except Exception as e:
            logger.error(f"Manager phase chat failed ({self.current_state}): {e}")
            return "Let's continue step-by-step. What is your current reasoning?"

    def _parse_display_figure_tool_call(self, response: str) -> tuple[str, Optional[str]]:
        """Parse display_figure tool calls from agent output and strip from user-visible text.

        Supported formats:
        - [[display_figure:1]]
        - display_figure(1)
        """
        if not response:
            return response, None

        bracket_pattern = r"\[\[\s*display_figure\s*:\s*(\d+)\s*\]\]"
        paren_pattern = r"\bdisplay_figure\(\s*(\d+)\s*\)"

        match = re.search(bracket_pattern, response, flags=re.IGNORECASE)
        if not match:
            match = re.search(paren_pattern, response, flags=re.IGNORECASE)
            if not match:
                return response, None
            cleaned = re.sub(paren_pattern, "", response, count=1, flags=re.IGNORECASE).strip()
            return cleaned, match.group(1)

        cleaned = re.sub(bracket_pattern, "", response, count=1, flags=re.IGNORECASE).strip()
        return cleaned, match.group(1)

    def _extract_figure_reference(self, text: str) -> Optional[str]:
        """Extract Figure N references from plain text."""
        if not text:
            return None
        match = re.search(r"\bfig(?:ure)?\.?\s*(\d+)\b", text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _should_proactively_display_image(self, user_message: str) -> bool:
        """Detect user requests where an image should be proactively shown."""
        if not user_message:
            return False
        text = user_message.lower()
        if not self.images:
            return False

        visual_keywords = (
            "physical exam",
            "on exam",
            "what do i see",
            "what do you see",
            "what is seen",
            "appearance",
            "look like",
            "visible",
            "inspection",
            "eye exam",
            "skin exam",
            "lesion",
            "rash",
            "swelling",
            "findings",
            "figure",
            "image",
            "photo",
            "picture",
            "diagnostic image",
            "scan",
            "ct",
            "mri",
            "xray",
            "x-ray",
            "radiograph",
            "ultrasound",
            "gram stain",
            "culture",
            "biopsy",
            "histology",
            "pathology",
            "immunofluorescence",
            "test result",
            "results",
        )
        return any(keyword in text for keyword in visual_keywords)

    def _default_figure_number(self) -> Optional[str]:
        """Return a stable default figure number for proactive visual display."""
        if not self.images:
            return None

        nums: list[int] = []
        for img in self.images:
            match = re.search(r"figure\s*(\d+)", img.lower())
            if match:
                nums.append(int(match.group(1)))
        if nums:
            return str(min(nums))
        return "1"

    def _extract_figure_captions(self, case_text: str) -> Dict[str, str]:
        """Extract figure -> caption mapping from case text."""
        if not case_text:
            return {}
        captions: Dict[str, str] = {}
        pattern = re.compile(r"Figure\s*(\d+)\s*[.:\-]\s*([^\n\r]+)", re.IGNORECASE)
        for match in pattern.finditer(case_text):
            num = match.group(1).strip()
            caption = match.group(2).strip()
            if num:
                captions[num] = caption
        return captions

    def _select_proactive_figure(self, user_message: str) -> Optional[str]:
        """Pick the best figure by matching user intent against figure captions."""
        if not self.images:
            return None
        if not self.figure_captions:
            return self._default_figure_number()

        query_tokens = self._tokenize_for_match(user_message)
        if not query_tokens:
            return self._default_figure_number()

        best_num: Optional[str] = None
        best_score = 0
        for fig_num, caption in self.figure_captions.items():
            caption_tokens = self._tokenize_for_match(caption)
            overlap = len(query_tokens & caption_tokens)
            if overlap > best_score:
                best_score = overlap
                best_num = fig_num

        if best_num and best_score > 0:
            return best_num
        return self._default_figure_number()

    def _tokenize_for_match(self, text: str) -> set[str]:
        words = re.findall(r"[a-z0-9]+", (text or "").lower())
        stop = {
            "the", "a", "an", "and", "or", "of", "to", "for", "with", "on", "in", "at",
            "is", "are", "do", "does", "what", "how", "can", "you", "i", "me", "my",
            "show", "see", "look", "image", "figure", "findings", "result", "results"
        }
        return {w for w in words if w not in stop and len(w) > 2}

    def display_image(self, figure_num: str) -> Optional[str]:
        """display_image tool for orchestrator: returns a URL for a figure number."""
        if not self.images or not self.case_id:
            return None
        clean_num = re.sub(r"[^0-9]", "", str(figure_num))
        if not clean_num:
            return None
        for img in self.images:
            if f"figure{clean_num}" in img.lower():
                # track reveal, but allow re-showing when explicitly requested by tool call
                self.revealed_images.add(img)
                return f"/images/{self.case_id}/{img}"
        return None

    def _determine_state(self, user_message: str) -> Dict[str, Any]:
        """
        Use LLM to determine the current state based on history.
        """
        payload = {
            "current_state": self.current_state,
            "latest_user_message": user_message,
            "recent_history": self.conversation_history[-5:] # Last 5 turns
        }
        
        try:
            response = chat_complete(
                [
                    {"role": "system", "content": ORCHESTRATOR_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload)}
                ],
                response_format={"type": "json_object"}
            )
            data = json.loads(response)
            if not isinstance(data, dict):
                return {"state": self.current_state}
            return data
        except Exception as e:
            logger.error(f"State determination failed: {e}")
            return {"state": self.current_state}

    def get_first_message(self) -> str:
        """Get the opening message from the patient agent."""
        if isinstance(self.agents["information_gathering"], PatientAgent):
             return self.agents["information_gathering"].first_sentence
        return "Hello."
