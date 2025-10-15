"""
Socratic Agent for Medical Microbiology Tutor (V4)

This agent conducts socratic dialogue to help students reason through differential diagnoses
and improve their clinical reasoning skills.
Adapted from V3 to work standalone in V4 structure.
"""

import os
import dotenv
import numpy as np
import pickle
import sys
from typing import List, Dict, Any
from datetime import datetime
import logging

try:
    import faiss
    from microtutor.Feedback.feedback_faiss import retrieve_similar_examples, get_embedding, index, texts
    FAISS_AVAILABLE = True
except ImportError:
    # FAISS is optional
    FAISS_AVAILABLE = False
    faiss = None
    index = None
    texts = []
    from microtutor.utils import get_embedding
    def retrieve_similar_examples(*args, **kwargs): return []

from microtutor.core.llm_router import chat_complete
from microtutor.core.config_helper import config

# Load environment variables
dotenv.load_dotenv()


def get_socratic_system_prompt() -> str:
    """Get the core system prompt for the socratic agent."""
    return """You are a microbiology tutor conducting a socratic dialogue with a medical student to help further their clinical reasoning. 

    INPUT:
    - a full microbiology case 
    - a conversational history between the student and a patient guided by a preceptor, where the student has gathered information about the patient to reach a set of differential diagnoses. 

    TASK:
    1. Critically help the student reason about the various differential diagnoses they have provided and those they might not have provided but should have. 
    You do this through:
    - Asking the student to summarise the reasons pro and con each differential they listed
    - Correcting the student if some of these reasons are incorrect
    - Asking leading questions -> 'if this had happened to the patient instead of that, how would that affect your reasoning?'
    - Asking leading questions about information that the patient did NOT ask about but that is important for reaching the differential diagnosis. 

    RULES:
    - You must only reply with one question per output! Not a large block of text.
    - You must then guide the student through their answers to cover the other questions you want to ask during the multi-turn conversation. 
    EXITING SOCRATIC METHOD
    - When you feel the socratic dialogue has covered the key learning points and the student has demonstrated good clinical reasoning, conclude your response with the exact signal: [SOCRATIC_COMPLETE] to indicate the section is complete.
    - If the student asks to move on, continue, or indicates they want to proceed with the case (phrases like "let's continue", "move on", "back to the case", "proceed", "done with socratic", etc.), acknowledge their request and conclude your response with [SOCRATIC_COMPLETE].
    - The [SOCRATIC_COMPLETE] signal should only be used when you are genuinely finished with the socratic dialogue for this section OR when the student explicitly requests to move on.

    PRINCIPLES of SOCRATIC DIALOGUE:
    1) Challenging Assumptions: Formulate questions to expose and challenge the individual's pre-existing notions and assumptions. 
    2) Cooperative Inquiry: The dialogue is a shared, cooperative process of seeking truth, rather than a competitive argument. 
    3) Logical Flow: The line of questioning should follow a logical sequence to build upon previous thoughts and ideas. 
    4) Guiding questions: Formulate the flow such that you guide the student towards a greater and correct understanding of clinical reasoning. 

    EXAMPLES in SOCRATIC mode
    "[Student] 'My top differentials are strep pneumonia, fungal pneumonia and lung cancer' -> [Socratic] 'Ok! So what are your reasons for each of these?'"
    "[Student] 'I think it's lung cancer because the person has persistent cough for a few weeks' -> [Socratic] 'Right, but what other signs or symptoms would be crucial to differentiate lung cancer from ...?'"
    "[Student] 'Well, to have lung cancer, the patient would probably also have weight loss, potentially night sweats.' -> [Socratic] 'That's a great point. Let's now imagine that the patient was immunocompromised. How would this change your differentials and why?'"
    
    EXAMPLES of EXITING SOCRATIC mode. 
    "[Student] 'Ok let's move on to the rest of the case!' -> [Socratic] 'Great work reasoning through those differentials! You've demonstrated solid clinical thinking. Let's continue with the case. [SOCRATIC_COMPLETE]'"
    After all the core questions have been discussed... "[Student] 'Finally, I think pneumococcal pneumonia is most likely because of the rusty sputum and consolidation on chest X-ray.' -> [Socratic] 'Excellent reasoning! Let's now continue with the case. [SOCRATIC_COMPLETE]'"
    """


