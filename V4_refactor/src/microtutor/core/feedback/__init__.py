"""
Feedback infrastructure module for MicroTutor.

This module provides FAISS-based feedback indexing and retrieval capabilities.
Feedback data is stored in PostgreSQL and FAISS indices are auto-generated
in data/feedback_auto/.

Architecture:
- TutorService retrieves feedback once and passes it to tools via conversation history
- AutoFAISSGenerator: Generates FAISS indices from PostgreSQL database
- AutoFeedbackRetriever: Retrieves similar feedback examples
- DatabaseFeedbackLoader: Loads feedback from PostgreSQL
- FeedbackProcessor: Processes and embeds feedback entries
"""

try:
    # Core processing
    from .processor import FeedbackProcessor, FeedbackEntry, FeedbackExample
    
    # Database access
    from .database_loader import DatabaseFeedbackLoader, DatabaseFeedbackConfig
    
    # Auto-generation and retrieval
    from .auto_generator import get_auto_faiss_generator, AutoFAISSGenerator
    from .auto_retriever import AutoFeedbackRetriever, get_auto_feedback_retriever
    
    # Formatting feedback examples for prompts
    from .formatter import format_feedback_examples, get_feedback_examples_for_tool
    
    FEEDBACK_AVAILABLE = True
    
    __all__ = [
        # Main components
        "AutoFAISSGenerator",
        "get_auto_faiss_generator",
        "AutoFeedbackRetriever", 
        "get_auto_feedback_retriever",
        "DatabaseFeedbackLoader",
        "DatabaseFeedbackConfig",
        "FeedbackProcessor",
        "FeedbackEntry",
        "FeedbackExample",
        "format_feedback_examples",
        "get_feedback_examples_for_tool",
        "FEEDBACK_AVAILABLE",
    ]
    
except ImportError as e:
    import logging
    logging.warning(f"Feedback module not available: {e}")
    FEEDBACK_AVAILABLE = False
    
    # Provide fallback functions
    def get_auto_feedback_retriever(*args, **kwargs):
        return None
    
    def get_auto_faiss_generator(*args, **kwargs):
        return None
    
    def get_feedback_examples_for_tool(*args, **kwargs):
        return ""
    
    def format_feedback_examples(*args, **kwargs):
        return ""
    
    __all__ = [
        "get_auto_feedback_retriever",
        "get_auto_faiss_generator",
        "get_feedback_examples_for_tool", 
        "format_feedback_examples",
        "FEEDBACK_AVAILABLE",
    ]
