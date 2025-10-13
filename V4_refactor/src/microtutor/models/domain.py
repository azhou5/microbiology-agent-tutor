"""Domain models representing core business entities for MicroTutor.

These models define the core data structures used throughout the application.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class TutorState(str, Enum):
    """Current state of the tutoring session."""
    INITIALIZING = "initializing"
    INFORMATION_GATHERING = "information_gathering"
    PROBLEM_REPRESENTATION = "problem_representation"
    DIFFERENTIAL_DIAGNOSIS = "differential_diagnosis"
    INVESTIGATIONS = "investigations"
    TREATMENT = "treatment"
    SOCRATIC_MODE = "socratic_mode"
    COMPLETED = "completed"


class TokenUsage(BaseModel):
    """Tracks token usage for LLM calls."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0


class TutorContext(BaseModel):
    """Context for a tutoring session."""
    case_id: str
    organism: str
    case_description: Optional[str] = None
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    current_state: TutorState = TutorState.INITIALIZING
    model_name: str = "o3-mini"
    session_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True


class TutorResponse(BaseModel):
    """Complete response from tutor service."""
    content: str
    tools_used: List[str] = Field(default_factory=list)
    token_usage: Optional[TokenUsage] = None
    processing_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    """Chat message in a conversation."""
    role: str = Field(..., description="One of: user, assistant, system")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(None, description="Optional message timestamp")


class Case(BaseModel):
    """Minimal case representation used during sessions."""
    organism: str
    description: str
    initial_presentation: str
    difficulty: str = Field(default="intermediate")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Feedback(BaseModel):
    """User/expert feedback on model outputs."""
    rating: Optional[int] = Field(None, ge=1, le=5)
    feedback_text: Optional[str] = None
    session_id: Optional[str] = None
    case_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    extra: Dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "TutorState",
    "TokenUsage",
    "TutorContext",
    "TutorResponse",
    "Message",
    "Case",
    "Feedback"
]
