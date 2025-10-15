#!/usr/bin/env python3
"""
Extract training data from feedback chat histories.

This script extracts [user_input, llm_routing] pairs from the feedback data
to create a high-quality training dataset for the fast classifier.
"""

import json
import logging
import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple
import pandas as pd
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def classify_response_type(response_content: str) -> str:
    """Classify the response type based on content patterns.
    
    Args:
        response_content: The assistant's response content
        
    Returns:
        Classification: 'tutor_direct', 'patient', 'socratic', 'hint'
    """
    response_lower = response_content.lower()
    
    # Check for patient responses
    if response_lower.startswith("patient:") or "patient:" in response_lower:
        return "patient"
    
    # Check for socratic questioning patterns
    socratic_patterns = [
        "what do you think", "why do you think", "how would you", "what if",
        "consider", "suppose", "imagine", "what would happen if",
        "do you think", "what should", "what could", "what might"
    ]
    if any(pattern in response_lower for pattern in socratic_patterns):
        return "socratic"
    
    # Check for hint patterns
    hint_patterns = [
        "hint:", "clue:", "tip:", "suggestion:", "consider this:",
        "think about", "remember that", "keep in mind", "note that"
    ]
    if any(pattern in response_lower for pattern in hint_patterns):
        return "hint"
    
    # Check for tutor direct responses
    tutor_patterns = [
        "tutor:", "explanation:", "answer:", "the answer is",
        "based on", "according to", "this is because", "the reason is"
    ]
    if any(pattern in response_lower for pattern in tutor_patterns):
        return "tutor_direct"
    
    # Default to tutor_direct for other responses
    return "tutor_direct"


