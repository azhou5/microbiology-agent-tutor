"""
Database feedback loader for automatic FAISS index generation.

This module loads feedback data directly from the PostgreSQL database
instead of JSON files, enabling real-time feedback index updates.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import text

from microtutor.core.feedback.processor import FeedbackEntry

logger = logging.getLogger(__name__)


@dataclass
class DatabaseFeedbackConfig:
    """Configuration for database feedback loading."""
    min_rating: int = 1
    max_entries: Optional[int] = None
    include_case_feedback: bool = True
    include_regular_feedback: bool = True
    filter_by_organism: Optional[str] = None
    days_back: Optional[int] = None


class DatabaseFeedbackLoader:
    """Loads feedback data from PostgreSQL database for FAISS index generation."""
    
    def __init__(self, db_session: Session):
        """Initialize database feedback loader.
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db_session = db_session
    
    def load_feedback_entries(
        self, 
        config: Optional[DatabaseFeedbackConfig] = None
    ) -> List[FeedbackEntry]:
        """Load feedback entries from database.
        
        Args:
            config: Configuration for loading feedback data
            
        Returns:
            List of FeedbackEntry objects
        """
        if config is None:
            config = DatabaseFeedbackConfig()
        
        logger.info("Loading feedback entries from database...")
        
        entries = []
        
        # Load regular feedback
        if config.include_regular_feedback:
            regular_entries = self._load_regular_feedback(config)
            entries.extend(regular_entries)
            logger.info(f"Loaded {len(regular_entries)} regular feedback entries")
        
        # Load case feedback (convert to regular feedback format)
        if config.include_case_feedback:
            case_entries = self._load_case_feedback(config)
            entries.extend(case_entries)
            logger.info(f"Loaded {len(case_entries)} case feedback entries")
        
        logger.info(f"Total feedback entries loaded: {len(entries)}")
        return entries
    
    def _load_regular_feedback(self, config: DatabaseFeedbackConfig) -> List[FeedbackEntry]:
        """Load regular feedback from the feedback table."""
        try:
            # Build query with filters
            query = """
                SELECT 
                    id,
                    timestamp,
                    organism,
                    rating,
                    rated_message,
                    feedback_text,
                    replacement_text,
                    case_id,
                    chat_history
                FROM feedback
                WHERE 1=1
            """
            
            params = {}
            
            if config.min_rating is not None:
                query += " AND rating::int >= :min_rating"
                params['min_rating'] = config.min_rating
            
            if config.filter_by_organism:
                query += " AND organism = :organism"
                params['organism'] = config.filter_by_organism
            
            if config.days_back:
                query += " AND timestamp >= NOW() - INTERVAL '1 day' * CAST(:days_back AS INTEGER)"
                params['days_back'] = config.days_back
            
            query += " ORDER BY timestamp DESC"
            
            if config.max_entries:
                query += " LIMIT :max_entries"
                params['max_entries'] = config.max_entries
            
            result = self.db_session.execute(text(query), params)
            rows = result.fetchall()
            
            entries = []
            for row in rows:
                try:
                    import json
                    
                    # Try to get chat_history from the feedback table first
                    chat_history = []
                    if hasattr(row, 'chat_history') and row.chat_history:
                        try:
                            if isinstance(row.chat_history, str):
                                chat_history = json.loads(row.chat_history)
                            elif isinstance(row.chat_history, list):
                                chat_history = row.chat_history
                        except:
                            pass
                    
                    # If no chat_history in feedback, try to get from conversation_logs
                    if not chat_history and row.case_id:
                        chat_history = self._get_conversation_history(row.case_id)
                    
                    # Determine message type
                    message_type = self._determine_message_type(row.rated_message)
                    
                    entry = FeedbackEntry(
                        id=str(row.id),
                        timestamp=row.timestamp,
                        organism=row.organism or "",
                        rating=int(row.rating),
                        rated_message=row.rated_message or "",
                        feedback_text=row.feedback_text or "",
                        replacement_text=row.replacement_text or "",
                        chat_history=chat_history,
                        case_id=row.case_id or "",
                        message_type=message_type
                    )
                    entries.append(entry)
                    
                except Exception as e:
                    logger.warning(f"Failed to parse regular feedback entry {row.id}: {e}")
                    continue
            
            return entries
            
        except Exception as e:
            logger.error(f"Failed to load regular feedback: {e}")
            return []
    
    def _get_conversation_history(self, case_id: str) -> List[Dict[str, str]]:
        """Get conversation history from conversation_logs table for a given case_id."""
        try:
            result = self.db_session.execute(text("""
                SELECT role, content
                FROM conversation_logs
                WHERE case_id = :case_id
                ORDER BY timestamp ASC
            """), {'case_id': case_id})
            
            rows = result.fetchall()
            chat_history = [{"role": row.role, "content": row.content} for row in rows if row.role != 'system']
            return chat_history
            
        except Exception as e:
            logger.warning(f"Failed to get conversation history for case {case_id}: {e}")
            return []
    
    def _load_case_feedback(self, config: DatabaseFeedbackConfig) -> List[FeedbackEntry]:
        """Load case feedback and convert to FeedbackEntry format."""
        try:
            # Build query for case feedback
            query = """
                SELECT 
                    id,
                    timestamp,
                    organism,
                    detail_rating,
                    helpfulness_rating,
                    accuracy_rating,
                    comments,
                    case_id
                FROM case_feedback
                WHERE 1=1
            """
            
            params = {}
            
            if config.filter_by_organism:
                query += " AND organism = :organism"
                params['organism'] = config.filter_by_organism
            
            if config.days_back:
                query += " AND timestamp >= NOW() - INTERVAL '1 day' * CAST(:days_back AS INTEGER)"
                params['days_back'] = config.days_back
            
            query += " ORDER BY timestamp DESC"
            
            if config.max_entries:
                query += " LIMIT :max_entries"
                params['max_entries'] = config.max_entries
            
            result = self.db_session.execute(text(query), params)
            rows = result.fetchall()
            
            entries = []
            for row in rows:
                try:
                    # Convert case feedback to regular feedback format
                    # Use average of ratings as the main rating
                    avg_rating = (int(row.detail_rating) + int(row.helpfulness_rating) + int(row.accuracy_rating)) / 3
                    
                    # Create a synthetic message for case feedback
                    synthetic_message = f"Case feedback for case {row.case_id}: Detail={row.detail_rating}, Helpfulness={row.helpfulness_rating}, Accuracy={row.accuracy_rating}"
                    if row.comments:
                        synthetic_message += f" - Comments: {row.comments}"
                    
                    entry = FeedbackEntry(
                        id=f"case_feedback_{row.id}",
                        timestamp=row.timestamp,
                        organism=row.organism or "",
                        rating=int(avg_rating),
                        rated_message=synthetic_message,
                        feedback_text=row.comments or "",
                        replacement_text="",  # Case feedback doesn't have replacement text
                        chat_history=[],  # Case feedback doesn't have chat history
                        case_id=row.case_id or "",
                        message_type="case_feedback"
                    )
                    entries.append(entry)
                    
                except Exception as e:
                    logger.warning(f"Failed to parse case feedback entry {row.id}: {e}")
                    continue
            
            return entries
            
        except Exception as e:
            logger.error(f"Failed to load case feedback: {e}")
            return []
    
    def _determine_message_type(self, message: str) -> str:
        """Determine message type based on content."""
        if not message:
            return "other"
        
        message_lower = message.lower()
        
        # Check for patient-related keywords
        patient_keywords = [
            "patient", "symptoms", "complaints", "history", "vital signs",
            "physical exam", "chief complaint", "presenting", "feeling"
        ]
        
        # Check for tutor-related keywords
        tutor_keywords = [
            "diagnosis", "treatment", "management", "recommendation",
            "suggest", "consider", "approach", "strategy", "plan"
        ]
        
        patient_score = sum(1 for keyword in patient_keywords if keyword in message_lower)
        tutor_score = sum(1 for keyword in tutor_keywords if keyword in message_lower)
        
        if patient_score > tutor_score:
            return "patient"
        elif tutor_score > patient_score:
            return "tutor"
        else:
            return "other"
    
    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get statistics about feedback in the database."""
        try:
            # Regular feedback stats
            regular_stats = self.db_session.execute(text("""
                SELECT 
                    COUNT(*) as total_count,
                    AVG(rating::int) as avg_rating,
                    MIN(rating::int) as min_rating,
                    MAX(rating::int) as max_rating,
                    COUNT(DISTINCT organism) as unique_organisms,
                    COUNT(DISTINCT case_id) as unique_cases
                FROM feedback
            """)).fetchone()
            
            # Case feedback stats
            case_stats = self.db_session.execute(text("""
                SELECT 
                    COUNT(*) as total_count,
                    AVG((detail_rating::float + helpfulness_rating::float + accuracy_rating::float) / 3) as avg_rating,
                    COUNT(DISTINCT organism) as unique_organisms,
                    COUNT(DISTINCT case_id) as unique_cases
                FROM case_feedback
            """)).fetchone()
            
            return {
                "regular_feedback": {
                    "total_count": regular_stats.total_count or 0,
                    "avg_rating": float(regular_stats.avg_rating) if regular_stats.avg_rating else 0.0,
                    "min_rating": float(regular_stats.min_rating) if regular_stats.min_rating else 0.0,
                    "max_rating": float(regular_stats.max_rating) if regular_stats.max_rating else 0.0,
                    "unique_organisms": regular_stats.unique_organisms or 0,
                    "unique_cases": regular_stats.unique_cases or 0
                },
                "case_feedback": {
                    "total_count": case_stats.total_count or 0,
                    "avg_rating": float(case_stats.avg_rating) if case_stats.avg_rating else 0.0,
                    "unique_organisms": case_stats.unique_organisms or 0,
                    "unique_cases": case_stats.unique_cases or 0
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get feedback stats: {e}")
            return {
                "regular_feedback": {"total_count": 0, "avg_rating": 0.0, "min_rating": 0.0, "max_rating": 0.0, "unique_organisms": 0, "unique_cases": 0},
                "case_feedback": {"total_count": 0, "avg_rating": 0.0, "unique_organisms": 0, "unique_cases": 0}
            }
