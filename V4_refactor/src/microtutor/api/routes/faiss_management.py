"""
FAISS index management API endpoints.

Provides endpoints for managing automatic FAISS index generation and updates.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel

# Try to import feedback modules (optional)
try:
    from microtutor.feedback.auto_faiss_generator import get_auto_faiss_generator
    from microtutor.feedback.database_feedback_loader import DatabaseFeedbackConfig
    FEEDBACK_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Feedback modules not available: {e}")
    FEEDBACK_AVAILABLE = False
    get_auto_faiss_generator = None
    DatabaseFeedbackConfig = None

from microtutor.api.dependencies import get_db
from microtutor.services.background_service import get_background_service, BackgroundTaskService

logger = logging.getLogger(__name__)

router = APIRouter()


class FAISSUpdateRequest(BaseModel):
    """Request model for FAISS index update."""
    force_update: bool = False
    min_rating: Optional[int] = None
    max_entries: Optional[int] = None
    include_case_feedback: bool = True
    include_regular_feedback: bool = True
    filter_by_organism: Optional[str] = None
    days_back: Optional[int] = None


class FAISSStatusResponse(BaseModel):
    """Response model for FAISS index status."""
    last_update: Optional[str]
    total_entries: int
    regular_feedback_count: int
    case_feedback_count: int
    min_rating: int
    max_rating: int
    should_update: bool
    index_files_exist: Dict[str, bool]


@router.get(
    "/status",
    response_model=FAISSStatusResponse,
    summary="Get FAISS index status",
    description="Get current status of automatic FAISS index generation"
)
async def get_faiss_status() -> FAISSStatusResponse:
    """Get current FAISS index status."""
    if not FEEDBACK_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feedback system not available"
        )
    
    try:
        generator = get_auto_faiss_generator()
        status_data = generator.get_status()
        
        return FAISSStatusResponse(**status_data)
        
    except Exception as e:
        logger.error(f"Failed to get FAISS status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get FAISS status"
        )


@router.post(
    "/update",
    summary="Update FAISS indices",
    description="Manually trigger FAISS index update from database feedback"
)
async def update_faiss_indices(
    request: FAISSUpdateRequest,
    background_service: BackgroundTaskService = Depends(get_background_service)
) -> Dict[str, Any]:
    """Update FAISS indices from database feedback."""
    try:
        # Queue the update task
        success = background_service.update_faiss_indices_async(
            force_update=request.force_update
        )
        
        if success:
            return {
                "status": "success",
                "message": "FAISS index update queued successfully",
                "force_update": request.force_update
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to queue FAISS index update"
            )
            
    except Exception as e:
        logger.error(f"Failed to update FAISS indices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update FAISS indices"
        )


@router.post(
    "/generate",
    summary="Generate FAISS indices immediately",
    description="Generate FAISS indices immediately (synchronous operation)"
)
async def generate_faiss_indices(
    request: FAISSUpdateRequest,
    db = Depends(get_db)
) -> Dict[str, Any]:
    """Generate FAISS indices immediately."""
    if not FEEDBACK_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feedback system not available"
        )
    
    try:
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )
        
        generator = get_auto_faiss_generator()
        
        # Create config from request
        config = DatabaseFeedbackConfig(
            min_rating=request.min_rating or 1,
            max_entries=request.max_entries,
            include_case_feedback=request.include_case_feedback,
            include_regular_feedback=request.include_regular_feedback,
            filter_by_organism=request.filter_by_organism,
            days_back=request.days_back
        )
        
        # Generate indices
        result = generator.generate_indices(
            force_update=request.force_update,
            config=config
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to generate FAISS indices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate FAISS indices: {str(e)}"
        )


@router.get(
    "/stats",
    summary="Get feedback database statistics",
    description="Get statistics about feedback data in the database"
)
async def get_feedback_stats(db = Depends(get_db)) -> Dict[str, Any]:
    """Get feedback database statistics."""
    try:
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )
        
        try:
            from microtutor.feedback.database_feedback_loader import DatabaseFeedbackLoader
        except ImportError:
            class DatabaseFeedbackLoader:
                pass
        
        loader = DatabaseFeedbackLoader(db)
        stats = loader.get_feedback_stats()
        
        return {
            "status": "success",
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get feedback stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get feedback statistics"
        )


@router.post(
    "/cleanup",
    summary="Cleanup old FAISS indices",
    description="Clean up old FAISS index files to save space"
)
async def cleanup_old_indices(
    keep_days: int = Query(7, ge=1, le=30, description="Number of days to keep old indices")
) -> Dict[str, Any]:
    """Clean up old FAISS index files."""
    if not FEEDBACK_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feedback system not available"
        )
    
    try:
        generator = get_auto_faiss_generator()
        generator.cleanup_old_indices(keep_days=keep_days)
        
        return {
            "status": "success",
            "message": f"Cleaned up indices older than {keep_days} days"
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup old indices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup old indices"
        )
