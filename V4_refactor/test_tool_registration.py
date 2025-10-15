#!/usr/bin/env python3
"""
Test script to verify all tools are properly registered in the engine.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_tool_registration():
    """Test that all expected tools are registered in the engine."""
    
    print("🧪 Testing Tool Registration")
    print("="*50)
    
    try:
        from microtutor.tools import get_tool_engine, list_tools
        
        # Get the tool engine
        engine = get_tool_engine()
        
        # List all available tools
        available_tools = list_tools()
        
        print(f"\n📋 Available Tools ({len(available_tools)}):")
        print("-" * 40)
        for tool in sorted(available_tools):
            print(f"✅ {tool}")
        
        # Expected tools based on the configurations
        expected_tools = [
            "patient",
            "socratic", 
            "hint",
            "ddx_case_search",
            "update_phase",
            "tests_management",
            "problem_representation",
            "feedback",
            "mcq"
        ]
        
        print(f"\n🔍 Expected Tools ({len(expected_tools)}):")
        print("-" * 40)
        for tool in sorted(expected_tools):
            status = "✅" if tool in available_tools else "❌"
            print(f"{status} {tool}")
        
        # Check for missing tools
        missing_tools = [tool for tool in expected_tools if tool not in available_tools]
        extra_tools = [tool for tool in available_tools if tool not in expected_tools]
        
        print(f"\n📊 Registration Status:")
        print("-" * 40)
        print(f"✅ Registered: {len(available_tools)}")
        print(f"🎯 Expected: {len(expected_tools)}")
        print(f"❌ Missing: {len(missing_tools)}")
        print(f"➕ Extra: {len(extra_tools)}")
        
        if missing_tools:
            print(f"\n❌ Missing Tools:")
            for tool in missing_tools:
                print(f"   - {tool}")
        
        if extra_tools:
            print(f"\n➕ Extra Tools:")
            for tool in extra_tools:
                print(f"   - {tool}")
        
        # Test tool execution for key tools
        print(f"\n🔧 Testing Tool Execution:")
        print("-" * 40)
        
        test_cases = [
            ("patient", {"input_text": "How are you feeling?", "case": "Test case"}),
            ("hint", {"input_text": "I need help", "case": "Test case"}),
            ("tests_management", {"input_text": "What tests should I order?", "case": "Test case"}),
        ]
        
        for tool_name, args in test_cases:
            if tool_name in available_tools:
                try:
                    result = engine.execute_tool(tool_name, args)
                    if result.get('success'):
                        print(f"✅ {tool_name}: Execution successful")
                    else:
                        print(f"⚠️  {tool_name}: Execution failed - {result.get('error', 'Unknown error')}")
                except Exception as e:
                    print(f"❌ {tool_name}: Exception - {e}")
            else:
                print(f"❌ {tool_name}: Not available")
        
        # Overall assessment
        if len(missing_tools) == 0:
            print(f"\n✅ All expected tools are registered!")
        else:
            print(f"\n⚠️  Some tools are missing from registration")
        
        return len(missing_tools) == 0
        
    except Exception as e:
        print(f"❌ Error testing tool registration: {e}")
        return False

if __name__ == "__main__":
    success = test_tool_registration()
    if success:
        print("\n🎉 Tool registration test passed!")
    else:
        print("\n💥 Tool registration test failed!")
