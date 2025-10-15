#!/usr/bin/env python3
"""
Train fast classifier for MicroTutor input routing.

This script trains various types of fast classifiers to route user inputs
to the appropriate response type (tutor_direct, patient, socratic, hint).
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from typing import List, Dict, Any
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from microtutor.core.fast_classifier import (
    EmbeddingClassifier, 
    MLClassifier,
    HybridClassifier,
    create_fast_classifier
)
from microtutor.core.classification_dataset import ClassificationDatasetBuilder
# Database engine not available in this version

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_classifier_performance(
    classifier, 
    test_examples: List[Dict[str, Any]], 
    classifier_name: str
) -> Dict[str, Any]:
    """Test classifier performance on examples.
    
    Args:
        classifier: Trained classifier
        test_examples: List of test examples
        classifier_name: Name of the classifier
        
    Returns:
        Performance metrics
    """
    logger.info(f"Testing {classifier_name} performance...")
    
    correct_predictions = 0
    total_predictions = len(test_examples)
    processing_times = []
    
    for example in test_examples:
        start_time = time.time()
        
        result = classifier.classify(example['user_input'])
        processing_time = (time.time() - start_time) * 1000
        processing_times.append(processing_time)
        
        if result.classification == example['classification']:
            correct_predictions += 1
    
    accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0
    avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
    
    return {
        "accuracy": accuracy,
        "avg_processing_time_ms": avg_processing_time,
        "total_predictions": total_predictions,
        "correct_predictions": correct_predictions
    }


async def main():
    """Main function to train fast classifiers."""
    
    print("🚀 Training Fast Classifiers for MicroTutor")
    print("=" * 60)
    
    try:
        # Load training data
        logs_dir = Path("logs")
        training_data_path = logs_dir / "classification_dataset" / "feedback_training_data.csv"
        
        if not training_data_path.exists():
            logger.error(f"Training data not found: {training_data_path}")
            logger.info("Run build_classification_dataset.py first")
            return 1
        
        logger.info(f"Loading training data from {training_data_path}")
        
        import pandas as pd
        df = pd.read_csv(training_data_path)
        examples = df.to_dict('records')
        
        logger.info(f"Loaded {len(examples)} training examples")
        
        # Split data
        from sklearn.model_selection import train_test_split
        
        train_examples, test_examples = train_test_split(
            examples, test_size=0.2, random_state=42, 
            stratify=[ex['classification'] for ex in examples]
        )
        
        logger.info(f"Split: {len(train_examples)} train, {len(test_examples)} test")
        
        # Train different classifiers
        classifiers = {}
        results = {}
        
        # 1. Embedding classifier
        print("\n1️⃣ Training Embedding Classifier")
        print("-" * 40)
        
        try:
            embedding_classifier = EmbeddingClassifier()
            embedding_classifier.train(train_examples)
            
            embedding_results = await test_classifier_performance(
                embedding_classifier, test_examples, "Embedding"
            )
            classifiers["embedding"] = embedding_classifier
            results["embedding"] = embedding_results
            
            print(f"   Accuracy: {embedding_results['accuracy']:.3f}")
            print(f"   Avg processing time: {embedding_results['avg_processing_time_ms']:.2f}ms")
            
        except Exception as e:
            logger.warning(f"Embedding classifier failed: {e}")
            results["embedding"] = {"accuracy": 0, "avg_processing_time_ms": 0}
        
        # 2. ML classifier
        print("\n2️⃣ Training ML Classifier")
        print("-" * 40)
        
        try:
            ml_classifier = MLClassifier()
            ml_classifier.train(train_examples)
            
            ml_results = await test_classifier_performance(
                ml_classifier, test_examples, "ML"
            )
            classifiers["ml"] = ml_classifier
            results["ml"] = ml_results
            
            print(f"   Accuracy: {ml_results['accuracy']:.3f}")
            print(f"   Avg processing time: {ml_results['avg_processing_time_ms']:.2f}ms")
            
        except Exception as e:
            logger.error(f"ML classifier failed: {e}")
            results["ml"] = {"accuracy": 0, "avg_processing_time_ms": 0}
        
        # 3. Hybrid classifier
        print("\n3️⃣ Training Hybrid Classifier")
        print("-" * 40)
        
        try:
            hybrid_classifier = HybridClassifier()
            hybrid_classifier.train(train_examples)
            
            hybrid_results = await test_classifier_performance(
                hybrid_classifier, test_examples, "Hybrid"
            )
            classifiers["hybrid"] = hybrid_classifier
            results["hybrid"] = hybrid_results
            
            print(f"   Accuracy: {hybrid_results['accuracy']:.3f}")
            print(f"   Avg processing time: {hybrid_results['avg_processing_time_ms']:.2f}ms")
            
        except Exception as e:
            logger.error(f"Hybrid classifier failed: {e}")
            results["hybrid"] = {"accuracy": 0, "avg_processing_time_ms": 0}
        
        # Summary
        print("\n📊 Performance Summary")
        print("=" * 60)
        print(f"{'Classifier':<15} {'Accuracy':<10} {'Speed (ms)':<12} {'Score':<10}")
        print("-" * 60)
        
        best_score = 0
        best_classifier = None
        
        for name, result in results.items():
            if result['accuracy'] > 0:  # Only show working classifiers
                # Score = accuracy * speed_factor (faster is better)
                speed_factor = 1.0 / max(result['avg_processing_time_ms'], 0.1)
                score = result['accuracy'] * speed_factor
                
                print(f"{name:<15} {result['accuracy']:<10.3f} {result['avg_processing_time_ms']:<12.2f} {score:<10.3f}")
                
                if score > best_score:
                    best_score = score
                    best_classifier = name
        
        print("-" * 60)
        print(f"🏆 Best classifier: {best_classifier} (score: {best_score:.3f})")
        
        # Save best classifier
        if best_classifier and best_classifier in classifiers:
            model_dir = logs_dir / "classification_dataset" / "models"
            model_dir.mkdir(exist_ok=True)
            
            if best_classifier == "hybrid":
                model_path = model_dir / "hybrid_classifier.json"
                classifiers[best_classifier].save(model_path)
                print(f"💾 Best classifier saved to: {model_path}")
            else:
                # For other classifiers, save as pickle
                model_path = model_dir / f"{best_classifier}_classifier.pkl"
                import pickle
                with open(model_path, 'wb') as f:
                    pickle.dump(classifiers[best_classifier], f)
                print(f"💾 Best classifier saved to: {model_path}")
        
        # Test with sample inputs
        print("\n🧪 Testing with Sample Inputs")
        print("-" * 40)
        
        sample_inputs = [
            "What is Staphylococcus aureus?",
            "The patient is feeling nauseous and has a fever",
            "Why do you think this infection occurred?",
            "Can you give me a hint about the diagnosis?",
            "Explain how antibiotics work",
            "I'm experiencing chest pain and shortness of breath"
        ]
        
        if best_classifier and best_classifier in classifiers:
            best_classifier_obj = classifiers[best_classifier]
            
            for input_text in sample_inputs:
                result = best_classifier_obj.classify(input_text)
                print(f"   '{input_text}'")
                print(f"   → {result.classification} (confidence: {result.confidence:.3f}, {result.processing_time_ms:.2f}ms)")
                print()
        
        print("✅ Classifier training completed successfully!")
        print("\n🎯 Next Steps:")
        print("   1. Deploy the best classifier in your application")
        print("   2. Monitor performance in production")
        print("   3. Retrain periodically with new data")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Classifier training failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
