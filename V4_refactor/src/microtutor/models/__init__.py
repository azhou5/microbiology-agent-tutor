"""Data models for the Microbiology Tutor.

Includes Pydantic models (validation) and SQLAlchemy models (database).
"""

from .requests import (
    StartCaseRequest,
    ChatRequest,
    FeedbackRequest,
    CaseFeedbackRequest,
    Message
)
from .responses import (
    StartCaseResponse,
    ChatResponse,
    FeedbackResponse,
    CaseFeedbackResponse,
    ErrorResponse,
    OrganismListResponse
)
from .domain import (
    TutorState,
    TokenUsage,
    TutorContext,
    TutorResponse,
    Case,
    Feedback
)
from .database import (
    Base,
    ConversationLog,
    FeedbackEntry,
    CaseFeedbackEntry
)

__all__ = [
    # Requests
    "StartCaseRequest",
    "ChatRequest",
    "FeedbackRequest",
    "CaseFeedbackRequest",
    "Message",
    # Responses
    "StartCaseResponse",
    "ChatResponse",
    "FeedbackResponse",
    "CaseFeedbackResponse",
    "ErrorResponse",
    "OrganismListResponse",
    # Domain
    "TutorState",
    "TokenUsage",
    "TutorContext",
    "TutorResponse",
    "Case",
    "Feedback",
    # Database
    "Base",
    "ConversationLog",
    "FeedbackEntry",
    "CaseFeedbackEntry",
]
