from openai import OpenAI
from typing import Callable
from agents.patient import run_patient
from agents.case import get_case
from agents.hint import run_hint
from agents.socratic import run_socratic
import os
import dotenv
import sys
import json
import re
import pickle
import numpy as np
import faiss
from agents.patient import get_embedding  
from Feedback.feedback_faiss import retrieve_similar_examples, index, texts
import config
from datetime import datetime
import logging
import time


dotenv.load_dotenv()

from llm_router import chat_complete
from llm_router import llm_manager
from tutor_prompts_tools import generate_tool_descriptions, get_system_message_template, get_tool_rules


# Tool mapping - includes all three agents
name_to_function_map: dict[str, Callable] = {
    "patient": run_patient,
    "hint": run_hint,
    "socratic": run_socratic
}



# Removed top-level messages and history lists
# Removed main() function
class MedicalMicrobiologyTutor:
    """Adapter class to make the function-based tutor compatible with the web app."""

    def __init__(self, 
                 output_tool_directly: bool = config.OUTPUT_TOOL_DIRECTLY, 
                 run_with_faiss: bool = config.USE_FAISS, 
                 reward_model_sampling: bool = config.REWARD_MODEL_SAMPLING,
                 model_name: str = None):
        
        self.output_tool_directly = output_tool_directly
        self.run_with_faiss = run_with_faiss
        self.reward_model_sampling = reward_model_sampling
        self.current_model = model_name or config.API_MODEL_NAME

        self.id = "tutor_agent"
        # Initialize messages with a placeholder system message
        self.messages = [{"role": "system", "content": "Initializing..."}]
        self.current_organism = None
        self.case_description = None # To store the current case details
        self.last_user_message = "" # Keep track of the last user message if needed for context
        self.initial_presentations = self._load_initial_presentations()
        self.hpi_data = self._load_hpi_data()

    def _load_initial_presentations(self):
        """Loads pre-generated initial case sentences from a JSON file."""
        try:
            # Assuming this script is run from the V3_reasoning_multiagent directory
            with open('Case_Outputs/ambiguous_with_ages.json', 'r') as f:
                presentations = json.load(f)
                logging.info("Successfully loaded pre-generated initial presentations.")
                return presentations
        except FileNotFoundError:
            logging.warning("ambiguous_with_ages.json not found. Will fall back to LLM generation.")
            return {}
        except json.JSONDecodeError:
            logging.error("Error decoding ambiguous_with_ages.json. Will fall back to LLM generation.")
            return {}

    def _load_hpi_data(self):
        """Loads pre-generated HPI sections from a JSON file."""
        try:
            with open('Case_Outputs/HPI_per_organism.json', 'r') as f:
                hpi_data = json.load(f)
                logging.info("Successfully loaded pre-generated HPI data.")
                return hpi_data
        except FileNotFoundError:
            logging.warning("HPI_per_organism.json not found. Will fall back to using full case description for generation.")
            return {}
        except json.JSONDecodeError:
            logging.error("Error decoding HPI_per_organism.json. Will fall back to full case description.")
            return {}

    def _has_tool_action(self, response: str) -> bool:
        """
        Check if the response contains a tool action in various formats.
        
        Args:
            response: The LLM response to check
            
        Returns:
            bool: True if a tool action is detected, False otherwise
        """
        # Check for explicit [Action] marker
        if "[Action]" in response:
            return True
            
        # Generate dynamic pattern from available tool names
        tool_names = "|".join(re.escape(name) for name in name_to_function_map.keys())
        
        # Check for JSON object that matches our tool names (including variations)
        # Create a more flexible pattern that catches variations like "socratic_agent"
        tool_keywords = "|".join(re.escape(name) for name in name_to_function_map.keys())
        json_patterns = [
            r'```json\s*(\{.*\})\s*```',  # JSON in code blocks
            rf'(\{{[^{{}}]*"(?:{tool_keywords})(?:_\w+)?"[^{{}}]*\}})',  # Direct JSON with tool names (including variations)
        ]
        
        for pattern in json_patterns:
            if re.search(pattern, response, re.DOTALL | re.IGNORECASE):
                return True
                
        return False

    def _extract_tool_action(self, response: str) -> tuple[str, str]:
        """
        Extract tool name and input from various response formats.
        
        Args:
            response: The LLM response containing the tool action
            
        Returns:
            tuple: (tool_name, tool_input) or (None, None) if extraction fails
        """
        # Generate dynamic pattern from available tool names
        tool_names = "|".join(re.escape(name) for name in name_to_function_map.keys())
        
        # First try to extract from [Action] format
        if "[Action]" in response:
            action_text = response.split("[Action]", 1)[1].strip()
            json_match = re.search(r'```json\s*(\{.*\})\s*```|(\{.*\})', action_text, re.DOTALL | re.IGNORECASE)
            if json_match:
                json_str = json_match.group(1) or json_match.group(2)
                json_str = json_str.strip()
            else:
                json_str = action_text
        else:
            # Try to find JSON directly in the response using dynamic pattern
            # Use flexible pattern that catches variations like "socratic_agent"
            tool_keywords = "|".join(re.escape(name) for name in name_to_function_map.keys())
            json_match = re.search(rf'```json\s*(\{{.*\}})\s*```|(\{{[^{{}}]*"(?:{tool_keywords})(?:_\w+)?"[^{{}}]*\}})', response, re.DOTALL | re.IGNORECASE)
            if json_match:
                json_str = json_match.group(1) or json_match.group(2)
                json_str = json_str.strip()
            else:
                return None, None
        
        try:
            action_data = json.loads(json_str)
            tool_name = list(action_data.keys())[0]
            tool_input = action_data[tool_name]
            
            # Apply fuzzy matching to handle variations in tool names
            tool_name = self._fuzzy_match_tool_name(tool_name)
            
            return tool_name, tool_input
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            print(f"Warning: Could not parse tool action JSON: {e}")
            return None, None

    def _fuzzy_match_tool_name(self, tool_name: str) -> str:
        """
        Apply fuzzy matching to handle variations in tool names.
        
        Args:
            tool_name: The extracted tool name that might not match exactly
            
        Returns:
            str: The correct tool name from name_to_function_map, or original if no match
        """
        tool_name_lower = tool_name.lower()
        
        # Define keyword mappings for fuzzy matching
        keyword_mappings = {
            'socratic': 'socratic',
            'patient': 'patient', 
            'hint': 'hint'
        }
        
        # First try exact match
        if tool_name in name_to_function_map:
            return tool_name
            
        # Try fuzzy matching based on keywords
        for keyword, correct_name in keyword_mappings.items():
            if keyword in tool_name_lower:
                print(f"[DEBUG] Fuzzy matched '{tool_name}' -> '{correct_name}'")
                return correct_name
        
        # If no fuzzy match found, return original (will trigger error in main logic)
        print(f"[DEBUG] No fuzzy match found for '{tool_name}', keeping original")
        return tool_name

    def _update_system_message(self):
        """Formats and updates the system message with current tool descriptions and case."""
        # Generate tool descriptions and rules dynamically
        tool_descriptions = generate_tool_descriptions(name_to_function_map)
        tool_rules = get_tool_rules()
        
        # Get the system message template
        system_message_template = get_system_message_template()
        
        if self.case_description:
            formatted_system_message = system_message_template.format(
                tool_descriptions=tool_descriptions,
                tool_rules=tool_rules,
                case=self.case_description
            )
            # Create or update the system message
            if not self.messages:
                self.messages = [{"role": "system", "content": formatted_system_message}]
            else:
                self.messages[0]["content"] = formatted_system_message
        else:
            formatted_system_message = system_message_template.format(
                tool_descriptions=tool_descriptions,
                tool_rules=tool_rules,
                case="No case loaded yet."
            )
            # Create or update the system message
            if not self.messages:
                self.messages = [{"role": "system", "content": formatted_system_message}]
            else:
                self.messages[0]["content"] = formatted_system_message

    def _generate_initial_presentation(self):
        """Generate the initial case presentation using a dedicated LLM call with retries."""
        
        # Prioritize HPI data as the source for generation. Fall back to full case description.
        text_to_summarize = self.hpi_data.get(self.current_organism)
        if not text_to_summarize:
            logging.warning(f"No HPI data for '{self.current_organism}'. Falling back to full case description.")
            text_to_summarize = self.case_description
            # Truncate the full case description to avoid exceeding token limits
            max_length = 3000  # A safe number of characters
            if len(text_to_summarize) > max_length:
                text_to_summarize = text_to_summarize[:max_length] + "..."
        else:
            logging.info(f"Using HPI data for '{self.current_organism}' to generate initial presentation.")

        if not text_to_summarize:
            logging.error("No content available to generate an initial presentation.")
            return None

        prompt = f"""Here is a clinical case summary:
        {text_to_summarize}

        Generate a one-line initial presentation of this case.
        Focus on the patient's demographics and chief complaint.
        Use this exact format: "A [age]-year-old [sex] presents with [chief complaint]."
        
        MAKE THIS INITIAL PRESENTATION PURPOSEFULLY INCOMPLETE! You MUST NOT PROVIDE the CLICHING SYMPTOMS for the diagnosis.
        For example:
        "A 72-year-old male presents with a 5-day history of productive cough and fever"
        "A 45-year-old female presents with increasing redness, swelling, and pain in her left knee"

        Keep it concise and focused on the most important presenting complaint."""
                
        max_retries = 3
        for attempt in range(max_retries):
            try:
                system_prompt = "You are a helpful assistant that generates clinical case presentations."
                response = chat_complete(
                    system_prompt=system_prompt, 
                    user_prompt=prompt, 
                    model=self.current_model
                )
                
                # If we get a valid response, return it immediately.
                if response:
                    return response.strip()
                
                # If the response is None, log it and retry.
                logging.warning(f"Initial presentation generation failed. Retrying... (Attempt {attempt + 1}/{max_retries})")

            except Exception as e:
                logging.error(f"An unexpected error occurred in _generate_initial_presentation on attempt {attempt + 1}/{max_retries}: {e}")
            
            time.sleep(1) # Wait 1 second before the next attempt
        
        logging.error("All retries for initial presentation failed. Returning a default presentation.")
        return "A patient presents for evaluation."

    def start_new_case(self, organism=None, force_regenerate=False):
        """Initialize a new case with the specified organism."""
        logging.info(f"[BACKEND_START_CASE] 3a. Tutor's start_new_case method called with organism: '{organism}'.")
        self.current_organism = organism or "staphylococcus aureus"
        logging.info(f"[BACKEND_START_CASE]   - Current organism set to: '{self.current_organism}'")

        # Get the case for the organism
        if force_regenerate:
            logging.info(f"[BACKEND_START_CASE] 3b. Force regenerating case for {self.current_organism}.")
            from agents.case_generator_rag import CaseGeneratorRAGAgent
            case_generator = CaseGeneratorRAGAgent()
            self.case_description = case_generator.regenerate_case(self.current_organism)
        else:
            logging.info(f"[BACKEND_START_CASE] 3b. Getting case for '{self.current_organism}' via get_case().")
            self.case_description = get_case(self.current_organism)
        
        if not self.case_description:
            logging.error("[BACKEND_START_CASE] <<< Failed to load case description.")
            return "Error: Could not load case for the specified organism."

        logging.info("[BACKEND_START_CASE] 3e. Resetting message history and updating system message.")
        # Reset the message history and set the formatted system message
        self.messages = []  # Clear messages first
        self._update_system_message()  # This will create the system message
        
        logging.info("[BACKEND_START_CASE] 4. Getting initial case presentation.")
        # Try to get the initial presentation from the pre-generated file first.
        initial_response = self.initial_presentations.get(self.current_organism)
        
        # If not found, fall back to generating it.
        if not initial_response:
            logging.warning(f"No pre-generated presentation for '{self.current_organism}'. Falling back to LLM generation.")
            try:
                initial_response = self._generate_initial_presentation()
            except Exception as e:
                logging.error(f"[BACKEND_START_CASE] <<< Error getting initial presentation: {e}")
                return f"Error: Could not get initial case presentation. {e}"
        else:
            logging.info(f"Using pre-generated initial presentation for '{self.current_organism}'.")

        if not initial_response:
             logging.error(f"[BACKEND_START_CASE] <<< Failed to get any initial presentation for {self.current_organism}.")
             return f"Error: Could not produce an initial presentation for {self.current_organism}."

        logging.info("[BACKEND_START_CASE] 5. Adding initial messages to history and returning response.")
        # Add both the system message and initial response to history
        self.messages = [
            {"role": "system", "content": self.messages[0]["content"]},
            {"role": "assistant", "content": initial_response}
        ]
        return initial_response

    def get_available_organisms(self):
        """Get a list of organisms that have cached cases."""
        try:
            from agents.case_generator_rag import CaseGeneratorRAGAgent
            case_generator = CaseGeneratorRAGAgent()
            return case_generator.get_cached_organisms()
        except Exception as e:
            print(f"Error getting cached organisms: {e}")
            return []

    def clear_case_cache(self, organism=None):
        """Clear the case cache for a specific organism or all organisms."""
        try:
            from agents.case_generator_rag import CaseGeneratorRAGAgent
            case_generator = CaseGeneratorRAGAgent()
            case_generator.clear_cache(organism)
            return f"Cache cleared for {organism if organism else 'all organisms'}"
        except Exception as e:
            print(f"Error clearing cache: {e}")
            return f"Error clearing cache: {e}"

    def reset(self):
        """Reset the tutor state for a new session. Only call this when explicitly starting a new case."""
        # Reset messages to initial state (or just clear them)
        self.messages = [{"role": "system", "content": "Initializing..."}]
        self.current_organism = None
        self.case_description = None
        self.last_user_message = ""

    # Add conversation history logging
    CONVERSATION_LOG_FILE = 'conversation_logs/conversation_history.txt'

    def log_conversation_history(self, messages, user_input=None):
        """Log the conversation history to a file."""
        log_conv_start_time = datetime.now()
        try:
            # Ensure conversation_logs directory exists
            import os
            os.makedirs('conversation_logs', exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.CONVERSATION_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"Timestamp: {timestamp}\n")
                if user_input:
                    f.write(f"User Input: {user_input}\n")
                f.write("Current Conversation History:\n")
                for msg in messages:
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')
                    f.write(f"{role.upper()}: {content}\n")
                f.write(f"{'='*50}\n")
        except Exception as e:
            print(f"Error logging conversation history: {e}")
        logging.info(f"[TUTOR_PERF] log_conversation_history took: {datetime.now() - log_conv_start_time}")

    def __call__(self, task):
        """Process a user message (task) and return the tutor's response."""
        call_start_time = datetime.now()
        logging.info(f"[TUTOR_PERF] __call__ started at {call_start_time}")

        if isinstance(task, str):
            message_content = task
        elif hasattr(task, 'instruction'):
            message_content = task.instruction
        else:
            print(f"Warning: Unexpected task format: {type(task)}")
            message_content = str(task)

        self.last_user_message = message_content
        print(f"\n[DEBUG] User message: {message_content}")

        should_append_user_message = True
        if self.messages and len(self.messages) > 0:
            last_msg = self.messages[-1]
            if last_msg.get("role") == "user" and last_msg.get("content") == message_content:
                should_append_user_message = False

        if should_append_user_message:
            self.messages.append({"role": "user", "content": message_content})

        log_user_msg_time = datetime.now()
        self.log_conversation_history(self.messages, user_input=message_content if should_append_user_message else None)
        logging.info(f"[TUTOR_PERF] log_conversation_history (user msg) took: {datetime.now() - log_user_msg_time}")

        try:
            initial_llm_call_start_time = datetime.now()
            # Use the full message history for multi-turn chat
            initial_response = llm_manager.generate_response(self.messages, model=self.current_model)
            logging.info(f"[TUTOR_PERF] Initial LLM call (generate_response) took: {datetime.now() - initial_llm_call_start_time}")
            print(f"\n[DEBUG] Initial LLM response: {initial_response}")

            if not self._has_tool_action(initial_response):
                if self.run_with_faiss and index is not None:
                    faiss_start_time = datetime.now()
                    try:
                        recent_context = ""
                        if self.messages:
                            recent_context = "Chat history:\n"
                            for msg in self.messages[-5:-1]:
                                if isinstance(msg, dict) and "role" in msg and "content" in msg:
                                    recent_context += f"{msg['role']}: {msg['content']}\n"
                        
                        embedding_text = recent_context
                        embedding = get_embedding(embedding_text)
                        distances, indices = index.search(np.array([embedding]).astype('float32'), k=4)
                        similar_examples = [texts[idx] for idx in indices[0]]
                        examples_text = "\n\nSimilar tutor examples with feedback (including rated messages and expert feedback):\n" + "\n---\n".join(similar_examples)
                        
                        original_system_content = self.messages[0]["content"]
                        enhanced_system_content = original_system_content + examples_text + "\n\nYou should provide high-quality tutor responses based on the examples and feedback above."
                        enhanced_messages = self.messages.copy()
                        enhanced_messages[0]["content"] = enhanced_system_content
                        
                        print(examples_text)
                        enhanced_llm_call_start_time = datetime.now()
                        response_content = llm_manager.generate_response(enhanced_messages, model=self.current_model)
                        logging.info(f"[TUTOR_PERF] Enhanced LLM call with FAISS took: {datetime.now() - enhanced_llm_call_start_time}")
                        print(f"\n[DEBUG] Enhanced LLM response with FAISS: {response_content}")
                    except Exception as e:
                        print(f"Warning: FAISS retrieval failed, using original response: {e}")
                        response_content = initial_response
                    logging.info(f"[TUTOR_PERF] FAISS processing and optional enhanced call took: {datetime.now() - faiss_start_time}")
                else:
                    response_content = initial_response
                
                self.messages.append({"role": "assistant", "content": response_content})
                log_assistant_msg_time = datetime.now()
                self.log_conversation_history(self.messages)
                logging.info(f"[TUTOR_PERF] log_conversation_history (assistant direct) took: {datetime.now() - log_assistant_msg_time}")
                logging.info(f"[TUTOR_PERF] __call__ (direct response path) completed in: {datetime.now() - call_start_time}")
                return response_content
            
            action_processing_start_time = datetime.now()
            response_content = initial_response
            try:
                # Use robust tool action extraction
                tool_name, tool_input = self._extract_tool_action(response_content)
                
                if tool_name is None or tool_input is None:
                    print(f"Warning: Could not extract tool action from response: {response_content}")
                    # Fall back to direct response
                    self.messages.append({"role": "assistant", "content": response_content})
                    self.log_conversation_history(self.messages)
                    return response_content
                
                print(f"\n[DEBUG] Tool name: {tool_name}, Input: {tool_input}")

                if tool_name in name_to_function_map:
                    tool_function = name_to_function_map[tool_name]
                    tool_call_start_time = datetime.now()
                    if tool_name == "patient":
                        if not self.case_description:
                            raise ValueError("Case description is not available for the patient tool.")
                        
                        tool_result = tool_function(tool_input, self.case_description, self.messages, model=self.current_model)
                        print(f"\n[DEBUG] Patient tool result: {tool_result}")  # Debug log
                        
                        # --- GRACEFUL FALLBACK ---
                        if not tool_result or not tool_result.strip():
                            print("[WARN] Patient tool returned an empty response. Using fallback.")
                            tool_result = "Patient: I'm not sure how to answer that. Could you ask in a different way?"
                        # --- END GRACEFUL FALLBACK ---

                        if self.output_tool_directly:
                            tool_result = re.sub(r'\[Action\]:\s*|\s*\[Observation\]:\s*', '', tool_result)
                            tool_result = re.sub(r'```json\s*|\s*```', '', tool_result)
                            tool_result = re.sub(r'^\s*{\s*"patient"\s*:\s*"|"\s*}\s*$', '', tool_result)
                            tool_result = tool_result.strip()
                            if not tool_result.startswith("Patient: "):
                                tool_result = f"Patient: {tool_result}"
                        
                        print(f"\n[DEBUG] Final cleaned response: {tool_result}")
                        self.messages.append({"role": "assistant", "content": tool_result})
                        log_patient_resp_time = datetime.now()
                        self.log_conversation_history(self.messages)
                        logging.info(f"[TUTOR_PERF] log_conversation_history (patient tool) took: {datetime.now() - log_patient_resp_time}")
                        logging.info(f"[TUTOR_PERF] Patient tool processing (incl. LLM & logging) took: {datetime.now() - tool_call_start_time}")
                        logging.info(f"[TUTOR_PERF] __call__ (patient tool path) completed in: {datetime.now() - call_start_time}")
                        return tool_result
                    elif tool_name == "hint":
                        if not self.case_description:
                            raise ValueError("Case description is not available for the hint tool.")
                        
                        tool_result = run_hint(tool_input, self.case_description, self.messages, model=self.current_model)
                        print(f"\n[DEBUG] Hint tool result: {tool_result}")  # Debug log
                        
                        if self.output_tool_directly:
                            tool_result = re.sub(r'\[Action\]:\s*|\s*\[Observation\]:\s*', '', tool_result)
                            tool_result = re.sub(r'```json\s*|\s*```', '', tool_result)
                            tool_result = re.sub(r'^\s*{\s*"hint"\s*:\s*"|"\s*}\s*$', '', tool_result)
                            tool_result = tool_result.strip()
                        
                        self.messages.append({"role": "assistant", "content": tool_result})
                        log_hint_resp_time = datetime.now()
                        self.log_conversation_history(self.messages)
                        logging.info(f"[TUTOR_PERF] log_conversation_history (hint tool) took: {datetime.now() - log_hint_resp_time}")
                        logging.info(f"[TUTOR_PERF] Hint tool processing (incl. LLM & logging) took: {datetime.now() - tool_call_start_time}")
                        logging.info(f"[TUTOR_PERF] __call__ (hint tool path) completed in: {datetime.now() - call_start_time}")
                        return tool_result
                    elif tool_name == "socratic":
                        if not self.case_description:
                            raise ValueError("Case description is not available for the socratic tool.")
                        
                        tool_result = run_socratic(tool_input, self.case_description, self.messages, model=self.current_model)
                        print(f"\n[DEBUG] Socratic tool result: {tool_result}")  # Debug log
                        
                        if self.output_tool_directly:
                            tool_result = re.sub(r'\[Action\]:\s*|\s*\[Observation\]:\s*', '', tool_result)
                            tool_result = re.sub(r'```json\s*|\s*```', '', tool_result)
                            tool_result = re.sub(r'^\s*{\s*"socratic"\s*:\s*"|"\s*}\s*$', '', tool_result)
                            tool_result = tool_result.strip()
                        
                        self.messages.append({"role": "assistant", "content": tool_result})
                        log_socratic_resp_time = datetime.now()
                        self.log_conversation_history(self.messages)
                        logging.info(f"[TUTOR_PERF] log_conversation_history (socratic tool) took: {datetime.now() - log_socratic_resp_time}")
                        logging.info(f"[TUTOR_PERF] Socratic tool processing (incl. LLM & logging) took: {datetime.now() - tool_call_start_time}")
                        logging.info(f"[TUTOR_PERF] __call__ (socratic tool path) completed in: {datetime.now() - call_start_time}")
                        return tool_result
                    else:
                        tool_result = tool_function(tool_input)

                        tool_output = f"[Observation]: {tool_result}"

                        self.messages.append({"role": "system", "content": tool_output})
                        final_llm_call_start_time = datetime.now()
                        final_response = llm_manager.generate_response(self.messages, model=self.current_model)
                        logging.info(f"[TUTOR_PERF] Final LLM call (after other tool) took: {datetime.now() - final_llm_call_start_time}")
                        self.messages.append({"role": "assistant", "content": final_response})
                        log_final_resp_time = datetime.now()
                        self.log_conversation_history(self.messages)
                        logging.info(f"[TUTOR_PERF] log_conversation_history (other tool) took: {datetime.now() - log_final_resp_time}")
                        logging.info(f"[TUTOR_PERF] Other tool processing took: {datetime.now() - tool_call_start_time}")
                        logging.info(f"[TUTOR_PERF] __call__ (other tool path) completed in: {datetime.now() - call_start_time}")
                        return final_response
                else:
                    print(f"Warning: Tool '{tool_name}' not found")
                    retry_llm_call_start_time = datetime.now()
                    retry_response = llm_manager.generate_response(self.messages, model=self.current_model)
                    logging.info(f"[TUTOR_PERF] Retry LLM call (tool not found) took: {datetime.now() - retry_llm_call_start_time}")
                    self.messages.append({"role": "assistant", "content": retry_response})
                    log_retry_resp_time = datetime.now()
                    self.log_conversation_history(self.messages)
                    logging.info(f"[TUTOR_PERF] log_conversation_history (tool not found) took: {datetime.now() - log_retry_resp_time}")
                    logging.info(f"[TUTOR_PERF] __call__ (tool not found path) completed in: {datetime.now() - call_start_time}")
                    return retry_response

            except Exception as e:
                print(f"Error executing tool: {e}")
                error_llm_call_start_time = datetime.now()
                retry_response = llm_manager.generate_response(self.messages, model=self.current_model)
                logging.info(f"[TUTOR_PERF] LLM call (error executing tool) took: {datetime.now() - error_llm_call_start_time}")
                self.messages.append({"role": "assistant", "content": retry_response})
                log_error_resp_time = datetime.now()
                self.log_conversation_history(self.messages)
                logging.info(f"[TUTOR_PERF] log_conversation_history (error executing tool) took: {datetime.now() - log_error_resp_time}")
                logging.info(f"[TUTOR_PERF] __call__ (error executing tool path) completed in: {datetime.now() - call_start_time}")
                return retry_response
            logging.info(f"[TUTOR_PERF] Action processing block took: {datetime.now() - action_processing_start_time}")

        except Exception as e:
            print(f"Error during LLM call or processing: {e}")
            error_response = f"Sorry, an error occurred: {e}"
            self.messages.append({"role": "assistant", "content": error_response})
            log_generic_error_time = datetime.now()
            self.log_conversation_history(self.messages, error_response)
            logging.info(f"[TUTOR_PERF] log_conversation_history (generic error) took: {datetime.now() - log_generic_error_time}")
            logging.info(f"[TUTOR_PERF] __call__ (generic error path) completed in: {datetime.now() - call_start_time}")
            return error_response


# Terminal interactive mode
if __name__ == "__main__" and config.TERMINAL_MODE:
    # Terminal interactive mode
    tutor = MedicalMicrobiologyTutor()
    print("Starting terminal interactive microbiology tutor...")
    # Load default case
    initial = tutor.start_new_case()
    print(initial)
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        if not user_input or user_input.lower() in ("exit", "quit"):
            print("Exiting.")
            break
        response = tutor(user_input)
        print(response)