def get_socratic_user_prompt() -> str:
    """Get the user prompt for socratic dialogue."""
    return """Based on the case and conversation history provided, conduct a socratic dialogue to help the student reason through their differential diagnoses. Ask probing questions, challenge assumptions, and guide their clinical reasoning without revealing the diagnosis."""



def log_socratic_conversation(input_text: str, system_prompt: str, response: str, model: str) -> None:
    """Log socratic conversation to conversation_logs/socratic_convo_history.txt"""
    try:
        # Ensure conversation_logs directory exists
        import os
        os.makedirs('conversation_logs', exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open('conversation_logs/socratic_convo_history.txt', 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"SOCRATIC CONVERSATION - {timestamp}\n")
            f.write(f"Model: {model}\n")
            f.write(f"{'='*80}\n")
            f.write(f"INPUT: {input_text}\n")
            f.write(f"{'-'*40}\n")
            f.write(f"SYSTEM PROMPT:\n{system_prompt}\n")
            f.write(f"{'-'*40}\n")
            f.write(f"SOCRATIC RESPONSE: {response}\n")
            f.write(f"{'='*80}\n")
    except Exception as e:
        print(f"Warning: Could not write to socratic conversation log: {str(e)}")


def run_socratic(input: str, case: str, history: List[Dict[str, str]], run_with_faiss: bool = False, model: str = None) -> str:
    """
    Conducts socratic dialogue to help students reason through differential diagnoses.
    
    Args:
        input: The student's input or request for socratic guidance
        case: The current case description
        history: Conversation history
        run_with_faiss: Whether to use FAISS for similar examples
        model: Model name to use for generation
        
    Returns:
        A socratic question or response to guide clinical reasoning
    """
    
    # Debug logging
    logging.info(f"[DEBUG] Socratic tool input: '{input}'")
    logging.info(f"[DEBUG] Socratic tool case length: {len(case) if case else 0} characters")
    logging.info(f"[DEBUG] Socratic tool history length: {len(history) if history else 0} messages")
    logging.info(f"[DEBUG] Socratic tool model: {model or config.API_MODEL_NAME}")
    
    # Filter out system messages from history to avoid confusion
    filtered_history = [msg for msg in history if msg.get('role') != 'system']
    
    # Format the full filtered conversation for context
    conversation_context = ""
    if filtered_history:
        conversation_context = "Chat history:\n"
        for message in filtered_history:
            if isinstance(message, dict) and "role" in message and "content" in message:
                conversation_context += f"{message['role']}: {message['content']}\n"
    
    logging.info(f"[DEBUG] Socratic tool conversation context: {conversation_context}")

    core_system_prompt = get_socratic_system_prompt()

    if run_with_faiss and index is not None:
        # Use conversation context for embedding
        embedding_text = conversation_context 
        
        # Get embedding for the combined text
        embedding = get_embedding(embedding_text)
        
        # Search for similar messages
        distances, indices = index.search(np.array([embedding]).astype('float32'), k=4)
        
        # Get the most similar examples
        similar_examples = [texts[idx] for idx in indices[0]]
        examples_text = "\n\nSimilar examples with feedback, including the rated message and expert feedback:\n" + "\n---\n".join(similar_examples)
        
        system_prompt = core_system_prompt + f"""
        Here is the case:
        {case}

        Here is the history of the conversation:
        {conversation_context}
        
        Here are some examples of similar exchanges and feedback:
        {examples_text}

        Based on the case and conversation history, provide a socratic question or response to guide the student's clinical reasoning.
        """
        print(examples_text)
    else:
        system_prompt = core_system_prompt + f"""
        Here is the case:
        {case}

        Here is the history of the conversation:
        {conversation_context}

        Based on the case and conversation history, provide a socratic question or response to guide the student's clinical reasoning.
        """

    # Debug logging for the full prompt being sent to LLM
    logging.info(f"[DEBUG] Socratic tool system prompt length: {len(system_prompt)} characters")
    logging.info(f"[DEBUG] Socratic tool user prompt: '{input}'")
    logging.info(f"[DEBUG] Socratic tool system prompt preview: {system_prompt[:500]}...")
    
    # Use the proper user prompt instead of the raw input
    user_prompt = get_socratic_user_prompt()
    
    response = chat_complete(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model or config.API_MODEL_NAME
    )
    
    logging.info(f"[DEBUG] Socratic tool raw response: '{response}'")
    
    # Log the socratic conversation
    log_socratic_conversation(
        input_text=input,
        system_prompt=system_prompt,
        response=response,
        model=model or config.API_MODEL_NAME
    )

    return response


