"""
Fast chat endpoints using ultra-fast input classification.

This module provides chat endpoints that use fast classification
to route inputs directly to the appropriate response type,
bypassing the slow LLM-based routing.
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
from microtutor.core.fast_classifier import get_fast_classifier, classify_input_fast
# Using simple config flag instead of complex classification config
from microtutor.api.dependencies import get_tutor_service, get_background_service_dependency
from microtutor.core.config_helper import config

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/chat/ultra_fast",
    response_model=ChatResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Ultra-fast chat with instant classification",
    description="Send a message with ultra-fast input classification for instant routing"
)
async def chat_ultra_fast(
    request: ChatRequest,
    tutor_service: TutorService = Depends(get_tutor_service),
    background_service: BackgroundTaskService = Depends(get_background_service_dependency)
) -> ChatResponse:
    """Process a chat message with ultra-fast classification.
    
    This endpoint uses fast classification to instantly determine the response type
    and route the input accordingly, bypassing slow LLM-based routing.
    
    - **message**: The student's question or response
    - **history**: Full conversation history including system messages
    - **organism_key**: Current organism being studied
    - **case_id**: Active case ID
    """
    start_time = datetime.now()
    logger.info(f"[CHAT_ULTRA_FAST] case_id={request.case_id}, message_len={len(request.message)}")
    
    # Validate case_id
    if not request.case_id:
        logger.warning("[CHAT_ULTRA_FAST] Missing case_id")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active case ID. Please start a new case."
        )
    
    # Validate organism_key
    if not request.organism_key:
        logger.warning(f"[CHAT_ULTRA_FAST] Missing organism_key for case_id={request.case_id}")
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
        
        # Get ML classification for suggestions/logging (if enabled)
        classification_result = None
        classification_time = 0.0
        
        if config.FAST_CLASSIFICATION_ENABLED:
            classification_start = datetime.now()
            classification_result = classify_input_fast(request.message)
            classification_time = (datetime.now() - classification_start).total_seconds() * 1000
            
            logger.info(f"[CHAT_ULTRA_FAST] ML classified as '{classification_result.classification}' "
                       f"in {classification_time:.2f}ms (confidence: {classification_result.confidence:.3f})")
        
        # Use LLM for actual routing (as requested - ML is OFF for routing)
        logger.info("[CHAT_ULTRA_FAST] Using LLM for tool routing (ML disabled for routing)")
        response = await tutor_service.process_message(
            message=request.message,
            context=context,
            feedback_enabled=request.feedback_enabled,
            feedback_threshold=request.feedback_threshold
        )
        
        response_content = response.content
        tools_used = response.tools_used
        
        # Calculate total processing time
        total_processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # Log conversation asynchronously
        from microtutor.api.routes.chat import log_conversation_async
        
        log_conversation_async(
            background_service,
            request.case_id,
            "user",
            request.message,
            metadata={
                "organism": request.organism_key,
                "fast_classification": classification_result.classification,
                "classification_confidence": classification_result.confidence,
                "classification_time_ms": classification_time
            }
        )
        
        log_conversation_async(
            background_service,
            request.case_id,
            "assistant",
            response_content,
            metadata={
                "tools_used": tools_used,
                "organism": request.organism_key,
                "fast_classification": classification_result.classification,
                "total_processing_time_ms": total_processing_time
            }
        )
        
        # Collect metrics asynchronously
        background_service.collect_metrics_async(
            event_type="ultra_fast_chat_completion",
            case_id=request.case_id,
            processing_time_ms=total_processing_time,
            model=context.model_name,
            metadata={
                "organism": request.organism_key,
                "tools_used": tools_used,
                "fast_classification": classification_result.classification,
                "classification_confidence": classification_result.confidence,
                "classification_time_ms": classification_time,
                "classification_method": classification_result.method
            }
        )
        
        logger.info(f"[CHAT_ULTRA_FAST] Completed in {total_processing_time:.2f}ms "
                   f"(classification: {classification_time:.2f}ms)")
        
        return ChatResponse(
            response=response_content,
            history=[
                {"role": msg["role"], "content": msg["content"]}
                for msg in context.conversation_history
            ],
            tools_used=tools_used,
            metadata={
                "processing_time_ms": total_processing_time,
                "case_id": request.case_id,
                "organism": request.organism_key,
                "fast_classification": classification_result.classification,
                "classification_confidence": classification_result.confidence,
                "classification_time_ms": classification_time,
                "classification_method": classification_result.method,
                "ultra_fast": True
            },
            feedback_examples=[]  # Could be populated if needed
        )
        
    except ValueError as e:
        logger.error(f"[CHAT_ULTRA_FAST] ValueError: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"[CHAT_ULTRA_FAST] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process message"
        )


async def _get_direct_tutor_response(
    message: str, 
    context: TutorContext, 
    tutor_service: TutorService
) -> str:
    """Get direct tutor response without tool routing.
    
    Args:
        message: User message
        context: Tutor context
        tutor_service: Tutor service
        
    Returns:
        Tutor response content
    """
    try:
        response = await tutor_service.process_message(
            message=message,
            context=context,
            feedback_enabled=True,
            feedback_threshold=0.7
        )
        return response.content
    except Exception as e:
        logger.error(f"Direct tutor response failed: {e}")
        return "I apologize, but I'm having trouble processing your request right now. Please try again."


@router.get(
    "/fast_classifier/status",
    summary="Get fast classifier status",
    description="Get status and performance metrics of the fast classifier"
)
async def get_fast_classifier_status() -> Dict[str, Any]:
    """Get fast classifier status and performance metrics.
    
    Returns:
        Dictionary with classifier status information
    """
    try:
        classifier = get_fast_classifier()
        
        # Test classifier performance
        test_inputs = [
            "What is Staphylococcus aureus?",
            "The patient is feeling nauseous",
            "Why do you think this happened?",
            "Can you give me a hint?"
        ]
        
        test_results = []
        total_time = 0
        
        for test_input in test_inputs:
            start_time = datetime.now()
            result = classifier.classify(test_input)
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            test_results.append({
                "input": test_input,
                "classification": result.classification,
                "confidence": result.confidence,
                "processing_time_ms": processing_time,
                "method": result.method
            })
            total_time += processing_time
        
        avg_processing_time = total_time / len(test_inputs) if test_inputs else 0
        
        return {
            "status": "success",
            "data": {
                "classifier_type": "hybrid",
                "avg_processing_time_ms": avg_processing_time,
                "test_results": test_results,
                "features": {
                    "embedding": True,
                    "ml": True,
                    "hybrid": True
                }
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get classifier status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve classifier status"
        )


@router.post(
    "/fast_classifier/test",
    summary="Test fast classifier",
    description="Test the fast classifier with custom input"
)
async def test_fast_classifier(
    input_text: str,
    case_id: Optional[str] = None,
    organism: Optional[str] = None
) -> Dict[str, Any]:
    """Test the fast classifier with custom input.
    
    Args:
        input_text: Text to classify
        case_id: Optional case ID for context
        organism: Optional organism for context
        
    Returns:
        Classification result
    """
    try:
        start_time = datetime.now()
        result = classify_input_fast(input_text)
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return {
            "status": "success",
            "data": {
                "input_text": input_text,
                "classification": result.classification,
                "confidence": result.confidence,
                "method": result.method,
                "processing_time_ms": processing_time,
                "features": result.features,
                "case_id": case_id,
                "organism": organism
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Classifier test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test classifier"
        )
