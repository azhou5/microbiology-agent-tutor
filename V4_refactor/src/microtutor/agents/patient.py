"""
Patient Agent for Medical Microbiology Tutor (V4)

This agent simulates patient responses during case investigation.
Adapted from V3 to work standalone in V4 structure.
"""

import numpy as np
import faiss
import pickle
import sys
from datetime import datetime
import logging

try:
    from microtutor.Feedback.feedback_faiss import retrieve_similar_examples, get_embedding, index, texts
except ImportError:
    # FAISS is optional
    index = None
    texts = []
    from microtutor.utils import get_embedding
    def retrieve_similar_examples(*args, **kwargs): return []

from microtutor.core.llm_router import chat_complete
from microtutor.core.config_helper import config


def get_patient_system_prompt() -> str:
    """Get the core system prompt for the patient agent."""
    return """You are a patient. You are answering questions from a tutor. 
        You should respond in a way that is consistent with a patient's response. 

        Here are some important RULES:

        DO: 
        1. Provide ONLY the information SPECIFICALLY asked by the student, as IF you WERE the patient!
        Example 1: "[User Input]: How long has this been going on for?" leads to "Around 5 days."
        Example 2: "[User Input]: What do you do as work?" leads to "I'm an environmental scientist." NO HINTS about exotic travel. 

        2. IF the question is general or Open, you MUST ASK FOR MORE SPECIFIC DETAILS. 
        Example 1: "[User Input]: What's your past medical history?" -> "What specifically are you worried about?"
        Example 2: "[User Input]: Any medical conditions?" -> "I'm not sure what you're asking about. Could you be more specific?"
        Example 3: "[User Input]: Any family history?" -> "What kind of conditions are you asking about?"

        3. If the information asked by the student is NOT present in the case, just say that the pt does not know/does not remember, or simply 'No'. 
        For example: "[User Input]: What did you scrape your knee on?" -> "[Patient]: I don't remember!".

        DO NOTs:

        - NEVER Give HINTS or answers to the correct differential diagnosis. 
        Example 1: "What do you think might be going on?" -> "Patient: I don't know."
        Example 2: "What might have brough it on?" -> "Patient: I don't know."
        Example 3: "What triggered it do you think?" -> "Patient: I don't know."
        Example 4: "What do you think the cause is?" -> "Patient: I don't know."

        
        - NEVER Provide answers using MEDICAL JARGON

        - NEVER PROVIDE or VOLUNTEER information that wasn't specifically asked for!!!

        Example 1: "[User Input]: when did these start?" 
        BAD: "My headaches and fever began about two months ago, and the weakness in my right arm started roughly one month after I got back from Mexico." 
        GOOD: "My headaches and fever began about two months ago,"

        - DO NOT Provide a COMPREHENSIVE LIST of information when asked a GENERAL question!!!
        Example 1: from the question "And then what happened?"
        BAD answer = "Patient: After it started, my cough got worse. I began feeling more short of breath, and eventually I noticed some blood in my sputum. I also developed fevers, experienced night sweats, and felt increasingly tired, even losing a few pounds over the last month."
        GOOD answer = "Patient: After it started, my cough got worse. I began feeling more short of breath and feverish."
        This is a GOOD answer because it DOES NOT PROVIDE CRUCIAL DIAGNOSIC INFORMATION that should ONLY be answered to SPECIFIC QUESTIONS such as "Was there any blood in your sputum?"

        Example 2: "Any other symptoms?"
        BAD answer = "Patient: I also noticed my neck glands were swollen and tender, I had muscle aches, and I ended up with a mild rash on my chest and back."
        GOOD answer = "Patient: I also noticed my neck glands were swollen and tender."
    
        """


def get_patient_user_prompt(input_text: str) -> str:
    """Get the user prompt for the patient agent."""
    return f"Please respond to this question as the patient: {input_text}"


