"""
Feedback integration module for MicroTutor.
Provides feedback-aware responses using FAISS-based retrieval.

⚠️  WARNING: This module requires FAISS and other ML dependencies.
    It is optional and will be disabled if dependencies are not available.
"""

try:
    from .feedback_processor import FeedbackProcessor, FeedbackEntry, process_feedback_json
    from .feedback_retriever import FeedbackRetriever, FeedbackExample, create_feedback_retriever
    from .feedback_prompts import (
        format_feedback_examples,
        get_feedback_examples_for_tool
    )
    
    FEEDBACK_AVAILABLE = True
    __all__ = [
        "FeedbackProcessor",
        "FeedbackEntry", 
        "process_feedback_json",
        "FeedbackRetriever",
        "FeedbackExample",
        "create_feedback_retriever",
        "format_feedback_examples",
        "get_feedback_examples_for_tool"
    ]
except ImportError as e:
    import logging
    logging.warning(f"Feedback module not available: {e}")
    FEEDBACK_AVAILABLE = False
    
    # Provide fallback functions
    def create_feedback_retriever(*args, **kwargs):
        return None
    
    def get_feedback_examples_for_tool(*args, **kwargs):
        return ""
    
    def format_feedback_examples(*args, **kwargs):
        return ""
    
    __all__ = [
        "create_feedback_retriever",
        "get_feedback_examples_for_tool", 
        "format_feedback_examples"
    ]
