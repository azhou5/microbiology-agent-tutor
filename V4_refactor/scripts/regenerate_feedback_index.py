#!/usr/bin/env python3
"""
Standalone script to regenerate FAISS feedback indices from database.

This script directly accesses the database and creates FAISS indices
without importing the full microtutor package (avoiding circular imports).

Usage:
    python regenerate_feedback_index.py
    python regenerate_feedback_index.py --force  # Force full regeneration
"""

import os
import sys
import json
import pickle
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

import numpy as np
import faiss
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from tqdm import tqdm

# Script directory
SCRIPT_DIR = Path(__file__).parent.absolute()

# Load environment
env_path = SCRIPT_DIR / 'dot_env_microtutor.txt'
if env_path.exists():
    load_dotenv(dotenv_path=str(env_path))
    print(f"✅ Loaded environment from: {env_path}")


@dataclass
class FeedbackEntry:
    """Simplified feedback entry for indexing."""
    id: str
    timestamp: datetime
    organism: str
    rating: int
    rated_message: str
    feedback_text: Optional[str]
    replacement_text: Optional[str]
    chat_history: List[Dict[str, str]]
    case_id: str
    message_type: str
    
    @property
    def is_high_quality(self) -> bool:
        return self.rating >= 4
    
    @property
    def is_low_quality(self) -> bool:
        return self.rating <= 2


def get_database_url() -> str:
    """Get database URL from environment."""
    use_global = os.getenv("USE_GLOBAL_DB", "True").lower() == "true"
    
    if use_global:
        return os.getenv(
            "GLOBAL_DATABASE_URL",
            'postgresql://microllm_user:t6f7TKRdLESfZ3NdBZUFiZJUi5rE7spQ@dpg-d0m0210dl3ps73bsbmu0-a/microllm'
        )
    else:
        return os.getenv(
            "LOCAL_DATABASE_URL",
            'postgresql://postgres:postgres@localhost:5432/microbiology_feedback'
        )


def get_embedding(text: str) -> List[float]:
    """Get embedding for text using OpenAI API."""
    from openai import OpenAI, AzureOpenAI
    
    use_azure = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"
    
    if use_azure:
        client = AzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        )
        model = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
    else:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = "text-embedding-3-small"
    
    response = client.embeddings.create(input=text, model=model)
    return response.data[0].embedding


def determine_message_type(message: str) -> str:
    """Determine if message is from patient or tutor."""
    if not message:
        return "other"
    
    message_lower = message.lower()
    
    patient_keywords = ["patient", "symptoms", "complaints", "history", "vital signs", 
                       "physical exam", "chief complaint", "presenting", "feeling"]
    tutor_keywords = ["diagnosis", "treatment", "management", "recommendation",
                     "suggest", "consider", "approach", "strategy", "plan"]
    
    patient_score = sum(1 for kw in patient_keywords if kw in message_lower)
    tutor_score = sum(1 for kw in tutor_keywords if kw in message_lower)
    
    if patient_score > tutor_score:
        return "patient"
    elif tutor_score > patient_score:
        return "tutor"
    return "other"


def load_feedback_from_database(engine) -> List[FeedbackEntry]:
    """Load feedback entries from database."""
    entries = []
    
    # Load regular feedback
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, timestamp, organism, rating, rated_message, 
                   feedback_text, replacement_text, case_id
            FROM feedback
            ORDER BY timestamp DESC
        """))
        
        for row in result.fetchall():
            try:
                entry = FeedbackEntry(
                    id=str(row[0]),
                    timestamp=row[1],
                    organism=row[2] or "",
                    rating=int(row[3]) if row[3] else 3,
                    rated_message=row[4] or "",
                    feedback_text=row[5] or "",
                    replacement_text=row[6] or "",
                    chat_history=[],
                    case_id=row[7] or "",
                    message_type=determine_message_type(row[4] or "")
                )
                entries.append(entry)
            except Exception as e:
                print(f"⚠️  Failed to parse entry {row[0]}: {e}")
    
    # Load case feedback
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, timestamp, organism, detail_rating, helpfulness_rating,
                   accuracy_rating, comments, case_id
            FROM case_feedback
            ORDER BY timestamp DESC
        """))
        
        for row in result.fetchall():
            try:
                avg_rating = (int(row[3]) + int(row[4]) + int(row[5])) / 3
                entry = FeedbackEntry(
                    id=f"case_{row[0]}",
                    timestamp=row[1],
                    organism=row[2] or "",
                    rating=int(avg_rating),
                    rated_message=f"Case feedback: {row[6] or ''}",
                    feedback_text=row[6] or "",
                    replacement_text="",
                    chat_history=[],
                    case_id=row[7] or "",
                    message_type="case_feedback"
                )
                entries.append(entry)
            except Exception as e:
                print(f"⚠️  Failed to parse case entry {row[0]}: {e}")
    
    return entries