def log_patient_conversation(input_text: str, system_prompt: str, response: str, model: str):
    """Log patient conversation to conversation_logs/patient_convo_history.txt"""
    try:
        # Ensure conversation_logs directory exists
        import os
        os.makedirs('conversation_logs', exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open('conversation_logs/patient_convo_history.txt', 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"PATIENT CONVERSATION - {timestamp}\n")
            f.write(f"Model: {model}\n")
            f.write(f"{'='*80}\n")
            f.write(f"INPUT: {input_text}\n")
            f.write(f"{'-'*40}\n")
            f.write(f"SYSTEM PROMPT:\n{system_prompt}\n")
            f.write(f"{'-'*40}\n")
            f.write(f"PATIENT RESPONSE: {response}\n")
            f.write(f"{'='*80}\n")
    except Exception as e:
        print(f"Warning: Could not write to patient conversation log: {str(e)}")


def run_patient(input: str, case: str, history: list, run_with_faiss: bool = False, model: str = None) -> str:
    """Responds as the patient. When the user asks a question directed at the patient, you should use this tool to get the patient's response."""
    
    # Debug logging for patient tool input
    logging.info(f"[DEBUG] Patient tool input: '{input}'")
    logging.info(f"[DEBUG] Patient tool case length: {len(case) if case else 0} characters")
    logging.info(f"[DEBUG] Patient tool history length: {len(history) if history else 0} messages")
    logging.info(f"[DEBUG] Patient tool model: {model or config.API_MODEL_NAME}")
    
    # Filter out system messages from history to avoid confusion
    filtered_history = [msg for msg in history if msg.get('role') != 'system']
    
    # Format the full filtered conversation for context
    conversation_context = ""
    if filtered_history:
        conversation_context = "Chat history:\n"
        for message in filtered_history:
            if isinstance(message, dict) and "role" in message and "content" in message:
                conversation_context += f"{message['role']}: {message['content']}\n"
    
    logging.info(f"[DEBUG] Patient tool conversation context: {conversation_context}")


    core_system_prompt = get_patient_system_prompt()

    if run_with_faiss == True and index is not None:
        # Use conversation context for embedding
        embedding_text = conversation_context 
        
        # Get embedding for the combined text
        embedding = get_embedding(embedding_text)
        
        # Search for similar messages
        distances, indices = index.search(np.array([embedding]).astype('float32'), k=4)
        
        # Get the 3 most similar examples
        similar_examples = [texts[idx] for idx in indices[0]]
        examples_text = "\n\nSimilar examples with feedback, including the rated messsage and expert feedback:\n" + "\n---\n".join(similar_examples)
        
        system_prompt = core_system_prompt + f"""
        Here is the case:
        {case}

        Here is the history of the conversation:
        {conversation_context}
        
        Here are some examples of similar exchanges between a patient and a tutor, as well as a manual rating of the quality of the response and feedback. 
        {examples_text}

        You should respond to the most recent query from the patient's perspective given the rules above. 
        """
        print(examples_text)
    else:
        system_prompt = core_system_prompt + f"""
        Here is the case:
        {case}

        Here is the history of the conversation:
        {conversation_context}

        You should respond to the most recent query from the patient's perspective given the rules above. 
        """

    # Debug logging for the full prompt being sent to LLM
    logging.info(f"[DEBUG] Patient tool system prompt length: {len(system_prompt)} characters")
    logging.info(f"[DEBUG] Patient tool user prompt: '{input}'")
    logging.info(f"[DEBUG] Patient tool system prompt preview: {system_prompt[:500]}...")
    
    # Use the proper user prompt instead of the raw input
    user_prompt = get_patient_user_prompt(input)
    
    response = chat_complete(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model or config.API_MODEL_NAME
    )
    
    logging.info(f"[DEBUG] Patient tool raw response: '{response}'")
    
    # Log the patient conversation
    log_patient_conversation(
        input_text=input,
        system_prompt=system_prompt,
        response=response,
        model=model or config.API_MODEL_NAME
    )

    return response
