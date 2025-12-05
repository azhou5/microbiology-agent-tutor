"""Service layer for business logic.

This module contains all business logic services, organized by domain:
- tutor/: Main tutoring service
- case/: Case management and generation
- mcq/: Multiple choice question services
- feedback/: Feedback management
- voice/: Voice synthesis and transcription
- guideline/: Clinical guideline services
- infrastructure/: Supporting services (cost, background, factory)
- adapters/: Adapter pattern implementations
"""

# Main domain services
from .tutor import TutorService, ServiceConfig
from .case import CaseService, get_case, CaseGeneratorRAGAgent
from .feedback import FeedbackService
from .voice import VoiceService
from .mcq import MCQService, MCPMCQAgent, create_mcp_mcq_agent
from .guideline import GuidelineService, GuidelinesCache, get_guidelines_cache

# Infrastructure services
from .infrastructure import (
    CostService,
    BackgroundTaskService,
    get_background_service,
    create_tutor_service,
)

__all__ = [
    # Domain services
    "TutorService",
    "ServiceConfig",
    "CaseService",
    "get_case",
    "CaseGeneratorRAGAgent",
    "FeedbackService",
    "VoiceService",
    "MCQService",
    "MCPMCQAgent",
    "create_mcp_mcq_agent",
    "GuidelineService",
    "GuidelinesCache",
    "get_guidelines_cache",
    # Infrastructure
    "CostService",
    "BackgroundTaskService",
    "get_background_service",
    "create_tutor_service",
]
