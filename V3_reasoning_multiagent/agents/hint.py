"""
Hint Agent for Medical Microbiology Tutor

This agent provides strategic hints to guide students during case investigation
without revealing the diagnosis or providing medical jargon.
"""

import os
import dotenv
import numpy as np
import faiss
from typing import List, Dict, Any
from datetime import datetime
import logging

from Feedback.feedback_faiss import retrieve_similar_examples, get_embedding, index, texts
from llm_router import chat_complete
import config

# Load environment variables
dotenv.load_dotenv()


def get_hint_system_prompt() -> str:
    """Get the core system prompt for the hint agent."""
    return """You are a microbiology tutor providing a single strategic hint to help guide the student's investigation.

    Your task is to:
    1. Analyze the case and conversation history
    2. Identify ONE important question that hasn't been asked yet
    3. Suggest this question in a way that guides the student without revealing the diagnosis

    Rules for providing hints:
    1. Suggest ONLY ONE question at a time
    2. The question should be specific and focused
    3. DO NOT reveal the diagnosis or provide medical jargon
    4. DO NOT suggest questions that have already been asked
    5. The question should help progress the case investigation
    6. Format your response as: "Hint: Consider asking about [specific question]"

    Example good hints:
    - "Hint: Consider asking about the color and consistency of the sputum"
    - "Hint: Consider asking about any recent travel history"
    - "Hint: Consider asking about the timing of symptoms in relation to meals"

    Example bad hints:
    - "Hint: Ask about tuberculosis symptoms" (too specific to diagnosis)
    - "Hint: Ask about their medical history" (too vague)
    - "Hint: Ask about their symptoms" (too general)
    """


def get_hint_user_prompt(input_text: str) -> str:
    """Get the user prompt for the hint agent."""
    return f"Based on the case and conversation history, provide a strategic hint to help guide the student's investigation. Student request: {input_text}"


def log_hint_conversation(input_text: str, system_prompt: str, response: str, model: str) -> None:
    """Log hint conversation to conversation_logs/hint_convo_history.txt"""
    try:
        # Ensure conversation_logs directory exists
        import os
        os.makedirs('conversation_logs', exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open('conversation_logs/hint_convo_history.txt', 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"HINT CONVERSATION - {timestamp}\n")
            f.write(f"Model: {model}\n")
            f.write(f"{'='*80}\n")
            f.write(f"INPUT: {input_text}\n")
            f.write(f"{'-'*40}\n")
            f.write(f"SYSTEM PROMPT:\n{system_prompt}\n")
            f.write(f"{'-'*40}\n")
            f.write(f"HINT RESPONSE: {response}\n")
            f.write(f"{'='*80}\n")
    except Exception as e:
        print(f"Warning: Could not write to hint conversation log: {str(e)}")


def run_hint(input: str, case: str, history: List[Dict[str, str]], run_with_faiss: bool = config.USE_FAISS, model: str = None) -> str:
    """
    Provides strategic hints to guide student investigation.
    
    Args:
        input: The hint request from the student
        case: The current case description
        history: Conversation history
        run_with_faiss: Whether to use FAISS for similar examples
        model: Model name to use for generation
        
    Returns:
        A strategic hint in the form of a question
    """
    
    # Debug logging
    logging.info(f"[DEBUG] Hint tool input: '{input}'")
    logging.info(f"[DEBUG] Hint tool case length: {len(case) if case else 0} characters")
    logging.info(f"[DEBUG] Hint tool history length: {len(history) if history else 0} messages")
    logging.info(f"[DEBUG] Hint tool model: {model or config.API_MODEL_NAME}")
    
    # Filter out system messages from history to avoid confusion
    filtered_history = [msg for msg in history if msg.get('role') != 'system']
    
    # Format the full filtered conversation for context
    conversation_context = ""
    if filtered_history:
        conversation_context = "Chat history:\n"
        for message in filtered_history:
            if isinstance(message, dict) and "role" in message and "content" in message:
                conversation_context += f"{message['role']}: {message['content']}\n"
    
    logging.info(f"[DEBUG] Hint tool conversation context: {conversation_context}")

    core_system_prompt = get_hint_system_prompt()

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

        Based on the case and conversation history, provide a single strategic hint in the form of a question that hasn't been asked yet.
        """
        print(examples_text)
    else:
        system_prompt = core_system_prompt + f"""
        Here is the case:
        {case}

        Here is the history of the conversation:
        {conversation_context}

        Based on the case and conversation history, provide a single strategic hint in the form of a question that hasn't been asked yet.
        """

    # Debug logging for the full prompt being sent to LLM
    logging.info(f"[DEBUG] Hint tool system prompt length: {len(system_prompt)} characters")
    logging.info(f"[DEBUG] Hint tool user prompt: '{input}'")
    logging.info(f"[DEBUG] Hint tool system prompt preview: {system_prompt[:500]}...")
    
    # Use the proper user prompt instead of the raw input
    user_prompt = get_hint_user_prompt(input)
    
    response = chat_complete(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model or config.API_MODEL_NAME
    )
    
    logging.info(f"[DEBUG] Hint tool raw response: '{response}'")
    
    # Log the hint conversation
    log_hint_conversation(
        input_text=input,
        system_prompt=system_prompt,
        response=response,
        model=model or config.API_MODEL_NAME
    )

    return response


