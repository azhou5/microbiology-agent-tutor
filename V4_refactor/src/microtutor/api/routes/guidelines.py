"""
Guidelines API Router

Handles requests for fetching clinical guidelines.
Uses the local RAG-based cache to retrieve guidelines.
"""

import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException, Depends
from microtutor.services.guideline.cache import get_guidelines_cache, GuidelinesCache

logger = logging.getLogger(__name__)

router = APIRouter()

class GuidelinesRequest(BaseModel):
    organism: str
    case_context: Optional[str] = None

class GuidelinesResponse(BaseModel):
    organism: str
    diagnostic_approach: str = ""
    treatment_protocols: str = ""
    clinical_guidelines: str = ""
    recent_evidence: list = []
    stub_mode: bool = False
    
    # Allow extra fields for RAG data
    model_config = {
        "extra": "allow"
    }

@router.post("/guidelines/fetch", response_model=GuidelinesResponse)
async def fetch_guidelines(
    request: GuidelinesRequest,
    cache: GuidelinesCache = Depends(get_guidelines_cache)
):
    """
    Fetch guidelines for a specific organism using RAG.
    """
    try:
        # Use the local RAG cache to fetch guidelines
        # This will perform vector search if embeddings are available
        result = await cache.prefetch_guidelines_for_organism(
            organism=request.organism,
            case_description=request.case_context
        )
        
        # Transform the result to match the expected response format
        # The frontend expects certain fields, but RAG returns 'found_guidelines'
        
        response_data = {
            "organism": result.get("organism", request.organism),
            "stub_mode": result.get("stub_mode", False),
            "recent_evidence": []
        }
        
        # Format found guidelines into the response fields
        found_guidelines = result.get("found_guidelines", [])
        if found_guidelines:
            # Combine all found chunks into the clinical_guidelines field for display
            guidelines_text = ""
            for i, item in enumerate(found_guidelines, 1):
                topic = item.get("topic", "Unknown")
                title = item.get("title", "Unknown Source")
                text = item.get("text", "")
                
                guidelines_text += f"### {i}. {topic} ({title})\n\n{text}\n\n---\n\n"
            
            response_data["clinical_guidelines"] = guidelines_text
            
            # Also populate other fields if we can (or leave them empty/generic)
            response_data["diagnostic_approach"] = "See detailed guidelines above."
            response_data["treatment_protocols"] = "See detailed guidelines above."
            
        return GuidelinesResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Error fetching guidelines: {e}")
        raise HTTPException(status_code=500, detail=str(e))

