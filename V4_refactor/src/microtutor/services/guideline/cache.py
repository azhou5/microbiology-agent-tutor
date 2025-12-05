"""
Guidelines Cache Service - Stub implementation for future RAG-based guidelines.

This service is currently a stub that will be implemented with the following protocol:

FUTURE IMPLEMENTATION PLAN:
===========================

1. **Input Format**: PDF files stored in data/guidelines/
2. **Conversion**: PDFs → Markdown (using pdf parsing libraries)
3. **Embedding**: Convert markdown chunks to embeddings (sentence-transformers)
4. **RAG Pipeline**: 
   - Store embeddings in vector database (FAISS/Chroma)
   - When organism-specific guidelines needed:
     a. Query with organism name + case context
     b. Retrieve top-k most relevant chunks
     c. Extract organism-specific sections from retrieved chunks
     d. Combine into formatted guidelines
5. **Output**: Formatted guidelines string for tests_management LLM

CURRENT STATUS:
===============
- Interface is ready and functional
- Returns empty guidelines (stub implementation)
- Can be enabled/disabled via enable_guidelines flag
- All integration points are in place
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class GuidelinesCache:
    """
    Stub service for clinical guidelines caching and retrieval.
    
    Currently returns empty guidelines. Future implementation will:
    - Load PDFs from data/guidelines/
    - Convert to markdown
    - Create embeddings
    - Use RAG to find organism-specific sections
    - Return formatted guidelines for tests_management tool
    """
    
    def __init__(self, guidelines_dir: Optional[str] = None, project_root: Optional[str] = None):
        """
        Initialize guidelines cache stub.
        
        Args:
            guidelines_dir: Path to guidelines directory (defaults to data/guidelines/)
            project_root: Project root directory for resolving relative paths
        """
        # Resolve project root
        if project_root:
            self._project_root = Path(project_root)
        else:
            # __file__ is at: V4_refactor/src/microtutor/services/guideline/cache.py
            # V4_refactor is 5 levels up: guideline -> services -> microtutor -> src -> V4_refactor
            self._project_root = Path(__file__).parent.parent.parent.parent.parent
        
        # Resolve guidelines directory
        if guidelines_dir:
            self._guidelines_dir = Path(guidelines_dir)
        else:
            self._guidelines_dir = self._project_root / "data" / "guidelines"
        
        # Create guidelines directory if it doesn't exist
        self._guidelines_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Guidelines cache initialized (stub mode) - directory: {self._guidelines_dir}")
        logger.info("Guidelines functionality will be implemented with PDF→Markdown→Embeddings→RAG pipeline")
    
    def get_cached(self, organism: str) -> Optional[Dict[str, Any]]:
        """
        Get cached guidelines for an organism (stub - always returns None).
        
        Args:
            organism: The organism name
            
        Returns:
            None (stub implementation)
        """
        # TODO: Implement caching once RAG pipeline is ready
        return None
    
    async def prefetch_guidelines_for_organism(
        self,
        organism: str,
        case_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Load guidelines for an organism (stub - returns empty guidelines).
        
        FUTURE IMPLEMENTATION:
        - Load PDFs from data/guidelines/
        - Convert to markdown chunks
        - Use embeddings + RAG to find organism-specific sections
        - Extract and format relevant guidelines
        - Return formatted guidelines dict
        
        Args:
            organism: The pathogen/condition
            case_description: Optional case context for targeted search
            
        Returns:
            Empty guidelines dict (stub implementation)
        """
        logger.info(f"Guidelines requested for: {organism} (stub - returning empty)")
        
        # Return empty guidelines structure
        # TODO: Implement PDF→Markdown→Embeddings→RAG pipeline
        return {
            "organism": organism,
            "diagnostic_approach": "",
            "treatment_protocols": "",
            "clinical_guidelines": "",
            "recent_evidence": [],
            "fetched_at": datetime.now(),
            "sources": [],
            "file_source": None,
            "stub_mode": True  # Flag to indicate this is stub data
        }
    
    def format_guidelines_for_tool(
        self,
        guidelines: Optional[Dict[str, Any]],
        tool_name: str
    ) -> str:
        """
        Format guidelines for inclusion in tool prompts.
        
        Args:
            guidelines: The guidelines data
            tool_name: Name of the tool requesting guidelines
            
        Returns:
            Formatted string to append to tool prompt (empty if no guidelines)
        """
        if not guidelines or guidelines.get("stub_mode"):
            # Return empty string for stub mode
            return ""
        
        if tool_name == "tests_management":
            return f"""
## Pre-fetched Clinical Guidelines

**Organism:** {guidelines.get('organism', 'Unknown')}

**Diagnostic Approach:**
{guidelines.get('diagnostic_approach', 'Not available')}

**Treatment Protocols:**
{guidelines.get('treatment_protocols', 'Not available')}

**Clinical Guidelines:**
{guidelines.get('clinical_guidelines', 'Not available')}

Use these evidence-based guidelines to inform your discussion with the student.
"""
        
        elif tool_name == "mcq_tool":
            return f"""
## Evidence-Based Context for MCQ Generation

**Organism:** {guidelines.get('organism', 'Unknown')}

**Key Guidelines:**
- Diagnostic: {guidelines.get('diagnostic_approach', 'Not available')}
- Treatment: {guidelines.get('treatment_protocols', 'Not available')}

Generate MCQs based on current evidence-based practices.
"""
        
        else:
            # Generic format
            return f"\n\n[Clinical Guidelines: {guidelines.get('organism', 'Unknown')}]"


# Global singleton
_guidelines_cache: Optional[GuidelinesCache] = None


def get_guidelines_cache(
    guidelines_dir: Optional[str] = None,
    project_root: Optional[str] = None
) -> GuidelinesCache:
    """Get or create the global guidelines cache."""
    global _guidelines_cache
    if _guidelines_cache is None:
        _guidelines_cache = GuidelinesCache(
            guidelines_dir=guidelines_dir,
            project_root=project_root
        )
    return _guidelines_cache
