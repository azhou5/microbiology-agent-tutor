"""Data schemas for the Microbiology Tutor.

Includes Pydantic models (validation) and SQLAlchemy models (database).
Reorganized from models/ for better clarity.
"""

from .api.requests import (
    StartCaseRequest,
    ChatRequest,
    FeedbackRequest,
    CaseFeedbackRequest,
    Message
)
from .api.responses import (
    StartCaseResponse,
    ChatResponse,
    FeedbackResponse,
    CaseFeedbackResponse,
    ErrorResponse,
    OrganismListResponse
)
from .domain.domain import (
    TutorState,
    TokenUsage,
    TutorContext,
    TutorResponse,
    Case,
    Feedback
)
from .database.database import (
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

