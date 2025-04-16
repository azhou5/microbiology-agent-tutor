import os
from agents.case_generator_rag import CaseGeneratorRAGAgent

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
    # Check if it's a path (for backward compatibility)
    if os.path.exists(organism):
        try:
            with open(organism, 'r') as file:
                return file.read()
        except Exception as e:
            print(f"Error reading case from file: {str(e)}")
    
    # Otherwise, generate a case for the specified organism
    return case_generator.generate_case(organism)
    