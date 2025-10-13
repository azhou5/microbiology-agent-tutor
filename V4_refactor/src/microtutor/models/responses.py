"""Pydantic response models for API endpoints.

This module defines all response models returned by the FastAPI endpoints.
Each model ensures consistent response structure and automatic documentation.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from .requests import Message


class StartCaseResponse(BaseModel):
    """Response when starting a new case.
    
    Attributes:
        initial_message: Initial tutor message to start the case
        history: Initial conversation history
        case_id: Case ID for this session
        organism: Organism for this case
    """
    
    initial_message: str = Field(
        ...,
        description="Initial tutor message introducing the case"
    )
    history: List[Message] = Field(
        ...,
        description="Initial conversation history including system message"
    )
    case_id: str = Field(
        ...,
        description="Case ID for this session"
    )
    organism: str = Field(
        ...,
        description="Organism for this case"
    )
    
    class Config:
        """Pydantic config with example."""
        schema_extra = {
            "example": {
                "initial_message": "Welcome! Let me present a 45-year-old patient...",
                "history": [
                    {
                        "role": "system",
                        "content": "You are an expert microbiology tutor..."
                    },
                    {
                        "role": "assistant",
                        "content": "Welcome! Let me present a 45-year-old patient..."
                    }
                ],
                "case_id": "case_2024_abc123",
                "organism": "staphylococcus aureus"
            }
        }


class ChatResponse(BaseModel):
    """Response from a chat interaction.
    
    Attributes:
        response: Tutor's response message
        history: Updated conversation history
        tools_used: Tools used in generating this response
        metadata: Additional metadata (tokens, timing, etc.)
    """
    
    response: str = Field(
        ...,
        description="Tutor's response to the user's message"
    )
    history: List[Message] = Field(
        ...,
        description="Updated conversation history"
    )
    tools_used: Optional[List[str]] = Field(
        default_factory=list,
        description="List of tools used (e.g., 'patient', 'hint')"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata including token usage and timing"
    )
    
    class Config:
        """Pydantic config with example."""
        schema_extra = {
            "example": {
                "response": "The patient's temperature is 38.5°C, indicating fever.",
                "history": [
                    {"role": "user", "content": "What is the patient's temperature?"},
                    {"role": "assistant", "content": "The patient's temperature is 38.5°C..."}
                ],
                "tools_used": ["patient"],
                "metadata": {
                    "processing_time_ms": 1234.5,
                    "token_usage": {
                        "prompt_tokens": 150,
                        "completion_tokens": 45,
                        "total_tokens": 195
                    }
                }
            }
        }


class FeedbackResponse(BaseModel):
    """Response after submitting feedback.
    
    Attributes:
        status: Status message
        feedback_id: Database ID of the feedback entry
    """
    
    status: str = Field(
        default="Feedback received",
        description="Status message"
    )
    feedback_id: Optional[int] = Field(
        None,
        description="Database ID of the feedback entry"
    )
    
    class Config:
        """Pydantic config with example."""
        schema_extra = {
            "example": {
                "status": "Feedback received",
                "feedback_id": 12345
            }
        }


class CaseFeedbackResponse(BaseModel):
    """Response after submitting case feedback.
    
    Attributes:
        status: Status message
        feedback_id: Database ID of the feedback entry
    """
    
    status: str = Field(
        default="Case feedback received",
        description="Status message"
    )
    feedback_id: Optional[int] = Field(
        None,
        description="Database ID of the feedback entry"
    )
    
    class Config:
        """Pydantic config with example."""
        schema_extra = {
            "example": {
                "status": "Case feedback received",
                "feedback_id": 67890
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response for all endpoints.
    
    Attributes:
        error: Human-readable error message
        error_code: Machine-readable error code
        details: Additional error details
        needs_new_case: Whether client should start a new case
    """
    
    error: str = Field(
        ..., 
        description="Human-readable error message"
    )
    error_code: Optional[str] = Field(
        None, 
        description="Machine-readable error code"
    )
    details: Optional[Dict[str, Any]] = Field(
        None, 
        description="Additional error details for debugging"
    )
    needs_new_case: bool = Field(
        default=False, 
        description="Whether the client should start a new case"
    )
    
    class Config:
        """Pydantic config with example."""
        schema_extra = {
            "example": {
                "error": "No active case ID. Please start a new case.",
                "error_code": "NO_CASE_ID",
                "details": None,
                "needs_new_case": True
            }
        }


class OrganismListResponse(BaseModel):
    """List of available organisms with cached cases.
    
    Attributes:
        organisms: List of available organisms
        count: Number of organisms available
    """
    
    organisms: List[str] = Field(
        ...,
        description="Available organisms with pre-generated cases"
    )
    count: int = Field(
        ...,
        description="Number of organisms available"
    )
    
    class Config:
        """Pydantic config with example."""
        schema_extra = {
            "example": {
                "organisms": [
                    "staphylococcus aureus",
                    "streptococcus pneumoniae",
                    "escherichia coli"
                ],
                "count": 3
            }
        }


class HealthCheckResponse(BaseModel):
    """Health check response.
    
    Attributes:
        status: Health status
        timestamp: Current timestamp
        version: API version
    """
    
    status: str = Field(
        ...,
        description="Health status (healthy, degraded, unhealthy)"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Current server timestamp"
    )
    version: str = Field(
        default="4.0.0",
        description="API version"
    )
    
    class Config:
        """Pydantic config with example."""
        schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2024-10-13T12:34:56.789Z",
                "version": "4.0.0"
            }
        }

