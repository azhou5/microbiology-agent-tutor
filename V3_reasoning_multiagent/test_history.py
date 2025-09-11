#!/usr/bin/env python3
"""
Test script to verify that the tutor properly maintains conversation and case history.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tutor import MedicalMicrobiologyTutor

def test_history_maintenance():
    print("Testing tutor history maintenance...\n")
    
    # Create a tutor instance
    tutor = MedicalMicrobiologyTutor()
    
    # Start a new case
    print("1. Starting new case with Staphylococcus aureus...")
    initial_message = tutor.start_new_case("staphylococcus aureus")
    print(f"Initial message: {initial_message}")
    
    # Check that the system message contains the case
    print("\n2. Checking system message...")
    system_msg = tutor.messages[0]["content"]
    if "Initializing..." in system_msg:
        print("❌ ERROR: System message still shows 'Initializing...'")
    elif "Here is the case:" in system_msg:
        print("✓ System message contains case information")
    else:
        print("❌ ERROR: System message doesn't contain expected case marker")
    
    # Check case_description
    print("\n3. Checking case_description...")
    if tutor.case_description:
        print(f"✓ Case description loaded: {tutor.case_description[:100]}...")
    else:
        print("❌ ERROR: No case description loaded")
    
    # Test a patient-directed question
    print("\n4. Testing patient-directed question...")
    response = tutor("When did this start?")
    print(f"Response: {response}")
    
    if "Patient:" in response or "[Action]" in tutor.messages[-2]["content"]:
        print("✓ Question was routed to patient tool")
    else:
        print("❌ ERROR: Question was not routed to patient tool")
    
    # Check message history
    print("\n5. Checking message history...")
    print(f"Total messages: {len(tutor.messages)}")
    for i, msg in enumerate(tutor.messages):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")[:100] + "..." if len(msg.get("content", "")) > 100 else msg.get("content", "")
        print(f"  [{i}] {role}: {content}")
    
    # Test resetting
    print("\n6. Testing reset...")
    tutor.reset()
    if tutor.case_description is None and tutor.messages[0]["content"] == "Initializing...":
        print("✓ Reset cleared case context as expected")
    else:
        print("❌ ERROR: Reset didn't properly clear case context")

if __name__ == "__main__":
    test_history_maintenance() 