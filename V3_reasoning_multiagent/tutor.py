from openai import OpenAI
from typing import Callable
from agents.patient import run_patient
from agents.case import get_case
import os
import dotenv
import sys
import json
from agents.patient import run_patient
import re
import pickle
import numpy as np
import faiss
from agents.patient import get_embedding  
from Feedback.feedback_faiss import retrieve_similar_examples, index, texts
import config


dotenv.load_dotenv()

from llm_router import chat_complete


# Tool mapping - only includes 'patient' now
name_to_function_map: dict[str, Callable] = {
    "patient": run_patient,
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

Note: Only use [Action] when you need to interact with the patient tool. For all other responses (including the initial presenting complaint), respond directly without using [Action].

For each iteration, you should ONLY respond with:
1. An [Action] specifying the tool to use (only when using the patient tool)
OR
A direct response as the tutor

You will be given a microbiology case and a student question.
Available tools:
{tool_descriptions}

When the question is directed to the patient, you MUST use the patient tool.

Example usage:
[User Input]: When did your fever start?
[Action]: {{"patient": "When did your fever start?"}}

You may also respond yourself as the tutor when handling case flow (and doing anything that does not involve the patient), and your personal specifications will be provided below.

   PHASE 1: Information gathering
    1) Start the case by providing an initial presenting complaint. This is a very short punchy first issue the patient comes in with.
    For example: "Preceptor: A 62 year old female presents with increasing redness, swelling, and pain in her left knee."
    Don't add any more output to this, as the student knows to ask more questions.
    2) When the student asks for specific information from the case about the patient, route it to the patient. Then, reeport the patient agen'ts response, with the following format:
    "Patient: <patient response>"
    3) When the student asks for vital signs, or physical examination, or specific investigations, respond as the Tutor, providing ONLY the information asked for. For example: "What are her vital signs?" -> "Tutor: Her vital signs are ... ".

    PHASE 2: Problem representation
    4) When the key points from the history, vitals and the physical examination have been gathered, OR when the student starts providing differential diagnoses, ask the student to provide first a **PROBLEM REPRESENTATION**, which is essentially a diagnostically important summary of this patient's case so far that includes all the key information.
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

    def start_new_case(self, organism=None, force_regenerate=False):
        """Initialize a new case with the specified organism."""
        self.current_organism = organism or "staphylococcus aureus"

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
        
        # Get initial case presentation from the LLM
        try:
            initial_response = chat_complete(self.messages, model=self.current_model)
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
        """Reset the tutor state for a new session."""
        # Reset messages to initial state (or just clear them)
        self.messages = [{"role": "system", "content": "Initializing..."}]
        self.current_organism = None
        self.case_description = None
        self.last_user_message = ""
        # self.history = [] # Reset history if used

    def __call__(self, task):
        """Process a user message (task) and return the tutor's response."""
        if isinstance(task, str):
            message = task
        elif hasattr(task, 'instruction'):
            message = task.instruction
        else:
            print(f"Warning: Unexpected task format: {type(task)}")
            message = str(task)

        self.last_user_message = message
        print(f"\n[DEBUG] User message: {message}")

        self.messages.append({"role": "user", "content": message})

        try:
            # First, get initial response to check if it's a tool call or direct response
            initial_response = chat_complete(self.messages, model=self.current_model)
            print(f"\n[DEBUG] Initial LLM response: {initial_response}")

            # If it's a direct response (no [Action]), add FAISS examples and regenerate
            if "[Action]" not in initial_response:
                # Add FAISS functionality for tutor direct responses
                if self.run_with_faiss and index is not None:
                    try:
                        # Format the recent history similar to how the index was created
                        recent_context = ""
                        if self.messages:
                            recent_context = "Chat history:\n"
                            for msg in self.messages[-5:-1]:  # Get last 4 messages like in patient agent
                                if isinstance(msg, dict) and "role" in msg and "content" in msg:
                                    recent_context += f"{msg['role']}: {msg['content']}\n"
                        
                        # Get embedding for the context (not including current user message in "rated message" since tutor hasn't responded yet)
                        embedding_text = recent_context
                        embedding = get_embedding(embedding_text)
                        
                        # Search for similar tutor examples
                        distances, indices = index.search(np.array([embedding]).astype('float32'), k=4)
                        
                        # Get the most similar examples
                        similar_examples = [texts[idx] for idx in indices[0]]
                        examples_text = "\n\nSimilar tutor examples with feedback (including rated messages and expert feedback):\n" + "\n---\n".join(similar_examples)
                        
                        # Update system message to include examples
                        original_system_content = self.messages[0]["content"]
                        enhanced_system_content = original_system_content + examples_text + "\n\nYou should provide high-quality tutor responses based on the examples and feedback above."
                        
                        # Create enhanced messages for this specific call
                        enhanced_messages = self.messages.copy()
                        enhanced_messages[0]["content"] = enhanced_system_content
                        
                        # Get enhanced response with FAISS examples
                        response_content = chat_complete(enhanced_messages, model=self.current_model)
                        print(f"\n[DEBUG] Enhanced LLM response with FAISS: {response_content}")
                        
                    except Exception as e:
                        print(f"Warning: FAISS retrieval failed, using original response: {e}")
                        response_content = initial_response
                else:
                    response_content = initial_response
                
                self.messages.append({"role": "assistant", "content": response_content})
                print(examples_text)

                return response_content
            
            # Handle [Action] response (tool calls) - no FAISS enhancement since rated message would be from tool
            response_content = initial_response
            try:
                # Extract the action text after [Action]
                action_text = response_content.split("[Action]", 1)[1].strip()
                print(f"\n[DEBUG] Action text: {action_text}")
                
                # Try to parse the JSON, handling both formats:
                # 1. {"patient": "question"}
                # 2. ```json {"patient": "question"}```
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
                    if tool_name == "patient":
                        if not self.case_description:
                            raise ValueError("Case description is not available for the patient tool.")
                        
                        # Pass the current message history
                        tool_result = tool_function(tool_input, self.case_description, self.messages, model=self.current_model)
                        print(f"\n[DEBUG] Patient tool result: {tool_result}")  # Debug log
                        
                        # Clean the response if output_tool_directly is True
                        if self.output_tool_directly:
                            # Remove any [Action] or [Observation] wrappers
                            tool_result = re.sub(r'\[Action\]:\s*|\s*\[Observation\]:\s*', '', tool_result)
                            # Remove any JSON formatting
                            tool_result = re.sub(r'```json\s*|\s*```', '', tool_result)
                            # Remove any remaining JSON structure
                            tool_result = re.sub(r'^\s*{\s*"patient"\s*:\s*"|"\s*}\s*$', '', tool_result)
                            # Clean up any extra whitespace
                            tool_result = tool_result.strip()
                            # Add "Patient: " prefix if not already present
                            if not tool_result.startswith("Patient: "):
                                tool_result = f"Patient: {tool_result}"
                        
                        print(f"\n[DEBUG] Final cleaned response: {tool_result}")
                        
                        # Add the patient's response to the message history
                        self.messages.append({"role": "assistant", "content": tool_result})
                        return tool_result
                    else:
                        # Handle other tools if they are added later
                        tool_result = tool_function(tool_input)

                        tool_output = f"[Observation]: {tool_result}"

                        # Add the action's result (observation) back into the message history
                        self.messages.append({"role": "system", "content": tool_output})

                        # Get a new response from the LLM, now including the tool's observation
                        final_response = chat_complete(self.messages, model=self.current_model)
                        # Add this final assistant response to history
                        self.messages.append({"role": "assistant", "content": final_response})
                        return final_response
                else:
                    # Handle case where the requested tool is not found
                    print(f"Warning: Tool '{tool_name}' not found")
                    # Get a new response from the tutor
                    retry_response = chat_complete(self.messages, model=self.current_model)
                    self.messages.append({"role": "assistant", "content": retry_response})
                    return retry_response

            except Exception as e:
                print(f"Error executing tool: {e}")
                # Just get a new response from the tutor
                retry_response = chat_complete(self.messages, model=self.current_model)
                self.messages.append({"role": "assistant", "content": retry_response})
                return retry_response

        except Exception as e:
            print(f"Error during LLM call or processing: {e}")
            error_response = f"Sorry, an error occurred: {e}"
            self.messages.append({"role": "assistant", "content": error_response})
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
