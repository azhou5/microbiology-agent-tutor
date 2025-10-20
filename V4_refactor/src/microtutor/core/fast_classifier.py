"""
Fast Input Classifier for MicroTutor.

This module provides ultra-fast input classification using multiple approaches:
1. Rule-based classification (fastest)
2. Embedding-based classification (fast + accurate)
3. Lightweight ML classification (accurate)
4. Hybrid approach (best of all worlds)
"""

import json
import logging
import pickle
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd
from microtutor.core.config_helper import config

# Try to import scikit-learn modules (optional due to NumPy compatibility issues)
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import classification_report, accuracy_score
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError as e:
    logging.warning(f"scikit-learn not available: {e}")
    SKLEARN_AVAILABLE = False
    # Provide fallback classes
    class TfidfVectorizer:
        def __init__(self, *args, **kwargs):
            pass
        def fit_transform(self, *args, **kwargs):
            return np.array([])
        def transform(self, *args, **kwargs):
            return np.array([])
    
    class LogisticRegression:
        def __init__(self, *args, **kwargs):
            pass
        def fit(self, *args, **kwargs):
            return self
        def predict(self, *args, **kwargs):
            return np.array([])
        def predict_proba(self, *args, **kwargs):
            return np.array([])
    
    class RandomForestClassifier:
        def __init__(self, *args, **kwargs):
            pass
        def fit(self, *args, **kwargs):
            return self
        def predict(self, *args, **kwargs):
            return np.array([])
        def predict_proba(self, *args, **kwargs):
            return np.array([])
    
    def classification_report(*args, **kwargs):
        return ""
    
    def accuracy_score(*args, **kwargs):
        return 0.0
    
    def train_test_split(*args, **kwargs):
        return args[0], args[0], args[1], args[1]

