"""
Simple database exploration API endpoints.

This module provides GET endpoints for retrieving and exploring data
stored in the MicroTutor database using the same pattern as existing endpoints.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, status, Query

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/stats",
    summary="Get database statistics",
    description="Get overall statistics about the database content"
)
async def get_database_stats() -> Dict[str, Any]:
    """Get database statistics using the same pattern as organisms endpoint.
    
    Returns:
        Dictionary with database statistics
    """
    try:
        # Use the same pattern as the organisms endpoint
        from microtutor.agents.case_generator_rag import CaseGeneratorRAGAgent
        
        case_generator = CaseGeneratorRAGAgent()
        cached_organisms = case_generator.get_cached_organisms()
        
        return {
            "status": "success",
            "data": {
                "cached_organisms": len(cached_organisms),
                "organisms_list": cached_organisms[:10],  # First 10
                "generated_at": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve database statistics"
        )


@router.get(
    "/cases/simple",
    summary="Get cases summary",
    description="Get a simple summary of cases from the database"
)
async def get_cases_summary() -> Dict[str, Any]:
    """Get a simple summary of cases.
    
    Returns:
        Dictionary with cases summary
    """
    try:
        # This is a placeholder - we'll need to implement actual database queries
        # For now, let's return what we can get from the existing system
        
        from microtutor.agents.case_generator_rag import CaseGeneratorRAGAgent
        
        case_generator = CaseGeneratorRAGAgent()
        cached_organisms = case_generator.get_cached_organisms()
        
        return {
            "status": "success",
            "data": {
                "message": "Database exploration endpoints are working!",
                "available_organisms": len(cached_organisms),
                "organisms": cached_organisms,
                "note": "Full database queries coming soon - this is a proof of concept"
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get cases summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cases summary"
        )
