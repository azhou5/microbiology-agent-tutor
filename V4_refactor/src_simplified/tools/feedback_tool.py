import json
import logging
import pickle
import importlib
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)

class FeedbackTool:
    def __init__(self, index_dir: str = "data/feedback_auto", enabled: bool = False):
        self.index_dir = Path(index_dir)
        self.enabled = enabled
        self.index = None
        self.texts = []
        self.entries = []
        self.faiss = None
        self.faiss_available = False
        if self.enabled:
            self._init_faiss()
            self.load_index()
        else:
            logger.info("Feedback indexing is disabled by configuration.")

    def _init_faiss(self):
        """Import FAISS only when indexing is enabled."""
        try:
            self.faiss = importlib.import_module("faiss")
            self.faiss_available = True
        except ImportError:
            self.faiss = None
            self.faiss_available = False
            logger.warning("FAISS is not installed; indexing/search is unavailable.")

    def load_index(self):
        if not self.enabled:
            return
        if not self.faiss_available or self.faiss is None:
            return

        try:
            index_path = self.index_dir / "feedback_index.faiss"
            texts_path = self.index_dir / "feedback_texts.pkl"
            entries_path = self.index_dir / "feedback_entries.pkl"

            if index_path.exists() and texts_path.exists() and entries_path.exists():
                self.index = self.faiss.read_index(str(index_path))
                with open(texts_path, 'rb') as f:
                    self.texts = pickle.load(f)
                with open(entries_path, 'rb') as f:
                    self.entries = pickle.load(f)
                logger.info(f"Loaded feedback index with {self.index.ntotal} entries.")
            else:
                logger.warning(f"Feedback index files not found in {self.index_dir}")
        except Exception as e:
            logger.error(f"Failed to load feedback index: {e}")

    def search_feedback(self, query_embedding: List[float], k: int = 3) -> List[Dict[str, Any]]:
        if not self.enabled or not self.index or not self.faiss_available or self.faiss is None:
            return []

        try:
            query_vector = np.array([query_embedding], dtype='float32')
            self.faiss.normalize_L2(query_vector)
            distances, indices = self.index.search(query_vector, k)
            
            results = []
            for i, idx in enumerate(indices[0]):
                if idx != -1 and idx < len(self.entries):
                    entry = self.entries[idx]
                    results.append({
                        "text": self.texts[idx],
                        "entry": entry,
                        "score": float(distances[0][i])
                    })
            return results
        except Exception as e:
            logger.error(f"Feedback search failed: {e}")
            return []

    def save_feedback(self, feedback_data: Dict[str, Any]):
        # Simplified save logic - just append to a JSON file for now
        # In a real system, this would update the index or DB
        feedback_file = self.index_dir / "new_feedback.json"
        try:
            existing_data = []
            if feedback_file.exists():
                with open(feedback_file, 'r') as f:
                    existing_data = json.load(f)
            
            existing_data.append(feedback_data)
            
            with open(feedback_file, 'w') as f:
                json.dump(existing_data, f, indent=2)
            logger.info("Saved new feedback.")
        except Exception as e:
            logger.error(f"Failed to save feedback: {e}")

