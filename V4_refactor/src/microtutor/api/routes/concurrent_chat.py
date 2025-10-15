"""
Concurrent chat endpoints for optimized performance.

This module provides chat endpoints that use concurrent processing
for all operations that can run in parallel, while keeping the
main LLM flow sequential.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status

from microtutor.models.requests import StartCaseRequest, ChatRequest
from microtutor.models.responses import StartCaseResponse, ChatResponse, ErrorResponse
from microtutor.models.domain import TutorContext
from microtutor.services.tutor_service import TutorService
from microtutor.services.background_service import BackgroundTaskService
from microtutor.core.concurrent_processing import process_chat_concurrent, process_start_case_concurrent
from microtutor.api.dependencies import get_tutor_service, get_background_service_dependency
from microtutor.core.config_helper import config

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/start_case/concurrent",
    response_model=StartCaseResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Start a new case with concurrent processing",
    description="Initialize a new case with concurrent background operations for optimal performance"
)
async def start_case_concurrent(
    request: StartCaseRequest,
    tutor_service: TutorService = Depends(get_tutor_service),
    background_service: BackgroundTaskService = Depends(get_background_service_dependency)
) -> StartCaseResponse:
    """Start a new case with concurrent background processing.
    
    This endpoint uses concurrent processing for all background operations
    while keeping the main LLM flow sequential.
    
    - **organism**: The microorganism to study (e.g., "staphylococcus aureus")
    - **case_id**: Client-generated unique case ID
    - **model_name**: Optional LLM model to use (defaults to o3-mini)
    """
    logger.info(f"[START_CASE_CONCURRENT] organism={request.organism}, case_id={request.case_id}")
    
    try:
        # Process with concurrent background operations
        results = await process_start_case_concurrent(
            organism=request.organism,
            case_id=request.case_id,
            background_service=background_service,
            tutor_service=tutor_service,
            model_name=request.model_name,
            use_hpi_only=request.use_hpi_only
        )
        
        response = results["llm_response"]
        processing_time = results["processing_time_ms"]
        
        logger.info(f"[START_CASE_CONCURRENT] Success in {processing_time:.2f}ms for case_id={request.case_id}")
        
        # Get the actual system prompt that was used
        from microtutor.core.tutor_prompt import get_system_message_template
        from microtutor.agents.case import get_case
        
        case_description = get_case(request.organism, use_hpi_only=request.use_hpi_only)
        system_message_template = get_system_message_template()
        system_prompt = system_message_template.format(
            case=case_description,
            Examples_of_Good_and_Bad_Responses=""
        )
        
        return StartCaseResponse(
            initial_message=response.content,
            history=[
                {"role": "system", "content": system_prompt},
                {"role": "assistant", "content": response.content}
            ],
            case_id=request.case_id,
            organism=request.organism
        )
        
    except ValueError as e:
        logger.error(f"[START_CASE_CONCURRENT] ValueError: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"[START_CASE_CONCURRENT] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start case"
        )


@router.post(
    "/chat/concurrent",
    response_model=ChatResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Send a chat message with concurrent processing",
    description="Send a message to the tutor with concurrent background operations for optimal performance"
)
async def chat_concurrent(
    request: ChatRequest,
    tutor_service: TutorService = Depends(get_tutor_service),
    background_service: BackgroundTaskService = Depends(get_background_service_dependency)
) -> ChatResponse:
    """Process a chat message with concurrent background processing.
    
    This endpoint uses concurrent processing for all background operations
    while keeping the main LLM flow sequential.
    
    - **message**: The student's question or response
    - **history**: Full conversation history including system messages
    - **organism_key**: Current organism being studied
    - **case_id**: Active case ID
    """
    start_time = datetime.now()
    logger.info(f"[CHAT_CONCURRENT] case_id={request.case_id}, message_len={len(request.message)}")
    
    # Validate case_id
    if not request.case_id:
        logger.warning("[CHAT_CONCURRENT] Missing case_id")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active case ID. Please start a new case."
        )
    
    # Validate organism_key
    if not request.organism_key:
        logger.warning(f"[CHAT_CONCURRENT] Missing organism_key for case_id={request.case_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organism. Please start a new case."
        )
    
    try:
        # Create context from request
        default_model = getattr(config, 'API_MODEL_NAME', 'o4-mini-2025-04-16')
        context = TutorContext(
            case_id=request.case_id,
            organism=request.organism_key,
            conversation_history=[msg.model_dump() for msg in request.history],
            model_name=request.model_name or default_model
        )
        
        # Process with concurrent background operations
        results = await process_chat_concurrent(
            case_id=request.case_id,
            organism=request.organism_key,
            user_message=request.message,
            background_service=background_service,
            tutor_service=tutor_service,
            context=context
        )
        
        response = results["llm_response"]
        processing_time = results["processing_time_ms"]
        
        logger.info(f"[CHAT_CONCURRENT] Completed in {processing_time:.2f}ms for case_id={request.case_id}")
        
        # Debug feedback examples
        feedback_examples = getattr(response, 'feedback_examples', [])
        logger.info(f"[CHAT_CONCURRENT] Feedback examples count: {len(feedback_examples)}")
        
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
                "organism": request.organism_key,
                "concurrent_processing": True
            },
            feedback_examples=feedback_examples
        )
        
    except ValueError as e:
        logger.error(f"[CHAT_CONCURRENT] ValueError: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"[CHAT_CONCURRENT] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process message"
        )


@router.get(
    "/concurrent/status",
    summary="Get concurrent processing status",
    description="Get status of concurrent processing operations"
)
async def get_concurrent_status(
    background_service: BackgroundTaskService = Depends(get_background_service_dependency)
) -> Dict[str, Any]:
    """Get concurrent processing status.
    
    Returns:
        Dictionary with concurrent processing status information
    """
    try:
        from microtutor.core.concurrent_processing import get_concurrent_processor
        processor = get_concurrent_processor()
        
        return {
            "status": "success",
            "data": {
                "active_tasks": len(processor.active_tasks),
                "completed_tasks": len(processor.completed_tasks),
                "background_service_running": background_service.running,
                "background_queue_size": background_service.task_queue.qsize(),
                "max_workers": background_service.max_workers
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get concurrent status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve concurrent processing status"
        )
