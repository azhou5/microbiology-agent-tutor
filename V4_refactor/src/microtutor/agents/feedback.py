"""
Feedback Agent for Medical Microbiology Tutor (V4)

This agent provides comprehensive feedback on the student's performance
throughout the case, highlighting strengths and areas for improvement.
"""

import numpy as np
import pickle
import sys
from datetime import datetime
import logging

try:
    import faiss
    from microtutor.feedback.feedback_faiss import retrieve_similar_examples, get_embedding, index, texts
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


def get_feedback_system_prompt() -> str:
    """Get the core system prompt for the feedback agent."""
    return """You are a medical microbiology tutor providing comprehensive feedback on student performance.

    TASK:
    Provide detailed feedback on the student's performance across all phases of the case:
    1. Information gathering quality and thoroughness
    2. Problem representation organization and completeness
    3. Differential diagnosis reasoning and prioritization
    4. Test selection appropriateness and interpretation
    5. Management plan evidence-base and practicality
    6. Overall clinical reasoning and decision-making

    FEEDBACK PRINCIPLES:
    1. Be constructive and supportive while being honest about areas for improvement
    2. Highlight specific strengths and specific weaknesses
    3. Provide actionable recommendations for improvement
    4. Connect feedback to real clinical practice
    5. Encourage reflection on decision-making process
    6. Acknowledge good clinical reasoning when present

    FEEDBACK STRUCTURE:
    - Start with overall assessment and key strengths
    - Address each phase systematically
    - Provide specific examples from their performance
    - Suggest concrete improvements
    - End with encouragement and next steps

    RESPONSE STYLE:
    - Use a supportive but professional tone
    - Be specific about what they did well and what needs improvement
    - Provide clear, actionable advice
    - Use medical terminology appropriately
    - Encourage continued learning and practice

    EXITING FEEDBACK:
    - When you've provided comprehensive feedback, conclude your response with the exact signal: [FEEDBACK_COMPLETE]
    - If the student asks questions about the feedback, address them and then conclude with [FEEDBACK_COMPLETE]

    EXAMPLES of GOOD FEEDBACK:
    "[Student] 'I think I did okay on the differential diagnosis' -> [Tutor] 'You showed good clinical reasoning in your differential diagnosis. Your prioritization of pneumonia was well-reasoned based on the chest X-ray findings. However, I noticed you didn't consider fungal infections in this immunocompromised patient - that's an important consideration for future cases.'"
    
    "[Student] 'What could I have done better?' -> [Tutor] 'Your information gathering was thorough, but you could have asked more specific questions about the patient's travel history and exposure risks. This information is crucial for infectious disease cases.'"
    """


def get_feedback_user_prompt() -> str:
    """Get the user prompt for feedback guidance."""
    return """Please provide comprehensive feedback on my performance throughout this case. 
    What did I do well, and what areas should I focus on for improvement?"""


def run_feedback(
    input_text: str,
    case: str,
    history: list = None,
    model: str = None
) -> str:
    """
    Run the feedback agent.
    
    Args:
        input_text: The student's input/question
        case: The case description
        history: Conversation history
        model: Model to use (optional)
        
    Returns:
        str: The feedback agent's response
    """
    try:
        # Prepare conversation history
        conversation_history = history or []
        
        # Get system prompt
        system_prompt = get_feedback_system_prompt()
        
        # Create user prompt with case context
        user_prompt = f"""Case: {case}

Student's question/input: {input_text}

{get_feedback_user_prompt()}"""
        
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
        logging.error(f"Error in feedback agent: {e}")
        return "I apologize, but I'm having trouble providing feedback right now. Could you please try again?"


# For backward compatibility and tool integration
def run_feedback_tool(input_text: str, case: str, conversation_history: list = None, model: str = None) -> str:
    """Tool-compatible wrapper for feedback agent."""
    return run_feedback(input_text, case, conversation_history, model)
