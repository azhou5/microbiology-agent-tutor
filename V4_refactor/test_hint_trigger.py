#!/usr/bin/env python3
"""
Test script to verify hint tool triggers for the immunocompromise scenario.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from microtutor.tools.hint import HintTool
from microtutor.tools.prompts import get_hint_system_prompt, get_hint_user_prompt
import json

def test_hint_tool_trigger():
    """Test that hint tool provides appropriate guidance for immunocompromise scenario."""
    
    # Load hint tool configuration
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'tools', 'hint_tool.json')
    with open(config_path, 'r') as f:
        tool_config = json.load(f)
    
    # Create hint tool instance
    hint_tool = HintTool(tool_config)
    
    # Test scenario from the image
    test_case = """
    A 22-year-old college student presents with fever, cough, and shortness of breath for 3 days.
    She has no significant past medical history and takes only occasional antihistamines for seasonal allergies.
    She lives in a dormitory and has been attending weekend social events.
    """
    
    test_input = "I'm worried about immunocompromise. anything else I should be worried about?"
    
    # Test the hint tool
    try:
        result = hint_tool.run({
            'input_text': test_input,
            'case': test_case,
            'covered_topics': ['fever', 'cough', 'shortness of breath'],
            'model': 'gpt-4'
        })
        
        if result['success']:
            print("✅ Hint tool executed successfully!")
            print(f"Input: {test_input}")
            print(f"Response: {result['result']}")
            print("\nThe hint tool should now trigger for this type of vague guidance request.")
        else:
            print("❌ Hint tool failed:")
            print(f"Error: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error testing hint tool: {e}")

def test_prompt_quality():
    """Test the quality of hint prompts."""
    
    test_case = """
    A 22-year-old college student presents with fever, cough, and shortness of breath for 3 days.
    She has no significant past medical history and takes only occasional antihistamines for seasonal allergies.
    She lives in a dormitory and has been attending weekend social events.
    """
    
    test_input = "I'm worried about immunocompromise. anything else I should be worried about?"
    covered_topics = ['fever', 'cough', 'shortness of breath']
    
    # Test system prompt
    system_prompt = get_hint_system_prompt()
    print("📋 System Prompt:")
    print(system_prompt)
    print("\n" + "="*50 + "\n")
    
    # Test user prompt
    user_prompt = get_hint_user_prompt(test_case, test_input, covered_topics)
    print("📋 User Prompt:")
    print(user_prompt)
    print("\n" + "="*50 + "\n")
    
    # Check if prompts contain key elements
    key_elements = [
        "immunocompromise" in system_prompt.lower() or "what else should I be worried about" in system_prompt.lower(),
        "specific" in system_prompt.lower(),
        "guidance" in system_prompt.lower(),
        "strategic hint" in user_prompt.lower()
    ]
    
    if all(key_elements):
        print("✅ Prompts contain all key elements for handling the immunocompromise scenario")
    else:
        print("❌ Prompts missing some key elements")
        print(f"Key elements found: {key_elements}")

if __name__ == "__main__":
    print("🧪 Testing Hint Tool for Immunocompromise Scenario")
    print("="*60)
    
    print("\n1. Testing Prompt Quality:")
    test_prompt_quality()
    
    print("\n2. Testing Hint Tool Execution:")
    test_hint_tool_trigger()
    
    print("\n✅ Test completed!")
