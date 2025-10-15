"""
Classification Dataset Builder for MicroTutor.

This module collects and processes conversation data to build a dataset
for training fast input classification models.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import pandas as pd
import numpy as np
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


@dataclass
class ClassificationExample:
    """A single example for classification training."""
    
    # Input data
    user_input: str
    case_id: str
    organism: str
    conversation_context: List[Dict[str, str]]
    
    # Classification target
    classification: str  # 'tutor_direct', 'patient', 'socratic', 'hint'
    confidence: float  # How confident we are in this classification
    
    # Metadata
    timestamp: datetime
    model_used: str
    processing_time_ms: float
    
    # Tool information
    tools_used: List[str]
    response_length: int
    response_type: str  # 'direct_answer', 'tool_call', 'mixed'
    
    # Optional fields
    tool_results: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "user_input": self.user_input,
            "case_id": self.case_id,
            "organism": self.organism,
            "conversation_context": self.conversation_context,
            "classification": self.classification,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "model_used": self.model_used,
            "processing_time_ms": self.processing_time_ms,
            "tools_used": self.tools_used,
            "tool_results": self.tool_results,
            "response_length": self.response_length,
            "response_type": self.response_type
        }


class ClassificationDatasetBuilder:
    """Builds classification datasets from conversation logs."""
    
    def __init__(self, db_engine: Optional[Engine] = None, logs_dir: Optional[Path] = None):
        """Initialize dataset builder.
        
        Args:
            db_engine: Database engine for querying conversation logs
            logs_dir: Directory containing conversation log files
        """
        self.db_engine = db_engine
        self.logs_dir = logs_dir or Path("logs")
        self.dataset_dir = self.logs_dir / "classification_dataset"
        self.dataset_dir.mkdir(exist_ok=True)
        
        # Classification rules for determining labels
        self.classification_rules = {
            "tutor_direct": [
                "explain", "teach", "show", "describe", "what is", "how does",
                "define", "tell me about", "can you explain", "help me understand"
            ],
            "patient": [
                "patient", "symptoms", "feeling", "pain", "hurt", "uncomfortable",
                "nausea", "fever", "headache", "cough", "breathing", "chest pain"
            ],
            "socratic": [
                "why", "how", "what if", "what do you think", "what would happen",
                "what should", "what could", "what might", "do you think", "consider"
            ],
            "hint": [
                "hint", "clue", "tip", "suggestion", "help", "guidance",
                "nudge", "direction", "point me", "give me a hint"
            ]
        }
    
    def collect_from_database(
        self, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[ClassificationExample]:
        """Collect classification examples from database.
        
        Args:
            start_date: Start date for data collection
            end_date: End date for data collection
            limit: Maximum number of examples to collect
            
        Returns:
            List of classification examples
        """
        if not self.db_engine:
            logger.warning("No database engine available")
            return []
        
        logger.info("Collecting classification examples from database...")
        
        # Build query
        query = """
            SELECT 
                cl1.case_id,
                cl1.timestamp,
                cl1.content as user_input,
                cl2.content as assistant_response,
                cl1.metadata as user_metadata,
                cl2.metadata as assistant_metadata
            FROM conversation_logs cl1
            JOIN conversation_logs cl2 ON cl1.case_id = cl2.case_id 
                AND cl1.timestamp < cl2.timestamp
                AND cl2.role = 'assistant'
            WHERE cl1.role = 'user'
            ORDER BY cl1.timestamp DESC
        """
        
        params = {}
        if start_date:
            query += " AND cl1.timestamp >= :start_date"
            params["start_date"] = start_date
        if end_date:
            query += " AND cl1.timestamp <= :end_date"
            params["end_date"] = end_date
        if limit:
            query += " LIMIT :limit"
            params["limit"] = limit
        
        try:
            with self.db_engine.connect() as conn:
                result = conn.execute(text(query), params)
                rows = result.fetchall()
                
                examples = []
                for row in rows:
                    try:
                        example = self._create_example_from_db_row(row)
                        if example:
                            examples.append(example)
                    except Exception as e:
                        logger.warning(f"Failed to process row: {e}")
                        continue
                
                logger.info(f"Collected {len(examples)} examples from database")
                return examples
                
        except Exception as e:
            logger.error(f"Database collection failed: {e}")
            return []
    
    def collect_from_logs(
        self, 
        case_ids: Optional[List[str]] = None,
        days_back: int = 30
    ) -> List[ClassificationExample]:
        """Collect classification examples from log files.
        
        Args:
            case_ids: Specific case IDs to process (None for all)
            days_back: Number of days back to look for logs
            
        Returns:
            List of classification examples
        """
        logger.info("Collecting classification examples from log files...")
        
        examples = []
        conversations_dir = self.logs_dir / "conversations"
        
        if not conversations_dir.exists():
            logger.warning(f"Conversations directory not found: {conversations_dir}")
            return examples
        
        # Get case files to process
        if case_ids:
            case_files = [conversations_dir / f"{case_id}.jsonl" for case_id in case_ids]
        else:
            # Get all case files from the last N days
            cutoff_date = datetime.now() - timedelta(days=days_back)
            case_files = []
            for case_file in conversations_dir.glob("*.jsonl"):
                if case_file.stat().st_mtime > cutoff_date.timestamp():
                    case_files.append(case_file)
        
        for case_file in case_files:
            try:
                case_examples = self._process_case_file(case_file)
                examples.extend(case_examples)
            except Exception as e:
                logger.warning(f"Failed to process {case_file}: {e}")
                continue
        
        logger.info(f"Collected {len(examples)} examples from log files")
        return examples
    
    def _create_example_from_db_row(self, row) -> Optional[ClassificationExample]:
        """Create classification example from database row."""
        try:
            # Parse metadata
            user_metadata = json.loads(row.user_metadata) if row.user_metadata else {}
            assistant_metadata = json.loads(row.assistant_metadata) if row.assistant_metadata else {}
            
            # Extract tools used
            tools_used = assistant_metadata.get("tools_used", [])
            
            # Classify the input
            classification, confidence = self._classify_input(
                row.user_input, 
                tools_used,
                row.assistant_response
            )
            
            # Determine response type
            response_type = self._determine_response_type(tools_used, row.assistant_response)
            
            return ClassificationExample(
                user_input=row.user_input,
                case_id=row.case_id,
                organism=user_metadata.get("organism", "unknown"),
                conversation_context=[],  # Would need additional query for full context
                classification=classification,
                confidence=confidence,
                timestamp=row.timestamp,
                model_used=assistant_metadata.get("model", "unknown"),
                processing_time_ms=assistant_metadata.get("processing_time_ms", 0.0),
                tools_used=tools_used,
                response_length=len(row.assistant_response),
                response_type=response_type
            )
            
        except Exception as e:
            logger.warning(f"Failed to create example from DB row: {e}")
            return None
    
    def _process_case_file(self, case_file: Path) -> List[ClassificationExample]:
        """Process a single case file to extract examples."""
        examples = []
        
        with open(case_file, 'r') as f:
            lines = f.readlines()
        
        # Group messages by conversation turns
        user_messages = []
        assistant_messages = []
        
        for line in lines:
            try:
                entry = json.loads(line.strip())
                if entry["role"] == "user":
                    user_messages.append(entry)
                elif entry["role"] == "assistant":
                    assistant_messages.append(entry)
            except json.JSONDecodeError:
                continue
        
        # Match user messages with assistant responses
        for i, user_msg in enumerate(user_messages):
            if i < len(assistant_messages):
                assistant_msg = assistant_messages[i]
                
                try:
                    example = self._create_example_from_messages(
                        user_msg, assistant_msg, case_file.stem
                    )
                    if example:
                        examples.append(example)
                except Exception as e:
                    logger.warning(f"Failed to create example from messages: {e}")
                    continue
        
        return examples
    
    def _create_example_from_messages(
        self, 
        user_msg: Dict[str, Any], 
        assistant_msg: Dict[str, Any], 
        case_id: str
    ) -> Optional[ClassificationExample]:
        """Create classification example from user and assistant messages."""
        try:
            # Extract tools used
            tools_used = assistant_msg.get("metadata", {}).get("tools_used", [])
            
            # Classify the input
            classification, confidence = self._classify_input(
                user_msg["content"],
                tools_used,
                assistant_msg["content"]
            )
            
            # Determine response type
            response_type = self._determine_response_type(tools_used, assistant_msg["content"])
            
            return ClassificationExample(
                user_input=user_msg["content"],
                case_id=case_id,
                organism=user_msg.get("metadata", {}).get("organism", "unknown"),
                conversation_context=[],  # Could be populated with full conversation
                classification=classification,
                confidence=confidence,
                timestamp=datetime.fromisoformat(user_msg["timestamp"]),
                model_used=assistant_msg.get("metadata", {}).get("model", "unknown"),
                processing_time_ms=assistant_msg.get("metadata", {}).get("processing_time_ms", 0.0),
                tools_used=tools_used,
                response_length=len(assistant_msg["content"]),
                response_type=response_type
            )
            
        except Exception as e:
            logger.warning(f"Failed to create example from messages: {e}")
            return None
    
    def _classify_input(
        self, 
        user_input: str, 
        tools_used: List[str], 
        assistant_response: str
    ) -> Tuple[str, float]:
        """Classify user input based on tools used and response characteristics.
        
        Args:
            user_input: The user's input text
            tools_used: List of tools that were called
            assistant_response: The assistant's response
            
        Returns:
            Tuple of (classification, confidence)
        """
        user_input_lower = user_input.lower()
        
        # Rule 1: If tools were used, classify based on tool type
        if tools_used:
            if "patient" in tools_used:
                return "patient", 0.9
            elif "socratic" in tools_used:
                return "socratic", 0.9
            elif "hint" in tools_used:
                return "hint", 0.9
            else:
                # Tool was used but not one of our classification categories
                return "tutor_direct", 0.7
        
        # Rule 2: If no tools used, classify based on keywords
        for category, keywords in self.classification_rules.items():
            if any(keyword in user_input_lower for keyword in keywords):
                return category, 0.8
        
        # Rule 3: Analyze response characteristics
        if self._is_direct_answer(assistant_response):
            return "tutor_direct", 0.6
        elif self._is_questioning_response(assistant_response):
            return "socratic", 0.6
        else:
            return "tutor_direct", 0.5
    
    def _determine_response_type(self, tools_used: List[str], response: str) -> str:
        """Determine the type of response based on tools and content."""
        if not tools_used:
            return "direct_answer"
        elif len(tools_used) == 1:
            return "tool_call"
        else:
            return "mixed"
    
    def _is_direct_answer(self, response: str) -> bool:
        """Check if response is a direct answer."""
        # Look for patterns that suggest direct answers
        direct_patterns = [
            "is a", "are", "is", "means", "refers to", "defined as",
            "the answer is", "the result is", "the diagnosis is"
        ]
        return any(pattern in response.lower() for pattern in direct_patterns)
    
    def _is_questioning_response(self, response: str) -> bool:
        """Check if response contains questions."""
        return "?" in response and any(
            word in response.lower() 
            for word in ["what", "how", "why", "when", "where", "do you", "can you"]
        )
    
    def save_dataset(
        self, 
        examples: List[ClassificationExample], 
        filename: Optional[str] = None
    ) -> Path:
        """Save classification examples to file.
        
        Args:
            examples: List of classification examples
            filename: Optional filename (defaults to timestamp-based name)
            
        Returns:
            Path to saved file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"classification_dataset_{timestamp}.jsonl"
        
        filepath = self.dataset_dir / filename
        
        with open(filepath, 'w') as f:
            for example in examples:
                f.write(json.dumps(example.to_dict()) + '\n')
        
        logger.info(f"Saved {len(examples)} examples to {filepath}")
        return filepath
    
    def load_dataset(self, filepath: Path) -> List[ClassificationExample]:
        """Load classification examples from file.
        
        Args:
            filepath: Path to dataset file
            
        Returns:
            List of classification examples
        """
        examples = []
        
        with open(filepath, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    example = ClassificationExample(
                        user_input=data["user_input"],
                        case_id=data["case_id"],
                        organism=data["organism"],
                        conversation_context=data["conversation_context"],
                        classification=data["classification"],
                        confidence=data["confidence"],
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                        model_used=data["model_used"],
                        processing_time_ms=data["processing_time_ms"],
                        tools_used=data["tools_used"],
                        tool_results=data.get("tool_results"),
                        response_length=data["response_length"],
                        response_type=data["response_type"]
                    )
                    examples.append(example)
                except Exception as e:
                    logger.warning(f"Failed to load example: {e}")
                    continue
        
        logger.info(f"Loaded {len(examples)} examples from {filepath}")
        return examples
    
    def create_training_data(self, examples: List[ClassificationExample]) -> pd.DataFrame:
        """Create training data DataFrame from examples.
        
        Args:
            examples: List of classification examples
            
        Returns:
            DataFrame suitable for training
        """
        data = []
        
        for example in examples:
            # Create features
            features = {
                "user_input": example.user_input,
                "input_length": len(example.user_input),
                "word_count": len(example.user_input.split()),
                "has_question": "?" in example.user_input,
                "has_medical_terms": self._has_medical_terms(example.user_input),
                "organism": example.organism,
                "conversation_length": len(example.conversation_context),
                "response_length": example.response_length,
                "tools_used": ",".join(example.tools_used),
                "response_type": example.response_type,
                "classification": example.classification,
                "confidence": example.confidence
            }
            
            # Add keyword features
            for category, keywords in self.classification_rules.items():
                features[f"has_{category}_keywords"] = any(
                    keyword in example.user_input.lower() for keyword in keywords
                )
            
            data.append(features)
        
        return pd.DataFrame(data)
    
    def _has_medical_terms(self, text: str) -> bool:
        """Check if text contains medical terms."""
        medical_terms = [
            "patient", "symptoms", "diagnosis", "treatment", "disease", "infection",
            "fever", "pain", "nausea", "vomiting", "diarrhea", "cough", "breathing",
            "temperature", "blood pressure", "heart rate", "pulse", "oxygen"
        ]
        return any(term in text.lower() for term in medical_terms)
    
    def generate_dataset_summary(self, examples: List[ClassificationExample]) -> Dict[str, Any]:
        """Generate summary statistics for the dataset.
        
        Args:
            examples: List of classification examples
            
        Returns:
            Dictionary with summary statistics
        """
        if not examples:
            return {"error": "No examples provided"}
        
        # Basic counts
        total_examples = len(examples)
        classifications = [ex.classification for ex in examples]
        unique_classifications = list(set(classifications))
        
        # Classification distribution
        classification_counts = {cls: classifications.count(cls) for cls in unique_classifications}
        
        # Confidence statistics
        confidences = [ex.confidence for ex in examples]
        
        # Response type distribution
        response_types = [ex.response_type for ex in examples]
        response_type_counts = {rt: response_types.count(rt) for rt in set(response_types)}
        
        # Tool usage statistics
        all_tools = []
        for ex in examples:
            all_tools.extend(ex.tools_used)
        tool_counts = {tool: all_tools.count(tool) for tool in set(all_tools)}
        
        # Input length statistics
        input_lengths = [len(ex.user_input) for ex in examples]
        
        return {
            "total_examples": total_examples,
            "classification_distribution": classification_counts,
            "confidence_stats": {
                "mean": np.mean(confidences),
                "std": np.std(confidences),
                "min": np.min(confidences),
                "max": np.max(confidences)
            },
            "response_type_distribution": response_type_counts,
            "tool_usage": tool_counts,
            "input_length_stats": {
                "mean": np.mean(input_lengths),
                "std": np.std(input_lengths),
                "min": np.min(input_lengths),
                "max": np.max(input_lengths)
            },
            "date_range": {
                "earliest": min(ex.timestamp for ex in examples).isoformat(),
                "latest": max(ex.timestamp for ex in examples).isoformat()
            }
        }


def build_classification_dataset(
    db_engine: Optional[Engine] = None,
    logs_dir: Optional[Path] = None,
    days_back: int = 30,
    limit: Optional[int] = None
) -> Tuple[List[ClassificationExample], Dict[str, Any]]:
    """Build classification dataset from available data sources.
    
    Args:
        db_engine: Database engine for querying
        logs_dir: Directory containing log files
        days_back: Number of days back to collect data
        limit: Maximum number of examples to collect
        
    Returns:
        Tuple of (examples, summary_stats)
    """
    builder = ClassificationDatasetBuilder(db_engine, logs_dir)
    
    # Collect from both sources
    db_examples = builder.collect_from_database(limit=limit)
    log_examples = builder.collect_from_logs(days_back=days_back)
    
    # Combine and deduplicate
    all_examples = db_examples + log_examples
    unique_examples = list({ex.user_input: ex for ex in all_examples}.values())
    
    # Generate summary
    summary = builder.generate_dataset_summary(unique_examples)
    
    # Save dataset
    if unique_examples:
        filepath = builder.save_dataset(unique_examples)
        summary["saved_to"] = str(filepath)
    
    return unique_examples, summary
