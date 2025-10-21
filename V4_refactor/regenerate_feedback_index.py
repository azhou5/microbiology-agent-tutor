#!/usr/bin/env python3
"""
Regenerate FAISS feedback index from database with improved filtering.
This script fixes the issue where entries without valid user input were being included.
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, 'src')

# Load environment
load_dotenv('dot_env_microtutor.txt')

from microtutor.feedback.feedback_processor import FeedbackProcessor, FeedbackEntry
from microtutor.core.config_helper import config
import json
from datetime import datetime
import logging
import psycopg2

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_feedback_from_database() -> list:
    """Load feedback entries from PostgreSQL database."""
    logger.info("Loading feedback entries from database...")
    
    # Connect to PostgreSQL
    db_url = os.getenv('GLOBAL_DATABASE_URL')
    if not db_url:
        raise ValueError("GLOBAL_DATABASE_URL not found in environment")
    
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    # Query all feedback entries
    query = """
    SELECT id, rating, rated_message, feedback_text, replacement_text, 
           chat_history, case_id, timestamp
    FROM feedback
    ORDER BY id
    """
    
    cursor.execute(query)
    results = cursor.fetchall()
    logger.info(f"Found {len(results)} feedback entries in database")
    
    conn.close()
    
    entries = []
    for row in results:
        entry_id, rating, rated_message, feedback_text, replacement_text, chat_history_str, case_id, timestamp = row
        
        try:
            # Parse chat history - it might already be a list or a JSON string
            chat_history = []
            if chat_history_str:
                if isinstance(chat_history_str, list):
                    chat_history = chat_history_str
                else:
                    chat_history = json.loads(chat_history_str)
            
            # Determine message type
            message_type = "other"
            if rated_message.lower().startswith("patient:"):
                message_type = "patient"
            elif rated_message.lower().startswith("tutor:"):
                message_type = "tutor"
            
            entry = FeedbackEntry(
                id=entry_id,
                timestamp=timestamp if timestamp else datetime.now(),
                organism="unknown",  # Not stored in database
                rating=int(rating),
                rated_message=rated_message,
                feedback_text=feedback_text,
                replacement_text=replacement_text,
                chat_history=chat_history,
                case_id=case_id,
                message_type=message_type
            )
            entries.append(entry)
            
        except Exception as e:
            logger.warning(f"Failed to parse entry {entry_id}: {e}")
            continue
    
    logger.info(f"Successfully loaded {len(entries)} feedback entries")
    return entries

def main():
    """Regenerate FAISS index with improved filtering."""
    logger.info("="*80)
    logger.info("REGENERATING FAISS FEEDBACK INDEX")
    logger.info("="*80)
    
    # Load feedback from database
    entries = load_feedback_from_database()
    
    if not entries:
        logger.error("No feedback entries found in database")
        return 1
    
    # Initialize processor
    processor = FeedbackProcessor()
    processor.entries = entries
    
    # Create output directory
    output_dir = Path("data/feedback")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("Creating FAISS index with improved filtering...")
    
    try:
        # Create main index
        index, texts, valid_entries = processor.create_faiss_index(
            output_dir=str(output_dir),
            batch_size=32
        )
        
        logger.info(f"✅ Main index created with {len(valid_entries)} valid entries")
        
        # Create patient-specific index
        patient_output_dir = output_dir / "patient"
        patient_index, patient_texts, patient_entries = processor.create_faiss_index(
            output_dir=str(patient_output_dir),
            batch_size=32,
            filter_by_type="patient"
        )
        
        logger.info(f"✅ Patient index created with {len(patient_entries)} valid entries")
        
        # Create tutor-specific index
        tutor_output_dir = output_dir / "tutor"
        tutor_index, tutor_texts, tutor_entries = processor.create_faiss_index(
            output_dir=str(tutor_output_dir),
            batch_size=32,
            filter_by_type="tutor"
        )
        
        logger.info(f"✅ Tutor index created with {len(tutor_entries)} valid entries")
        
        # Summary
        logger.info("="*80)
        logger.info("REGENERATION COMPLETE")
        logger.info("="*80)
        logger.info(f"Total entries processed: {len(entries)}")
        logger.info(f"Valid entries for main index: {len(valid_entries)}")
        logger.info(f"Valid entries for patient index: {len(patient_entries)}")
        logger.info(f"Valid entries for tutor index: {len(tutor_entries)}")
        logger.info("="*80)
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to create FAISS index: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
