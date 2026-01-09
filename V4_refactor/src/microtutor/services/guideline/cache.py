"""
Guidelines Cache Service - RAG-based guideline retrieval.

This service implements a RAG pipeline to retrieve relevant clinical guidelines
based on organism and case context.
"""

import logging
import json
import os
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

from openai import AsyncAzureOpenAI, AsyncOpenAI
from microtutor.core.config.config_helper import config

logger = logging.getLogger(__name__)


class GuidelinesCache:
    """
    Service for clinical guidelines caching and RAG retrieval.
    
    Loads pre-computed embeddings and performs vector search to find
    relevant guideline chunks for a given case.
    """
    
    def __init__(self, guidelines_dir: Optional[str] = None, project_root: Optional[str] = None):
        """
        Initialize guidelines cache.
        
        Args:
            guidelines_dir: Path to guidelines directory (defaults to data/guidelines/)
            project_root: Project root directory for resolving relative paths
        """
        # Resolve project root
        if project_root:
            self._project_root = Path(project_root)
        else:
            # __file__ is at: V4_refactor/src/microtutor/services/guideline/cache.py
            self._project_root = Path(__file__).parent.parent.parent.parent.parent
        
        # Resolve guidelines directory
        if guidelines_dir:
            self._guidelines_dir = Path(guidelines_dir)
        else:
            self._guidelines_dir = self._project_root / "data" / "guidelines"
        
        # Create guidelines directory if it doesn't exist
        self._guidelines_dir.mkdir(parents=True, exist_ok=True)
        
        # Load embeddings
        # self._guidelines_dir is already set to data/guidelines
        self.embeddings_path = self._guidelines_dir / "embeddings.jsonl"
        self.local_embeddings = []
        self._load_embeddings()
        
        # Setup OpenAI client
        self.client = None
        self._setup_client()
        
        logger.info(f"Guidelines cache initialized - directory: {self._guidelines_dir}")
        if self.local_embeddings:
            logger.info(f"RAG enabled with {len(self.local_embeddings)} chunks")
        else:
            logger.warning("RAG disabled - no embeddings loaded")

    def _setup_client(self):
        """Initialize OpenAI client based on config."""
        try:
            if config.USE_AZURE_OPENAI:
                self.client = AsyncAzureOpenAI(
                    azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
                    api_key=config.AZURE_OPENAI_API_KEY,
                    api_version=config.AZURE_OPENAI_API_VERSION
                )
            elif config.OPENAI_API_KEY:
                self.client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
            else:
                logger.warning("No OpenAI credentials found for GuidelinesCache")
        except Exception as e:
            logger.error(f"Failed to setup OpenAI client for GuidelinesCache: {e}")

    def _load_embeddings(self):
        """Load embeddings from JSONL file."""
        if self.embeddings_path.exists():
            try:
                count = 0
                with open(self.embeddings_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            self.local_embeddings.append(json.loads(line))
                            count += 1
                logger.info(f"Loaded {count} guideline embeddings from {self.embeddings_path}")
            except Exception as e:
                logger.error(f"Failed to load embeddings: {e}")
        else:
            logger.warning(f"Embeddings file not found at {self.embeddings_path}")

    def get_cached(self, organism: str) -> Optional[Dict[str, Any]]:
        """
        Get cached guidelines for an organism (stub - always returns None).
        
        Args:
            organism: The organism name
            
        Returns:
            None (stub implementation)
        """
        # TODO: Implement actual caching mechanism if needed
        return None
    
    async def prefetch_guidelines_for_organism(
        self,
        organism: str,
        case_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieve guidelines using RAG.
        
        Args:
            organism: The pathogen/condition
            case_description: Optional case context for targeted search
            
        Returns:
            Dict containing retrieved guidelines
        """
        if not self.local_embeddings or not self.client:
            return self._get_stub_guidelines(organism)
            
        logger.info(f"Searching guidelines for: {organism}")
        
        try:
            # Construct query: organism + case text
            query = f"{organism} {case_description or ''}".strip()
            
            # Embed query using same model as generation
            resp = await self.client.embeddings.create(
                input=query,
                model="text-embedding-3-small"
            )
            query_vec = np.array(resp.data[0].embedding)
            
            # Vector search
            found_items = self._vector_search(query_vec, top_k=2)
            
            return {
                "organism": organism,
                "found_guidelines": found_items,
                "fetched_at": datetime.now(),
                "stub_mode": False
            }
            
        except Exception as e:
            logger.error(f"Error searching guidelines: {e}")
            return self._get_stub_guidelines(organism)

    def _vector_search(self, query_vec: np.ndarray, top_k: int = 2) -> List[Dict[str, Any]]:
        """Perform cosine similarity search."""
        if not self.local_embeddings:
            return []
            
        scores = []
        q_norm = np.linalg.norm(query_vec)
        
        if q_norm == 0:
            return []
            
        for item in self.local_embeddings:
            vec = np.array(item['embedding'])
            v_norm = np.linalg.norm(vec)
            
            if v_norm == 0:
                score = 0
            else:
                score = np.dot(query_vec, vec) / (q_norm * v_norm)
                
            scores.append((score, item))
            
        # Sort by score descending
        scores.sort(key=lambda x: x[0], reverse=True)
        
        # Return top k items
        return [item for _, item in scores[:top_k]]

    def _get_stub_guidelines(self, organism: str) -> Dict[str, Any]:
        """Return empty/stub guidelines."""
        return {
            "organism": organism,
            "diagnostic_approach": "",
            "treatment_protocols": "",
            "clinical_guidelines": "",
            "recent_evidence": [],
            "fetched_at": datetime.now(),
            "sources": [],
            "file_source": None,
            "stub_mode": True
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
            Formatted string to append to tool prompt
        """
        if not guidelines:
            return ""
        
        # Handle stub/empty mode
        if guidelines.get("stub_mode"):
            return ""
            
        found_items = guidelines.get("found_guidelines", [])
        if not found_items:
            return ""
            
        # Format for RAG results
        formatted = "POTENTIAL CLINICAL CONTEXTS (based on similar guidelines):\n"
        
        for i, item in enumerate(found_items, 1):
            topic = item.get("topic", "Unknown")
            text = item.get("text", "")
            title = item.get("title", "Unknown Source")
            
            formatted += f"\n{i}. Topic/Organism: {topic}\n"
            formatted += f"   Source: {title}\n"
            formatted += f"   Context: {text}\n"
            
        return formatted


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
