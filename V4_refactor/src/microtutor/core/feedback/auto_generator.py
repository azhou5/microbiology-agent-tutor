"""
Automatic FAISS index generation service.

This service automatically generates and updates FAISS indices from database feedback
data, enabling continuous improvement of the feedback system.
"""

import logging
import pickle
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from contextlib import contextmanager
import faiss
import numpy as np

from microtutor.core.feedback.database_loader import DatabaseFeedbackLoader, DatabaseFeedbackConfig
from microtutor.core.feedback.processor import FeedbackProcessor, FeedbackEntry
from microtutor.utils.embedding_utils import get_embedding

logger = logging.getLogger(__name__)


@contextmanager
def get_db_session():
    """Get database session with proper cleanup.
    
    This is a proper context manager that ensures the database session
    is closed after use, unlike using next(get_db()) which leaks connections.
    
    Yields:
        Database session or None if not configured
    """
    from microtutor.api.dependencies import get_db
    
    db_gen = get_db()
    db = next(db_gen)
    try:
        yield db
    finally:
        # Properly close the generator to trigger cleanup
        try:
            next(db_gen)
        except StopIteration:
            pass


def get_project_root() -> Path:
    """Get the project root directory (V4_refactor).
    
    This ensures paths work correctly regardless of current working directory.
    """
    # Navigate from src/microtutor/core/feedback to V4_refactor
    return Path(__file__).parent.parent.parent.parent.parent


