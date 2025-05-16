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
from Feedback.feedback_faiss import retrieve_similar_examples
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
system_message_template = """You are an expert microbiology instructor running a case with a student.You run in a loop of [Thought], [Action], [Observation].
Use [Thought] to describe your thoughts about the question you have been asked.
[Action] is the tool you choose to solve the current problem. This should be a JSON object containing the tool name with corresponding tool input.
[Observation] will be the result of running those actions.

Note: Only use [Action] when you need to interact with the patient tool. For all other responses (including the initial presenting complaint), respond directly without using [Action].

For each iteration, you should ONLY respond with:
1. A [Thought] explaining your reasoning (optional for direct responses)
2. An [Action] specifying the tool to use (only when using the patient tool)
OR
A direct response as the tutor

You will be given a microbiology case and a student question.
Available tools:
{tool_descriptions}

When the question is directed to the patient, you MUST use the patient tool.

Example usage:
[User Input]: When did your fever start?
[Thought]: The question is directed to the patient. So, I will use the patient tool.
[Action]: {{"patient": "When did your fever start?"}}

You will be called again with this:
[Observation]: {{"patient": "A few days ago"}}

You then output:
[Answer]: Patient: A few days ago

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
                 reward_model_sampling: bool = config.REWARD_MODEL_SAMPLING):
        
        self.output_tool_directly = output_tool_directly
        self.run_with_faiss = run_with_faiss
        self.reward_model_sampling = reward_model_sampling

        self.id = "tutor_agent"
        # Initialize messages with a placeholder system message
        self.messages = [{"role": "system", "content": "Initializing..."}]
        # History might not be needed if messages list serves as the full context
        # self.history = [] # Consider removing if not used elsewhere
        self.current_organism = None
        self.case_description = None # To store the current case details
        self.last_user_message = "" # Keep track of the last user message if needed for context

    def _update_system_message(self):
        """Formats and updates the system message with current tool descriptions and case."""
        if self.case_description:
            formatted_system_message = system_message_template.format(
                tool_descriptions=tool_descriptions, # Uses the globally generated descriptions
                case=self.case_description
            )
            self.messages[0]["content"] = formatted_system_message
        else:
            # Handle case where case_description is not yet set
             self.messages[0]["content"] = system_message_template.format(
                tool_descriptions=tool_descriptions,
                case="No case loaded yet."
            )

    def start_new_case(self, organism=None):
        """Initialize a new case with the specified organism."""
        self.current_organism = organism or "staphylococcus aureus" # Default organism

        # Get the case for the organism
        self.case_description = get_case(self.current_organism)
        if not self.case_description:
             # Handle error case where case could not be loaded
             return "Error: Could not load case for the specified organism."

        # Reset the message history and set the formatted system message
        self.messages = [{"role": "system", "content": "Initializing..."}]
        self._update_system_message() # Update the system message with the loaded case

        # Get initial case presentation from the LLM
        try:
            initial_response = chat_complete(self.messages)
            # Add the initial assistant response to the message history
            self.messages.append({"role": "assistant", "content": initial_response})
            return initial_response
        except Exception as e:
            print(f"Error getting initial case presentation: {e}")
            return f"Error: Could not get initial case presentation. {e}"

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
        # Extract the user's message from the task
        if isinstance(task, str):
            message = task
        elif hasattr(task, 'instruction'):
            message = task.instruction
        else:
            # Fallback or error handling if task format is unexpected
            print(f"Warning: Unexpected task format: {type(task)}")
            message = str(task) # Attempt to convert to string

        self.last_user_message = message # Store last user message

        # Add user message to the conversation history
        self.messages.append({"role": "user", "content": message})

        try:
            response_content = chat_complete(self.messages)

            # Check if the response contains an action request
            if "[Action]" in response_content:
                tool_name = None  # initialize before inner try to avoid UnboundLocalError
                try:
                    # Extract action details
                    action_text = response_content.split("[Action]:", 1)[1].strip()
                    # Improved JSON extraction to handle potential markdown/text around it
                    json_match = re.search(r'```json\s*(\{.*\})\s*```|(\{.*\})', action_text, re.DOTALL | re.IGNORECASE)
                    if json_match:
                        # Prioritize JSON within markdown, then raw JSON
                        json_str = json_match.group(1) or json_match.group(2)
                        json_str = json_str.strip()
                    else:
                        # Fallback if no clear JSON structure is found
                        print(f"Warning: Could not extract JSON from action text: {action_text}")
                        json_str = action_text # Attempt to parse directly

                    action_data = json.loads(json_str)
                    tool_name = list(action_data.keys())[0]
                    tool_input = action_data[tool_name]

                    # Execute the appropriate tool
                    if tool_name in name_to_function_map:
                        tool_function = name_to_function_map[tool_name]
                        # Pass necessary context (case description, history) to the tool
                        if tool_name == "patient":
                             if not self.case_description:
                                 raise ValueError("Case description is not available for the patient tool.")
                             # Pass the current message history
                             tool_result = tool_function(tool_input, self.case_description, self.messages)
                        else:
                             # Handle other tools if they are added later
                             tool_result = tool_function(tool_input)

                        if self.output_tool_directly:
                            final_response = tool_result
                            # Add the tool result to the message history
                            tool_output = f"[Observation]: {json.dumps({tool_name: tool_result})}"
                            self.messages.append({"role": "system", "content": tool_output})
                            self.messages.append({"role": "assistant", "content": final_response})
                            return final_response
                        else:
                            # Add the action's result (observation) back into the message history
                            tool_output = f"[Observation]: {json.dumps({tool_name: tool_result})}"
                            self.messages.append({"role": "system", "content": tool_output})

                            final_response = chat_complete(self.messages)
                            # Add this final assistant response to history
                            self.messages.append({"role": "assistant", "content": final_response})
                            return final_response
                    else:
                        # Handle case where the requested tool is not found
                        tool_output = f"[Observation]: Error: Tool '{tool_name}' not found."
                        self.messages.append({"role": "system", "content": tool_output})
                        # Get response after error observation
                        final_response = chat_complete(self.messages)
                        self.messages.append({"role": "assistant", "content": final_response})
                        return final_response

                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON action: {e} - Action text: {action_text}")
                    error_message = f"[Observation]: Error processing action - Invalid format: {e}"
                    self.messages.append({"role": "system", "content": error_message})
                    # Get response after error observation

                    final_response = chat_complete(self.messages)
                    self.messages.append({"role": "assistant", "content": final_response})
                    return final_response
                except Exception as e:
                    print(f"Error executing tool '{tool_name}': {e}")
                    error_message = f"[Observation]: Error executing tool '{tool_name}': {e}"
                    self.messages.append({"role": "system", "content": error_message})
                    # Get response after error observation
                    final_response = chat_complete(self.messages)
                    self.messages.append({"role": "assistant", "content": final_response})
                    return final_response
            else:
                if self.run_with_faiss:
                    # Direct tutor response: fetch and append similar feedback examples
                    similar = retrieve_similar_examples(message, self.messages)
                    examples_text = "\n\nSimilar examples with feedback:\n" + "\n---\n".join(similar)
                    full_response = response_content + examples_text
                else:
                    full_response = response_content
                self.messages.append({"role": "assistant", "content": full_response})
                return full_response

        except Exception as e:
            print(f"Error during LLM call or processing: {e}")
            # Return a user-friendly error message
            error_response = f"Sorry, an error occurred: {e}"
            self.messages.append({"role": "assistant", "content": error_response}) # Log error response
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
