"""
MCQ API Routes for MicroTutor V4

API endpoints for MCQ generation, response processing, and feedback.
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from microtutor.services.mcq.mcp_service import MCPMCQAgent, create_mcp_mcq_agent
from microtutor.schemas.domain.domain import MCQ, MCQResponse, MCQFeedback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcq", tags=["MCQ"])

# Global agent instance (in production, use dependency injection)
_mcp_agent: Optional[MCPMCQAgent] = None


def get_mcp_agent() -> MCPMCQAgent:
    """Get or create MCP MCQ agent instance."""
    global _mcp_agent
    if _mcp_agent is None:
        _mcp_agent = create_mcp_mcq_agent()
    return _mcp_agent


# Request/Response Models
class MCQGenerationRequest(BaseModel):
    """Request model for MCQ generation."""
    topic: str = Field(..., description="Medical topic for the question")
    case_context: Optional[str] = Field(None, description="Case context for more targeted questions")
    difficulty: str = Field("intermediate", description="Question difficulty level")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")


class MCQGenerationResponse(BaseModel):
    """Response model for MCQ generation."""
    success: bool
    mcq_display: Optional[str] = None
    mcq_data: Optional[dict] = None
    session_id: Optional[str] = None
    error: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class MCQResponseRequest(BaseModel):
    """Request model for MCQ response processing."""
    session_id: str = Field(..., description="Session ID with active MCQ")
    selected_answer: str = Field(..., description="Selected answer letter (a, b, c, d)")
    response_time_ms: Optional[int] = Field(None, description="Response time in milliseconds")


class MCQResponseResponse(BaseModel):
    """Response model for MCQ response processing."""
    success: bool
    feedback_display: Optional[str] = None
    is_correct: Optional[bool] = None
    feedback_data: Optional[dict] = None
    session_id: Optional[str] = None
    error: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class SessionSummaryResponse(BaseModel):
    """Response model for session summary."""
    success: bool
    summary: Optional[dict] = None
    error: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


# API Endpoints

@router.post("/generate", response_model=MCQGenerationResponse)
async def generate_mcq(
    request: MCQGenerationRequest,
    agent: MCPMCQAgent = Depends(get_mcp_agent)
):
    """
    Generate a multiple choice question based on clinical guidelines.
    
    **Example Request:**
    ```json
    {
        "topic": "MRSA treatment",
        "case_context": "Patient with MRSA pneumonia",
        "difficulty": "intermediate",
        "session_id": "session_123"
    }
    ```
    
    **Example Response:**
    ```json
    {
        "success": true,
        "mcq_display": "**Question: What is the first-line treatment for MRSA pneumonia?**\\n\\na) Vancomycin\\nb) Daptomycin\\nc) Linezolid\\nd) Ceftaroline\\n\\n**Instructions:** Click on your answer choice...",
        "mcq_data": {
            "question_id": "uuid-123",
            "question_text": "What is the first-line treatment for MRSA pneumonia?",
            "options": [...],
            "correct_answer": "a",
            "explanation": "...",
            "topic": "MRSA treatment"
        },
        "session_id": "session_123"
    }
    ```
    """
    try:
        result = agent.generate_mcq_for_topic(
            topic=request.topic,
            case_context=request.case_context,
            difficulty=request.difficulty,
            session_id=request.session_id
        )
        
        if result['success']:
            logger.info(f"Generated MCQ for topic: {request.topic}")
            return MCQGenerationResponse(**result)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to generate MCQ: {result.get('error', 'Unknown error')}"
            )
            
    except Exception as e:
        logger.error(f"MCQ generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"MCQ generation failed: {str(e)}"
        )


@router.post("/respond", response_model=MCQResponseResponse)
async def process_mcq_response(
    request: MCQResponseRequest,
    agent: MCPMCQAgent = Depends(get_mcp_agent)
):
    """
    Process a student's response to an MCQ and provide feedback.
    
    **Example Request:**
    ```json
    {
        "session_id": "session_123",
        "selected_answer": "a",
        "response_time_ms": 15000
    }
    ```
    
    **Example Response:**
    ```json
    {
        "success": true,
        "feedback_display": "**Your Answer: A**\\n\\nCorrect! Vancomycin is the first-line treatment...",
        "is_correct": true,
        "feedback_data": {
            "question_id": "uuid-123",
            "is_correct": true,
            "explanation": "...",
            "additional_guidance": "Excellent!...",
            "next_question_suggestion": "Would you like to explore..."
        },
        "session_id": "session_123"
    }
    ```
    """
    try:
        result = agent.process_mcq_response(
            session_id=request.session_id,
            selected_answer=request.selected_answer,
            response_time_ms=request.response_time_ms
        )
        
        if result['success']:
            logger.info(f"Processed MCQ response for session: {request.session_id}")
            return MCQResponseResponse(**result)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to process response: {result.get('error', 'Unknown error')}"
            )
            
    except Exception as e:
        logger.error(f"MCQ response processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Response processing failed: {str(e)}"
        )


@router.get("/session/{session_id}/summary", response_model=SessionSummaryResponse)
async def get_session_summary(
    session_id: str,
    agent: MCPMCQAgent = Depends(get_mcp_agent)
):
    """
    Get a summary of MCQ performance for a session.
    
    **Example Response:**
    ```json
    {
        "success": true,
        "summary": {
            "total_questions": 5,
            "correct_answers": 4,
            "accuracy_percentage": 80.0,
            "average_response_time_ms": 12500.0,
            "topics_covered": 3
        }
    }
    ```
    """
    try:
        result = agent.get_session_summary(session_id)
        
        if result['success']:
            return SessionSummaryResponse(**result)
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found: {result.get('error', 'Unknown error')}"
            )
            
    except Exception as e:
        logger.error(f"Session summary failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Session summary failed: {str(e)}"
        )


@router.delete("/session/{session_id}")
async def clear_session(
    session_id: str,
    agent: MCPMCQAgent = Depends(get_mcp_agent)
):
    """
    Clear all MCQ data for a session.
    
    **Example Response:**
    ```json
    {
        "success": true,
        "message": "Session session_123 cleared successfully"
    }
    ```
    """
    try:
        result = agent.clear_session(session_id)
        
        if result['success']:
            return {"success": True, "message": result['message']}
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to clear session: {result.get('error', 'Unknown error')}"
            )
            
    except Exception as e:
        logger.error(f"Session clear failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Session clear failed: {str(e)}"
        )


@router.get("/health")
async def health_check(agent: MCPMCQAgent = Depends(get_mcp_agent)):
    """
    Health check for MCQ service.
    
    **Example Response:**
    ```json
    {
        "status": "healthy",
        "service": "MCQ",
        "agent_available": true
    }
    ```
    """
    try:
        is_available = agent.is_available()
        
        return {
            "status": "healthy" if is_available else "unhealthy",
            "service": "MCQ",
            "agent_available": is_available
        }
        
    except Exception as e:
        logger.error(f"MCQ health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "MCQ",
            "agent_available": False,
            "error": str(e)
        }
