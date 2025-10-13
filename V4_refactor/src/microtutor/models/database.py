"""Database models for MicroTutor V4.

These models match the V3 schema for compatibility.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ConversationLog(Base):
    """Log of all conversation messages between user and tutor."""
    
    __tablename__ = 'conversation_log'
    
    id = Column(Integer, primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    role = Column(String(50), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    
    def __repr__(self):
        return f"<ConversationLog(case_id='{self.case_id}', role='{self.role}')>"


class FeedbackEntry(Base):
    """User feedback on tutor responses."""
    
    __tablename__ = 'feedback'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    organism = Column(String(128), nullable=True)
    rating = Column(String(2), nullable=False)  # '++', '+', '0', '-'
    rated_message = Column(Text, nullable=True)
    feedback_text = Column(Text, nullable=True)
    replacement_text = Column(Text, nullable=True)
    chat_history = Column(Text, nullable=True)  # JSON string
    case_id = Column(String(128), nullable=True)
    
    def __repr__(self):
        return f"<FeedbackEntry(case_id='{self.case_id}', rating='{self.rating}')>"


class CaseFeedbackEntry(Base):
    """User feedback on overall case quality."""
    
    __tablename__ = 'case_feedback'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    organism = Column(String(128), nullable=True)
    detail_rating = Column(String(2), nullable=False)
    helpfulness_rating = Column(String(2), nullable=False)
    accuracy_rating = Column(String(2), nullable=False)
    comments = Column(Text, nullable=True)
    case_id = Column(String(128), nullable=True)
    
    def __repr__(self):
        return f"<CaseFeedbackEntry(case_id='{self.case_id}', detail={self.detail_rating})>"

