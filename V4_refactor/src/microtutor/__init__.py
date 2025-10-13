"""
MicroTutor V4: Modern AI-powered microbiology tutoring system.

This package provides an interactive tutoring system with:
- FastAPI-based REST API with automatic documentation
- Pydantic models for type-safe request/response handling
- Clean service layer architecture
- Separation of concerns for better maintainability

Main Components:
- API layer (FastAPI routes and app)
- Service layer (business logic)
- Models (Pydantic data models)
- Core (LLM routing, prompts, utilities)
- Agents (patient, socratic, hint simulation)

Example:
    >>> from microtutor.services import TutorService
    >>> tutor = TutorService()
    >>> response = await tutor.start_case("staphylococcus aureus", "case_123")
"""

__version__ = "4.0.0"
__author__ = "Riccardo Conci"
__email__ = "riccardo.conci@harvard.edu"
__license__ = "MIT"

from microtutor.services import TutorService, CaseService, FeedbackService
from microtutor.models import (
    StartCaseRequest,
    ChatRequest,
    StartCaseResponse,
    ChatResponse,
    TutorContext,
    TutorState
)

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "TutorService",
    "CaseService",
    "FeedbackService",
    "StartCaseRequest",
    "ChatRequest",
    "StartCaseResponse",
    "ChatResponse",
    "TutorContext",
    "TutorState"
]
