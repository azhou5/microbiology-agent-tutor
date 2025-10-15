"""
Real database exploration API endpoints.

This module provides GET endpoints for retrieving actual data
from the MicroTutor PostgreSQL database.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, status, Query
import asyncpg
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_db_connection():
    """Get database connection using the same config as the app."""
    from config.config import config
    return await asyncpg.connect(config.database_url, ssl='require')


@router.get(
    "/feedback",
    summary="Get feedback data",
    description="Retrieve feedback ratings from the database"
)
async def get_feedback_data(
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of records to return"),
    organism: Optional[str] = Query(None, description="Filter by organism")
) -> Dict[str, Any]:
    """Get feedback data from the database.
    
    Args:
        limit: Maximum number of records to return
        organism: Optional organism filter
        
    Returns:
        Dictionary with feedback data
    """
    try:
        conn = await get_db_connection()
        
        # Build query
        query = """
            SELECT 
                id,
                timestamp,
                organism,
                detail_rating,
                helpfulness_rating,
                accuracy_rating,
                comments,
                case_id
            FROM case_feedback 
        """
        params = {"limit": limit}
        
        if organism:
            query += " WHERE organism = $1"
            params["organism"] = organism
            
        query += " ORDER BY timestamp DESC LIMIT $1"
        
        rows = await conn.fetch(query, limit if not organism else (organism, limit))
        await conn.close()
        
        return {
            "status": "success",
            "data": [
                {
                    "id": row["id"],
                    "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
                    "organism": row["organism"],
                    "detail_rating": row["detail_rating"],
                    "helpfulness_rating": row["helpfulness_rating"],
                    "accuracy_rating": row["accuracy_rating"],
                    "comments": row["comments"],
                    "case_id": row["case_id"]
                }
                for row in rows
            ],
            "count": len(rows)
        }
        
    except Exception as e:
        logger.error(f"Failed to get feedback data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve feedback data: {str(e)}"
        )


@router.get(
    "/tables",
    summary="List database tables",
    description="Get information about all tables in the database"
)
async def list_database_tables() -> Dict[str, Any]:
    """List all tables in the database.
    
    Returns:
        Dictionary with table information
    """
    try:
        conn = await get_db_connection()
        
        # Get table information
        query = """
            SELECT 
                table_name,
                table_type
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """
        
        tables = await conn.fetch(query)
        
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
                WHERE table_name = $1 
                AND table_schema = 'public'
                ORDER BY ordinal_position
            """
            columns = await conn.fetch(col_query, table["table_name"])
            
            table_details.append({
                "name": table["table_name"],
                "type": table["table_type"],
                "columns": [
                    {
                        "name": col["column_name"],
                        "type": col["data_type"],
                        "nullable": col["is_nullable"] == "YES",
                        "default": col["column_default"]
                    }
                    for col in columns
                ]
            })
        
        await conn.close()
        
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
            detail=f"Failed to retrieve table information: {str(e)}"
        )


@router.get(
    "/stats",
    summary="Get database statistics",
    description="Get overall statistics about the database content"
)
async def get_database_stats() -> Dict[str, Any]:
    """Get database statistics.
    
    Returns:
        Dictionary with database statistics
    """
    try:
        conn = await get_db_connection()
        
        # Get table counts
        tables = ["case_feedback", "cases", "conversation_logs", "cost_logs"]
        stats = {}
        
        for table in tables:
            try:
                count_query = f"SELECT COUNT(*) FROM {table}"
                count = await conn.fetchval(count_query)
                stats[table] = count
            except Exception as e:
                logger.warning(f"Could not count {table}: {e}")
                stats[table] = "error"
        
        # Get organism distribution from case_feedback
        org_query = """
            SELECT organism, COUNT(*) as count
            FROM case_feedback 
            GROUP BY organism 
            ORDER BY count DESC
        """
        org_result = await conn.fetch(org_query)
        organism_stats = [
            {"organism": row["organism"], "count": row["count"]}
            for row in org_result
        ]
        
        # Get average ratings
        rating_query = """
            SELECT 
                AVG(CAST(detail_rating AS INTEGER)) as avg_detail,
                AVG(CAST(helpfulness_rating AS INTEGER)) as avg_helpfulness,
                AVG(CAST(accuracy_rating AS INTEGER)) as avg_accuracy,
                COUNT(*) as total_ratings
            FROM case_feedback
        """
        rating_result = await conn.fetchrow(rating_query)
        
        await conn.close()
        
        return {
            "status": "success",
            "data": {
                "table_counts": stats,
                "organism_distribution": organism_stats,
                "average_ratings": {
                    "detail": round(float(rating_result["avg_detail"]), 2) if rating_result["avg_detail"] else 0,
                    "helpfulness": round(float(rating_result["avg_helpfulness"]), 2) if rating_result["avg_helpfulness"] else 0,
                    "accuracy": round(float(rating_result["avg_accuracy"]), 2) if rating_result["avg_accuracy"] else 0,
                    "total_ratings": rating_result["total_ratings"]
                },
                "generated_at": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve database statistics: {str(e)}"
        )