# Try to import sentence transformers for embedding-based classification
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logging.warning("sentence-transformers not available. Embedding classification disabled.")

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Result of input classification."""
    
    classification: str  # 'tutor_direct', 'patient', 'socratic', 'hint'
    confidence: float   # 0.0 to 1.0
    method: str        # 'embedding', 'ml', 'hybrid', 'embedding_fallback', 'ml_fallback', 'hybrid_fallback'
    processing_time_ms: float
    features: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "classification": self.classification,
            "confidence": self.confidence,
            "method": self.method,
            "processing_time_ms": self.processing_time_ms,
            "features": self.features
        }


# Rule-based classifier removed - using more sophisticated approaches


class EmbeddingClassifier:
    """Fast embedding-based classifier."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize embedding classifier.
        
        Args:
            model_name: Sentence transformer model name
        """
        self.model_name = model_name
        self.model = None
        self.reference_embeddings = {}
        self.classification_labels = []
        
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.model = SentenceTransformer(model_name)
                logger.info(f"✅ Loaded embedding model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                self.model = None
        else:
            logger.warning("Sentence transformers not available")
    
    def train(self, examples: List[Dict[str, Any]]) -> None:
        """Train the embedding classifier.
        
        Args:
            examples: List of training examples with 'user_input' and 'classification' keys
        """
        if not self.model:
            logger.warning("No embedding model available")
            return
        
        logger.info("Training embedding classifier...")
        
        # Group examples by classification
        classification_groups = {}
        for example in examples:
            classification = example['classification']
            if classification not in classification_groups:
                classification_groups[classification] = []
            classification_groups[classification].append(example['user_input'])
        
        # Create reference embeddings for each classification
        self.reference_embeddings = {}
        self.classification_labels = list(classification_groups.keys())
        
        for classification, texts in classification_groups.items():
            # Use first few examples as reference
            reference_texts = texts[:5]  # Use first 5 examples as reference
            embeddings = self.model.encode(reference_texts)
            self.reference_embeddings[classification] = np.mean(embeddings, axis=0)
        
        logger.info(f"Trained embedding classifier with {len(self.classification_labels)} classes")
    
    def classify(self, text: str) -> ClassificationResult:
        """Classify input text using embeddings.
        
        Args:
            text: Input text to classify
            
        Returns:
            Classification result
        """
        start_time = time.time()
        
        if not self.model or not self.reference_embeddings:
            # Fallback to default classification
            return ClassificationResult(
                classification="tutor_direct",
                confidence=0.5,
                method="embedding_fallback",
                processing_time_ms=(time.time() - start_time) * 1000,
                features={"error": "No model or reference embeddings available"}
            )
        
        try:
            # Get embedding for input text
            input_embedding = self.model.encode([text])[0]
            
            # Calculate similarities to reference embeddings
            similarities = {}
            for classification, ref_embedding in self.reference_embeddings.items():
                # Cosine similarity
                similarity = np.dot(input_embedding, ref_embedding) / (
                    np.linalg.norm(input_embedding) * np.linalg.norm(ref_embedding)
                )
                similarities[classification] = similarity
            
            # Find best match
            classification = max(similarities, key=similarities.get)
            confidence = similarities[classification]
            
            # Normalize confidence to 0-1 range
            confidence = max(0.0, min(1.0, (confidence + 1) / 2))
            
        except Exception as e:
            logger.warning(f"Embedding classification failed: {e}")
            # Fallback to default classification
            return ClassificationResult(
                classification="tutor_direct",
                confidence=0.5,
                method="embedding_error",
                processing_time_ms=(time.time() - start_time) * 1000,
                features={"error": str(e)}
            )
        
        processing_time = (time.time() - start_time) * 1000
        
        return ClassificationResult(
            classification=classification,
            confidence=confidence,
            method="embedding",
            processing_time_ms=processing_time,
            features={"similarities": similarities}
        )


class MLClassifier:
    """Lightweight machine learning classifier."""
    
    def __init__(self, model_type: str = "logistic_regression"):
        """Initialize ML classifier.
        
        Args:
            model_type: Type of model ('logistic_regression' or 'random_forest')
        """
        self.model_type = model_type
        self.model = None
        self.vectorizer = None
        self.classes_ = None
        
        if model_type == "logistic_regression":
            self.model = LogisticRegression(random_state=42, max_iter=1000)
        elif model_type == "random_forest":
            self.model = RandomForestClassifier(random_state=42, n_estimators=100)
        else:
            raise ValueError(f"Unknown model type: {model_type}")
    
    def train(self, examples: List[Dict[str, Any]]) -> None:
        """Train the ML classifier.
        
        Args:
            examples: List of training examples with 'user_input' and 'classification' keys
        """
        logger.info(f"Training {self.model_type} classifier...")
        
        # Prepare data
        texts = [ex['user_input'] for ex in examples]
        labels = [ex['classification'] for ex in examples]
        
        # Create features
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        
        X = self.vectorizer.fit_transform(texts)
        y = np.array(labels)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Train model
        self.model.fit(X_train, y_train)
        self.classes_ = self.model.classes_
        
        # Evaluate
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        logger.info(f"ML classifier trained with accuracy: {accuracy:.3f}")
        logger.info(f"Classification report:\n{classification_report(y_test, y_pred)}")
    
    def classify(self, text: str) -> ClassificationResult:
        """Classify input text using ML model.
        
        Args:
            text: Input text to classify
            
        Returns:
            Classification result
        """
        start_time = time.time()
        
        if not self.model or not self.vectorizer:
            # Fallback to default classification
            return ClassificationResult(
                classification="tutor_direct",
                confidence=0.5,
                method="ml_fallback",
                processing_time_ms=(time.time() - start_time) * 1000,
                features={"error": "No model or vectorizer available"}
            )
        
        try:
            # Vectorize input
            X = self.vectorizer.transform([text])
            
            # Predict
            prediction = self.model.predict(X)[0]
            probabilities = self.model.predict_proba(X)[0]
            
            # Get confidence (max probability)
            confidence = np.max(probabilities)
            
        except Exception as e:
            logger.warning(f"ML classification failed: {e}")
            # Fallback to default classification
            return ClassificationResult(
                classification="tutor_direct",
                confidence=0.5,
                method="ml_error",
                processing_time_ms=(time.time() - start_time) * 1000,
                features={"error": str(e)}
            )
        
        processing_time = (time.time() - start_time) * 1000
        
        return ClassificationResult(
            classification=prediction,
            confidence=confidence,
            method="ml",
            processing_time_ms=processing_time,
            features={"probabilities": dict(zip(self.classes_, probabilities))}
        )


class HybridClassifier:
    """Hybrid classifier combining embedding and ML approaches."""
    
    def __init__(self, use_embedding: bool = True, use_ml: bool = True):
        """Initialize hybrid classifier.
        
        Args:
            use_embedding: Whether to use embedding classifier
            use_ml: Whether to use ML classifier
        """
        self.embedding_classifier = EmbeddingClassifier() if use_embedding else None
        self.ml_classifier = MLClassifier() if use_ml else None
        
        # Weights for combining results (adjusted after removing rule-based)
        self.weights = {
            "embedding": 0.6,
            "ml": 0.4
        }
    
    def train(self, examples: List[Dict[str, Any]]) -> None:
        """Train all available classifiers.
        
        Args:
            examples: List of training examples
        """
        logger.info("Training hybrid classifier...")
        
        if self.embedding_classifier:
            self.embedding_classifier.train(examples)
        
        if self.ml_classifier:
            self.ml_classifier.train(examples)
        
        logger.info("Hybrid classifier training completed")
    
    def classify(self, text: str) -> ClassificationResult:
        """Classify input text using hybrid approach.
        
        Args:
            text: Input text to classify
            
        Returns:
            Classification result
        """
        start_time = time.time()
        
        # Get predictions from available classifiers
        results = {}
        
        # Embedding-based
        if self.embedding_classifier:
            embedding_result = self.embedding_classifier.classify(text)
            results["embedding"] = embedding_result
        
        # ML-based
        if self.ml_classifier:
            ml_result = self.ml_classifier.classify(text)
            results["ml"] = ml_result
        
        # If no classifiers available, return default
        if not results:
            return ClassificationResult(
                classification="tutor_direct",
                confidence=0.5,
                method="hybrid_fallback",
                processing_time_ms=(time.time() - start_time) * 1000,
                features={"error": "No classifiers available"}
            )
        
        # Combine results
        classification_scores = {}
        total_confidence = 0.0
        
        for method, result in results.items():
            if method in self.weights:
                weight = self.weights[method]
                classification = result.classification
                confidence = result.confidence * weight
                
                if classification not in classification_scores:
                    classification_scores[classification] = 0.0
                
                classification_scores[classification] += confidence
                total_confidence += confidence
        
        # Find best classification
        if classification_scores:
            best_classification = max(classification_scores, key=classification_scores.get)
            best_confidence = classification_scores[best_classification]
        else:
            best_classification = "tutor_direct"
            best_confidence = 0.5
        
        # Normalize confidence
        if total_confidence > 0:
            best_confidence = best_confidence / total_confidence
        
        processing_time = (time.time() - start_time) * 1000
        
        return ClassificationResult(
            classification=best_classification,
            confidence=best_confidence,
            method="hybrid",
            processing_time_ms=processing_time,
            features={
                "individual_results": {method: result.to_dict() for method, result in results.items()},
                "classification_scores": classification_scores
            }
        )
    
    def save(self, filepath: Path) -> None:
        """Save the hybrid classifier.
        
        Args:
            filepath: Path to save the classifier
        """
        classifier_data = {
            "weights": self.weights,
            "embedding_classifier": None,  # Will be saved separately if needed
            "ml_classifier": None  # Will be saved separately if needed
        }
        
        # Save ML classifier if available
        if self.ml_classifier and self.ml_classifier.model:
            ml_filepath = filepath.parent / f"{filepath.stem}_ml.pkl"
            with open(ml_filepath, 'wb') as f:
                pickle.dump({
                    "model": self.ml_classifier.model,
                    "vectorizer": self.ml_classifier.vectorizer,
                    "classes": self.ml_classifier.classes_
                }, f)
            classifier_data["ml_classifier_path"] = str(ml_filepath)
        
        # Save main classifier data
        with open(filepath, 'w') as f:
            json.dump(classifier_data, f, indent=2)
        
        logger.info(f"Hybrid classifier saved to {filepath}")
    
    def load(self, filepath: Path) -> None:
        """Load the hybrid classifier.
        
        Args:
            filepath: Path to load the classifier from
        """
        with open(filepath, 'r') as f:
            classifier_data = json.load(f)
        
        self.weights = classifier_data.get("weights", self.weights)
        
        # Load ML classifier if available
        if "ml_classifier_path" in classifier_data:
            ml_filepath = Path(classifier_data["ml_classifier_path"])
            if ml_filepath.exists():
                with open(ml_filepath, 'rb') as f:
                    ml_data = pickle.load(f)
                
                if self.ml_classifier:
                    self.ml_classifier.model = ml_data["model"]
                    self.ml_classifier.vectorizer = ml_data["vectorizer"]
                    self.ml_classifier.classes_ = ml_data["classes"]
        
        logger.info(f"Hybrid classifier loaded from {filepath}")


def create_fast_classifier(
    classifier_type: str = "hybrid",
    training_data_path: Optional[Path] = None
) -> Any:
    """Create and train a fast classifier.
    
    Args:
        classifier_type: Type of classifier ('embedding', 'ml', 'hybrid')
        training_data_path: Path to training data CSV file
        
    Returns:
        Trained classifier
    """
    if classifier_type == "embedding":
        classifier = EmbeddingClassifier()
        if training_data_path and training_data_path.exists():
            df = pd.read_csv(training_data_path)
            examples = df.to_dict('records')
            classifier.train(examples)
        return classifier
    
    elif classifier_type == "ml":
        classifier = MLClassifier()
        if training_data_path and training_data_path.exists():
            df = pd.read_csv(training_data_path)
            examples = df.to_dict('records')
            classifier.train(examples)
        return classifier
    
    elif classifier_type == "hybrid":
        classifier = HybridClassifier()
        if training_data_path and training_data_path.exists():
            df = pd.read_csv(training_data_path)
            examples = df.to_dict('records')
            classifier.train(examples)
        return classifier
    
    else:
        raise ValueError(f"Unknown classifier type: {classifier_type}. Available: 'embedding', 'ml', 'hybrid'")


# Global classifier instance
_fast_classifier: Optional[HybridClassifier] = None


def get_fast_classifier() -> HybridClassifier:
    """Get the global fast classifier instance."""
    global _fast_classifier
    if _fast_classifier is None:
        _fast_classifier = HybridClassifier()
    return _fast_classifier


def classify_input_fast(text: str) -> ClassificationResult:
    """Fast input classification using the global classifier.
    
    Args:
        text: Input text to classify
        
    Returns:
        Classification result
    """
    # If classification is disabled, return default
    if not config.FAST_CLASSIFICATION_ENABLED:
        return ClassificationResult(
            classification="tutor_direct",
            confidence=0.5,
            method="disabled",
            processing_time_ms=0.0,
            features={"disabled": True}
        )
    
    # Get classifier and classify
    classifier = get_fast_classifier()
    result = classifier.classify(text)
    
    # Add configuration info to features
    if result.features is None:
        result.features = {}
    
    result.features.update({
        "config_enabled": config.FAST_CLASSIFICATION_ENABLED
    })
    
    return result
