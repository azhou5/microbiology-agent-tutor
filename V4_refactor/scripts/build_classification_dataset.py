#!/usr/bin/env python3
"""
Build classification dataset from MicroTutor conversation logs.

This script collects user inputs and their corresponding tool usage
to build a dataset for training fast input classification models.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from microtutor.core.classification_dataset import (
    ClassificationDatasetBuilder, 
    build_classification_dataset,
    ClassificationExample
)
# Database engine not available in this version
from microtutor.core.config_helper import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def main():
    """Main function to build classification dataset."""
    
    print("🚀 Building Classification Dataset for MicroTutor")
    print("=" * 60)
    
    try:
        # Database not available in this version
        db_engine = None
        logger.info("Will collect from log files only")
        
        # Set up logs directory
        logs_dir = Path("logs")
        if not logs_dir.exists():
            logger.warning(f"Logs directory not found: {logs_dir}")
            return 1
        
        # Build dataset
        logger.info("📊 Collecting classification examples...")
        
        examples, summary = build_classification_dataset(
            db_engine=db_engine,
            logs_dir=logs_dir,
            days_back=30,  # Last 30 days
            limit=1000     # Max 1000 examples
        )
        
        if not examples:
            logger.error("❌ No examples collected. Check your data sources.")
            return 1
        
        # Display summary
        print(f"\n📈 Dataset Summary:")
        print(f"   Total examples: {summary['total_examples']}")
        print(f"   Classification distribution:")
        for cls, count in summary['classification_distribution'].items():
            percentage = (count / summary['total_examples']) * 100
            print(f"     {cls}: {count} ({percentage:.1f}%)")
        
        print(f"\n📊 Confidence Statistics:")
        conf_stats = summary['confidence_stats']
        print(f"   Mean: {conf_stats['mean']:.3f}")
        print(f"   Std:  {conf_stats['std']:.3f}")
        print(f"   Range: {conf_stats['min']:.3f} - {conf_stats['max']:.3f}")
        
        print(f"\n🔧 Tool Usage:")
        for tool, count in summary['tool_usage'].items():
            if tool:  # Skip empty strings
                print(f"   {tool}: {count}")
        
        print(f"\n📝 Input Length Statistics:")
        length_stats = summary['input_length_stats']
        print(f"   Mean: {length_stats['mean']:.1f} characters")
        print(f"   Range: {length_stats['min']} - {length_stats['max']} characters")
        
        print(f"\n📅 Date Range:")
        print(f"   From: {summary['date_range']['earliest']}")
        print(f"   To:   {summary['date_range']['latest']}")
        
        if 'saved_to' in summary:
            print(f"\n💾 Dataset saved to: {summary['saved_to']}")
        
        # Create training data
        logger.info("🔄 Creating training data...")
        builder = ClassificationDatasetBuilder(db_engine, logs_dir)
        training_df = builder.create_training_data(examples)
        
        # Save training data
        training_file = logs_dir / "classification_dataset" / "training_data.csv"
        training_df.to_csv(training_file, index=False)
        logger.info(f"💾 Training data saved to: {training_file}")
        
        # Show sample data
        print(f"\n📋 Sample Data:")
        print(training_df.head().to_string())
        
        print(f"\n✅ Dataset building completed successfully!")
        print(f"\n🎯 Next Steps:")
        print(f"   1. Review the dataset for quality")
        print(f"   2. Train a fast classifier (see train_fast_classifier.py)")
        print(f"   3. Deploy the classifier for real-time routing")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Dataset building failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
