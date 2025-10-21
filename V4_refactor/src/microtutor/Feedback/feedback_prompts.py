"""
Feedback integration for existing prompts.
Formats feedback examples and inserts them into prompt templates using {} placeholders.
"""

from typing import List, Dict, Any, Optional
from microtutor.feedback.feedback_retriever import FeedbackRetriever, FeedbackExample


def format_feedback_examples(
    examples: List[FeedbackExample],
    message_type: str = "tutor"
) -> str:
    """
    Format feedback examples for insertion into prompts.
    
    Args:
        examples: List of feedback examples
        message_type: Type of message (tutor, patient, socratic, hint)
        
    Returns:
        Formatted feedback examples string
    """
    if not examples:
        return ""
    
    feedback_section = "=== EXPERT FEEDBACK EXAMPLES ===\n"
    
    if message_type == "tutor":
        feedback_section += "Here are examples of good and bad tutor responses to similar questions:\n"
    elif message_type == "patient":
        feedback_section += "Here are examples of good and bad patient responses to similar questions:\n"
    elif message_type == "socratic":
        feedback_section += "Here are examples of good and bad socratic responses to similar questions:\n"
    elif message_type == "hint":
        feedback_section += "Here are examples of good and bad hints to similar questions:\n"
    else:
        feedback_section += "Here are examples of good and bad responses to similar questions:\n"
    
    for i, example in enumerate(examples, 1):
        quality_indicator = "✓ GOOD" if example.is_positive_example else "✗ AVOID" if example.is_negative_example else "~ OK"
        feedback_section += f"\nExample {i} ({quality_indicator} - Rating: {example.entry.rating}/5):\n"
        # Extract the last user input from chat history for the question
        last_user_input = ""
        if example.entry.chat_history:
            for msg in reversed(example.entry.chat_history):
                if 'role' in msg and 'content' in msg and msg['role'] == 'user':
                    last_user_input = msg['content'].strip()
                    break
        feedback_section += f"Question: {last_user_input}\n"
        feedback_section += f"Response: {example.entry.rated_message}\n"
        
        if example.entry.feedback_text:
            feedback_section += f"Expert feedback: {example.entry.feedback_text}\n"
        
        if example.entry.replacement_text:
            feedback_section += f"Better approach: {example.entry.replacement_text}\n"
    
    feedback_section += "\nUse these examples to guide your response style. Follow the good examples and avoid the patterns in the negative examples."
    
    return feedback_section


def get_feedback_examples_for_tool(
    user_input: str,
    conversation_history: List[Dict[str, str]],
    tool_name: str,
    feedback_retriever: Optional[FeedbackRetriever] = None,
    include_feedback: bool = True,
    similarity_threshold: Optional[float] = None
) -> str:
    """
    Get formatted feedback examples for a specific tool.
    
    Args:
        user_input: Current user question/input
        conversation_history: Previous conversation messages
        tool_name: Name of the tool (patient, socratic, hint, etc.)
        feedback_retriever: Optional feedback retriever for examples
        include_feedback: Whether to include feedback examples
        
    Returns:
        Formatted feedback examples string
    """
    if not include_feedback or not feedback_retriever:
        return ""
    
    # Use "all" message type to get all feedback types for better examples
    message_type = "all"
    
    # Get relevant feedback examples
    examples = feedback_retriever.retrieve_feedback_examples(
        current_message=user_input,
        conversation_history=conversation_history,
        message_type=message_type,
        k=5,  # Increase to get more examples
        similarity_threshold=similarity_threshold
    )
    
    return format_feedback_examples(examples, message_type)


