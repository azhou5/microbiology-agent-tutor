"""
Monitoring and analytics API endpoints.

This module provides endpoints for monitoring system performance,
costs, and other metrics.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

try:
    from fastapi import APIRouter, Depends, HTTPException, status
except ImportError:
    # Fallback for development
    from typing import Any
    class APIRouter:
        def __init__(self, **kwargs): pass
        def get(self, *args, **kwargs): return lambda x: x
        def post(self, *args, **kwargs): return lambda x: x
    def Depends(x): return x
    class HTTPException(Exception): pass
    class status:
        HTTP_500_INTERNAL_SERVER_ERROR = 500

from microtutor.services.infrastructure.cost import get_cost_service, CostService
from microtutor.services.infrastructure.background import get_background_service, BackgroundTaskService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/costs/summary",
    summary="Get cost summary",
    description="Get summary of LLM usage costs and statistics"
)
async def get_cost_summary(
    cost_service: CostService = Depends(get_cost_service)
) -> Dict[str, Any]:
    """Get cost summary statistics.
    
    Returns:
        Dictionary with cost summary including total cost, request count, etc.
    """
    try:
        summary = cost_service.get_cost_summary()
        return {
            "status": "success",
            "data": summary,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get cost summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cost summary"
        )


@router.get(
    "/costs/recent",
    summary="Get recent costs",
    description="Get recent cost information for individual requests"
)
async def get_recent_costs(
    limit: int = 100,
    cost_service: CostService = Depends(get_cost_service)
) -> Dict[str, Any]:
    """Get recent cost information.
    
    Args:
        limit: Maximum number of recent costs to return (default: 100)
        
    Returns:
        Dictionary with recent cost data
    """
    try:
        recent_costs = cost_service.get_recent_costs(limit=limit)
        return {
            "status": "success",
            "data": recent_costs,
            "count": len(recent_costs),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get recent costs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve recent costs"
        )


@router.post(
    "/costs/reset",
    summary="Reset cost tracking",
    description="Reset all cost tracking data (use with caution)"
)
async def reset_costs(
    cost_service: CostService = Depends(get_cost_service)
) -> Dict[str, str]:
    """Reset all cost tracking data.
    
    Returns:
        Success message
    """
    try:
        cost_service.reset_costs()
        logger.info("Cost tracking reset by API call")
        return {
            "status": "success",
            "message": "Cost tracking reset successfully"
        }
    except Exception as e:
        logger.error(f"Failed to reset costs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset cost tracking"
        )


@router.get(
    "/costs/export",
    summary="Export cost data",
    description="Export cost history to JSON file"
)
async def export_costs(
    filename: Optional[str] = None,
    cost_service: CostService = Depends(get_cost_service)
) -> Dict[str, str]:
    """Export cost data to JSON file.
    
    Args:
        filename: Optional filename (defaults to timestamp-based name)
        
    Returns:
        Success message with file path
    """
    try:
        if filename is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"microtutor_costs_{timestamp}.json"
        
        # Ensure filename has .json extension
        if not filename.endswith('.json'):
            filename += '.json'
        
        # Export to data directory
        from pathlib import Path
        data_dir = Path(__file__).parent.parent.parent / "data"
        data_dir.mkdir(exist_ok=True)
        
        filepath = data_dir / filename
        cost_service.export_costs(str(filepath))
        
        return {
            "status": "success",
            "message": f"Cost data exported to {filepath}",
            "filepath": str(filepath)
        }
    except Exception as e:
        logger.error(f"Failed to export costs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export cost data"
        )


@router.get(
    "/background/status",
    summary="Get background service status",
    description="Get status of background task processing service"
)
async def get_background_status(
    background_service: BackgroundTaskService = Depends(get_background_service)
) -> Dict[str, Any]:
    """Get background service status.
    
    Returns:
        Dictionary with background service status information
    """
    try:
        # Get queue size (approximate)
        queue_size = background_service.task_queue.qsize()
        
        return {
            "status": "success",
            "data": {
                "running": background_service.running,
                "max_workers": background_service.max_workers,
                "queue_size": queue_size,
                "queue_max_size": background_service.queue_size,
                "active_workers": len(background_service.workers)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get background status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve background service status"
        )


@router.get(
    "/health/detailed",
    summary="Detailed health check",
    description="Get detailed health information including all services"
)
async def detailed_health_check(
    cost_service: CostService = Depends(get_cost_service),
    background_service: BackgroundTaskService = Depends(get_background_service)
) -> Dict[str, Any]:
    """Get detailed health information.
    
    Returns:
        Dictionary with detailed health status
    """
    try:
        # Get cost summary
        cost_summary = cost_service.get_cost_summary()
        
        # Get background service status
        queue_size = background_service.task_queue.qsize()
        
        # Check database connectivity (if configured)
        db_status = "unknown"
        try:
            from microtutor.api.dependencies import get_db
            # This is a simple check - in production you might want more sophisticated checks
            db_status = "available"
        except Exception:
            db_status = "unavailable"
        
        return {
            "status": "healthy",
            "service": "microtutor",
            "version": "4.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "background_service": {
                    "status": "running" if background_service.running else "stopped",
                    "queue_size": queue_size,
                    "max_workers": background_service.max_workers
                },
                "cost_service": {
                    "status": "active",
                    "total_cost_usd": cost_summary.get("total_cost_usd", 0.0),
                    "request_count": cost_summary.get("request_count", 0)
                },
                "database": {
                    "status": db_status
                }
            }
        }
    except Exception as e:
        logger.error(f"Failed to get detailed health status: {e}")
        return {
            "status": "unhealthy",
            "service": "microtutor",
            "version": "4.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }
