"""
Mock database API endpoints for testing when database connection is not available.

This module provides mock GET endpoints that return sample data
when the real database is not accessible.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import random

from fastapi import APIRouter, HTTPException, status, Query

logger = logging.getLogger(__name__)
router = APIRouter()

# Mock data
MOCK_CASE_FEEDBACK = [
    {
        "id": 1,
        "timestamp": "2024-10-15T10:30:00Z",
        "organism": "staphylococcus aureus",
        "detail_rating": "4",
        "helpfulness_rating": "5",
        "accuracy_rating": "4",
        "comments": "Great case study! Very detailed and helpful for understanding the clinical presentation.",
        "case_id": "case_001"
    },
    {
        "id": 2,
        "timestamp": "2024-10-15T11:15:00Z",
        "organism": "escherichia coli",
        "detail_rating": "3",
        "helpfulness_rating": "4",
        "accuracy_rating": "3",
        "comments": "Good case but could use more information about treatment options.",
        "case_id": "case_002"
    },
    {
        "id": 3,
        "timestamp": "2024-10-15T12:00:00Z",
        "organism": "streptococcus pneumoniae",
        "detail_rating": "5",
        "helpfulness_rating": "5",
        "accuracy_rating": "5",
        "comments": "Excellent case! Perfect level of detail and very educational.",
        "case_id": "case_003"
    },
    {
        "id": 4,
        "timestamp": "2024-10-15T13:45:00Z",
        "organism": "pseudomonas aeruginosa",
        "detail_rating": "2",
        "helpfulness_rating": "3",
        "accuracy_rating": "2",
        "comments": "Case was too complex for the level indicated. Needs simplification.",
        "case_id": "case_004"
    },
    {
        "id": 5,
        "timestamp": "2024-10-15T14:20:00Z",
        "organism": "staphylococcus aureus",
        "detail_rating": "4",
        "helpfulness_rating": "4",
        "accuracy_rating": "4",
        "comments": "Good case study with clear clinical presentation.",
        "case_id": "case_005"
    }
]

MOCK_FEEDBACK = [
    {
        "id": 1,
        "timestamp": "2024-10-15T09:30:00Z",
        "organism": "staphylococcus aureus",
        "rating": "4",
        "rated_message": "The patient presents with fever, chills, and a painful red lesion on the arm...",
        "feedback_text": "Good explanation of the clinical presentation",
        "replacement_text": "",
        "chat_history": '{"messages": [{"role": "user", "content": "What are the key symptoms?"}, {"role": "assistant", "content": "The patient presents with fever, chills, and a painful red lesion on the arm..."}]}',
        "case_id": "case_001"
    },
    {
        "id": 2,
        "timestamp": "2024-10-15T10:15:00Z",
        "organism": "escherichia coli",
        "rating": "3",
        "rated_message": "Based on the symptoms, this could be a UTI...",
        "feedback_text": "Could be more specific about diagnostic criteria",
        "replacement_text": "Based on the symptoms and urinalysis results showing nitrites and leukocyte esterase, this is consistent with a UTI...",
        "chat_history": '{"messages": [{"role": "user", "content": "What is the likely diagnosis?"}, {"role": "assistant", "content": "Based on the symptoms, this could be a UTI..."}]}',
        "case_id": "case_002"
    }
]

MOCK_STATS = {
    "table_counts": {
        "case_feedback": 5,
        "feedback": 2,
        "cases": 3,
        "conversation_logs": 15
    },
    "organism_distribution": [
        {"organism": "staphylococcus aureus", "count": 2},
        {"organism": "escherichia coli", "count": 1},
        {"organism": "streptococcus pneumoniae", "count": 1},
        {"organism": "pseudomonas aeruginosa", "count": 1}
    ],
    "average_ratings": {
        "detail": 3.6,
        "helpfulness": 4.2,
        "accuracy": 3.6,
        "total_ratings": 5
    }
}


@router.get(
    "/feedback",
    summary="Get feedback data (Mock)",
    description="Retrieve mock feedback entries for testing when database is not available"
)
async def get_feedback_data(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of feedback entries to return"),
    organism: Optional[str] = Query(None, description="Filter by organism")
) -> Dict[str, Any]:
    """Get mock feedback data.
    
    Args:
        limit: Maximum number of feedback entries to return
        organism: Optional organism filter
        
    Returns:
        Dictionary with mock feedback data
    """
    try:
        # Filter by organism if specified
        data = MOCK_FEEDBACK
        if organism:
            data = [item for item in data if item.get("organism", "").lower() == organism.lower()]
        
        # Apply limit
        data = data[:limit]
        
        return {
            "status": "success",
            "data": data,
            "count": len(data),
            "note": "This is mock data - database connection not available"
        }
        
    except Exception as e:
        logger.error(f"Failed to get mock feedback data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve mock feedback data: {str(e)}"
        )


@router.get(
    "/case_feedback",
    summary="Get case feedback data (Mock)",
    description="Retrieve mock case feedback entries for testing when database is not available"
)
async def get_case_feedback_data(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of case feedback entries to return"),
    organism: Optional[str] = Query(None, description="Filter by organism")
) -> Dict[str, Any]:
    """Get mock case feedback data.
    
    Args:
        limit: Maximum number of case feedback entries to return
        organism: Optional organism filter
        
    Returns:
        Dictionary with mock case feedback data
    """
    try:
        # Filter by organism if specified
        data = MOCK_CASE_FEEDBACK
        if organism:
            data = [item for item in data if item.get("organism", "").lower() == organism.lower()]
        
        # Apply limit
        data = data[:limit]
        
        return {
            "status": "success",
            "data": data,
            "count": len(data),
            "note": "This is mock data - database connection not available"
        }
        
    except Exception as e:
        logger.error(f"Failed to get mock case feedback data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve mock case feedback data: {str(e)}"
        )


@router.get(
    "/stats",
    summary="Get database statistics (Mock)",
    description="Get mock database statistics for testing when database is not available"
)
async def get_database_stats() -> Dict[str, Any]:
    """Get mock database statistics.
    
    Returns:
        Dictionary with mock database statistics
    """
    try:
        return {
            "status": "success",
            "data": MOCK_STATS,
            "timestamp": datetime.utcnow().isoformat(),
            "note": "This is mock data - database connection not available"
        }
        
    except Exception as e:
        logger.error(f"Failed to get mock database statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve mock database statistics: {str(e)}"
        )
