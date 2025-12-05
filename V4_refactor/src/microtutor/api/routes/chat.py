"""Chat-related API endpoints."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from microtutor.api.dependencies import get_tutor_service
from microtutor.core.config.config_helper import config
from microtutor.schemas.api.requests import StartCaseRequest, ChatRequest, FeedbackRequest, CaseFeedbackRequest
from microtutor.schemas.api.responses import StartCaseResponse, ChatResponse, ErrorResponse
from microtutor.schemas.domain.domain import TutorContext
from microtutor.services.infrastructure.background import BackgroundTaskService, get_background_service
from microtutor.services.tutor.service import TutorService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/start_case",
    response_model=StartCaseResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Start a new microbiology case",
    description="Initialize a new case for the selected organism with a unique case ID"
)
async def start_case(
    request: StartCaseRequest,
    tutor_service: TutorService = Depends(get_tutor_service),
    background_service: BackgroundTaskService = Depends(get_background_service)
) -> StartCaseResponse:
    """Start a new case with the selected organism.
    
    - **organism**: The microorganism to study (e.g., "staphylococcus aureus")
    - **case_id**: Client-generated unique case ID
    - **model_name**: Optional LLM model to use (defaults to o3-mini)
    """
    model_name = request.model_name or config.API_MODEL_NAME
    logger.info(f"[START_CASE] organism={request.organism}, case_id={request.case_id}, model={model_name}")
    
    try:
        response = await tutor_service.start_case(
            organism=request.organism,
            case_id=request.case_id,
            model_name=request.model_name,
            enable_guidelines=request.enable_guidelines or False
        )
        
        # Log asynchronously
        background_service.log_conversation_async(
            case_id=request.case_id,
            role="system",
            content=f"Case started: {request.organism}",
            metadata={"organism": request.organism, "model": model_name}
        )
        background_service.log_conversation_async(
            case_id=request.case_id,
            role="assistant",
            content=response.content,
            metadata={"tools_used": response.tools_used}
        )
        
        logger.info(f"[START_CASE] Success for case_id={request.case_id}")
        
        return StartCaseResponse(
            initial_message=response.content,
            history=[{"role": "assistant", "content": response.content}],
            case_id=request.case_id,
            organism=request.organism
        )
        
    except ValueError as e:
        logger.error(f"[START_CASE] ValueError: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"[START_CASE] Error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to start case")


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Send a chat message",
    description="Send a message to the tutor and receive a response"
)
async def chat(
    request: ChatRequest,
    tutor_service: TutorService = Depends(get_tutor_service),
    background_service: BackgroundTaskService = Depends(get_background_service)
) -> ChatResponse:
    """Process a chat message from the student.
    
    - **message**: The student's question or response
    - **history**: Full conversation history including system messages
    - **organism_key**: Current organism being studied
    - **case_id**: Active case ID
    """
    start_time = datetime.now()
    
    # Validate required fields
    if not request.case_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active case ID. Please start a new case.")
    if not request.organism_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active organism. Please start a new case.")
    
    model_name = request.model_name or config.API_MODEL_NAME
    use_azure = request.model_provider.lower() == 'azure' if request.model_provider else None
    
    logger.info(f"[CHAT] case_id={request.case_id}, model={model_name}, organism={request.organism_key}")
    
    try:
        # Filter system messages from incoming history
        from microtutor.utils.conversation_utils import filter_system_messages
        clean_history = filter_system_messages([msg.model_dump() for msg in request.history])
        
        context = TutorContext(
            case_id=request.case_id,
            organism=request.organism_key,
            conversation_history=clean_history,
            model_name=model_name,
            use_azure=use_azure,
            session_metadata={"enable_guidelines": request.enable_guidelines or False}
        )
        
        # Log user message asynchronously
        background_service.log_conversation_async(
            case_id=request.case_id,
            role="user",
            content=request.message,
            metadata={"organism": request.organism_key}
        )
        
        # Process message
        response = await tutor_service.process_message(
            message=request.message,
            context=context,
            feedback_enabled=request.feedback_enabled,
            feedback_threshold=request.feedback_threshold
        )
        
        # Log assistant response asynchronously
        background_service.log_conversation_async(
            case_id=request.case_id,
            role="assistant",
            content=response.content,
            metadata={"tools_used": response.tools_used, "organism": request.organism_key}
        )
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"[CHAT] Completed in {processing_time:.2f}ms for case_id={request.case_id}")
        
        return ChatResponse(
            response=response.content,
            history=[{"role": msg["role"], "content": msg["content"]} for msg in context.conversation_history],
            tools_used=response.tools_used,
            metadata={
                "processing_time_ms": processing_time,
                "case_id": request.case_id,
                "organism": request.organism_key
            },
            feedback_examples=response.feedback_examples or []
        )
        
    except ValueError as e:
        logger.error(f"[CHAT] ValueError: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"[CHAT] Error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process message")


@router.post(
    "/feedback",
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Submit feedback for a tutor response",
    description="Submit rating and optional feedback for a specific tutor message"
)
async def submit_feedback(
    request: FeedbackRequest,
    background_service: BackgroundTaskService = Depends(get_background_service)
) -> dict:
    """Submit feedback for a specific tutor response."""
    logger.info(f"[FEEDBACK] case_id={request.case_id}, rating={request.rating}, organism={request.organism}")
    
    try:
        background_service.log_feedback_async(
            case_id=request.case_id or "unknown",
            rating=request.rating,
            message=request.message,
            feedback_text=request.feedback_text or "",
            replacement_text=request.replacement_text or "",
            organism=request.organism or ""
        )
        return {"status": "success", "message": "Feedback received"}
        
    except Exception as e:
        logger.error(f"[FEEDBACK] Error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to submit feedback")


@router.post(
    "/case_feedback",
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Submit overall case feedback",
    description="Submit ratings and comments for the entire case experience"
)
async def submit_case_feedback(
    request: CaseFeedbackRequest,
    background_service: BackgroundTaskService = Depends(get_background_service)
) -> dict:
    """Submit overall feedback for a completed case."""
    logger.info(f"[CASE_FEEDBACK] case_id={request.case_id}, organism={request.organism}, ratings=({request.detail}, {request.helpfulness}, {request.accuracy})")
    
    try:
        background_service.log_case_feedback_async(
            case_id=request.case_id,
            detail_rating=request.detail,
            helpfulness_rating=request.helpfulness,
            accuracy_rating=request.accuracy,
            comments=request.comments or "",
            organism=request.organism or ""
        )
        return {"status": "success", "message": "Case feedback received"}
        
    except Exception as e:
        logger.error(f"[CASE_FEEDBACK] Error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to submit case feedback")


@router.get(
    "/organisms",
    summary="Get available organisms",
    description="Get list of organisms with pre-generated cases"
)
async def get_available_organisms() -> dict:
    """Get list of organisms that have pre-generated cases available."""
    try:
        from microtutor.services.case import CaseGeneratorRAGAgent
        
        case_generator = CaseGeneratorRAGAgent()
        cached_organisms = case_generator.get_cached_organisms()
        hpi_organisms = case_generator.get_hpi_organisms()
        
        logger.info(f"[ORGANISMS] Found {len(cached_organisms)} cached organisms")
        
        return {
            "status": "success",
            "organisms": cached_organisms,
            "hpi_organisms": hpi_organisms,
            "count": len(cached_organisms)
        }
        
    except Exception as e:
        logger.error(f"[ORGANISMS] Error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve organisms")
