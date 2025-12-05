"""Case service for managing medical cases.

This service handles:
- Loading cases for organisms
- Caching case data
- Retrieving available organisms

Now using V4's standalone agents - no V3 dependencies!
"""

from typing import List, Optional, Dict, Any
import logging

# Import directly from submodules to avoid circular imports
from .case_loader import get_case
from .case_generator_rag import CaseGeneratorRAGAgent

logger = logging.getLogger(__name__)


class CaseService:
    """Service for managing medical microbiology cases."""
    
    def __init__(self):
        """Initialize case service."""
        logger.info("CaseService initialized")
        self._cache: Dict[str, str] = {}
    
    async def get_case(self, organism: str) -> Optional[str]:
        """Get case description for an organism.
        
        Args:
            organism: The microorganism name
            
        Returns:
            Case description or None if not found
        """
        # Check cache first
        if organism in self._cache:
            logger.info(f"Case for '{organism}' found in cache")
            return self._cache[organism]
        
        # Get from V3 logic
        try:
            case_description = get_case(organism)
            if case_description:
                self._cache[organism] = case_description
                logger.info(f"Case for '{organism}' loaded and cached")
            return case_description
        except Exception as e:
            logger.error(f"Error loading case for '{organism}': {e}")
            return None
    
    async def get_available_organisms(self) -> List[str]:
        """Get list of organisms with available cases.
        
        Returns:
            List of organism names
        """
        try:
            case_generator = CaseGeneratorRAGAgent()
            organisms = case_generator.get_cached_organisms()
            logger.info(f"Found {len(organisms)} available organisms")
            return organisms
        except Exception as e:
            logger.error(f"Error getting available organisms: {e}")
            return []
    
    def clear_cache(self):
        """Clear the case cache."""
        self._cache.clear()
        logger.info("Case cache cleared")

