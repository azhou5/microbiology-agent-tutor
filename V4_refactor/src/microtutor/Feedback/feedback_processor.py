"""
Enhanced feedback data processor for JSON feedback format.
Processes feedback data and creates embeddings for FAISS retrieval.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import logging
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import faiss
import pickle
from tqdm import tqdm

from microtutor.utils.embedding_utils import get_embedding

logger = logging.getLogger(__name__)


@dataclass
class FeedbackEntry:
    """Structured feedback entry."""
    id: int
    timestamp: datetime
    organism: str
    rating: int
    rated_message: str
    feedback_text: Optional[str]
    replacement_text: Optional[str]
    chat_history: List[Dict[str, str]]
    case_id: str
    message_type: str  # 'patient' or 'tutor'
    
    @property
    def is_high_quality(self) -> bool:
        """Check if this is a high-quality example (rating >= 4)."""
        return self.rating >= 4
    
    @property
    def is_low_quality(self) -> bool:
        """Check if this is a low-quality example (rating <= 2)."""
        return self.rating <= 2


class FeedbackProcessor:
    """Processes feedback data and creates FAISS indices."""
    
    def __init__(self, embedding_model: str = "text-embedding-3-small"):
        """Initialize feedback processor."""
        self.embedding_model = embedding_model
        self.entries: List[FeedbackEntry] = []
    
    def load_feedback_from_json(self, json_file_path: str) -> List[FeedbackEntry]:
        """Load feedback entries from JSON file."""
        logger.info(f"Loading feedback from {json_file_path}")
        
        with open(json_file_path, 'r') as f:
            data = json.load(f)
        
        entries = []
        for item in data.get('feedback', []):
            try:
                # Parse chat history
                chat_history = []
                if item.get('chat_history'):
                    if isinstance(item['chat_history'], str):
                        chat_history = json.loads(item['chat_history'])
                    else:
                        chat_history = item['chat_history']
                
                # Determine message type based on content
                message_type = self._determine_message_type(item['rated_message'])
                
                entry = FeedbackEntry(
                    id=item['id'],
                    timestamp=datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00')),
                    organism=item['organism'],
                    rating=int(item['rating']),
                    rated_message=item['rated_message'],
                    feedback_text=item.get('feedback_text'),
                    replacement_text=item.get('replacement_text'),
                    chat_history=chat_history,
                    case_id=item['case_id'],
                    message_type=message_type
                )
                entries.append(entry)
                
            except Exception as e:
                logger.warning(f"Failed to parse feedback entry {item.get('id', 'unknown')}: {e}")
                continue
        
        self.entries = entries
        logger.info(f"Loaded {len(entries)} feedback entries")
        return entries
    
    def _determine_message_type(self, message: str) -> str:
        """Determine if message is from patient or tutor based on content."""
        message_lower = message.lower()
        
        # Check for explicit prefixes first
        if message_lower.startswith('patient:') or 'patient:' in message_lower:
            return 'patient'
        elif message_lower.startswith('tutor:') or 'tutor:' in message_lower:
            return 'tutor'
        # Check for JSON format with patient/tutor keys
        elif '{"patient":' in message_lower or '"patient":' in message_lower:
            return 'patient'
        elif '{"tutor":' in message_lower or '"tutor":' in message_lower:
            return 'tutor'
        else:
            # If not obviously one or the other, classify as 'other'
            return 'other'
    def create_embedding_text(
        self, 
        entry: FeedbackEntry, 
        include_context: bool = True,
        context_messages: int = 0,  # Default to 0 = just last user input
        include_feedback: bool = False,
        include_replacement: bool = False,
        include_quality: bool = True
    ) -> str:
        """Create text for embedding from feedback entry.
        
        Args:
            entry: The feedback entry to create embedding text for
            include_context: Whether to include chat history context
            context_messages: Number of recent messages to include (0 = just last user input)
            include_feedback: Whether to include expert feedback text
            include_replacement: Whether to include replacement text
            include_quality: Whether to include quality rating information
        """
        parts = []
        
        # Add recent chat history for context
        if include_context and entry.chat_history:
            if context_messages == 0:
                # Just include the last user input before the rated response
                for msg in reversed(entry.chat_history):
                    if 'role' in msg and 'content' in msg and msg['role'] == 'user':
                        parts.append(f"User input: {msg['content']}")
                        break
            else:
                # Include last k back-and-forth messages
                parts.append("Recent conversation context:")
                for msg in entry.chat_history[-context_messages:]:
                    if 'role' in msg and 'content' in msg:
                        parts.append(f"{msg['role']}: {msg['content']}")
        
        # For better similarity matching, we'll keep the embedding text minimal
        # and only include the user input part. The rated message and other context
        # will be available in the FeedbackExample object for display purposes.
        
        # Don't add quality rating to embedding text for better similarity matching
        # Quality filtering will be done after retrieval
        
        return "\n".join(parts)
    def create_faiss_index(
        self, 
        output_dir: str,
        batch_size: int = 32,
        filter_by_type: Optional[str] = None,
        min_rating: Optional[int] = None
    ) -> Tuple[faiss.Index, List[str], List[FeedbackEntry]]:
        """Create FAISS index from feedback entries."""
        logger.info("Creating FAISS index from feedback entries")
        
        # Filter entries if needed
        filtered_entries = self.entries
        if filter_by_type:
            # Include 'other' entries in both patient and tutor indices
            if filter_by_type == "patient":
                filtered_entries = [e for e in filtered_entries if e.message_type in ['patient', 'other']]
            elif filter_by_type == "tutor":
                filtered_entries = [e for e in filtered_entries if e.message_type in ['tutor', 'other']]
            else:
                filtered_entries = [e for e in filtered_entries if e.message_type == filter_by_type]
        if min_rating is not None:
            filtered_entries = [e for e in filtered_entries if e.rating >= min_rating]
        
        logger.info(f"Using {len(filtered_entries)} entries for indexing")
        
        if not filtered_entries:
            raise ValueError("No entries to index after filtering")
        
        # Create embedding texts - use only last user input for embedding
        texts = []
        for entry in filtered_entries:
            text = self.create_embedding_text(
                entry, 
                include_context=True, 
                context_messages=0,  # Only last user input
                include_feedback=False,  # Don't include feedback in embedding
                include_replacement=False,  # Don't include replacement in embedding
                include_quality=True  # Include quality for filtering
            )
            texts.append(text)
        
        # Get embedding dimension
        sample_embedding = get_embedding(texts[0])
        embedding_dim = len(sample_embedding)
        logger.info(f"Embedding dimension: {embedding_dim}")
        
        # Generate embeddings in batches
        embeddings = []
        for i in tqdm(range(0, len(texts), batch_size), desc="Generating embeddings"):
            batch = texts[i:i+batch_size]
            try:
                batch_embeddings = [get_embedding(text) for text in batch]
                embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"Batch embedding failed: {e}")
                # Use zero embeddings as fallback
                embeddings.extend([np.zeros(embedding_dim) for _ in batch])
        
        # Create FAISS index
        embeddings_array = np.array(embeddings).astype('float32')
        index = faiss.IndexFlatL2(embedding_dim)
        index.add(embeddings_array)
        
        # Save index and metadata
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        index_path = output_path / "feedback_index.faiss"
        texts_path = output_path / "feedback_texts.pkl"
        entries_path = output_path / "feedback_entries.pkl"
        
        with open(index_path, 'wb') as f:
            pickle.dump(index, f)
        
        with open(texts_path, 'wb') as f:
            pickle.dump(texts, f)
        
        with open(entries_path, 'wb') as f:
            pickle.dump(filtered_entries, f)
        
        logger.info(f"Saved FAISS index to {index_path}")
        logger.info(f"Index contains {index.ntotal} vectors")
        
        return index, texts, filtered_entries


def process_feedback_json(
    json_file_path: str,
    output_dir: str,
    message_type: Optional[str] = None,
    min_rating: Optional[int] = None
) -> Tuple[faiss.Index, List[str], List[FeedbackEntry]]:
    """Convenience function to process feedback JSON and create FAISS index."""
    processor = FeedbackProcessor()
    processor.load_feedback_from_json(json_file_path)
    return processor.create_faiss_index(
        output_dir=output_dir,
        filter_by_type=message_type,
        min_rating=min_rating
    )


if __name__ == "__main__":
    # Example usage
    json_file = "/Users/riccardoconci/Library/Mobile Documents/com~apple~CloudDocs/HQ_2024/Projects/2024_Harvard_AIM/Research/MicroTutor/feedback_202509211048.json"
    output_dir = "/Users/riccardoconci/Library/Mobile Documents/com~apple~CloudDocs/HQ_2024/Projects/2024_Harvard_AIM/Research/MicroTutor/microbiology-agent-tutor/V4_refactor/data/feedback"
    
    # Process all feedback
    index, texts, entries = process_feedback_json(json_file, output_dir)
    
    # Process only patient feedback with rating >= 3
    patient_index, patient_texts, patient_entries = process_feedback_json(
        json_file, 
        f"{output_dir}/patient", 
        message_type="patient", 
        min_rating=3
    )
    
    # Process only tutor feedback with rating >= 3
    tutor_index, tutor_texts, tutor_entries = process_feedback_json(
        json_file, 
        f"{output_dir}/tutor", 
        message_type="tutor", 
        min_rating=3
    )
