"""
Guidelines API routes - Search clinical guidelines across multiple sources.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from microtutor.services.guideline_service import GuidelineService
from microtutor.services.guidelines_cache import get_guidelines_cache
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/guidelines", tags=["guidelines"])

# Dependency injection
_guideline_service: Optional[GuidelineService] = None


def get_guideline_service() -> GuidelineService:
    """Get or create guideline service singleton."""
    global _guideline_service
    if _guideline_service is None:
        # Try ToolUniverse first, fall back to custom tools
        _guideline_service = GuidelineService(use_tooluniverse=True)
    return _guideline_service


# Request/Response Models
class GuidelineSearchRequest(BaseModel):
    """Request to search clinical guidelines."""
    
    query: str = Field(
        ...,
        description="Medical condition, treatment, or clinical topic",
        json_schema_extra={"example": "MRSA treatment"}
    )
    sources: Optional[List[str]] = Field(
        None,
        description="List of sources to search (NICE, PubMed, WHO, etc.)",
        json_schema_extra={"example": ["NICE", "PubMed"]}
    )
    limit: int = Field(
        5,
        ge=1,
        le=20,
        description="Maximum results per source"
    )


class GuidelineSearchResponse(BaseModel):
    """Response from guideline search."""
    
    query: str = Field(..., description="Original search query")
    results: Dict[str, List[Dict[str, Any]]] = Field(
        ...,
        description="Guidelines organized by source"
    )
    total: int = Field(..., description="Total number of guidelines found")
    summary: str = Field(..., description="Formatted summary for LLM context")
    sources_searched: List[str] = Field(..., description="Sources that were searched")


class OrganismGuidelinesResponse(BaseModel):
    """Response from organism-specific guideline search."""
    
    organism: str = Field(..., description="Organism name")
    query: str = Field(..., description="Constructed search query")
    results: Dict[str, List[Dict[str, Any]]] = Field(
        ...,
        description="Guidelines organized by source"
    )
    total: int = Field(..., description="Total number of guidelines found")
    summary: str = Field(..., description="Formatted summary for LLM context")


class HealthCheckResponse(BaseModel):
    """Health check response."""
    
    status: str
    guideline_search_available: bool
    available_sources: List[str]
    backend: str


class GuidelineFetchRequest(BaseModel):
    """Request to fetch guidelines for an organism."""
    
    organism: str = Field(
        ...,
        description="Organism name",
        json_schema_extra={"example": "staphylococcus aureus"}
    )


class GuidelineFetchResponse(BaseModel):
    """Response from guideline fetch."""
    
    organism: str = Field(..., description="Organism name")
    clinical_guidelines: Optional[str] = Field(None, description="Clinical guidelines")
    diagnostic_approach: Optional[str] = Field(None, description="Diagnostic approach")
    treatment_protocols: Optional[str] = Field(None, description="Treatment protocols")
    recent_evidence: List[Dict[str, Any]] = Field(default_factory=list, description="Recent evidence")
    fetched_at: str = Field(..., description="When guidelines were fetched")
    sources: List[str] = Field(default_factory=list, description="Sources used")
    query_strategy: str = Field(default="intelligent_multi_source", description="Query strategy used")


# Routes
@router.get("/health", response_model=HealthCheckResponse)
async def health_check(
    service: GuidelineService = Depends(get_guideline_service)
):
    """
    Check if guideline search service is available.
    
    Returns:
        Status, available sources, and backend type (ToolUniverse or custom)
    """
    return HealthCheckResponse(
        status="healthy" if service.is_available() else "unavailable",
        guideline_search_available=service.is_available(),
        available_sources=service.get_available_sources(),
        backend="ToolUniverse" if service.use_tooluniverse else "Custom"
    )


@router.post("/search", response_model=GuidelineSearchResponse)
async def search_guidelines(
    request: GuidelineSearchRequest,
    service: GuidelineService = Depends(get_guideline_service)
):
    """
    Search clinical guidelines across multiple sources.
    
    **Example Request:**
    ```json
    {
        "query": "MRSA treatment",
        "sources": ["NICE", "PubMed"],
        "limit": 5
    }
    ```
    
    **Example Response:**
    ```json
    {
        "query": "MRSA treatment",
        "results": {
            "NICE": [
                {
                    "title": "Antimicrobial prescribing guideline: MRSA",
                    "url": "https://www.nice.org.uk/...",
                    "summary": "Guidelines for treating MRSA infections...",
                    "date": "2023-05-15"
                }
            ],
            "PubMed": [...]
        },
        "total": 12,
        "summary": "## Clinical Guidelines\\n\\n### NICE Guidelines\\n...",
        "sources_searched": ["NICE", "PubMed"]
    }
    ```
    
    Args:
        request: Search parameters (query, sources, limit)
        service: Injected guideline service
        
    Returns:
        GuidelineSearchResponse with results from all sources
        
    Raises:
        HTTPException: If search fails or service unavailable
    """
    if not service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Guideline search service is not available. "
                   "Install ToolUniverse or check custom tool implementations."
        )
    
    try:
        # Execute search
        results = await service.search_guidelines(
            query=request.query,
            sources=request.sources,
            limit=request.limit
        )
        
        # Generate summary
        summary = service.get_guideline_summary(results)
        
        # Count total
        total = sum(
            len(guidelines) 
            for guidelines in results.values() 
            if isinstance(guidelines, list)
        )
        
        # Determine which sources were actually searched
        sources_searched = list(results.keys())
        
        logger.info(
            f"Guideline search completed: query='{request.query}', "
            f"sources={sources_searched}, total={total}"
        )
        
        return GuidelineSearchResponse(
            query=request.query,
            results=results,
            total=total,
            summary=summary,
            sources_searched=sources_searched
        )
        
    except Exception as e:
        logger.error(f"Guideline search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Guideline search failed: {str(e)}"
        )


@router.get("/organism/{organism}", response_model=OrganismGuidelinesResponse)
async def search_for_organism(
    organism: str,
    treatment_focus: bool = Query(
        True,
        description="Include 'treatment' in search query"
    ),
    limit: int = Query(
        3,
        ge=1,
        le=10,
        description="Max results per source"
    ),
    service: GuidelineService = Depends(get_guideline_service)
):
    """
    Search guidelines for a specific organism or pathogen.
    
    This endpoint is optimized for microbiology/infectious disease use cases.
    
    **Example Request:**
    ```
    GET /api/v1/guidelines/organism/staphylococcus%20aureus?treatment_focus=true&limit=3
    ```
    
    **Example Response:**
    ```json
    {
        "organism": "Staphylococcus aureus",
        "query": "Staphylococcus aureus treatment guidelines",
        "results": {
            "NICE": [...],
            "PubMed": [...],
            "WHO": [...]
        },
        "total": 9,
        "summary": "## Clinical Guidelines\\n\\n..."
    }
    ```
    
    Args:
        organism: Organism name (e.g., "Staphylococcus aureus")
        treatment_focus: Include "treatment" in query
        limit: Max results per source
        service: Injected guideline service
        
    Returns:
        OrganismGuidelinesResponse with organism-specific guidelines
        
    Raises:
        HTTPException: If search fails or service unavailable
    """
    if not service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Guideline search service is not available"
        )
    
    try:
        # Execute organism-specific search
        result = await service.search_for_organism(
            organism=organism,
            treatment_focus=treatment_focus,
            limit=limit
        )
        
        # Generate summary
        summary = service.get_guideline_summary(result["results"])
        
        logger.info(
            f"Organism guideline search completed: organism='{organism}', "
            f"total={result['total_guidelines']}"
        )
        
        return OrganismGuidelinesResponse(
            organism=result["organism"],
            query=result["query"],
            results=result["results"],
            total=result["total_guidelines"],
            summary=summary
        )
        
    except Exception as e:
        logger.error(f"Organism guideline search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Organism guideline search failed: {str(e)}"
        )


@router.get("/sources", response_model=Dict[str, Any])
async def get_available_sources(
    service: GuidelineService = Depends(get_guideline_service)
):
    """
    Get list of available guideline sources.
    
    Returns:
        Dictionary with available sources and their descriptions
    """
    sources_info = {
        "NICE": {
            "name": "NICE (UK)",
            "description": "National Institute for Health and Care Excellence",
            "type": "Official Guidelines",
            "available": "NICE" in service.get_available_sources()
        },
        "PubMed": {
            "name": "PubMed",
            "description": "NCBI PubMed clinical practice guidelines",
            "type": "Peer-Reviewed",
            "available": "PubMed" in service.get_available_sources()
        },
        "WHO": {
            "name": "WHO",
            "description": "World Health Organization guidelines",
            "type": "International Guidelines",
            "available": "WHO" in service.get_available_sources()
        },
        "EuropePMC": {
            "name": "Europe PMC",
            "description": "Europe PubMed Central guidelines",
            "type": "European Research",
            "available": "EuropePMC" in service.get_available_sources()
        }
    }
    
    available_count = sum(1 for s in sources_info.values() if s["available"])
    
    return {
        "backend": "ToolUniverse" if service.use_tooluniverse else "Custom",
        "sources": sources_info,
        "total_available": available_count
    }


@router.post("/fetch", response_model=GuidelineFetchResponse)
async def fetch_guidelines(
    request: GuidelineFetchRequest
):
    """
    Fetch guidelines for a specific organism using the guidelines cache.
    
    This endpoint uses the intelligent guidelines cache service to fetch
    evidence-based clinical guidelines for the specified organism.
    
    **Example Request:**
    ```json
    {
        "organism": "staphylococcus aureus"
    }
    ```
    
    **Example Response:**
    ```json
    {
        "organism": "staphylococcus aureus",
        "clinical_guidelines": "Evidence-based guidelines for...",
        "diagnostic_approach": "Diagnostic approach includes...",
        "treatment_protocols": "Treatment protocols recommend...",
        "recent_evidence": [...],
        "fetched_at": "2024-01-15T10:30:00Z",
        "sources": ["EuropePMC", "PubMed", "NICE", "WHO"],
        "query_strategy": "intelligent_multi_source"
    }
    ```
    
    Args:
        request: GuidelineFetchRequest with organism name
        
    Returns:
        GuidelineFetchResponse with fetched guidelines
        
    Raises:
        HTTPException: If fetch fails
    """
    try:
        # Get guidelines cache service
        guidelines_cache = get_guidelines_cache(use_tooluniverse=False)
        
        # Fetch guidelines for the organism
        guidelines = await guidelines_cache.prefetch_guidelines_for_organism(
            organism=request.organism,
            case_description=None
        )
        
        # Convert datetime to string for JSON serialization
        if guidelines.get('fetched_at'):
            guidelines['fetched_at'] = guidelines['fetched_at'].isoformat()
        
        logger.info(f"Guidelines fetched for organism: {request.organism}")
        
        return GuidelineFetchResponse(**guidelines)
        
    except Exception as e:
        logger.error(f"Guideline fetch failed for {request.organism}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch guidelines for {request.organism}: {str(e)}"
        )