def create_embedding_text(entry: FeedbackEntry) -> str:
    """Create text for embedding from feedback entry."""
    return entry.rated_message


def create_faiss_index(
    entries: List[FeedbackEntry],
    output_dir: Path,
    filter_type: Optional[str] = None,
    min_rating: Optional[int] = None
) -> int:
    """Create FAISS index from entries."""
    
    # Filter entries
    filtered = entries
    if filter_type:
        if filter_type == "patient":
            filtered = [e for e in filtered if e.message_type in ['patient', 'other']]
        elif filter_type == "tutor":
            filtered = [e for e in filtered if e.message_type in ['tutor', 'other']]
    if min_rating:
        filtered = [e for e in filtered if e.rating >= min_rating]
    
    if not filtered:
        print(f"  ⚠️  No entries after filtering for {filter_type or 'all'}")
        return 0
    
    print(f"  Creating index for {len(filtered)} entries...")
    
    # Create embedding texts
    texts = [create_embedding_text(e) for e in filtered]
    valid_entries = []
    valid_texts = []
    
    for entry, text in zip(filtered, texts):
        if text and text.strip():
            valid_entries.append(entry)
            valid_texts.append(text)
    
    if not valid_texts:
        print(f"  ⚠️  No valid texts for {filter_type or 'all'}")
        return 0
    
    # Generate embeddings
    print(f"  Generating embeddings for {len(valid_texts)} entries...")
    embeddings = []
    for text in tqdm(valid_texts, desc="  Embeddings"):
        try:
            emb = get_embedding(text)
            embeddings.append(emb)
        except Exception as e:
            print(f"  ⚠️  Embedding failed: {e}")
            embeddings.append([0.0] * 1536)
    
    # Create FAISS index
    embeddings_array = np.array(embeddings).astype('float32')
    faiss.normalize_L2(embeddings_array)
    
    embedding_dim = embeddings_array.shape[1]
    index = faiss.IndexFlatIP(embedding_dim)
    index.add(embeddings_array)
    
    # Save
    output_dir.mkdir(parents=True, exist_ok=True)
    
    faiss.write_index(index, str(output_dir / "feedback_index.faiss"))
    
    with open(output_dir / "feedback_texts.pkl", 'wb') as f:
        pickle.dump(valid_texts, f)
    
    with open(output_dir / "feedback_entries.pkl", 'wb') as f:
        pickle.dump(valid_entries, f)
    
    print(f"  ✅ Saved {len(valid_entries)} entries to {output_dir}")
    return len(valid_entries)


def main():
    parser = argparse.ArgumentParser(description='Regenerate FAISS feedback indices')
    parser.add_argument('--force', action='store_true', help='Force regeneration')
    args = parser.parse_args()
    
    print("\n🔄 Regenerating FAISS Feedback Indices")
    print("=" * 50)
    
    # Connect to database
    db_url = get_database_url()
    if "localhost" not in db_url and "127.0.0.1" not in db_url:
        db_url = db_url + "?sslmode=require"
    
    print(f"\n📊 Connecting to database...")
    engine = create_engine(db_url, pool_pre_ping=True)
    
    # Test connection
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM feedback"))
        count = result.fetchone()[0]
        print(f"✅ Connected - {count} feedback entries in database")
    
    # Load entries
    print(f"\n📥 Loading entries from database...")
    entries = load_feedback_from_database(engine)
    print(f"✅ Loaded {len(entries)} total entries")
    
    if not entries:
        print("❌ No entries to index")
        return 1
    
    # Output directory
    output_dir = SCRIPT_DIR / "data" / "feedback_auto"
    
    # Create indices
    print(f"\n🔨 Creating FAISS indices...")
    
    # All feedback
    all_count = create_faiss_index(entries, output_dir)
    
    # Patient feedback (rating >= 3)
    patient_count = create_faiss_index(
        entries, output_dir / "patient",
        filter_type="patient", min_rating=3
    )
    
    # Tutor feedback (rating >= 3)
    tutor_count = create_faiss_index(
        entries, output_dir / "tutor",
        filter_type="tutor", min_rating=3
    )
    
    # Save metadata
    metadata = {
        "last_updated": datetime.now().isoformat(),
        "total_entries": len(entries),
        "regular_feedback_count": len([e for e in entries if e.message_type != "case_feedback"]),
        "case_feedback_count": len([e for e in entries if e.message_type == "case_feedback"]),
        "min_rating": min(e.rating for e in entries) if entries else 1,
        "max_rating": max(e.rating for e in entries) if entries else 5
    }
    
    with open(output_dir / "index_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n✅ Index regeneration complete!")
    print(f"   - All: {all_count} entries")
    print(f"   - Patient: {patient_count} entries")
    print(f"   - Tutor: {tutor_count} entries")
    print(f"   - Metadata saved to: {output_dir / 'index_metadata.json'}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
