"""
Analytics API routes for feedback dashboard.

Provides endpoints for retrieving feedback statistics, trends, and recent activity
for the live dashboard display.
"""

import logging
from datetime import datetime, timedelta
import pytz
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, func, desc

from fastapi import APIRouter, HTTPException, status, Depends, Query

from microtutor.api.dependencies import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/feedback/stats",
    summary="Get feedback statistics",
    description="Retrieve comprehensive feedback statistics for the dashboard"
)
async def get_feedback_stats(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get comprehensive feedback statistics."""
    try:
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )
        
        # Get basic counts
        regular_feedback_count = db.execute(text("SELECT COUNT(*) FROM feedback")).scalar()
        case_feedback_count = db.execute(text("SELECT COUNT(*) FROM case_feedback")).scalar()
        
        # Get average ratings
        avg_regular_rating = db.execute(text("SELECT AVG(rating::int) FROM feedback")).scalar() or 0
        avg_case_rating = db.execute(text("""
            SELECT AVG((detail_rating::int + helpfulness_rating::int + accuracy_rating::int) / 3.0) 
            FROM case_feedback
        """)).scalar() or 0
        
        # Get today's counts in EST timezone
        est = pytz.timezone('America/New_York')
        today = datetime.now(est).date()
        today_regular = db.execute(text("""
            SELECT COUNT(*) FROM feedback 
            WHERE DATE(timestamp) = :today
        """), {"today": today}).scalar()
        
        today_case = db.execute(text("""
            SELECT COUNT(*) FROM case_feedback 
            WHERE DATE(timestamp) = :today
        """), {"today": today}).scalar()
        
        # Get yesterday's counts for comparison
        yesterday = today - timedelta(days=1)
        yesterday_regular = db.execute(text("""
            SELECT COUNT(*) FROM feedback 
            WHERE DATE(timestamp) = :yesterday
        """), {"yesterday": yesterday}).scalar()
        
        yesterday_case = db.execute(text("""
            SELECT COUNT(*) FROM case_feedback 
            WHERE DATE(timestamp) = :yesterday
        """), {"yesterday": yesterday}).scalar()
        
        # Calculate trends
        regular_trend = today_regular - yesterday_regular
        case_trend = today_case - yesterday_case
        
        # Get last update time
        last_regular = db.execute(text("""
            SELECT MAX(timestamp) FROM feedback
        """)).scalar()
        
        last_case = db.execute(text("""
            SELECT MAX(timestamp) FROM case_feedback
        """)).scalar()
        
        last_update = max(
            last_regular or datetime.min,
            last_case or datetime.min
        )
        
        # Convert to EST if we have a valid timestamp
        if last_update != datetime.min:
            # If timestamp is naive, assume it's UTC and convert to EST
            if last_update.tzinfo is None:
                last_update = pytz.utc.localize(last_update).astimezone(est)
            else:
                last_update = last_update.astimezone(est)
        
        return {
            "status": "success",
            "data": {
                "message_feedback": {
                    "total": regular_feedback_count,
                    "today": today_regular,
                    "trend": regular_trend,
                    "avg_rating": round(avg_regular_rating, 1)
                },
                "case_feedback": {
                    "total": case_feedback_count,
                    "today": today_case,
                    "trend": case_trend,
                    "avg_rating": round(avg_case_rating, 1)
                },
                "overall": {
                    "total_feedback": regular_feedback_count + case_feedback_count,
                    "avg_rating": round((avg_regular_rating + avg_case_rating) / 2, 1),
                    "last_update": last_update.isoformat() if last_update != datetime.min else None
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get feedback stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve feedback statistics: {e}"
        )


@router.get(
    "/feedback/trends",
    summary="Get feedback trends over time",
    description="Retrieve feedback data for charting trends over specified time periods"
)
async def get_feedback_trends(
    time_range: str = Query("7d", description="Time range: 24h, 7d, 30d"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get feedback trends for charting."""
    try:
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )
        
        # Calculate date range
        now = datetime.now()
        if time_range == "all":
            start_date = None  # No date filter
            group_by = "DATE_TRUNC('day', timestamp)"
        elif time_range == "24h":
            start_date = now - timedelta(hours=24)
            group_by = "DATE_TRUNC('hour', timestamp)"
        elif time_range == "7d":
            start_date = now - timedelta(days=7)
            group_by = "DATE_TRUNC('day', timestamp)"
        elif time_range == "30d":
            start_date = now - timedelta(days=30)
            group_by = "DATE_TRUNC('day', timestamp)"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid time range. Use: all, 24h, 7d, 30d"
            )
        
        # Get regular feedback trends
        if start_date:
            regular_trends = db.execute(text(f"""
                SELECT 
                    {group_by} as time_bucket,
                    COUNT(*) as count,
                    AVG(rating::int) as avg_rating
                FROM feedback 
                WHERE timestamp >= :start_date
                GROUP BY {group_by}
                ORDER BY time_bucket
            """), {"start_date": start_date}).fetchall()
            
            # Get case feedback trends
            case_trends = db.execute(text(f"""
                SELECT 
                    {group_by} as time_bucket,
                    COUNT(*) as count,
                    AVG((detail_rating::int + helpfulness_rating::int + accuracy_rating::int) / 3.0) as avg_rating
                FROM case_feedback 
                WHERE timestamp >= :start_date
                GROUP BY {group_by}
                ORDER BY time_bucket
            """), {"start_date": start_date}).fetchall()
        else:
            # All time - no date filter
            regular_trends = db.execute(text(f"""
                SELECT 
                    {group_by} as time_bucket,
                    COUNT(*) as count,
                    AVG(rating::int) as avg_rating
                FROM feedback 
                GROUP BY {group_by}
                ORDER BY time_bucket
            """)).fetchall()
            
            # Get case feedback trends
            case_trends = db.execute(text(f"""
                SELECT 
                    {group_by} as time_bucket,
                    COUNT(*) as count,
                    AVG((detail_rating::int + helpfulness_rating::int + accuracy_rating::int) / 3.0) as avg_rating
                FROM case_feedback 
                GROUP BY {group_by}
                ORDER BY time_bucket
            """)).fetchall()
        
        # Format data for Chart.js
        labels = []
        regular_counts = []
        case_counts = []
        regular_ratings = []
        case_ratings = []
        
        if time_range == "all":
            # For all time, show cumulative data
            # Combine and sort all data by timestamp
            all_dates = set()
            for data in regular_trends:
                all_dates.add(data.time_bucket)
            for data in case_trends:
                all_dates.add(data.time_bucket)
            
            sorted_dates = sorted(all_dates)
            
            # Create cumulative counts
            regular_cumulative = 0
            case_cumulative = 0
            
            for date in sorted_dates:
                # Find data for this date
                regular_data = next((r for r in regular_trends if r.time_bucket == date), None)
                case_data = next((c for c in case_trends if c.time_bucket == date), None)
                
                # Add to cumulative counts
                if regular_data:
                    regular_cumulative += regular_data.count
                if case_data:
                    case_cumulative += case_data.count
                
                # Store cumulative values
                regular_counts.append(regular_cumulative)
                case_counts.append(case_cumulative)
                labels.append(date.strftime("%m/%d"))
                
                # Store ratings
                regular_ratings.append(round(regular_data.avg_rating, 1) if regular_data and regular_data.avg_rating else 0)
                case_ratings.append(round(case_data.avg_rating, 1) if case_data and case_data.avg_rating else 0)
                
        else:
            # For time ranges, show daily counts
            current = start_date
            while current <= now:
                if time_range == "24h":
                    time_key = current.replace(minute=0, second=0, microsecond=0)
                    current += timedelta(hours=1)
                else:
                    time_key = current.replace(hour=0, minute=0, second=0, microsecond=0)
                    current += timedelta(days=1)
                
                labels.append(time_key.strftime("%H:%M" if time_range == "24h" else "%m/%d"))
                
                # Find data for this time bucket
                regular_data = next((r for r in regular_trends if r.time_bucket == time_key), None)
                case_data = next((c for c in case_trends if c.time_bucket == time_key), None)
                
                regular_counts.append(regular_data.count if regular_data else 0)
                case_counts.append(case_data.count if case_data else 0)
                regular_ratings.append(round(regular_data.avg_rating, 1) if regular_data and regular_data.avg_rating else 0)
                case_ratings.append(round(case_data.avg_rating, 1) if case_data and case_data.avg_rating else 0)
        
        return {
            "status": "success",
            "data": {
                "labels": labels,
                "datasets": [
                    {
                        "label": "Message Feedback",
                        "data": regular_counts,
                        "borderColor": "#007bff",
                        "backgroundColor": "rgba(0, 123, 255, 0.1)",
                        "tension": 0.4
                    },
                    {
                        "label": "Case Feedback",
                        "data": case_counts,
                        "borderColor": "#28a745",
                        "backgroundColor": "rgba(40, 167, 69, 0.1)",
                        "tension": 0.4
                    }
                ],
                "ratings": {
                    "message_feedback": regular_ratings,
                    "case_feedback": case_ratings
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get feedback trends: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve feedback trends: {e}"
        )


@router.get(
    "/feedback/recent",
    summary="Get recent feedback activity",
    description="Retrieve recent feedback entries for the activity feed"
)
async def get_recent_feedback(
    limit: int = Query(10, ge=1, le=50, description="Number of recent entries to retrieve"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get recent feedback activity."""
    try:
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )
        
        # Get recent regular feedback
        recent_regular = db.execute(text("""
            SELECT 
                'message' as type,
                timestamp,
                organism,
                rating,
                LEFT(rated_message, 100) as message_preview,
                case_id
            FROM feedback 
            ORDER BY timestamp DESC 
            LIMIT :limit
        """), {"limit": limit}).fetchall()
        
        # Get recent case feedback
        recent_case = db.execute(text("""
            SELECT 
                'case' as type,
                timestamp,
                organism,
                (detail_rating::int + helpfulness_rating::int + accuracy_rating::int) / 3.0 as rating,
                LEFT(comments, 100) as message_preview,
                case_id
            FROM case_feedback 
            ORDER BY timestamp DESC 
            LIMIT :limit
        """), {"limit": limit}).fetchall()
        
        # Combine and sort by timestamp
        all_recent = list(recent_regular) + list(recent_case)
        all_recent.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Take the most recent entries
        recent_entries = all_recent[:limit]
        
        # Format for frontend
        formatted_entries = []
        for entry in recent_entries:
            formatted_entries.append({
                "type": entry.type,
                "timestamp": entry.timestamp.isoformat(),
                "organism": entry.organism or "Unknown",
                "rating": round(float(entry.rating), 1),
                "preview": entry.message_preview or "No preview available",
                "case_id": entry.case_id or "N/A",
                "time_ago": _get_time_ago(entry.timestamp)
            })
        
        return {
            "status": "success",
            "data": {
                "entries": formatted_entries,
                "total": len(formatted_entries)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get recent feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve recent feedback: {e}"
        )


def _get_time_ago(timestamp: datetime) -> str:
    """Convert timestamp to human-readable time ago string."""
    now = datetime.now()
    diff = now - timestamp
    
    if diff.days > 0:
        return f"{diff.days}d ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours}h ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes}m ago"
    else:
        return "Just now"
