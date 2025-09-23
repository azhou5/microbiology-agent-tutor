#!/usr/bin/env python3
"""
Test script for socratic routing mechanism.

This script tests the new routing functionality where messages get passed
directly to the socratic agent once it's been called, until the user asks
to continue or the socratic agent indicates the section is over.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tutor import MedicalMicrobiologyTutor
import config

def test_socratic_routing():
    """Test the socratic routing mechanism."""
    print("Testing Socratic Routing Mechanism")
    print("=" * 50)
    
    # Initialize tutor
    tutor = MedicalMicrobiologyTutor()
    
    # Start a new case
    print("1. Starting new case...")
    initial_response = tutor.start_new_case("staphylococcus aureus")
    print(f"Initial response: {initial_response}")
    print(f"Socratic mode: {tutor.socratic_mode}")
    print()
    
    # Simulate calling socratic tool (this would normally be done by the LLM)
    print("2. Simulating socratic tool call...")
    # Manually set socratic mode to simulate the tool being called
    tutor.socratic_mode = True
    tutor.socratic_conversation_count = 1
    print(f"Socratic mode set to: {tutor.socratic_mode}")
    print()
    
    # Test direct routing to socratic
    print("3. Testing direct routing to socratic agent...")
    test_messages = [
        "I think the patient has pneumonia based on the symptoms",
        "The fever and cough suggest a bacterial infection",
        "I'm considering staphylococcus aureus as the most likely cause"
    ]
    
    for i, message in enumerate(test_messages, 1):
        print(f"   Message {i}: {message}")
        print(f"   Socratic mode before: {tutor.socratic_mode}")
        
        # This should route directly to socratic agent
        response = tutor(message)
        print(f"   Response: {response}")
        print(f"   Socratic mode after: {tutor.socratic_mode}")
        print(f"   Conversation count: {tutor.socratic_conversation_count}")
        print()
    
    # Test exit condition
    print("4. Testing exit condition...")
    exit_message = "Let's continue with the case"
    print(f"Exit message: {exit_message}")
    print(f"Socratic mode before: {tutor.socratic_mode}")
    
    response = tutor(exit_message)
    print(f"Response: {response}")
    print(f"Socratic mode after: {tutor.socratic_mode}")
    print()
    
    # Test normal flow after exit
    print("5. Testing normal flow after socratic exit...")
    normal_message = "What should I do next?"
    print(f"Normal message: {normal_message}")
    print(f"Socratic mode before: {tutor.socratic_mode}")
    
    response = tutor(normal_message)
    print(f"Response: {response}")
    print(f"Socratic mode after: {tutor.socratic_mode}")
    print()
    
    print("Test completed!")

def test_completion_signal_detection():
    """Test completion signal detection."""
    print("\nTesting Completion Signal Detection")
    print("=" * 50)
    
    tutor = MedicalMicrobiologyTutor()
    
    # Test completion signal detection
    test_responses = [
        "That's a great analysis! [SOCRATIC_COMPLETE]",
        "I think we've covered the key points. [SOCRATIC_COMPLETE]",
        "What about the fever?",
        "Consider the patient's age. [SOCRATIC_COMPLETE]",
        "Let's move on to the next case. [SOCRATIC_COMPLETE]",
        "Can you explain more about the symptoms?"
    ]
    
    print("Testing completion signal detection:")
    for response in test_responses:
        has_signal = "[SOCRATIC_COMPLETE]" in response
        cleaned = response.replace("[SOCRATIC_COMPLETE]", "").strip()
        print(f"  '{response}' -> Signal: {has_signal}, Cleaned: '{cleaned}'")
    
    print("\nTesting socratic mode state management:")
    tutor.socratic_mode = True
    print(f"Initial socratic mode: {tutor.socratic_mode}")
    
    # Simulate a response with completion signal
    response_with_signal = "Great work! [SOCRATIC_COMPLETE]"
    print(f"Response with signal: '{response_with_signal}'")
    
    # Test the completion detection logic
    completion_signal = "[SOCRATIC_COMPLETE]"
    is_complete = completion_signal in response_with_signal
    print(f"Completion detected: {is_complete}")
    
    if is_complete:
        tutor.socratic_mode = False
        print(f"Socratic mode after completion: {tutor.socratic_mode}")

if __name__ == "__main__":
    # Note: This test requires the full environment to be set up
    # and may not work without proper API keys and dependencies
    print("Socratic Routing Test")
    print("Note: This test requires proper environment setup")
    print()
    
    try:
        test_completion_signal_detection()
        # Uncomment the line below to run the full test (requires API setup)
        # test_socratic_routing()
    except Exception as e:
        print(f"Test failed with error: {e}")
        print("This is expected if the environment is not fully set up.")
