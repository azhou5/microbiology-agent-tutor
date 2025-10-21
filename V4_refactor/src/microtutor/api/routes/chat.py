"""Chat-related API endpoints."""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from microtutor.models.requests import StartCaseRequest, ChatRequest, FeedbackRequest, CaseFeedbackRequest
from microtutor.models.responses import StartCaseResponse, ChatResponse, ErrorResponse
from microtutor.models.domain import TutorContext
from microtutor.models.database import ConversationLog
from microtutor.services.tutor_service_v2 import TutorService
from microtutor.services.background_service import BackgroundTaskService
from microtutor.core.streaming_llm import get_streaming_tutor_service, StreamingChunk
from microtutor.api.dependencies import get_tutor_service, get_db, get_background_service_dependency
from microtutor.core.logging_config import get_logger, log_conversation_turn
from microtutor.core.config_helper import config

logger = logging.getLogger(__name__)
router = APIRouter()

# Get the MicroTutor logger for detailed logging
mt_logger = get_logger()


def log_conversation_async(
    background_service: BackgroundTaskService, 
    case_id: str, 
    role: str, 
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Log a conversation message asynchronously.
    
    Args:
        background_service: Background task service
        case_id: Unique case identifier
        role: Message role ('user', 'assistant', 'system')
        content: Message content
        metadata: Optional metadata to include
    """
    background_service.log_conversation_async(
        case_id=case_id,
        role=role,
        content=content,
        metadata=metadata
    )


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
    background_service: BackgroundTaskService = Depends(get_background_service_dependency)
) -> StartCaseResponse:
    """Start a new case with the selected organism.
    
    - **organism**: The microorganism to study (e.g., "staphylococcus aureus")
    - **case_id**: Client-generated unique case ID
    - **model_name**: Optional LLM model to use (defaults to o3-mini)
    """
    logger.info(f"[START_CASE] organism={request.organism}, case_id={request.case_id}")
    
    # Log system and model for start case
    model_name = request.model_name or getattr(config, 'API_MODEL_NAME', 'o4-mini-2025-04-16')
    use_azure = getattr(config, 'USE_AZURE_OPENAI', True)
    system = 'AZURE' if use_azure else 'PERSONAL'
    
    print(f"🚀 [BACKEND] Starting New Case")
    print(f"🔧 [BACKEND] System: {system}")
    print(f"🤖 [BACKEND] Model: {model_name}")
    print(f"🦠 [BACKEND] Organism: {request.organism}")
    print(f"📝 [BACKEND] Case ID: {request.case_id}")
    
    try:
        # Call tutor service
        response = await tutor_service.start_case(
            organism=request.organism,
            case_id=request.case_id,
            model_name=request.model_name,
            use_hpi_only=request.use_hpi_only
        )
        
        # Log asynchronously to avoid blocking the response
        log_conversation_async(
            background_service, 
            request.case_id, 
            "system", 
            f"Case started: {request.organism}",
            metadata={"organism": request.organism, "model": request.model_name}
        )
        log_conversation_async(
            background_service, 
            request.case_id, 
            "assistant", 
            response.content,
            metadata={"tools_used": response.tools_used}
        )
        
        logger.info(f"[START_CASE] Success for case_id={request.case_id}")
        
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
    background_service: BackgroundTaskService = Depends(get_background_service_dependency)
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
        
        # Determine if we should use Azure based on model provider
        use_azure = None
        if request.model_provider:
            use_azure = request.model_provider.lower() == 'azure'
        
        # Determine final system and model
        final_model = request.model_name or default_model
        final_system = 'AZURE' if use_azure else 'PERSONAL'
        
        # Log system and model being used
        print(f"🔧 [BACKEND] Processing Chat Request")
        print(f"🤖 [BACKEND] System: {final_system}")
        print(f"🧠 [BACKEND] Model: {final_model}")
        print(f"📝 [BACKEND] Case ID: {request.case_id}")
        print(f"🦠 [BACKEND] Organism: {request.organism_key}")
        print(f"🎯 [BACKEND] Feedback Enabled: {request.feedback_enabled}")
        print(f"📊 [BACKEND] Threshold: {request.feedback_threshold}")
        
        context = TutorContext(
            case_id=request.case_id,
            organism=request.organism_key,
            conversation_history=[msg.model_dump() for msg in request.history],
            model_name=final_model,
            use_azure=use_azure
        )
        
        # Log user message asynchronously
        log_conversation_async(
            background_service,
            request.case_id,
            "user",
            request.message,
            metadata={"organism": request.organism_key}
        )
        
        # Process message with feedback settings
        response = await tutor_service.process_message(
            message=request.message,
            context=context,
            feedback_enabled=request.feedback_enabled,
            feedback_threshold=request.feedback_threshold
        )
        
        # Log assistant response asynchronously
        log_conversation_async(
            background_service,
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
        
        # Collect metrics asynchronously
        background_service.collect_metrics_async(
            event_type="chat_completion",
            case_id=request.case_id,
            processing_time_ms=processing_time,
            model=context.model_name,
            metadata={
                "organism": request.organism_key,
                "tools_used": response.tools_used,
                "feedback_enabled": request.feedback_enabled
            }
        )
        
        # Debug feedback examples
        feedback_examples = getattr(response, 'feedback_examples', [])
        logger.info(f"[CHAT] Feedback examples count: {len(feedback_examples)}")
        logger.info(f"[CHAT] Response type: {type(response)}")
        logger.info(f"[CHAT] Response attributes: {dir(response)}")
        
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
            },
            feedback_examples=feedback_examples
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
    background_service: BackgroundTaskService = Depends(get_background_service_dependency)
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
        # Log feedback asynchronously
        background_service.log_feedback_async(
            case_id=request.case_id or "unknown",
            rating=request.rating,
            message=request.message,
            feedback_text=request.feedback_text or "",
            replacement_text=request.replacement_text or "",
            organism=getattr(request, 'organism', '')
        )
        
        logger.info(f"[FEEDBACK] Successfully queued for case_id={request.case_id}")
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
    background_service: BackgroundTaskService = Depends(get_background_service_dependency)
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
        # Log case feedback asynchronously
        background_service.log_case_feedback_async(
            case_id=request.case_id,
            detail_rating=request.detail,
            helpfulness_rating=request.helpfulness,
            accuracy_rating=request.accuracy,
            comments=request.comments or "",
            organism=getattr(request, 'organism', '')
        )
        
        logger.info(f"[CASE_FEEDBACK] Successfully queued for case_id={request.case_id}")
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


@router.post(
    "/start_case/stream",
    summary="Start a new case with streaming response",
    description="Initialize a new case with streaming response for faster perceived performance"
)
async def start_case_stream(
    request: StartCaseRequest,
    tutor_service: TutorService = Depends(get_tutor_service),
    background_service: BackgroundTaskService = Depends(get_background_service_dependency)
) -> StreamingResponse:
    """Start a new case with streaming response.
    
    This endpoint provides the same functionality as /start_case but streams
    the response as it's generated, providing faster perceived performance.
    """
    logger.info(f"[START_CASE_STREAM] organism={request.organism}, case_id={request.case_id}")
    
    try:
        # Get streaming tutor service
        streaming_service = get_streaming_tutor_service(tutor_service)
        
        async def generate_stream():
            """Generate streaming response."""
            full_response = ""
            
            async for chunk in streaming_service.stream_start_case(
                organism=request.organism,
                case_id=request.case_id,
                model_name=request.model_name,
                use_hpi_only=request.use_hpi_only
            ):
                # Log chunk asynchronously
                if chunk.content:
                    log_conversation_async(
                        background_service,
                        request.case_id,
                        "assistant_chunk",
                        chunk.content,
                        metadata={
                            "chunk_index": chunk.metadata.get("chunk_index", 0),
                            "is_final": chunk.is_final,
                            "organism": request.organism
                        }
                    )
                
                # Accumulate full response
                full_response += chunk.content
                
                # Yield chunk as Server-Sent Events
                yield f"data: {chunk.content}\n\n"
                
                if chunk.is_final:
                    # Log complete response asynchronously
                    log_conversation_async(
                        background_service,
                        request.case_id,
                        "assistant",
                        full_response,
                        metadata={
                            "tools_used": [],
                            "organism": request.organism,
                            "streaming": True
                        }
                    )
                    break
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/plain; charset=utf-8"
            }
        )
        
    except Exception as e:
        logger.error(f"[START_CASE_STREAM] Error: {e}", exc_info=True)
        async def error_stream():
            yield f"data: Error: {str(e)}\n\n"
        return StreamingResponse(error_stream(), media_type="text/plain")


@router.post(
    "/chat/stream",
    summary="Send a chat message with streaming response",
    description="Send a message to the tutor and receive a streaming response"
)
async def chat_stream(
    request: ChatRequest,
    tutor_service: TutorService = Depends(get_tutor_service),
    background_service: BackgroundTaskService = Depends(get_background_service_dependency)
) -> StreamingResponse:
    """Process a chat message with streaming response.
    
    This endpoint provides the same functionality as /chat but streams
    the response as it's generated, providing faster perceived performance.
    """
    start_time = datetime.now()
    logger.info(f"[CHAT_STREAM] case_id={request.case_id}, message_len={len(request.message)}")
    
    # Validate inputs
    if not request.case_id:
        async def error_stream():
            yield "data: Error: No active case ID. Please start a new case.\n\n"
        return StreamingResponse(error_stream(), media_type="text/plain")
    
    if not request.organism_key:
        async def error_stream():
            yield "data: Error: No active organism. Please start a new case.\n\n"
        return StreamingResponse(error_stream(), media_type="text/plain")
    
    try:
        # Create context
        default_model = getattr(config, 'API_MODEL_NAME', 'o4-mini-2025-04-16')
        context = TutorContext(
            case_id=request.case_id,
            organism=request.organism_key,
            conversation_history=[msg.model_dump() for msg in request.history],
            model_name=request.model_name or default_model
        )
        
        # Log user message asynchronously
        log_conversation_async(
            background_service,
            request.case_id,
            "user",
            request.message,
            metadata={"organism": request.organism_key}
        )
        
        # Get streaming tutor service
        streaming_service = get_streaming_tutor_service(tutor_service)
        
        async def generate_stream():
            """Generate streaming response."""
            full_response = ""
            
            async for chunk in streaming_service.stream_process_message(
                message=request.message,
                context=context,
                feedback_enabled=request.feedback_enabled,
                feedback_threshold=request.feedback_threshold
            ):
                # Log chunk asynchronously
                if chunk.content:
                    log_conversation_async(
                        background_service,
                        request.case_id,
                        "assistant_chunk",
                        chunk.content,
                        metadata={
                            "chunk_index": chunk.metadata.get("chunk_index", 0),
                            "is_final": chunk.is_final,
                            "organism": request.organism_key
                        }
                    )
                
                # Accumulate full response
                full_response += chunk.content
                
                # Yield chunk as Server-Sent Events
                yield f"data: {chunk.content}\n\n"
                
                if chunk.is_final:
                    # Log complete response asynchronously
                    processing_time = (datetime.now() - start_time).total_seconds() * 1000
                    
                    log_conversation_async(
                        background_service,
                        request.case_id,
                        "assistant",
                        full_response,
                        metadata={
                            "tools_used": [],
                            "organism": request.organism_key,
                            "streaming": True,
                            "processing_time_ms": processing_time
                        }
                    )
                    
                    # Collect metrics asynchronously
                    background_service.collect_metrics_async(
                        event_type="chat_completion_stream",
                        case_id=request.case_id,
                        processing_time_ms=processing_time,
                        model=context.model_name,
                        metadata={
                            "organism": request.organism_key,
                            "streaming": True
                        }
                    )
                    break
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/plain; charset=utf-8"
            }
        )
        
    except Exception as e:
        logger.error(f"[CHAT_STREAM] Error: {e}", exc_info=True)
        async def error_stream():
            yield f"data: Error: {str(e)}\n\n"
        return StreamingResponse(error_stream(), media_type="text/plain")

