"""Feedback client adapter for the TutorService architecture.

This adapter wraps the AutoFeedbackRetriever to match the FeedbackClient protocol
expected by TutorService.
"""

import logging
from typing import List, Dict, Any, Optional

from microtutor.utils.protocols import FeedbackClient

logger = logging.getLogger(__name__)


class FeedbackClientAdapter(FeedbackClient):
    """Adapter that wraps AutoFeedbackRetriever to match the FeedbackClient protocol."""
    
    def __init__(self, feedback_retriever):
        """Initialize with an AutoFeedbackRetriever instance."""
        self.feedback_retriever = feedback_retriever
    
    def get_examples_for_tool(
        self,
        user_input: str,
        conversation_history: List[Dict[str, str]],
        tool_name: str,
        include_feedback: bool,
        similarity_threshold: Optional[float] = None,
    ) -> str:
        """Get feedback examples formatted as a string for the LLM prompt."""
        if not include_feedback or self.feedback_retriever is None:
            return ""
            
        try:
            from microtutor.core.feedback import get_feedback_examples_for_tool
            
            return get_feedback_examples_for_tool(
                user_input=user_input,
                conversation_history=conversation_history,
                tool_name=tool_name,
                feedback_retriever=self.feedback_retriever,
                include_feedback=include_feedback,
                similarity_threshold=similarity_threshold
            ) or ""
        except Exception as e:
            logger.warning("Failed to get feedback examples: %s", e)
            return ""
    
    def retrieve_feedback_examples(
        self,
        current_message: str,
        conversation_history: List[Dict[str, str]],
        message_type: str,
        k: int,
        similarity_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve structured feedback examples for the frontend."""
        if self.feedback_retriever is None:
            return []
            
        try:
            # AutoFeedbackRetriever uses retrieve_similar_examples
            min_rating = 3 if similarity_threshold else 1
            retrieved = self.feedback_retriever.retrieve_similar_examples(
                input_text=current_message,
                history=conversation_history,
                k=k,
                index_type=message_type if message_type in ["all", "patient", "tutor"] else "all",
                min_rating=min_rating
            )
            
            # Convert FeedbackExample objects to structured format for frontend
            return [
                {
                    "similarity_score": float(ex.similarity_score),
                    "is_positive_example": ex.is_positive_example,
                    "is_negative_example": ex.is_negative_example,
                    "entry": {
                        "rating": ex.entry.rating,
                        "organism": ex.entry.organism,
                        "case_id": ex.entry.case_id,
                        "rated_message": ex.entry.rated_message,
                        "feedback_text": ex.entry.feedback_text,
                        "replacement_text": ex.entry.replacement_text,
                        "chat_history": ex.entry.chat_history,
                    },
                    "text": ex.text,
                } for ex in retrieved
            ]
        except Exception as e:
            logger.warning("Failed to retrieve feedback examples: %s", e)
            return []
