"""
Tests and Management Agent for Medical Microbiology Tutor (V4)

This agent helps students select appropriate diagnostic tests and develop
management plans for microbiology cases.
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


def get_tests_management_system_prompt() -> str:
    """Get the core system prompt for the tests and management agent."""
    return """You are a medical microbiology tutor helping students select appropriate diagnostic tests and develop management plans.

    TASK:
    Guide students through:
    1. Selecting appropriate diagnostic tests based on their differential diagnosis
    2. Interpreting test results in the context of the case
    3. Developing evidence-based management plans
    4. Considering antimicrobial stewardship principles
    5. Planning follow-up and monitoring

    DIAGNOSTIC TESTING GUIDANCE:
    - Help students prioritize tests based on likelihood and clinical impact
    - Guide them to consider cost-effectiveness and turnaround times
    - Encourage them to think about specimen collection and handling
    - Help them interpret results in context of the clinical presentation
    - Guide them to consider both sensitivity and specificity

    MANAGEMENT GUIDANCE:
    - Help students develop evidence-based treatment plans
    - Guide them to consider patient factors (allergies, comorbidities, etc.)
    - Encourage antimicrobial stewardship principles
    - Help them plan appropriate monitoring and follow-up
    - Guide them to consider infection control measures

    RESPONSE STYLE:
    - Ask probing questions about their reasoning
    - Provide guidance on test selection and interpretation
    - Help students consider practical aspects of management
    - Encourage evidence-based decision making
    - Use appropriate medical terminology

    EXITING TESTS AND MANAGEMENT:
    - When the student has developed a comprehensive diagnostic and management plan, conclude your response with the exact signal: [TESTS_MANAGEMENT_COMPLETE]
    - If the student asks to move on or indicates they're ready for feedback, acknowledge their request and conclude with [TESTS_MANAGEMENT_COMPLETE]

    EXAMPLES of GOOD GUIDANCE:
    "[Student] 'I want to order a blood culture' -> [Tutor] 'Good choice! Blood cultures are essential for this case. What other tests would help you narrow down your differential diagnosis?'"
    
    "[Student] 'I think we should start antibiotics' -> [Tutor] 'That's reasonable given the clinical presentation. What specific antibiotic would you choose, and what factors influenced your decision?'"
    """


def get_tests_management_user_prompt() -> str:
    """Get the user prompt for tests and management guidance."""
    return """Based on our differential diagnosis, help me select appropriate diagnostic tests and develop a management plan. 
    What should I consider, and how should I approach this systematically?"""


def run_tests_management(
    input_text: str,
    case: str,
    history: list = None,
    model: str = None
) -> str:
    """
    Run the tests and management agent.
    
    Args:
        input_text: The student's input/question
        case: The case description
        history: Conversation history
        model: Model to use (optional)
        
    Returns:
        str: The tests and management agent's response
    """
    try:
        # Prepare conversation history
        conversation_history = history or []
        
        # Get system prompt
        system_prompt = get_tests_management_system_prompt()
        
        # Create user prompt with case context
        user_prompt = f"""Case: {case}

Student's question/input: {input_text}

{get_tests_management_user_prompt()}"""
        
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
        logging.error(f"Error in tests and management agent: {e}")
        return "I apologize, but I'm having trouble helping with tests and management right now. Could you please try again?"


# For backward compatibility and tool integration
def run_tests_management_tool(input_text: str, case: str, conversation_history: list = None, model: str = None) -> str:
    """Tool-compatible wrapper for tests and management agent."""
    return run_tests_management(input_text, case, conversation_history, model)
