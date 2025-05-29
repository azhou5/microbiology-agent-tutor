from openai import AzureOpenAI
import os
import dotenv
import numpy as np
import faiss
import pickle
import sys
from Feedback.feedback_faiss import retrieve_similar_examples, get_embedding, index, texts
import config


def run_hint(input: str, case: str, history: list, run_with_faiss: bool = config.USE_FAISS, model: str = None) -> str:
    """Analyzes the case and conversation history to suggest a single strategic question that hasn't been asked yet and could help the student progress."""
    
    # Format the recent history similar to how the index was created
    recent_context = ""
    if history:
        recent_context = "Chat history:\n"
        for message in history[-5:-1]:  # Get last 4 messages like in index generation
            if isinstance(message, dict) and "role" in message and "content" in message:
                recent_context += f"{message['role']}: {message['content']}\n"

    core_system_prompt = """You are a microbiology tutor providing a single strategic hint to help guide the student's investigation.

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

    if run_with_faiss == True and index is not None:
        # Combine recent history with current query for embedding
        embedding_text = recent_context 
        
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
        {history}
        
        Here are some examples of similar exchanges and feedback:
        {examples_text}

        Based on the case and conversation history, provide a single strategic hint in the form of a question that hasn't been asked yet.
        """
    else:
        system_prompt = core_system_prompt + f"""
        Here is the case:
        {case}

        Here is the history of the conversation:
        {history}

        Based on the case and conversation history, provide a single strategic hint in the form of a question that hasn't been asked yet.
        """

    client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"), 
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    )

    response = client.chat.completions.create(
        model=model or config.API_MODEL_NAME,  # Use passed model or default to config
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": input}],
    )

    return response.choices[0].message.content
