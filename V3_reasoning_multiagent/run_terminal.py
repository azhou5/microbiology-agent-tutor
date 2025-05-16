#!/usr/bin/env python
import sys
import config
from tutor import MedicalMicrobiologyTutor

def run_terminal_mode():
    """Run the Medical Microbiology Tutor in terminal mode."""
    print("\n=== Medical Microbiology Tutor - Terminal Mode ===\n")
    
    # Initialize the tutor
    tutor = MedicalMicrobiologyTutor(
        output_tool_directly=config.OUTPUT_TOOL_DIRECTLY,
        run_with_faiss=config.USE_FAISS,
        reward_model_sampling=config.REWARD_MODEL_SAMPLING
    )
    
    # Start a new case with the default organism
    organism = config.DEFAULT_ORGANISM
    initial_message = tutor.start_new_case(organism=organism)
    
    # Print the initial case description
    print(f"Starting new case with organism: {organism}")
    print(f"\nTutor: {initial_message}\n")
    
    # Main interaction loop
    try:
        while True:
            # Get user input
            user_message = input("You: ")
            
            # Check for exit command
            if user_message.lower() in ["exit", "quit", "q"]:
                print("\nExiting terminal mode. Goodbye!")
                break
                
            # Process the user message
            tutor_response = tutor(user_message)
            
            # Print the tutor's response
            print(f"\nTutor: {tutor_response}\n")
            
    except KeyboardInterrupt:
        print("\n\nSession terminated by user. Goodbye!")
    except Exception as e:
        print(f"\nError: {str(e)}")

if __name__ == "__main__":
    # Override configuration if command line arguments are provided
    if len(sys.argv) > 1:
        config.DEFAULT_ORGANISM = sys.argv[1]
        
    run_terminal_mode() 