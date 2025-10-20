"""
Intelligent feedback retriever with context awareness.
Retrieves relevant feedback examples based on current conversation context.
"""

import os
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
from dataclasses import dataclass

try:
    import numpy as np
    import faiss
    from microtutor.utils import get_embedding
    FAISS_AVAILABLE = True
except ImportError as e:
    import logging
    logging.warning(f"FAISS dependencies not available: {e}")
    FAISS_AVAILABLE = False
    # Provide fallback implementations
    def get_embedding(text: str) -> List[float]:
        return [0.0] * 1536  # Default embedding size
from microtutor.feedback.feedback_processor import FeedbackEntry
from microtutor.core.config_helper import config

logger = logging.getLogger(__name__)


@dataclass
class FeedbackExample:
    """A retrieved feedback example with metadata."""
    text: str
    entry: FeedbackEntry
    similarity_score: float
    is_positive_example: bool
    is_negative_example: bool


class FeedbackRetriever:
    """Retrieves relevant feedback examples based on context."""
    
    def __init__(self, feedback_dir: str):
        """Initialize feedback retriever with FAISS indices."""
        self.feedback_dir = Path(feedback_dir)
        self.indices = {}
        self.texts = {}
        self.entries = {}
        
        # Load different indices
        self._load_index("all", self.feedback_dir)
        self._load_index("patient", self.feedback_dir / "patient")
        self._load_index("tutor", self.feedback_dir / "tutor")
    
    def _load_index(self, name: str, index_dir: Path) -> None:
        """Load FAISS index and associated data."""
        try:
            index_path = index_dir / "feedback_index.faiss"
            texts_path = index_dir / "feedback_texts.pkl"
            entries_path = index_dir / "feedback_entries.pkl"
            
            if all(p.exists() for p in [index_path, texts_path, entries_path]):
                with open(index_path, 'rb') as f:
                    self.indices[name] = pickle.load(f)
                with open(texts_path, 'rb') as f:
                    self.texts[name] = pickle.load(f)
                
                # Load entries with proper class mapping
                try:
                    with open(entries_path, 'rb') as f:
                        self.entries[name] = pickle.load(f)
                except AttributeError as e:
                    if "FeedbackEntry" in str(e):
                        # Try to fix the pickle issue by using a custom unpickler
                        import sys
                        from microtutor.feedback.feedback_processor import FeedbackEntry
                        
                        # Create a custom unpickler that maps the old module to the new one
                        class CustomUnpickler(pickle.Unpickler):
                            def find_class(self, module, name):
                                if module == "__main__" and name == "FeedbackEntry":
                                    return FeedbackEntry
                                return super().find_class(module, name)
                        
                        with open(entries_path, 'rb') as f:
                            unpickler = CustomUnpickler(f)
                            self.entries[name] = unpickler.load()
                    else:
                        raise e
                
                logger.info(f"Loaded {name} feedback index with {self.indices[name].ntotal} entries")
            else:
                logger.warning(f"Feedback index not found for {name} at {index_dir}")
        except Exception as e:
            logger.error(f"Failed to load {name} feedback index: {e}")
    
    def _extract_last_user_input(self, conversation_history: List[Dict[str, str]]) -> str:
        """Extract the last user input from conversation history."""
        if not conversation_history:
            return ""
        
        # Look for the last user message
        for msg in reversed(conversation_history):
            if msg.get('role') == 'user' and msg.get('content'):
                return msg['content'].strip()
        
        return ""
    
    def _create_query_embedding(self, user_input: str, message_type: str = "all") -> np.ndarray:
        """Create embedding for query based on user input only."""
        # Create query text that matches the indexed format
        query_text = f"User input: {user_input}"
        embedding = get_embedding(query_text)
        return np.array([embedding]).astype('float32')
    
    def retrieve_feedback_examples(
        self,
        current_message: str,
        conversation_history: List[Dict[str, str]],
        message_type: str = "all",
        k: int = None,
        similarity_threshold: Optional[float] = None
    ) -> List[FeedbackExample]:
        """
        Retrieve relevant feedback examples for current context.
        
        Requirements:
        1. Embed only the last user input
        2. Find most relevant FAISS matches to similar inputs
        3. Return examples above similarity threshold (positive and negative work independently)
        4. If threshold not met, return empty list
        """
        
        # Get configuration - use passed threshold or fall back to config
        similarity_threshold = similarity_threshold or config.FEEDBACK_SIMILARITY_THRESHOLD
        max_examples = k or config.FEEDBACK_MAX_EXAMPLES
        
        # Extract last user input
        user_input = self._extract_last_user_input(conversation_history)
        if not user_input:
            logger.warning("No user input found in conversation history")
            return []
        
        # Determine which index to use
        index_name = message_type if message_type in self.indices else "all"
        
        if index_name not in self.indices:
            logger.warning(f"No feedback index available for {message_type}")
            return []
        
        # Create query embedding from user input only
        query_embedding = self._create_query_embedding(user_input, message_type)
        
        # Search for similar examples
        index = self.indices[index_name]
        texts = self.texts[index_name]
        entries = self.entries[index_name]
        
        # Normalize query embedding for cosine similarity
        faiss.normalize_L2(query_embedding)
        
        # Search for more examples than needed to find good matches
        search_k = min(max_examples * 5, index.ntotal)
        similarities, indices = index.search(query_embedding, search_k)
        
        # Convert to feedback examples with similarity scores
        all_examples = []
        for i, (similarity, idx) in enumerate(zip(similarities[0], indices[0])):
            if idx >= len(entries):
                continue
                
            entry = entries[idx]
            text = texts[idx]
            
            # For cosine similarity, higher values = more similar
            # Clamp to [0, 1] range for consistency
            similarity_score = max(0.0, min(1.0, similarity))
            
            example = FeedbackExample(
                text=text,
                entry=entry,
                similarity_score=similarity_score,
                is_positive_example=entry.is_high_quality,
                is_negative_example=entry.is_low_quality
            )
            all_examples.append(example)
        
        # Filter by similarity threshold
        threshold_examples = [
            ex for ex in all_examples 
            if ex.similarity_score >= similarity_threshold
        ]
        
        if not threshold_examples:
            logger.info(f"No examples found above similarity threshold {similarity_threshold}")
            return []
        
        # Separate positive and negative examples
        positive_examples = [ex for ex in threshold_examples if ex.is_positive_example]
        negative_examples = [ex for ex in threshold_examples if ex.is_negative_example]
        
        # Select best examples - positive and negative work independently
        selected_examples = []
        
        # Add best positive example if available
        if positive_examples:
            best_positive = max(positive_examples, key=lambda x: x.similarity_score)
            selected_examples.append(best_positive)
        
        # Add best negative example if available
        if negative_examples:
            best_negative = max(negative_examples, key=lambda x: x.similarity_score)
            selected_examples.append(best_negative)
        
        # Add remaining best examples up to max_examples
        remaining_examples = [
            ex for ex in threshold_examples 
            if ex not in selected_examples
        ]
        remaining_examples.sort(key=lambda x: x.similarity_score, reverse=True)
        
        selected_examples.extend(remaining_examples[:max_examples - len(selected_examples)])
        
        # Sort final results by similarity score
        selected_examples.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # Log detailed feedback retrieval information
        if selected_examples:
            logger.info(f"Retrieved {len(selected_examples)} feedback examples for {message_type} "
                       f"(threshold: {similarity_threshold}, positive: {len(positive_examples)}, "
                       f"negative: {len(negative_examples)})")
            
            # Create detailed feedback retrieval log
            self._log_feedback_retrieval(
                user_input=user_input,
                conversation_history=conversation_history,
                message_type=message_type,
                selected_examples=selected_examples,
                similarity_threshold=similarity_threshold,
                all_examples_count=len(all_examples),
                threshold_examples_count=len(threshold_examples)
            )
        else:
            logger.info(f"No examples found above similarity threshold {similarity_threshold}")
        
        return selected_examples
    
    def _log_feedback_retrieval(
        self, 
        user_input: str, 
        conversation_history: List[Dict[str, str]], 
        message_type: str,
        selected_examples: List['FeedbackExample'],
        similarity_threshold: float,
        all_examples_count: int,
        threshold_examples_count: int
    ) -> None:
        """Log detailed feedback retrieval information."""
        import json
        from datetime import datetime
        
        # Create detailed log entry
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "message_type": message_type,
            "user_input": user_input,
            "conversation_history": conversation_history,
            "similarity_threshold": similarity_threshold,
            "search_stats": {
                "total_candidates": all_examples_count,
                "above_threshold": threshold_examples_count,
                "selected": len(selected_examples)
            },
            "selected_examples": []
        }
        
        # Add details for each selected example
        for i, example in enumerate(selected_examples):
            example_log = {
                "rank": i + 1,
                "similarity_score": float(example.similarity_score),  # Convert numpy float32 to Python float
                "is_positive": example.is_positive_example,
                "is_negative": example.is_negative_example,
                "rating": example.entry.rating,
                "organism": example.entry.organism,
                "case_id": example.entry.case_id,
                "rated_message": example.entry.rated_message,
                "feedback_text": example.entry.feedback_text,
                "replacement_text": example.entry.replacement_text,
                "embedding_text": example.text
            }
            log_entry["selected_examples"].append(example_log)
        
        # Log to feedback retrieval log file (detailed JSON)
        log_file = self.feedback_dir / "logs" / "feedback_retrieval.log"
        log_file.parent.mkdir(exist_ok=True)
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, indent=2, ensure_ascii=False) + "\n\n")
        
        # Also create a human-readable summary log
        self._log_feedback_summary(
            user_input=user_input,
            message_type=message_type,
            selected_examples=selected_examples,
            similarity_threshold=similarity_threshold,
            threshold_examples_count=threshold_examples_count
        )
        
        # Also log a summary to the main logger
        logger.info(f"Feedback retrieval logged: {len(selected_examples)} examples selected "
                   f"for '{user_input[:50]}...' (scores: {[f'{ex.similarity_score:.3f}' for ex in selected_examples]})")
    
    def _log_feedback_summary(
        self,
        user_input: str,
        message_type: str,
        selected_examples: List['FeedbackExample'],
        similarity_threshold: float,
        threshold_examples_count: int
    ) -> None:
        """Create a human-readable summary log of feedback retrieval."""
        from datetime import datetime
        
        summary_file = self.feedback_dir / "logs" / "feedback_summary.log"
        summary_file.parent.mkdir(exist_ok=True)
        
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"FEEDBACK RETRIEVAL - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*80}\n")
            f.write(f"Message Type: {message_type}\n")
            f.write(f"User Input: {user_input}\n")
            f.write(f"Similarity Threshold: {similarity_threshold}\n")
            f.write(f"Candidates Above Threshold: {threshold_examples_count}\n")
            f.write(f"Selected Examples: {len(selected_examples)}\n")
            f.write(f"\n{'-'*40}\n")
            
            for i, example in enumerate(selected_examples, 1):
                f.write(f"\nEXAMPLE {i}:\n")
                f.write(f"  Similarity Score: {example.similarity_score:.4f}\n")
                f.write(f"  Quality: {'POSITIVE' if example.is_positive_example else 'NEGATIVE' if example.is_negative_example else 'NEUTRAL'}\n")
                f.write(f"  Rating: {example.entry.rating}/5\n")
                f.write(f"  Organism: {example.entry.organism}\n")
                f.write(f"  Case ID: {example.entry.case_id}\n")
                f.write(f"  Rated Message: {example.entry.rated_message[:200]}...\n")
                if example.entry.feedback_text:
                    f.write(f"  Feedback: {example.entry.feedback_text}\n")
                if example.entry.replacement_text:
                    f.write(f"  Replacement: {example.entry.replacement_text}\n")
                f.write(f"\n")
            
            f.write(f"{'='*80}\n\n")
    
def create_feedback_retriever(feedback_dir: str) -> FeedbackRetriever:
    """Create and initialize feedback retriever."""
    return FeedbackRetriever(feedback_dir)
