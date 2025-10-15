#!/usr/bin/env python3
"""
Simple test script to verify hint tool prompts for the immunocompromise scenario.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_hint_prompts():
    """Test the quality of hint prompts without requiring full dependencies."""
    
    # Import only the prompt functions
    from microtutor.tools.prompts import get_hint_system_prompt, get_hint_user_prompt
    
    test_case = """
    A 22-year-old college student presents with fever, cough, and shortness of breath for 3 days.
    She has no significant past medical history and takes only occasional antihistamines for seasonal allergies.
    She lives in a dormitory and has been attending weekend social events.
    """
    
    test_input = "I'm worried about immunocompromise. anything else I should be worried about?"
    covered_topics = ['fever', 'cough', 'shortness of breath']
    
    print("🧪 Testing Hint Tool Prompts for Immunocompromise Scenario")
    print("="*70)
    
    # Test system prompt
    system_prompt = get_hint_system_prompt()
    print("\n📋 System Prompt:")
    print("-" * 50)
    print(system_prompt)
    
    # Test user prompt
    user_prompt = get_hint_user_prompt(test_case, test_input, covered_topics)
    print("\n📋 User Prompt:")
    print("-" * 50)
    print(user_prompt)
    
    # Check if prompts contain key elements for the immunocompromise scenario
    print("\n🔍 Analyzing Prompt Quality:")
    print("-" * 50)
    
    key_elements = {
        "Contains 'what else should I be worried about' guidance": "what else should I be worried about" in system_prompt.lower(),
        "Contains specific guidance examples": "specific" in system_prompt.lower() and "instead of" in system_prompt.lower(),
        "Contains immunocompromise scenario handling": "immunocompromise" in system_prompt.lower() or "risk factors" in system_prompt.lower(),
        "Contains systematic approach guidance": "systematic" in system_prompt.lower(),
        "User prompt asks for strategic hint": "strategic hint" in user_prompt.lower(),
        "User prompt provides context": "student seems stuck" in user_prompt.lower(),
    }
    
    for element, found in key_elements.items():
        status = "✅" if found else "❌"
        print(f"{status} {element}")
    
    # Overall assessment
    found_count = sum(key_elements.values())
    total_count = len(key_elements)
    
    print(f"\n📊 Overall Quality: {found_count}/{total_count} key elements found")
    
    if found_count >= total_count * 0.8:
        print("✅ Prompts are well-configured for the immunocompromise scenario!")
    else:
        print("⚠️  Prompts may need further refinement")
    
    print("\n🎯 Expected Behavior:")
    print("When a student asks 'I'm worried about immunocompromise. anything else I should be worried about?'")
    print("The hint tool should provide specific guidance about:")
    print("- Risk factors to investigate")
    print("- Specific questions to ask")
    print("- Systematic approach to the case")
    print("- Without revealing the diagnosis")

if __name__ == "__main__":
    test_hint_prompts()
