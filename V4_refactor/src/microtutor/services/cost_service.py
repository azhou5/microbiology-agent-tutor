"""
Cost calculation service for LLM usage tracking.

This service handles async cost calculation and monitoring for LLM API calls.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Token usage information for cost calculation."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    timestamp: datetime


@dataclass
class CostInfo:
    """Cost information for a request."""
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    timestamp: datetime
    case_id: Optional[str] = None
    request_type: Optional[str] = None


class CostService:
    """Service for calculating and tracking LLM costs."""
    
    # Model pricing (per 1M tokens) - updated as of 2024
    MODEL_PRICING = {
        # OpenAI models
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 2.50, "output": 10.00},
        "gpt-4": {"input": 3.00, "output": 6.00},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        
        # O1 models (approximate pricing)
        "o1-preview": {"input": 15.00, "output": 60.00},
        "o1-mini": {"input": 3.00, "output": 12.00},
        "o4-mini-2025-04-16": {"input": 3.00, "output": 12.00},  # Estimated
        
        # Anthropic models
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
        "claude-3-5-haiku-20241022": {"input": 1.00, "output": 5.00},
        "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
        
        # Default fallback
        "default": {"input": 1.00, "output": 2.00}
    }
    
    def __init__(self):
        """Initialize the cost service."""
        self.total_cost_usd = 0.0
        self.request_count = 0
        self.cost_history: List[CostInfo] = []
        
        logger.info("CostService initialized")
    
    def calculate_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        case_id: Optional[str] = None,
        request_type: Optional[str] = None
    ) -> CostInfo:
        """Calculate cost for a request.
        
        Args:
            model: Model name
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            case_id: Optional case ID
            request_type: Optional request type (e.g., 'chat', 'start_case')
            
        Returns:
            CostInfo object with calculated cost
        """
        total_tokens = prompt_tokens + completion_tokens
        
        # Get pricing for model
        pricing = self.MODEL_PRICING.get(model, self.MODEL_PRICING["default"])
        
        # Calculate cost in USD
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost
        
        cost_info = CostInfo(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=total_cost,
            timestamp=datetime.utcnow(),
            case_id=case_id,
            request_type=request_type
        )
        
        # Update totals
        self.total_cost_usd += total_cost
        self.request_count += 1
        self.cost_history.append(cost_info)
        
        logger.info(
            f"Cost calculated: {model} - {total_tokens} tokens - ${total_cost:.6f} "
            f"(Total: ${self.total_cost_usd:.6f})"
        )
        
        return cost_info
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary statistics.
        
        Returns:
            Dictionary with cost summary
        """
        if not self.cost_history:
            return {
                "total_cost_usd": 0.0,
                "request_count": 0,
                "average_cost_per_request": 0.0,
                "tokens_by_model": {},
                "cost_by_model": {}
            }
        
        # Calculate statistics
        tokens_by_model = {}
        cost_by_model = {}
        
        for cost_info in self.cost_history:
            model = cost_info.model
            if model not in tokens_by_model:
                tokens_by_model[model] = 0
                cost_by_model[model] = 0.0
            
            tokens_by_model[model] += cost_info.total_tokens
            cost_by_model[model] += cost_info.cost_usd
        
        return {
            "total_cost_usd": self.total_cost_usd,
            "request_count": self.request_count,
            "average_cost_per_request": self.total_cost_usd / self.request_count,
            "tokens_by_model": tokens_by_model,
            "cost_by_model": cost_by_model,
            "last_updated": self.cost_history[-1].timestamp.isoformat() if self.cost_history else None
        }
    
    def get_recent_costs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent cost information.
        
        Args:
            limit: Maximum number of recent costs to return
            
        Returns:
            List of recent cost information
        """
        recent_costs = self.cost_history[-limit:] if self.cost_history else []
        
        return [
            {
                "model": cost.model,
                "prompt_tokens": cost.prompt_tokens,
                "completion_tokens": cost.completion_tokens,
                "total_tokens": cost.total_tokens,
                "cost_usd": cost.cost_usd,
                "timestamp": cost.timestamp.isoformat(),
                "case_id": cost.case_id,
                "request_type": cost.request_type
            }
            for cost in recent_costs
        ]
    
    def reset_costs(self) -> None:
        """Reset all cost tracking."""
        self.total_cost_usd = 0.0
        self.request_count = 0
        self.cost_history.clear()
        logger.info("Cost tracking reset")
    
    def export_costs(self, filepath: str) -> None:
        """Export cost history to JSON file.
        
        Args:
            filepath: Path to export file
        """
        try:
            export_data = {
                "summary": self.get_cost_summary(),
                "cost_history": self.get_recent_costs(limit=len(self.cost_history))
            }
            
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"Cost data exported to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to export cost data: {e}")


# Global cost service instance
_cost_service: Optional[CostService] = None


def get_cost_service() -> CostService:
    """Get the global cost service instance."""
    global _cost_service
    if _cost_service is None:
        _cost_service = CostService()
    return _cost_service


def calculate_cost_async(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    case_id: Optional[str] = None,
    request_type: Optional[str] = None
) -> CostInfo:
    """Calculate cost asynchronously (non-blocking).
    
    This function can be called from background tasks.
    """
    cost_service = get_cost_service()
    return cost_service.calculate_cost(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        case_id=case_id,
        request_type=request_type
    )