class AutoFAISSGenerator:
    """Automatically generates and updates FAISS indices from database feedback."""
    
    def __init__(self, output_dir: Optional[str] = None):
        """Initialize auto FAISS generator.
        
        Args:
            output_dir: Directory to store generated FAISS indices.
                       Defaults to data/feedback_auto in project root.
        """
        if output_dir is None:
            # Use absolute path relative to project root
            self.output_dir = get_project_root() / "data" / "feedback_auto"
        else:
            self.output_dir = Path(output_dir)
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"AutoFAISSGenerator initialized with output_dir: {self.output_dir}")
        
        self.processor = FeedbackProcessor()
        self.last_update = None
        self.update_interval = timedelta(hours=6)  # Update every 6 hours
        
        # Index metadata
        self.index_metadata = {
            "last_updated": None,
            "total_entries": 0,
            "regular_feedback_count": 0,
            "case_feedback_count": 0,
            "min_rating": 1,
            "max_rating": 5
        }
    
    def should_update(self) -> bool:
        """Check if indices should be updated based on time and data changes."""
        if self.last_update is None:
            return True
        
        # Check if enough time has passed
        if datetime.now() - self.last_update > self.update_interval:
            return True
        
        # Check if there's new data in the database
        try:
            with get_db_session() as db:
                if db is None:
                    return False
                
                loader = DatabaseFeedbackLoader(db)
                stats = loader.get_feedback_stats()
                
                total_entries = stats["regular_feedback"]["total_count"] + stats["case_feedback"]["total_count"]
                
                if total_entries > self.index_metadata["total_entries"]:
                    logger.info(f"New feedback data detected: {total_entries} total entries (was {self.index_metadata['total_entries']})")
                    return True
                
                return False
            
        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
            return False
    
    def generate_indices(
        self, 
        force_update: bool = False,
        config: Optional[DatabaseFeedbackConfig] = None
    ) -> Dict[str, Any]:
        """Generate FAISS indices from database feedback.
        
        Args:
            force_update: Force update even if not needed
            config: Configuration for loading feedback data
            
        Returns:
            Dictionary with generation results
        """
        if not force_update and not self.should_update():
            logger.info("No update needed for FAISS indices")
            return {"status": "skipped", "reason": "no_update_needed"}
        
        # Check if we can do incremental update
        if not force_update and self._can_do_incremental_update():
            return self._incremental_update(config)
        
        # Fall back to full regeneration
        return self._full_regeneration(config)
    
    def _full_regeneration(self, config: Optional[DatabaseFeedbackConfig] = None) -> Dict[str, Any]:
        """Perform full regeneration of FAISS indices."""
        try:
            # Get database session with proper context manager
            with get_db_session() as db:
                if db is None:
                    raise Exception("Database not available")
                
                loader = DatabaseFeedbackLoader(db)
                
                if config is None:
                    config = DatabaseFeedbackConfig(
                        min_rating=1,
                        include_regular_feedback=True,
                        include_case_feedback=True
                    )
                
                # Load feedback entries
                logger.info("Loading feedback entries from database...")
                entries = loader.load_feedback_entries(config)
                
                if not entries:
                    logger.warning("No feedback entries found in database")
                    return {"status": "failed", "reason": "no_entries"}
                
                # Update processor with new entries
                self.processor.entries = entries
            
            # Generate different types of indices (outside db session - don't need db anymore)
            results = {}
            
            # All feedback index
            logger.info("Generating all feedback index...")
            all_index, all_texts, all_entries = self.processor.create_faiss_index(
                output_dir=str(self.output_dir),
                batch_size=32
            )
            results["all"] = {
                "index_path": str(self.output_dir / "feedback_index.faiss"),
                "texts_path": str(self.output_dir / "feedback_texts.pkl"),
                "entries_path": str(self.output_dir / "feedback_entries.pkl"),
                "count": len(all_entries)
            }
            
            # Patient feedback index (rating >= 3)
            logger.info("Generating patient feedback index...")
            patient_index, patient_texts, patient_entries = self.processor.create_faiss_index(
                output_dir=str(self.output_dir / "patient"),
                batch_size=32,
                filter_by_type="patient",
                min_rating=3
            )
            results["patient"] = {
                "index_path": str(self.output_dir / "patient" / "feedback_index.faiss"),
                "texts_path": str(self.output_dir / "patient" / "feedback_texts.pkl"),
                "entries_path": str(self.output_dir / "patient" / "feedback_entries.pkl"),
                "count": len(patient_entries)
            }
            
            # Tutor feedback index (rating >= 3)
            logger.info("Generating tutor feedback index...")
            tutor_index, tutor_texts, tutor_entries = self.processor.create_faiss_index(
                output_dir=str(self.output_dir / "tutor"),
                batch_size=32,
                filter_by_type="tutor",
                min_rating=3
            )
            results["tutor"] = {
                "index_path": str(self.output_dir / "tutor" / "feedback_index.faiss"),
                "texts_path": str(self.output_dir / "tutor" / "feedback_texts.pkl"),
                "entries_path": str(self.output_dir / "tutor" / "feedback_entries.pkl"),
                "count": len(tutor_entries)
            }
            
            # Update metadata
            self.last_update = datetime.now()
            self.index_metadata.update({
                "last_updated": self.last_update.isoformat(),
                "total_entries": len(entries),
                "regular_feedback_count": len([e for e in entries if e.message_type != "case_feedback"]),
                "case_feedback_count": len([e for e in entries if e.message_type == "case_feedback"]),
                "min_rating": min(e.rating for e in entries) if entries else 1,
                "max_rating": max(e.rating for e in entries) if entries else 5
            })
            
            # Save metadata
            self._save_metadata()
            
            # Signal that indices have been updated (for live reload)
            self._notify_index_updated()
            
            logger.info(f"Successfully generated FAISS indices with {len(entries)} total entries")
            return {
                "status": "success",
                "results": results,
                "metadata": self.index_metadata,
                "incremental": False
            }
            
        except Exception as e:
            logger.error(f"Failed to generate FAISS indices: {e}")
            return {"status": "failed", "reason": str(e)}
    
    def _save_metadata(self) -> None:
        """Save index metadata to file."""
        try:
            metadata_path = self.output_dir / "index_metadata.json"
            import json
            with open(metadata_path, 'w') as f:
                json.dump(self.index_metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
    
    def _notify_index_updated(self) -> None:
        """Notify the AutoFeedbackRetriever to reload indices.
        
        This ensures that the in-memory FAISS indices are refreshed
        after new feedback is added and re-indexed.
        """
        try:
            from microtutor.core.feedback.auto_retriever import get_auto_feedback_retriever
            retriever = get_auto_feedback_retriever()
            retriever.refresh_indices()
            logger.info("AutoFeedbackRetriever indices refreshed after update")
        except Exception as e:
            logger.warning(f"Failed to notify retriever of index update: {e}")
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load index metadata from file."""
        try:
            metadata_path = self.output_dir / "index_metadata.json"
            if metadata_path.exists():
                import json
                with open(metadata_path, 'r') as f:
                    self.index_metadata = json.load(f)
                    if self.index_metadata.get("last_updated"):
                        self.last_update = datetime.fromisoformat(self.index_metadata["last_updated"])
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the auto FAISS generator."""
        self.load_metadata()
        
        return {
            "last_update": self.index_metadata.get("last_updated"),
            "total_entries": self.index_metadata.get("total_entries", 0),
            "regular_feedback_count": self.index_metadata.get("regular_feedback_count", 0),
            "case_feedback_count": self.index_metadata.get("case_feedback_count", 0),
            "min_rating": self.index_metadata.get("min_rating", 1),
            "max_rating": self.index_metadata.get("max_rating", 5),
            "should_update": self.should_update(),
            "index_files_exist": {
                "all": (self.output_dir / "feedback_index.faiss").exists(),
                "patient": (self.output_dir / "patient" / "feedback_index.faiss").exists(),
                "tutor": (self.output_dir / "tutor" / "feedback_index.faiss").exists()
            }
        }
    
    def cleanup_old_indices(self, keep_days: int = 7) -> None:
        """Clean up old index files to save space."""
        try:
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            
            for index_file in self.output_dir.rglob("*.faiss"):
                if index_file.stat().st_mtime < cutoff_date.timestamp():
                    logger.info(f"Removing old index file: {index_file}")
                    index_file.unlink()
            
            for pkl_file in self.output_dir.rglob("*.pkl"):
                if pkl_file.stat().st_mtime < cutoff_date.timestamp():
                    logger.info(f"Removing old pickle file: {pkl_file}")
                    pkl_file.unlink()
                    
        except Exception as e:
            logger.error(f"Failed to cleanup old indices: {e}")
    
    def _can_do_incremental_update(self) -> bool:
        """Check if we can do an incremental update instead of full regeneration."""
        try:
            # Check if existing indices exist
            all_index_path = self.output_dir / "feedback_index.faiss"
            if not all_index_path.exists():
                return False
            
            # Check if metadata exists
            metadata_path = self.output_dir / "index_metadata.json"
            if not metadata_path.exists():
                return False
            
            # Load current metadata
            import json
            with open(metadata_path, 'r') as f:
                current_metadata = json.load(f)
            
            # Check if we have a last update timestamp
            if not current_metadata.get("last_updated"):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to check incremental update capability: {e}")
            return False
    
    def _incremental_update(self, config: Optional[DatabaseFeedbackConfig] = None) -> Dict[str, Any]:
        """Perform incremental update by only processing new feedback."""
        try:
            logger.info("Performing incremental FAISS update...")
            
            # Get database session with proper context manager
            with get_db_session() as db:
                if db is None:
                    raise Exception("Database not available")
                
                loader = DatabaseFeedbackLoader(db)
                
                if config is None:
                    config = DatabaseFeedbackConfig(
                        min_rating=1,
                        include_regular_feedback=True,
                        include_case_feedback=True
                    )
                
                # Load only new feedback since last update
                last_update = datetime.fromisoformat(self.index_metadata["last_updated"])
                config.days_back = None  # We'll use timestamp filtering instead
                
                # Load all feedback and filter by timestamp
                all_entries = loader.load_feedback_entries(config)
                new_entries = [e for e in all_entries if e.timestamp > last_update]
                
                if not new_entries:
                    logger.info("No new feedback since last update")
                    return {"status": "skipped", "reason": "no_new_feedback"}
                
                logger.info(f"Found {len(new_entries)} new feedback entries since {last_update}")
            
            # Load existing indices
            existing_indices = {}
            existing_texts = {}
            existing_entries = {}
            
            for index_type in ["all", "patient", "tutor"]:
                index_dir = self.output_dir if index_type == "all" else self.output_dir / index_type
                index_path = index_dir / "feedback_index.faiss"
                texts_path = index_dir / "feedback_texts.pkl"
                entries_path = index_dir / "feedback_entries.pkl"
                
                if all(p.exists() for p in [index_path, texts_path, entries_path]):
                    with open(index_path, 'rb') as f:
                        existing_indices[index_type] = pickle.load(f)
                    with open(texts_path, 'rb') as f:
                        existing_texts[index_type] = pickle.load(f)
                    with open(entries_path, 'rb') as f:
                        existing_entries[index_type] = pickle.load(f)
            
            # Process new entries
            self.processor.entries = new_entries
            
            # Generate embeddings for new entries only
            new_texts = []
            for entry in new_entries:
                text = self.processor.create_embedding_text(
                    entry, 
                    include_context=True, 
                    context_messages=0,
                    include_feedback=False,
                    include_replacement=False,
                    include_quality=True
                )
                new_texts.append(text)
            
            # Generate embeddings for new texts
            logger.info(f"Generating embeddings for {len(new_texts)} new entries...")
            new_embeddings = []
            for text in new_texts:
                embedding = get_embedding(text)
                new_embeddings.append(embedding)
            
            new_embeddings_array = np.array(new_embeddings).astype('float32')
            
            # Normalize new embeddings for cosine similarity
            faiss.normalize_L2(new_embeddings_array)
            
            # Update each index type
            results = {}
            for index_type in ["all", "patient", "tutor"]:
                if index_type not in existing_indices:
                    continue
                
                # Filter new entries for this index type
                if index_type == "patient":
                    filtered_entries = [e for e in new_entries if e.message_type in ['patient', 'other'] and e.rating >= 3]
                elif index_type == "tutor":
                    filtered_entries = [e for e in new_entries if e.message_type in ['tutor', 'other'] and e.rating >= 3]
                else:  # all
                    filtered_entries = new_entries
                
                if not filtered_entries:
                    logger.info(f"No new entries for {index_type} index")
                    continue
                
                # Get corresponding texts and embeddings
                filtered_texts = []
                filtered_embeddings = []
                for entry in filtered_entries:
                    idx = new_entries.index(entry)
                    filtered_texts.append(new_texts[idx])
                    filtered_embeddings.append(new_embeddings[idx])
                
                if not filtered_texts:
                    continue
                
                # Add to existing index
                existing_indices[index_type].add(np.array(filtered_embeddings).astype('float32'))
                existing_texts[index_type].extend(filtered_texts)
                existing_entries[index_type].extend(filtered_entries)
                
                # Save updated index
                index_dir = self.output_dir if index_type == "all" else self.output_dir / index_type
                index_dir.mkdir(parents=True, exist_ok=True)
                
                index_path = index_dir / "feedback_index.faiss"
                texts_path = index_dir / "feedback_texts.pkl"
                entries_path = index_dir / "feedback_entries.pkl"
                
                with open(index_path, 'wb') as f:
                    pickle.dump(existing_indices[index_type], f)
                with open(texts_path, 'wb') as f:
                    pickle.dump(existing_texts[index_type], f)
                with open(entries_path, 'wb') as f:
                    pickle.dump(existing_entries[index_type], f)
                
                results[index_type] = {
                    "index_path": str(index_path),
                    "texts_path": str(texts_path),
                    "entries_path": str(entries_path),
                    "count": len(existing_entries[index_type]),
                    "new_entries": len(filtered_entries)
                }
                
                logger.info(f"Updated {index_type} index with {len(filtered_entries)} new entries (total: {len(existing_entries[index_type])})")
            
            # Update metadata
            self.last_update = datetime.now()
            self.index_metadata.update({
                "last_updated": self.last_update.isoformat(),
                "total_entries": len(all_entries),
                "regular_feedback_count": len([e for e in all_entries if e.message_type != "case_feedback"]),
                "case_feedback_count": len([e for e in all_entries if e.message_type == "case_feedback"]),
                "min_rating": min(e.rating for e in all_entries) if all_entries else 1,
                "max_rating": max(e.rating for e in all_entries) if all_entries else 5
            })
            
            self._save_metadata()
            
            # Signal that indices have been updated (for live reload)
            self._notify_index_updated()
            
            logger.info(f"Incremental update completed with {len(new_entries)} new entries")
            return {
                "status": "success",
                "results": results,
                "metadata": self.index_metadata,
                "incremental": True,
                "new_entries": len(new_entries)
            }
            
        except Exception as e:
            logger.error(f"Incremental update failed: {e}")
            # Fall back to full regeneration
            logger.info("Falling back to full regeneration...")
            return self._full_regeneration(config)


# Global instance
_auto_faiss_generator = None

def get_auto_faiss_generator() -> AutoFAISSGenerator:
    """Get the global auto FAISS generator instance."""
    global _auto_faiss_generator
    if _auto_faiss_generator is None:
        _auto_faiss_generator = AutoFAISSGenerator()
    return _auto_faiss_generator
