"""
Database exploration API endpoints.

This module provides GET endpoints for retrieving and exploring data
stored in the MicroTutor database.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, status, Query
from sqlalchemy import text

# from microtutor.api.dependencies import get_db
from microtutor.models.responses import ErrorResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/cases",
    summary="Get all cases",
    description="Retrieve all cases from the database with optional filtering"
)
async def get_all_cases(
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of cases to return"),
    offset: int = Query(0, ge=0, description="Number of cases to skip"),
    organism: Optional[str] = Query(None, description="Filter by organism"),
    db = None
) -> Dict[str, Any]:
    """Get all cases from the database.
    
    Args:
        limit: Maximum number of cases to return
        offset: Number of cases to skip
        organism: Optional organism filter
        db: Database connection
        
    Returns:
        Dictionary with cases data and metadata
    """
    if db is None:
        db = next(get_db())
    
    try:
        # Build query
        query = """
            SELECT 
                case_id,
                organism,
                created_at,
                updated_at,
                metadata
            FROM cases 
        """
        params = {"limit": limit, "offset": offset}
        
        if organism:
            query += " WHERE organism = :organism"
            params["organism"] = organism
            
        query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        
        result = db.execute(text(query), params)
        cases = result.fetchall()
        
        # Get total count
        count_query = "SELECT COUNT(*) FROM cases"
        if organism:
            count_query += " WHERE organism = :organism"
        
        total_count = db.execute(text(count_query), {"organism": organism} if organism else {}).scalar()
        
        return {
            "status": "success",
            "data": [
                {
                    "case_id": row.case_id,
                    "organism": row.organism,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    "metadata": row.metadata
                }
                for row in cases
            ],
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(cases) < total_count
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get cases: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cases"
        )


@router.get(
    "/cases/{case_id}",
    summary="Get case by ID",
    description="Retrieve a specific case and its conversation history"
)
async def get_case_by_id(
    case_id: str,
    db = None
) -> Dict[str, Any]:
    """Get a specific case by ID.
    
    Args:
        case_id: Unique case identifier
        db: Database connection
        
    Returns:
        Dictionary with case data and conversation history
    """
    if db is None:
        db = next(get_db())
    
    try:
        # Get case info
        case_query = """
            SELECT 
                case_id,
                organism,
                created_at,
                updated_at,
                metadata
            FROM cases 
            WHERE case_id = :case_id
        """
        case_result = db.execute(text(case_query), {"case_id": case_id})
        case_row = case_result.fetchone()
        
        if not case_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found"
            )
        
        # Get conversation history
        conv_query = """
            SELECT 
                role,
                content,
                timestamp,
                metadata
            FROM conversation_logs 
            WHERE case_id = :case_id
            ORDER BY timestamp ASC
        """
        conv_result = db.execute(text(conv_query), {"case_id": case_id})
        conversations = conv_result.fetchall()
        
        return {
            "status": "success",
            "data": {
                "case": {
                    "case_id": case_row.case_id,
                    "organism": case_row.organism,
                    "created_at": case_row.created_at.isoformat() if case_row.created_at else None,
                    "updated_at": case_row.updated_at.isoformat() if case_row.updated_at else None,
                    "metadata": case_row.metadata
                },
                "conversations": [
                    {
                        "role": conv.role,
                        "content": conv.content,
                        "timestamp": conv.timestamp.isoformat() if conv.timestamp else None,
                        "metadata": conv.metadata
                    }
                    for conv in conversations
                ],
                "conversation_count": len(conversations)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve case"
        )


@router.get(
    "/conversations",
    summary="Get recent conversations",
    description="Retrieve recent conversation logs across all cases"
)
async def get_recent_conversations(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of conversations to return"),
    hours: int = Query(24, ge=1, le=168, description="Number of hours to look back"),
    db = None
) -> Dict[str, Any]:
    """Get recent conversation logs.
    
    Args:
        limit: Maximum number of conversations to return
        hours: Number of hours to look back
        db: Database connection
        
    Returns:
        Dictionary with recent conversation data
    """
    if db is None:
        db = next(get_db())
    
    try:
        # Calculate time threshold
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
        
        query = """
            SELECT 
                cl.case_id,
                cl.role,
                cl.content,
                cl.timestamp,
                cl.metadata,
                c.organism
            FROM conversation_logs cl
            LEFT JOIN cases c ON cl.case_id = c.case_id
            WHERE cl.timestamp >= :time_threshold
            ORDER BY cl.timestamp DESC
            LIMIT :limit
        """
        
        result = db.execute(text(query), {
            "time_threshold": time_threshold,
            "limit": limit
        })
        conversations = result.fetchall()
        
        return {
            "status": "success",
            "data": [
                {
                    "case_id": conv.case_id,
                    "organism": conv.organism,
                    "role": conv.role,
                    "content": conv.content[:200] + "..." if len(conv.content) > 200 else conv.content,
                    "timestamp": conv.timestamp.isoformat() if conv.timestamp else None,
                    "metadata": conv.metadata
                }
                for conv in conversations
            ],
            "count": len(conversations),
            "time_range_hours": hours
        }
        
    except Exception as e:
        logger.error(f"Failed to get recent conversations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversations"
        )


@router.get(
    "/stats",
    summary="Get database statistics",
    description="Get overall statistics about the database content"
)
async def get_database_stats(db = None) -> Dict[str, Any]:
    """Get database statistics.
    
    Args:
        db: Database connection
        
    Returns:
        Dictionary with database statistics
    """
    if db is None:
        db = next(get_db())
    
    try:
        # Get table counts
        tables = ["cases", "conversation_logs", "feedback", "cost_logs"]
        stats = {}
        
        for table in tables:
            try:
                count_query = f"SELECT COUNT(*) FROM {table}"
                count = db.execute(text(count_query)).scalar()
                stats[table] = count
            except Exception as e:
                logger.warning(f"Could not count {table}: {e}")
                stats[table] = "error"
        
        # Get organism distribution
        org_query = """
            SELECT organism, COUNT(*) as count
            FROM cases 
            GROUP BY organism 
            ORDER BY count DESC
        """
        org_result = db.execute(text(org_query))
        organism_stats = [
            {"organism": row.organism, "count": row.count}
            for row in org_result.fetchall()
        ]
        
        # Get recent activity
        recent_query = """
            SELECT COUNT(*) as count
            FROM conversation_logs 
            WHERE timestamp >= :recent_time
        """
        recent_time = datetime.utcnow() - timedelta(hours=24)
        recent_count = db.execute(text(recent_query), {"recent_time": recent_time}).scalar()
        
        return {
            "status": "success",
            "data": {
                "table_counts": stats,
                "organism_distribution": organism_stats,
                "recent_activity": {
                    "conversations_last_24h": recent_count
                },
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
    "/tables",
    summary="List database tables",
    description="Get information about all tables in the database"
)
async def list_database_tables(db = None) -> Dict[str, Any]:
    """List all tables in the database.
    
    Args:
        db: Database connection
        
    Returns:
        Dictionary with table information
    """
    if db is None:
        db = next(get_db())
    
    try:
        # Get table information
        query = """
            SELECT 
                table_name,
                table_type
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """
        
        result = db.execute(text(query))
        tables = result.fetchall()
        
        # Get column information for each table
        table_details = []
        for table in tables:
            col_query = """
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns 
                WHERE table_name = :table_name 
                AND table_schema = 'public'
                ORDER BY ordinal_position
            """
            col_result = db.execute(text(col_query), {"table_name": table.table_name})
            columns = [
                {
                    "name": col.column_name,
                    "type": col.data_type,
                    "nullable": col.is_nullable == "YES",
                    "default": col.column_default
                }
                for col in col_result.fetchall()
            ]
            
            table_details.append({
                "name": table.table_name,
                "type": table.table_type,
                "columns": columns
            })
        
        return {
            "status": "success",
            "data": {
                "tables": table_details,
                "total_tables": len(tables)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to list database tables: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve table information"
        )
