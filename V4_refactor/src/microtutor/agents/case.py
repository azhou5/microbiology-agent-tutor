"""
Case Management for Medical Microbiology Tutor (V4)

This module handles loading and generating cases for organisms.
Adapted from V3 to work standalone in V4 structure.
"""

import os
import logging

from microtutor.agents.case_generator_rag import CaseGeneratorRAGAgent

# Initialize the case generator
case_generator = CaseGeneratorRAGAgent()

def get_case(organism):
    """
    Get a case for the specified organism, generating it if it doesn't exist.
    
    Args:
        organism (str): The organism to get a case for.
    
    Returns:
        str: The case text.
    """
    logging.info(f"[BACKEND_START_CASE] 3c. get_case function called for organism: '{organism}'.")
    # Check if it's a path (for backward compatibility)
    if os.path.exists(organism):
        try:
            with open(organism, 'r') as file:
                return file.read()
        except Exception as e:
            print(f"Error reading case from file: {str(e)}")
    
    # Otherwise, generate a case for the specified organism
    logging.info(f"[BACKEND_START_CASE]   - Calling case_generator.generate_case for '{organism}'.")
    return case_generator.generate_case(organism)
    