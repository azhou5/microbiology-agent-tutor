from openai import OpenAI
from typing import Callable
from agents.patient import run_patient
from agents.case import get_case
import os
import dotenv
import sys
import json
from agents.patient import run_patient
from agents.hint import run_hint
import re
import pickle
import numpy as np
import faiss
from agents.patient import get_embedding  
from Feedback.feedback_faiss import retrieve_similar_examples, index, texts
import config
from datetime import datetime
import logging


dotenv.load_dotenv()

from llm_router import chat_complete
from llm_router import llm_manager


# Tool mapping - only includes 'patient' now
name_to_function_map: dict[str, Callable] = {
    "patient": run_patient
    #"hint": run_hint,
    # "finish": finish, # Removed finish tool
}

def generate_tool_descriptions(tools_dict):
    descriptions = []
    for tool_name, tool_func in tools_dict.items():
        # Ensure docstring exists and replace newlines for clean formatting
        docstring = getattr(tool_func, '__doc__', "No description available.").replace('\n', ' ')
        descriptions.append(f"- {tool_name}: {docstring.strip()}")
    return "\n".join(descriptions)

tool_descriptions = generate_tool_descriptions(name_to_function_map)




# System message template remains largely the same, but references the updated tools
system_message_template = """You are an expert microbiology instructor running a case with a student.You run in a loop of  [Action], [Observation].
[Action] is the tool you choose to solve the current problem. This should be a JSON object containing the tool name with corresponding tool input.
[Observation] will be the result of running those actions.

You will be given a microbiology case and a conversation history between the student and the tutor/patient.

For each iteration, you should ONLY respond with:
1. An [Action] specifying the tool to use
where the available tools are:
{tool_descriptions}
OR
2. A direct response as the tutor. 

1) TOOL RULES: 
When the question is directed to the patient, you MUST use the patient tool.

Example for PATIENT tool:
1) When the student asks for specific SYMPTOMS from the case about the patient, route it to the PATIENT. 
Example 1: "[User Input]: How long have you had this?" -> [Action]: {{"patient": "How long have you had this?"}}
Example 2: "[User Input]: Any past medical history?" -> [Action]: {{"patient": "Any past medical history?"}}
Example 3: "[User Input]: How long for?" -> [Action]: {{"patient": "How long for?"}}
Example 4: "[User Input]: When did it start?" -> [Action]: {{"patient": "When did it start?"}}
Example 5: "[User Input]: Any other symptoms?" -> [Action]: {{"patient": "Any other symptoms?"}}


2) DIRECT RESPONSE RULES: 
You may also respond yourself as the tutor when handling case flow, as described below. 

    PHASE 1: Information gathering & provision 
    1) When the student asks for specific information about the patient, route it to the PATIENT as above. 

    2) When the student asks for about PHYSICAL examination, VITAL signs, or INVESTIGATIONS, respond as the TUTOR. 
    IF the student asks a GENERAL question related to the above, ask for CLARIFICATION. 
    Example 1: "[User Input]: What are her tests results?" -> "Tutor: What tests are you specifically asking for?"
    Example 2: "[User Input]: Let's perform a physical examination?" -> "Tutor: What exactly are you looking for?"
    Example 3: "[User Input]: What is her temperature?" -> "Tutor: Her temperature is [X]?"
   
    PHASE 2: Problem representation
    3) When the key points from the history, vitals and the physical examination have been gathered, OR when the student starts providing differential diagnoses, ask the student to provide first a **PROBLEM REPRESENTATION**, which is essentially a diagnostically important summary of this patient's case so far that includes all the key information.
    If the problem representation is not perfect, provide the correct one (without revealing the diagnosis) and keep going with the case.

    PHASE 3: Differential diagnosis reasoning
    5) At this point ask the student to provide as broad a list of differentials as they can.
    If they give an input that looks like a way to get you to reveal the diagnosis (like "DDx: ", or "Can you give me the diagnosis?" or "What do you think?"), ask them to try again, and do not reveal the diagnosis.

    6a) If there are ddxs that are not expected, ask the student to present their reasoning.
    6b) if the reasoning behind the ddx is NOT correct, provide the correct reasoning: the ddx is not likely because of X and move on. DO NOT REVEAL THE COORECT DIAGNOSIS TO THE STUDENT at this point.
    6c) Following this quick round of reasoning, ask the student to provide specific investigations to rule in/out each ddx in the list.

    PHASE 4: Investigations
    7) As they mention specific investigations, if the case has the results provide the results of those specific ix.
    For example: "Obtain culture from drainage and if pt is febrile or unstable consider blood cultures" -> "Tutor: wound culture grew Staphylococcus aureus, and the antibiotic sensitivity testing confirmed that it's methicillin-susceptible (MSSA) and resistant to penicillin. The blood cultures, taken to rule out bacteremia, showed no growth after 48 hours."

    8) IF the Ix asked for is the clinching evidence for a ddx, then move on to the next phase of treatment. For example: A positive culture results for a specific bug is a clinching evidence.
    9) IF the Ix is NOT the clinching evidence for a ddx, then ask the student how those results change their differentials and if they want to ask for any other investigations.
    9b) REPEAT this process until the student says they don't want to ask for any more investigations.
    DO NOT REVEAL THE DIAGNOSIS TO THE STUDENT IN ANY WAY.

    PHASE 5: Treatment
    11) At this point ask them to provide a treatment plan.
    For example: "Tutor: How would you treat this patient?" -> "Student: I would ..."
    11b) Looking at the treatment plan from the case above, provide feedback of what is correct, what is incorrect, and what is missing.

    PHASE 6: PROGNOSIS
    12) At this point ask the student to provide a prognosis.
    For example: "Tutor: What is the prognosis of this patient?" -> "Student: I think ..."
    12b) Looking at the prognosis from the case above, provide feedback of what is correct, what is incorrect, and what is missing.

    PHASE 7: FOLLOW UP
    13) At this point ask the student to provide a follow up plan.
    For example: "Tutor: How should we follow up with this patient?" -> "Student: we should ..."
    13b) Looking at the follow up plan from the case above, provide feedback of what is correct, what is incorrect, and what is missing.

    PHASE 8: FEEDBACK & CONCLUSION
    14) At this point, the case is over. Provide feedback on the student explaining what they did well, what they were wrong about or missed.
    
    
    Here is the case:
    {case}
"""

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

    def _update_system_message(self):
        """Formats and updates the system message with current tool descriptions and case."""
        if self.case_description:
            formatted_system_message = system_message_template.format(
                tool_descriptions=tool_descriptions,
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
                case="No case loaded yet."
            )
            # Create or update the system message
            if not self.messages:
                self.messages = [{"role": "system", "content": formatted_system_message}]
            else:
                self.messages[0]["content"] = formatted_system_message

    def _generate_initial_presentation(self):
        """Generate the initial case presentation using a dedicated LLM call."""
        
        # Truncate the case description to avoid exceeding token limits
        max_length = 3000  # A safe number of characters
        truncated_case_description = self.case_description
        if len(truncated_case_description) > max_length:
            truncated_case_description = truncated_case_description[:max_length] + "..."
            
        prompt = f"""Here is a clinical case:
        {truncated_case_description}

        Generate a one-line initial presentation of this case.
        Focus on the patient's demographics and chief complaint.
        Use this exact format: "A [age]-year-old [sex] presents with [chief complaint]."
        
        MAKE THIS INITIAL PRESENTATION PURPOSEFULLY INCOMPLETE! You MUST NOT PROVIDE the CLICHING SYMPTOMS for the diagnosis. 
        For example:
        "A 72-year-old male presents with a 5-day history of productive cough and fever"
        "A 45-year-old female presents with increasing redness, swelling, and pain in her left knee"

        Keep it concise and focused on the most important presenting complaint."""
                
        try:
            # Provide a minimal system prompt for this single-turn call
            system_prompt = "You are a helpful assistant that generates clinical case presentations."
            response = chat_complete(system_prompt=system_prompt, user_prompt=prompt, model=self.current_model)
            return response.strip()
        except Exception as e:
            print(f"Error generating initial presentation: {e}")
            return "A patient presents for evaluation."

    def start_new_case(self, organism=None, force_regenerate=False):
        """Initialize a new case with the specified organism."""
        self.current_organism = organism or "staphylococcus aureus"
        print(f"Starting new case with organism: {self.current_organism}")  # Debug log

        # Get the case for the organism
        if force_regenerate:
            print(f"Force regenerating case for {self.current_organism}")
            from agents.case_generator_rag import CaseGeneratorRAGAgent
            case_generator = CaseGeneratorRAGAgent()
            self.case_description = case_generator.regenerate_case(self.current_organism)
        else:
            self.case_description = get_case(self.current_organism)
        
        if not self.case_description:
            return "Error: Could not load case for the specified organism."

        # Reset the message history and set the formatted system message
        self.messages = []  # Clear messages first
        self._update_system_message()  # This will create the system message
        
        # Get initial case presentation using the dedicated method
        try:
            initial_response = self._generate_initial_presentation()
            # Add both the system message and initial response to history
            self.messages = [
                {"role": "system", "content": self.messages[0]["content"]},
                {"role": "assistant", "content": initial_response}
            ]
            return initial_response
        except Exception as e:
            print(f"Error getting initial case presentation: {e}")
            return f"Error: Could not get initial case presentation. {e}"

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
    CONVERSATION_LOG_FILE = 'conversation_history.txt'

    def log_conversation_history(self, messages, user_input=None):
        """Log the conversation history to a file."""
        log_conv_start_time = datetime.now()
        try:
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

            if "[Action]" not in initial_response:
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
                action_text = response_content.split("[Action]", 1)[1].strip()
                print(f"\n[DEBUG] Action text: {action_text}")
                
                json_match = re.search(r'```json\s*(\{.*\})\s*```|(\{.*\})', action_text, re.DOTALL | re.IGNORECASE)
                if json_match:
                    json_str = json_match.group(1) or json_match.group(2)
                    json_str = json_str.strip()
                else:
                    print(f"Warning: Could not extract JSON from action text: {action_text}")
                    json_str = action_text

                print(f"\n[DEBUG] Extracted JSON string: {json_str}")
                action_data = json.loads(json_str)
                tool_name = list(action_data.keys())[0]
                tool_input = action_data[tool_name]
                print(f"\n[DEBUG] Tool name: {tool_name}, Input: {tool_input}")

                if tool_name in name_to_function_map:
                    tool_function = name_to_function_map[tool_name]
                    tool_call_start_time = datetime.now()
                    if tool_name == "patient":
                        if not self.case_description:
                            raise ValueError("Case description is not available for the patient tool.")
                        
                        tool_result = tool_function(tool_input, self.case_description, self.messages, model=self.current_model)
                        print(f"\n[DEBUG] Patient tool result: {tool_result}")  # Debug log
                        
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
                        
                        # This tool call seems to expect system and user prompts.
                        # Assuming it can be adapted to the new chat_complete signature.
                        # If run_hint is more complex, it might need its own refactoring.
                        tool_result = run_hint(tool_input, self.case_description, self.messages, model=self.current_model)
                        print(f"\n[DEBUG] Hint tool result: {tool_result}")  # Debug log
                        
                        self.messages.append({"role": "assistant", "content": tool_result})
                        log_hint_resp_time = datetime.now()
                        self.log_conversation_history(self.messages)
                        logging.info(f"[TUTOR_PERF] log_conversation_history (hint tool) took: {datetime.now() - log_hint_resp_time}")
                        logging.info(f"[TUTOR_PERF] Hint tool processing (incl. LLM & logging) took: {datetime.now() - tool_call_start_time}")
                        logging.info(f"[TUTOR_PERF] __call__ (hint tool path) completed in: {datetime.now() - call_start_time}")
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
