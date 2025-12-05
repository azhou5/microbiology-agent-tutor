"""
Case Management for Medical Microbiology Tutor (V4)

This module handles loading and generating cases for organisms.
Adapted from V3 to work standalone in V4 structure.
"""

import os
import logging

from microtutor.services.case.case_generator_rag import CaseGeneratorRAGAgent

# Initialize the case generator
case_generator = CaseGeneratorRAGAgent()

def get_case(organism: str) -> str:
    """
    Get a case for the specified organism.
    
    Priority order:
    1. Check HPI_per_organism.json (cached full case descriptions from data/cases/cached/)
    2. Check case_cache.json (cached generated cases)
    3. Generate new case using QDRANT RAG (if available) or fallback
    
    Args:
        organism: The organism to get a case for
    
    Returns:
        str: The case text (full case description)
    """
    logging.info(f"[BACKEND_START_CASE] 3c. get_case function called for organism: '{organism}'.")
    
    # Check if it's a path (for backward compatibility)
    if os.path.exists(organism):
        try:
            with open(organism, 'r') as file:
                return file.read()
        except Exception as e:
            print(f"Error reading case from file: {str(e)}")
    
    # Generate or retrieve case for the specified organism
    # Priority: HPI_per_organism.json -> case_cache.json -> QDRANT RAG generation
    logging.info(f"[BACKEND_START_CASE]   - Calling case_generator.generate_case for '{organism}'.")
    return case_generator.generate_case(organism)
    