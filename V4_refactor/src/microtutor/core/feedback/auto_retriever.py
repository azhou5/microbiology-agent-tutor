"""
Auto feedback retriever that uses automatically generated FAISS indices.

This retriever loads feedback examples from the auto-generated FAISS indices
that are continuously updated from database feedback data.
"""

import logging
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional
import faiss
import numpy as np

from microtutor.core.feedback.processor import FeedbackExample
from microtutor.core.feedback.auto_generator import get_auto_faiss_generator, get_project_root
from microtutor.utils.embedding_utils import get_embedding

logger = logging.getLogger(__name__)


class AutoFeedbackRetriever:
    """Retrieves feedback examples using auto-generated FAISS indices."""
    
    def __init__(self, auto_feedback_dir: Optional[str] = None):
        """Initialize auto feedback retriever.
        
        Args:
            auto_feedback_dir: Directory containing auto-generated FAISS indices.
                              Defaults to data/feedback_auto in project root.
        """
        if auto_feedback_dir is None:
            # Use absolute path relative to project root
            self.auto_feedback_dir = get_project_root() / "data" / "feedback_auto"
        else:
            self.auto_feedback_dir = Path(auto_feedback_dir)
        
        self.indices = {}
        self.texts = {}
        self.entries = {}
        
        logger.info(f"AutoFeedbackRetriever initialized with dir: {self.auto_feedback_dir}")
        
        # Load auto-generated indices
        self._load_auto_indices()
    
    def _load_auto_indices(self) -> None:
        """Load auto-generated FAISS indices."""
        try:
            # Load all feedback index
            self._load_index("all", self.auto_feedback_dir)
            
            # Load patient feedback index
            self._load_index("patient", self.auto_feedback_dir / "patient")
            
            # Load tutor feedback index
            self._load_index("tutor", self.auto_feedback_dir / "tutor")
            
            logger.info("Auto-generated feedback indices loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load auto-generated indices: {e}")
    
    def _load_index(self, name: str, index_dir: Path) -> None:
        """Load FAISS index and associated data."""
        try:
            index_path = index_dir / "feedback_index.faiss"
            texts_path = index_dir / "feedback_texts.pkl"
            entries_path = index_dir / "feedback_entries.pkl"
            
            if all(p.exists() for p in [index_path, texts_path, entries_path]):
                with open(index_path, 'rb') as f:
                    index = pickle.load(f)
                    # Verify it's a FAISS index
                    if hasattr(index, 'ntotal'):
                        self.indices[name] = index
                    else:
                        logger.warning(f"Invalid FAISS index format for {name}")
                        return
                with open(texts_path, 'rb') as f:
                    self.texts[name] = pickle.load(f)
                with open(entries_path, 'rb') as f:
                    self.entries[name] = pickle.load(f)
                
                logger.info(f"Loaded {name} auto-feedback index with {self.indices[name].ntotal} entries")
            else:
                logger.warning(f"Auto-feedback index not found for {name} at {index_dir}")
                
        except Exception as e:
            logger.error(f"Failed to load {name} auto-feedback index: {e}")
    
    def retrieve_similar_examples(
        self, 
        input_text: str, 
        history: List[Dict[str, str]], 
        k: int = 3,
        index_type: str = "all",
        min_rating: int = 3
    ) -> List[FeedbackExample]:
        """Retrieve similar feedback examples.
        
        Args:
            input_text: Input text to find similar examples for
            history: Conversation history
            k: Number of examples to retrieve
            index_type: Type of index to use ("all", "patient", "tutor")
            min_rating: Minimum rating for examples
            
        Returns:
            List of similar feedback examples
        """
        try:
            if index_type not in self.indices:
                logger.warning(f"Index type {index_type} not available")
                return []
            
            # Get embedding for input text
            embedding = get_embedding(input_text)
            if not embedding:
                logger.warning("Failed to get embedding for input text")
                return []
            
            # Search for similar examples
            query_vector = np.array([embedding]).astype('float32')
            distances, indices = self.indices[index_type].search(query_vector, k)
            
            examples = []
            for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
                if idx >= len(self.entries[index_type]):
                    continue
                
                entry = self.entries[index_type][idx]
                
                # Filter by minimum rating
                if entry.rating < min_rating:
                    continue
                
                # Create feedback example
                example = FeedbackExample(
                    text=self.texts[index_type][idx],
                    entry=entry,
                    similarity_score=float(distance),
                    is_positive_example=entry.rating >= 3,
                    is_negative_example=entry.rating <= 2
                )
                examples.append(example)
            
            logger.info(f"Retrieved {len(examples)} similar examples from {index_type} index")
            return examples
            
        except Exception as e:
            logger.error(f"Failed to retrieve similar examples: {e}")
            return []
    
    def get_patient_examples(
        self, 
        input_text: str, 
        history: List[Dict[str, str]], 
        k: int = 3
    ) -> List[FeedbackExample]:
        """Get patient-related feedback examples."""
        return self.retrieve_similar_examples(
            input_text, history, k, index_type="patient", min_rating=3
        )
    
    def get_tutor_examples(
        self, 
        input_text: str, 
        history: List[Dict[str, str]], 
        k: int = 3
    ) -> List[FeedbackExample]:
        """Get tutor-related feedback examples."""
        return self.retrieve_similar_examples(
            input_text, history, k, index_type="tutor", min_rating=3
        )
    
    def get_all_examples(
        self, 
        input_text: str, 
        history: List[Dict[str, str]], 
        k: int = 5
    ) -> List[FeedbackExample]:
        """Get all feedback examples."""
        return self.retrieve_similar_examples(
            input_text, history, k, index_type="all", min_rating=1
        )
    
    def refresh_indices(self) -> None:
        """Refresh indices from auto-generated files."""
        try:
            logger.info("Refreshing auto-generated feedback indices...")
            self._load_auto_indices()
            logger.info("Auto-generated feedback indices refreshed successfully")
        except Exception as e:
            logger.error(f"Failed to refresh auto-generated indices: {e}")
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about loaded indices."""
        stats = {}
        for name in self.indices:
            stats[name] = {
                "total_entries": self.indices[name].ntotal,
                "texts_count": len(self.texts.get(name, [])),
                "entries_count": len(self.entries.get(name, []))
            }
        return stats


# Global instance
_auto_feedback_retriever = None

def get_auto_feedback_retriever() -> AutoFeedbackRetriever:
    """Get the global auto feedback retriever instance."""
    global _auto_feedback_retriever
    if _auto_feedback_retriever is None:
        _auto_feedback_retriever = AutoFeedbackRetriever()
    return _auto_feedback_retriever
