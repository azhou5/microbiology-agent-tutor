"""
Feedback integration module for MicroTutor.
Provides feedback-aware responses using FAISS-based retrieval.
"""

from .feedback_processor import FeedbackProcessor, FeedbackEntry, process_feedback_json
from .feedback_retriever import FeedbackRetriever, FeedbackExample, create_feedback_retriever
from .feedback_prompts import (
    format_feedback_examples,
    get_feedback_examples_for_tool
)

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
