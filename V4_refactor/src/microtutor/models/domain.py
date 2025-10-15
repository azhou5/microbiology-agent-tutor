"""Domain models representing core business entities for MicroTutor.

These models define the core data structures used throughout the application.
"""

from __future__ import annotations

from datetime import datetime
import pytz
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class TutorState(str, Enum):
    """Current state of the tutoring session."""
    INITIALIZING = "initializing"
    INFORMATION_GATHERING = "information_gathering"
    PROBLEM_REPRESENTATION = "problem_representation"
    DIFFERENTIAL_DIAGNOSIS = "differential_diagnosis"
    TESTS = "tests"
    MANAGEMENT = "management"
    SOCRATIC_MODE = "socratic_mode"
    FEEDBACK = "feedback"


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
    model_name: str = None
    use_azure: Optional[bool] = None
    session_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(use_enum_values=True)
    
    def get_model_name(self) -> str:
        """Get the model name, using config default if None."""
        if self.model_name is None:
            from microtutor.core.config_helper import config
            return config.API_MODEL_NAME
        return self.model_name


class TutorResponse(BaseModel):
    """Complete response from tutor service."""
    content: str
    tools_used: List[str] = Field(default_factory=list)
    token_usage: Optional[TokenUsage] = None
    processing_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    feedback_examples: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


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
    created_at: datetime = Field(default_factory=lambda: datetime.now(pytz.timezone('America/New_York')))
    extra: Dict[str, Any] = Field(default_factory=dict)


class MCQOption(BaseModel):
    """Single option in a multiple choice question."""
    letter: str = Field(..., description="Option letter (a, b, c, d)")
    text: str = Field(..., description="Option text")
    is_correct: bool = Field(False, description="Whether this option is correct")


class MCQ(BaseModel):
    """Multiple Choice Question based on guidelines."""
    question_id: str = Field(..., description="Unique identifier for the question")
    question_text: str = Field(..., description="The question text")
    options: List[MCQOption] = Field(..., description="List of answer options")
    correct_answer: str = Field(..., description="Letter of the correct answer")
    explanation: str = Field(..., description="Explanation of the correct answer")
    source_guidelines: List[str] = Field(default_factory=list, description="Guidelines this question is based on")
    difficulty: str = Field(default="intermediate", description="Question difficulty level")
    topic: str = Field(..., description="Medical topic/domain")
    created_at: datetime = Field(default_factory=lambda: datetime.now(pytz.timezone('America/New_York')))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MCQResponse(BaseModel):
    """Student's response to an MCQ."""
    question_id: str = Field(..., description="ID of the question being answered")
    selected_answer: str = Field(..., description="Letter of selected answer")
    is_correct: bool = Field(..., description="Whether the answer is correct")
    response_time_ms: Optional[int] = Field(None, description="Time taken to respond in milliseconds")
    session_id: Optional[str] = Field(None, description="Session ID")
    created_at: datetime = Field(default_factory=lambda: datetime.now(pytz.timezone('America/New_York')))


class MCQFeedback(BaseModel):
    """Feedback provided after MCQ response."""
    question_id: str = Field(..., description="ID of the question")
    is_correct: bool = Field(..., description="Whether the answer was correct")
    explanation: str = Field(..., description="Explanation of the correct answer")
    additional_guidance: Optional[str] = Field(None, description="Additional learning guidance")
    next_question_suggestion: Optional[str] = Field(None, description="Suggestion for follow-up question")
    created_at: datetime = Field(default_factory=lambda: datetime.now(pytz.timezone('America/New_York')))


__all__ = [
    "TutorState",
    "TokenUsage",
    "TutorContext",
    "TutorResponse",
    "Message",
    "Case",
    "Feedback",
    "MCQOption",
    "MCQ",
    "MCQResponse",
    "MCQFeedback"
]
