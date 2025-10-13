"""Chat-related API endpoints."""

import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from microtutor.models.requests import StartCaseRequest, ChatRequest, FeedbackRequest, CaseFeedbackRequest
from microtutor.models.responses import StartCaseResponse, ChatResponse, ErrorResponse
from microtutor.models.domain import TutorContext
from microtutor.models.database import ConversationLog
from microtutor.services.tutor_service import TutorService
from microtutor.api.dependencies import get_tutor_service, get_db
from microtutor.core.logging_config import get_logger, log_conversation_turn
from microtutor.core.config_helper import config

logger = logging.getLogger(__name__)
router = APIRouter()

# Get the MicroTutor logger for detailed logging
mt_logger = get_logger()


def log_conversation(db: Session, case_id: str, role: str, content: str) -> None:
    """Log a conversation message to the database.
    
    Args:
        db: Database session
        case_id: Unique case identifier
        role: Message role ('user', 'assistant', 'system')
        content: Message content
    """
    if db is None:
        return  # Database not configured
    
    try:
        log_entry = ConversationLog(
            case_id=case_id,
            timestamp=datetime.utcnow(),
            role=role,
            content=content
        )
        db.add(log_entry)
        db.commit()
        logger.debug(f"Logged {role} message for case {case_id}")
    except Exception as e:
        logger.error(f"Failed to log conversation: {e}")
        db.rollback()


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
    db=Depends(get_db)
) -> StartCaseResponse:
    """Start a new case with the selected organism.
    
    - **organism**: The microorganism to study (e.g., "staphylococcus aureus")
    - **case_id**: Client-generated unique case ID
    - **model_name**: Optional LLM model to use (defaults to o3-mini)
    """
    logger.info(f"[START_CASE] organism={request.organism}, case_id={request.case_id}")
    
    try:
        # Call tutor service
        response = await tutor_service.start_case(
            organism=request.organism,
            case_id=request.case_id,
            model_name=request.model_name,
            use_hpi_only=request.use_hpi_only
        )
        
        # Log to database if available
        log_conversation(db, request.case_id, "system", f"Case started: {request.organism}")
        log_conversation(db, request.case_id, "assistant", response.content)
        
        # Log to structured files
        mt_logger.log_conversation_turn(
            request.case_id,
            "system",
            f"Case started: {request.organism}",
            metadata={"organism": request.organism, "model": request.model_name}
        )
        mt_logger.log_conversation_turn(
            request.case_id,
            "assistant",
            response.content,
            metadata={"tools_used": response.tools_used}
        )
        
        logger.info(f"[START_CASE] Success for case_id={request.case_id}")
        
        return StartCaseResponse(
            initial_message=response.content,
            history=[
                {"role": "system", "content": "System initialized"},
                {"role": "assistant", "content": response.content}
            ],
            case_id=request.case_id,
            organism=request.organism
        )
        
    except ValueError as e:
        logger.error(f"[START_CASE] ValueError: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"[START_CASE] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start case"
        )


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
    db=Depends(get_db)
) -> ChatResponse:
    """Process a chat message from the student.
    
    - **message**: The student's question or response
    - **history**: Full conversation history including system messages
    - **organism_key**: Current organism being studied
    - **case_id**: Active case ID
    """
    start_time = datetime.now()
    logger.info(f"[CHAT] case_id={request.case_id}, message_len={len(request.message)}")
    
    # Validate case_id
    if not request.case_id:
        logger.warning("[CHAT] Missing case_id")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active case ID. Please start a new case."
        )
    
    # Validate organism_key
    if not request.organism_key:
        logger.warning(f"[CHAT] Missing organism_key for case_id={request.case_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organism. Please start a new case."
        )
    
    try:
        # Create context from request
        # Get model name from request or config (with safe fallback)
        default_model = getattr(config, 'API_MODEL_NAME', 'o4-mini-2025-04-16')
        context = TutorContext(
            case_id=request.case_id,
            organism=request.organism_key,
            conversation_history=[msg.dict() for msg in request.history],
            model_name=request.model_name or default_model
        )
        
        # Log user message to database
        log_conversation(db, request.case_id, "user", request.message)
        
        # Log user message to structured files
        mt_logger.log_conversation_turn(
            request.case_id,
            "user",
            request.message,
            metadata={"organism": request.organism_key}
        )
        
        # Process message
        response = await tutor_service.process_message(
            message=request.message,
            context=context
        )
        
        # Log assistant response to database
        log_conversation(db, request.case_id, "assistant", response.content)
        
        # Log assistant response to structured files
        mt_logger.log_conversation_turn(
            request.case_id,
            "assistant",
            response.content,
            metadata={
                "tools_used": response.tools_used,
                "organism": request.organism_key
            }
        )
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"[CHAT] Completed in {processing_time:.2f}ms for case_id={request.case_id}")
        
        return ChatResponse(
            response=response.content,
            history=[
                {"role": msg["role"], "content": msg["content"]}
                for msg in context.conversation_history
            ],
            tools_used=response.tools_used,
            metadata={
                "processing_time_ms": processing_time,
                "case_id": request.case_id,
                "organism": request.organism_key
            }
        )
        
    except ValueError as e:
        logger.error(f"[CHAT] ValueError: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"[CHAT] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process message"
        )


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
    db=Depends(get_db)
) -> dict:
    """Submit feedback for a specific tutor response.
    
    - **rating**: Rating from 1-4
    - **message**: The assistant message being rated
    - **feedback_text**: Optional detailed feedback
    - **replacement_text**: Optional suggested replacement
    - **case_id**: Associated case ID
    """
    logger.info(f"[FEEDBACK] case_id={request.case_id}, rating={request.rating}")
    
    try:
        # Log feedback to database if available
        if db is not None:
            feedback_log = ConversationLog(
                case_id=request.case_id or "unknown",
                timestamp=datetime.utcnow(),
                role="feedback",
                content=f"Rating: {request.rating}, Feedback: {request.feedback_text}"
            )
            db.add(feedback_log)
            db.commit()
        
        # Log to structured files
        mt_logger.log_feedback(
            case_id=request.case_id or "unknown",
            rating=request.rating,
            message=request.message,
            feedback_text=request.feedback_text or "",
            replacement_text=request.replacement_text or "",
            organism=getattr(request, 'organism', '')
        )
        
        logger.info(f"[FEEDBACK] Successfully logged for case_id={request.case_id}")
        return {"status": "success", "message": "Feedback received"}
        
    except Exception as e:
        logger.error(f"[FEEDBACK] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit feedback"
        )


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
    db=Depends(get_db)
) -> dict:
    """Submit overall feedback for a completed case.
    
    - **detail**: Rating for level of detail (1-4)
    - **helpfulness**: Rating for educational value (1-4)
    - **accuracy**: Rating for medical accuracy (1-4)
    - **comments**: Optional additional comments
    - **case_id**: Case ID for this feedback
    """
    logger.info(
        f"[CASE_FEEDBACK] case_id={request.case_id}, "
        f"detail={request.detail}, helpfulness={request.helpfulness}, accuracy={request.accuracy}"
    )
    
    try:
        # Log case feedback to database if available
        if db is not None:
            feedback_log = ConversationLog(
                case_id=request.case_id,
                timestamp=datetime.utcnow(),
                role="case_feedback",
                content=(
                    f"Detail: {request.detail}, Helpfulness: {request.helpfulness}, "
                    f"Accuracy: {request.accuracy}, Comments: {request.comments}"
                )
            )
            db.add(feedback_log)
            db.commit()
        
        # Log to structured files
        mt_logger.log_case_feedback(
            case_id=request.case_id,
            detail=request.detail,
            helpfulness=request.helpfulness,
            accuracy=request.accuracy,
            comments=request.comments or "",
            organism=getattr(request, 'organism', '')
        )
        
        logger.info(f"[CASE_FEEDBACK] Successfully logged for case_id={request.case_id}")
        return {"status": "success", "message": "Case feedback received"}
        
    except Exception as e:
        logger.error(f"[CASE_FEEDBACK] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit case feedback"
        )


@router.get(
    "/organisms",
    summary="Get available organisms",
    description="Get list of organisms with pre-generated cases"
)
async def get_available_organisms() -> dict:
    """Get list of organisms that have pre-generated cases available.
    
    Returns:
        Dictionary with organisms list and additional metadata
    """
    logger.info("[ORGANISMS] Fetching available organisms")
    
    try:
        from microtutor.agents.case_generator_rag import CaseGeneratorRAGAgent
        
        case_generator = CaseGeneratorRAGAgent()
        cached_organisms = case_generator.get_cached_organisms()
        hpi_organisms = case_generator.get_hpi_organisms()
        
        logger.info(f"[ORGANISMS] Found {len(cached_organisms)} cached organisms")
        
        return {
            "status": "success",
            "organisms": cached_organisms,
            "hpi_organisms": hpi_organisms,
            "count": len(cached_organisms),
            "message": "Available organisms retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"[ORGANISMS] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve organisms"
        )

