"""Phase detection and state management models for structured output."""

from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class PhaseTransitionReason(str, Enum):
    """Reason for phase transition."""
    COMPLETION_SIGNAL = "completion_signal"
    USER_REQUEST = "user_request"
    CONTENT_ANALYSIS = "content_analysis"
    TUTOR_DECISION = "tutor_decision"
    EXPLICIT_COMMAND = "explicit_command"


class PhaseConfidence(str, Enum):
    """Confidence level in phase detection."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PhaseState(BaseModel):
    """Current phase state with structured information."""
    current_phase: str = Field(..., description="Current phase name")
    phase_locked: bool = Field(default=False, description="Whether phase is locked")
    confidence: PhaseConfidence = Field(..., description="Confidence in phase detection")
    transition_reason: Optional[PhaseTransitionReason] = Field(None, description="Reason for transition")
    phase_progress: float = Field(ge=0.0, le=1.0, default=0.0, description="Progress within current phase (0-1)")
    next_phase: Optional[str] = Field(None, description="Next expected phase")
    phase_guidance: str = Field(..., description="Guidance text for current phase")
    completion_criteria: List[str] = Field(default_factory=list, description="Criteria for phase completion")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional phase metadata")


class TutorStructuredResponse(BaseModel):
    """Structured response from tutor including phase information."""
    content: str = Field(..., description="Main response content")
    phase_state: PhaseState = Field(..., description="Current phase state")
    tools_used: List[str] = Field(default_factory=list, description="Tools used in response")
    reasoning: Optional[str] = Field(None, description="Tutor's reasoning for phase decision")
    suggestions: List[str] = Field(default_factory=list, description="Suggestions for student")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional response metadata")


class PhaseTransitionRequest(BaseModel):
    """Request to transition to a specific phase."""
    target_phase: str = Field(..., description="Phase to transition to")
    reason: str = Field(..., description="Reason for transition request")
    force: bool = Field(default=False, description="Force transition even if validation fails")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")


class PhaseValidationResult(BaseModel):
    """Result of phase transition validation."""
    is_valid: bool = Field(..., description="Whether transition is valid")
    confidence: PhaseConfidence = Field(..., description="Confidence in validation")
    missing_criteria: List[str] = Field(default_factory=list, description="Missing completion criteria")
    suggestions: List[str] = Field(default_factory=list, description="Suggestions for completion")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
