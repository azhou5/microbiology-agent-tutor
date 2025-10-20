"""Feedback client adapter for the new TutorService architecture."""

from typing import List, Dict, Any, Optional
from microtutor.services.tutor_service_v2 import FeedbackClient
from microtutor.feedback import get_feedback_examples_for_tool


class FeedbackClientAdapter(FeedbackClient):
    """Adapter that wraps the existing feedback system to match the FeedbackClient protocol."""
    
    def __init__(self, feedback_retriever):
        self.feedback_retriever = feedback_retriever
    
    def get_examples_for_tool(
        self,
        user_input: str,
        conversation_history: List[Dict[str, str]],
        tool_name: str,
        include_feedback: bool,
        similarity_threshold: Optional[float] = None,  # Now properly passed to underlying functions
    ) -> str:
        """Get feedback examples as a string for the LLM."""
        try:
            return get_feedback_examples_for_tool(
                user_input=user_input,
                conversation_history=conversation_history,
                tool_name=tool_name,
                feedback_retriever=self.feedback_retriever,
                include_feedback=include_feedback,
                similarity_threshold=similarity_threshold
            ) or ""
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Failed to get feedback examples: %s", e)
            return ""
    
    def retrieve_feedback_examples(
        self,
        current_message: str,
        conversation_history: List[Dict[str, str]],
        message_type: str,
        k: int,
        similarity_threshold: Optional[float] = None,  # Now properly passed to underlying functions
    ) -> List[Dict[str, Any]]:
        """Retrieve structured feedback examples for the frontend."""
        try:
            retrieved = self.feedback_retriever.retrieve_feedback_examples(
                current_message=current_message,
                conversation_history=conversation_history,
                message_type=message_type,
                k=k,
                similarity_threshold=similarity_threshold
            )
            
            # Convert to structured format
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
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Failed to retrieve feedback examples: %s", e)
            return []