def extract_training_pairs(feedback_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract training pairs from feedback data.
    
    Args:
        feedback_data: The loaded feedback JSON data
        
    Returns:
        List of training examples
    """
    training_pairs = []
    
    for feedback_entry in feedback_data.get("feedback", []):
        try:
            # Parse chat history
            chat_history_str = feedback_entry.get("chat_history", "[]")
            if not chat_history_str:
                continue
                
            chat_history = json.loads(chat_history_str)
            
            # Extract user-assistant pairs
            for i in range(len(chat_history) - 1):
                current_msg = chat_history[i]
                next_msg = chat_history[i + 1]
                
                # Look for user -> assistant pairs
                if (current_msg.get("role") == "user" and 
                    next_msg.get("role") == "assistant"):
                    
                    user_input = current_msg.get("content", "").strip()
                    assistant_response = next_msg.get("content", "").strip()
                    
                    if user_input and assistant_response:
                        # Classify the response type
                        response_type = classify_response_type(assistant_response)
                        
                        # Create training example
                        training_example = {
                            "user_input": user_input,
                            "assistant_response": assistant_response,
                            "classification": response_type,
                            "confidence": 1.0,  # High confidence since it's real data
                            "organism": feedback_entry.get("organism", "unknown"),
                            "case_id": feedback_entry.get("case_id", "unknown"),
                            "timestamp": feedback_entry.get("timestamp", ""),
                            "rating": feedback_entry.get("rating", ""),
                            "feedback_text": feedback_entry.get("feedback_text", ""),
                            "replacement_text": feedback_entry.get("replacement_text", ""),
                            "response_length": len(assistant_response),
                            "input_length": len(user_input),
                            "has_question": "?" in user_input,
                            "has_medical_terms": any(term in user_input.lower() for term in [
                                "patient", "symptoms", "diagnosis", "treatment", "disease", "infection",
                                "fever", "pain", "nausea", "cough", "breathing", "temperature"
                            ])
                        }
                        
                        training_pairs.append(training_example)
                        
        except Exception as e:
            logger.warning(f"Failed to process feedback entry {feedback_entry.get('id', 'unknown')}: {e}")
            continue
    
    return training_pairs


def analyze_training_data(training_pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze the extracted training data.
    
    Args:
        training_pairs: List of training examples
        
    Returns:
        Analysis summary
    """
    if not training_pairs:
        return {"error": "No training data found"}
    
    # Basic counts
    total_pairs = len(training_pairs)
    
    # Classification distribution
    classifications = [pair["classification"] for pair in training_pairs]
    classification_counts = {}
    for cls in classifications:
        classification_counts[cls] = classification_counts.get(cls, 0) + 1
    
    # Rating distribution
    ratings = [pair["rating"] for pair in training_pairs if pair["rating"]]
    rating_counts = {}
    for rating in ratings:
        rating_counts[rating] = rating_counts.get(rating, 0) + 1
    
    # Organism distribution
    organisms = [pair["organism"] for pair in training_pairs]
    organism_counts = {}
    for org in organisms:
        organism_counts[org] = organism_counts.get(org, 0) + 1
    
    # Input length statistics
    input_lengths = [pair["input_length"] for pair in training_pairs]
    response_lengths = [pair["response_length"] for pair in training_pairs]
    
    # Question analysis
    questions = [pair for pair in training_pairs if pair["has_question"]]
    medical_terms = [pair for pair in training_pairs if pair["has_medical_terms"]]
    
    return {
        "total_pairs": total_pairs,
        "classification_distribution": classification_counts,
        "rating_distribution": rating_counts,
        "organism_distribution": organism_counts,
        "input_length_stats": {
            "mean": sum(input_lengths) / len(input_lengths),
            "min": min(input_lengths),
            "max": max(input_lengths)
        },
        "response_length_stats": {
            "mean": sum(response_lengths) / len(response_lengths),
            "min": min(response_lengths),
            "max": max(response_lengths)
        },
        "questions_count": len(questions),
        "medical_terms_count": len(medical_terms),
        "questions_percentage": (len(questions) / total_pairs) * 100,
        "medical_terms_percentage": (len(medical_terms) / total_pairs) * 100
    }


def main():
    """Main function to extract training data from feedback."""
    
    print("🚀 Extracting Training Data from Feedback Chat Histories")
    print("=" * 60)
    
    # Load feedback data
    feedback_file = Path("/Users/riccardoconci/Library/Mobile Documents/com~apple~CloudDocs/HQ_2024/Projects/2024_Harvard_AIM/Research/MicroTutor/microbiology-agent-tutor/feedback_202509211048.json")
    
    if not feedback_file.exists():
        logger.error(f"Feedback file not found: {feedback_file}")
        return 1
    
    logger.info(f"Loading feedback data from {feedback_file}")
    
    try:
        with open(feedback_file, 'r', encoding='utf-8') as f:
            feedback_data = json.load(f)
        
        logger.info(f"Loaded feedback data with {len(feedback_data.get('feedback', []))} entries")
        
    except Exception as e:
        logger.error(f"Failed to load feedback data: {e}")
        return 1
    
    # Extract training pairs
    logger.info("Extracting training pairs from chat histories...")
    training_pairs = extract_training_pairs(feedback_data)
    
    if not training_pairs:
        logger.error("No training pairs extracted")
        return 1
    
    logger.info(f"Extracted {len(training_pairs)} training pairs")
    
    # Analyze the data
    analysis = analyze_training_data(training_pairs)
    
    # Display analysis
    print(f"\n📊 Training Data Analysis:")
    print(f"   Total pairs: {analysis['total_pairs']}")
    
    print(f"\n📈 Classification Distribution:")
    for cls, count in analysis['classification_distribution'].items():
        percentage = (count / analysis['total_pairs']) * 100
        print(f"   {cls}: {count} ({percentage:.1f}%)")
    
    print(f"\n⭐ Rating Distribution:")
    for rating, count in analysis['rating_distribution'].items():
        percentage = (count / analysis['total_pairs']) * 100
        print(f"   Rating {rating}: {count} ({percentage:.1f}%)")
    
    print(f"\n🦠 Top Organisms:")
    sorted_organisms = sorted(analysis['organism_distribution'].items(), 
                            key=lambda x: x[1], reverse=True)[:5]
    for org, count in sorted_organisms:
        percentage = (count / analysis['total_pairs']) * 100
        print(f"   {org}: {count} ({percentage:.1f}%)")
    
    print(f"\n📝 Input Statistics:")
    print(f"   Mean length: {analysis['input_length_stats']['mean']:.1f} chars")
    print(f"   Range: {analysis['input_length_stats']['min']} - {analysis['input_length_stats']['max']} chars")
    
    print(f"\n💬 Response Statistics:")
    print(f"   Mean length: {analysis['response_length_stats']['mean']:.1f} chars")
    print(f"   Range: {analysis['response_length_stats']['min']} - {analysis['response_length_stats']['max']} chars")
    
    print(f"\n❓ Question Analysis:")
    print(f"   Questions: {analysis['questions_count']} ({analysis['questions_percentage']:.1f}%)")
    print(f"   Medical terms: {analysis['medical_terms_count']} ({analysis['medical_terms_percentage']:.1f}%)")
    
    # Save training data
    output_dir = Path("logs/classification_dataset")
    output_dir.mkdir(exist_ok=True)
    
    # Save as JSONL
    jsonl_file = output_dir / "feedback_training_data.jsonl"
    with open(jsonl_file, 'w', encoding='utf-8') as f:
        for pair in training_pairs:
            f.write(json.dumps(pair) + '\n')
    
    # Save as CSV
    csv_file = output_dir / "feedback_training_data.csv"
    df = pd.DataFrame(training_pairs)
    df.to_csv(csv_file, index=False)
    
    # Save analysis
    analysis_file = output_dir / "feedback_analysis.json"
    with open(analysis_file, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2)
    
    print(f"\n💾 Training data saved:")
    print(f"   JSONL: {jsonl_file}")
    print(f"   CSV: {csv_file}")
    print(f"   Analysis: {analysis_file}")
    
    # Show sample data
    print(f"\n📋 Sample Training Pairs:")
    for i, pair in enumerate(training_pairs[:5]):
        print(f"\n   Example {i+1}:")
        print(f"   User: '{pair['user_input'][:100]}{'...' if len(pair['user_input']) > 100 else ''}'")
        print(f"   Classification: {pair['classification']}")
        print(f"   Response: '{pair['assistant_response'][:100]}{'...' if len(pair['assistant_response']) > 100 else ''}'")
    
    print(f"\n✅ Training data extraction completed successfully!")
    print(f"\n🎯 Next Steps:")
    print(f"   1. Review the training data quality")
    print(f"   2. Train the fast classifier with this data")
    print(f"   3. Test performance on real inputs")
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
