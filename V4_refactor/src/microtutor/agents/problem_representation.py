"""
Problem Representation Agent for Medical Microbiology Tutor (V4)

This agent helps students organize and structure the clinical information
they've gathered into a clear problem representation.
"""

import numpy as np
import pickle
import sys
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


def get_problem_representation_system_prompt() -> str:
    """Get the core system prompt for the problem representation agent."""
    return """You are a medical microbiology tutor helping students organize clinical information into a clear problem representation.

    TASK:
    Help the student structure the information they've gathered into a comprehensive problem representation that includes:
    1. Chief complaint and history of present illness
    2. Key symptoms and their characteristics
    3. Physical examination findings
    4. Initial laboratory/imaging results
    5. Patient demographics and risk factors
    6. Timeline of illness progression

    GUIDANCE PRINCIPLES:
    1. Help students identify the most important clinical features
    2. Guide them to organize information chronologically and by system
    3. Encourage them to highlight key findings that will be important for differential diagnosis
    4. Help them recognize patterns and connections between symptoms
    5. Guide them to identify missing information that should be gathered

    RESPONSE STYLE:
    - Ask probing questions to help students think through the information
    - Provide gentle guidance on how to structure the problem representation
    - Help students identify gaps in their information gathering
    - Encourage systematic thinking about the clinical presentation
    - Use medical terminology appropriately but explain when needed

    EXITING PROBLEM REPRESENTATION:
    - When the student has created a comprehensive problem representation, conclude your response with the exact signal: [PROBLEM_REPRESENTATION_COMPLETE]
    - If the student asks to move on or indicates they're ready for differential diagnosis, acknowledge their request and conclude with [PROBLEM_REPRESENTATION_COMPLETE]

    EXAMPLES of GOOD GUIDANCE:
    "[Student] 'I have the patient's symptoms: fever, cough, chest pain' -> [Tutor] 'Good start! Let's organize this systematically. Can you tell me more about the characteristics of each symptom? When did they start, and how have they progressed?'"
    
    "[Student] 'The patient is a 65-year-old with diabetes and fever for 3 days' -> [Tutor] 'Excellent demographic information. Now let's structure this chronologically. What was the sequence of events leading up to this presentation?'"
    """


def get_problem_representation_user_prompt() -> str:
    """Get the user prompt for problem representation guidance."""
    return """Based on the information gathered so far, help me organize this into a clear problem representation. 
    What should I focus on, and how should I structure this information for the next phase of clinical reasoning?"""


def run_problem_representation(
    input_text: str,
    case: str,
    history: list = None,
    model: str = None
) -> str:
    """
    Run the problem representation agent.
    
    Args:
        input_text: The student's input/question
        case: The case description
        history: Conversation history
        model: Model to use (optional)
        
    Returns:
        str: The problem representation agent's response
    """
    try:
        # Prepare conversation history
        conversation_history = history or []
        
        # Get system prompt
        system_prompt = get_problem_representation_system_prompt()
        
        # Create user prompt with case context
        user_prompt = f"""Case: {case}

Student's question/input: {input_text}

{get_problem_representation_user_prompt()}"""
        
        # Call LLM
        response = chat_complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            conversation_history=conversation_history
        )
        
        if not response:
            return "I'm having trouble processing your request right now. Could you please try again?"
        
        return response
        
    except Exception as e:
        logging.error(f"Error in problem representation agent: {e}")
        return "I apologize, but I'm having trouble helping with problem representation right now. Could you please try again?"


# For backward compatibility and tool integration
def run_problem_representation_tool(input_text: str, case: str, conversation_history: list = None, model: str = None) -> str:
    """Tool-compatible wrapper for problem representation agent."""
    return run_problem_representation(input_text, case, conversation_history, model)
