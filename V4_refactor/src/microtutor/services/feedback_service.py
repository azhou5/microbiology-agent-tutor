"""Feedback service for managing user feedback.

This service handles:
- Saving feedback to database
- Saving case feedback
- Retrieving feedback for analysis
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import json

from microtutor.models.requests import FeedbackRequest, CaseFeedbackRequest

logger = logging.getLogger(__name__)


class FeedbackService:
    """Service for managing user feedback."""
    
    def __init__(self):
        """Initialize feedback service."""
        logger.info("FeedbackService initialized")
    
    async def save_feedback(
        self,
        feedback: FeedbackRequest,
        organism: Optional[str] = None,
        db_session: Optional[Any] = None
    ) -> int:
        """Save user feedback.
        
        Args:
            feedback: Feedback request data
            organism: Current organism (optional)
            db_session: Database session (optional)
            
        Returns:
            Feedback ID from database
        """
        logger.info(f"Saving feedback: rating={feedback.rating}, case_id={feedback.case_id}")
        
        # Extract visible history (user + assistant only)
        visible_history = [
            {"role": msg.role, "content": msg.content}
            for msg in feedback.history
            if msg.role in ['user', 'assistant']
        ]
        
        if db_session:
            # Save to database
            try:
                # Import DB model
                from microtutor.core.database import FeedbackEntry
                
                entry = FeedbackEntry(
                    timestamp=datetime.utcnow(),
                    organism=organism,
                    rating=str(feedback.rating),
                    rated_message=feedback.message,
                    feedback_text=feedback.feedback_text,
                    replacement_text=feedback.replacement_text,
                    chat_history=visible_history,
                    case_id=feedback.case_id
                )
                db_session.add(entry)
                await db_session.commit()
                await db_session.refresh(entry)
                
                logger.info(f"Feedback saved to database with ID: {entry.id}")
                return entry.id
                
            except Exception as e:
                logger.error(f"Error saving feedback to database: {e}", exc_info=True)
                await db_session.rollback()
                raise
        else:
            # Log to file as fallback
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "organism": organism,
                "rating": feedback.rating,
                "rated_message": feedback.message,
                "feedback_text": feedback.feedback_text,
                "replacement_text": feedback.replacement_text,
                "case_id": feedback.case_id,
                "visible_chat_history": visible_history
            }
            
            logger.info(f"Feedback logged: {json.dumps(log_entry)}")
            return 0
    
    async def save_case_feedback(
        self,
        feedback: CaseFeedbackRequest,
        organism: Optional[str] = None,
        db_session: Optional[Any] = None
    ) -> int:
        """Save case feedback.
        
        Args:
            feedback: Case feedback request data
            organism: Current organism (optional)
            db_session: Database session (optional)
            
        Returns:
            Feedback ID from database
        """
        logger.info(
            f"Saving case feedback: case_id={feedback.case_id}, "
            f"detail={feedback.detail}, helpfulness={feedback.helpfulness}, "
            f"accuracy={feedback.accuracy}"
        )
        
        if db_session:
            # Save to database
            try:
                from microtutor.core.database import CaseFeedbackEntry
                
                entry = CaseFeedbackEntry(
                    timestamp=datetime.utcnow(),
                    organism=organism or "Unknown",
                    detail_rating=str(feedback.detail),
                    helpfulness_rating=str(feedback.helpfulness),
                    accuracy_rating=str(feedback.accuracy),
                    comments=feedback.comments,
                    case_id=feedback.case_id
                )
                db_session.add(entry)
                await db_session.commit()
                await db_session.refresh(entry)
                
                logger.info(f"Case feedback saved to database with ID: {entry.id}")
                return entry.id
                
            except Exception as e:
                logger.error(f"Error saving case feedback to database: {e}", exc_info=True)
                await db_session.rollback()
                raise
        else:
            # Log to file as fallback
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "organism": organism or "Unknown",
                "detail_rating": feedback.detail,
                "helpfulness_rating": feedback.helpfulness,
                "accuracy_rating": feedback.accuracy,
                "comments": feedback.comments,
                "case_id": feedback.case_id
            }
            
            logger.info(f"Case feedback logged: {json.dumps(log_entry)}")
            return 0
    
    async def get_feedback_for_case(
        self,
        case_id: str,
        db_session: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """Get all feedback for a specific case.
        
        Args:
            case_id: Case ID to get feedback for
            db_session: Database session (optional)
            
        Returns:
            List of feedback entries
        """
        if not db_session:
            logger.warning("No database session provided for feedback retrieval")
            return []
        
        try:
            from microtutor.core.database import FeedbackEntry
            
            results = await db_session.execute(
                FeedbackEntry.__table__.select().where(
                    FeedbackEntry.case_id == case_id
                )
            )
            feedback_entries = results.fetchall()
            
            logger.info(f"Retrieved {len(feedback_entries)} feedback entries for case {case_id}")
            return [dict(entry) for entry in feedback_entries]
            
        except Exception as e:
            logger.error(f"Error retrieving feedback: {e}", exc_info=True)
            return []

