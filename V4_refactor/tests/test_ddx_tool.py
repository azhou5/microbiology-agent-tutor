"""
Test script for DDX Case Search Tool.

This demonstrates both usage patterns:
1. Programmatic case generation (for backend pipeline)
2. LLM tool usage (for dynamic case selection by tutor)
"""

import sys
import json
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from microtutor.agents.case_generator_ddx import (
    DDXCaseGenerator,
    generate_case,
    list_available_complaints
)
from microtutor.tools import get_tool_engine


def test_case_generation_pipeline():
    """Test 1: Use in case generation pipeline (programmatic)."""
    print("=" * 80)
    print("TEST 1: Case Generation Pipeline (Programmatic)")
    print("=" * 80)
    
    # Initialize generator
    generator = DDXCaseGenerator()
    
    # Search for cases
    print("\n🔍 Searching for cases with 'chest pain'...")
    search_results = generator.search_cases("chest pain", max_results=3)
    
    if search_results["success"]:
        matches = search_results["data"]["matches"]
        print(f"\n✅ Found {len(matches)} matches:")
        for i, match in enumerate(matches, 1):
            print(f"   {i}. Episode {match['episode_number']}: {match['presenting_complaint']}")
            print(f"      Similarity: {match['similarity_score']:.2%}")
    
    # Generate a case (no adaptation)
    print("\n📄 Generating case (raw)...")
    result = generator.generate_case_from_ddx("chest pain")
    
    if result["success"]:
        print("\n✅ Case generated successfully!")
        print(f"   Episode: {result['metadata']['episode_number']}")
        print(f"   Complaint: {result['metadata']['presenting_complaint']}")
        print(f"   Case length: {len(result['case'])} characters")
        print(f"\n   Preview (first 500 chars):")
        print(f"   {result['case'][:500]}...")
    else:
        print(f"\n❌ Failed: {result.get('error')}")
    
    # Generate adapted case
    print("\n🎓 Generating case (adapted for medical student)...")
    result_adapted = generator.generate_case_from_ddx(
        "chest pain",
        adapt_for_level="medical_student",
        focus_areas=["cardiology", "diagnostics"]
    )
    
    if result_adapted["success"]:
        print("\n✅ Adapted case generated!")
        print(f"   Adapted: {result_adapted['adapted']}")
        print(f"   Case length: {len(result_adapted['case'])} characters")


def test_llm_tool_usage():
    """Test 2: Use as LLM tool (for dynamic case selection)."""
    print("\n\n" + "=" * 80)
    print("TEST 2: LLM Tool Usage (Dynamic Case Selection)")
    print("=" * 80)
    
    # Get tool engine
    engine = get_tool_engine()
    
    print(f"\n🔧 Available tools: {engine.list_tools()}")
    
    # Check if DDX tool is registered
    if "ddx_case_search" in engine.list_tools():
        print("✅ DDX Case Search tool is registered!")
        
        # Get tool schema (for LLM function calling)
        schemas = engine.get_tool_schemas()
        ddx_schema = next((s for s in schemas if s["function"]["name"] == "ddx_case_search"), None)
        
        if ddx_schema:
            print("\n📋 Tool Schema (for OpenAI function calling):")
            print(json.dumps(ddx_schema, indent=2))
        
        # Execute tool through engine
        print("\n🤖 Executing DDX tool through engine...")
        result = engine.execute_tool(
            "ddx_case_search",
            {
                "presenting_complaint": "fever",
                "return_top_n": 2,
                "extract_full_text": True
            }
        )
        
        if result["success"]:
            print("\n✅ Tool executed successfully!")
            data = result["result"]
            print(f"   Found {len(data['matches'])} matches")
            if data.get("top_match"):
                print(f"   Top match: Episode {data['top_match']['metadata']['episode_number']}")
                print(f"   Complaint: {data['top_match']['metadata']['presenting_complaint']}")
        else:
            print(f"\n❌ Tool execution failed: {result.get('error')}")
    else:
        print("❌ DDX tool not found in registry")


def test_convenience_functions():
    """Test 3: Quick convenience functions."""
    print("\n\n" + "=" * 80)
    print("TEST 3: Convenience Functions")
    print("=" * 80)
    
    # List available complaints
    print("\n📋 Listing available presenting complaints...")
    complaints = list_available_complaints()
    
    if complaints:
        print(f"\n✅ Found {len(complaints)} unique presenting complaints")
        print("\n   Sample complaints (first 20):")
        for complaint in complaints[:20]:
            print(f"   - {complaint}")
    else:
        print("\n⚠️  No complaints found (check PDF directory)")
    
    # Quick case generation
    print("\n🚀 Quick case generation using convenience function...")
    case = generate_case("abdominal pain", level="resident")
    
    if case:
        print(f"\n✅ Case generated! Length: {len(case)} characters")
        print(f"\n   Preview:")
        print(f"   {case[:400]}...")
    else:
        print("\n❌ Case generation failed")


def test_batch_generation():
    """Test 4: Batch case generation."""
    print("\n\n" + "=" * 80)
    print("TEST 4: Batch Case Generation")
    print("=" * 80)
    
    generator = DDXCaseGenerator()
    
    complaints = ["syncope", "headache", "dyspnea"]
    
    print(f"\n📦 Generating cases for: {complaints}")
    
    output_dir = project_root / "Case_Outputs" / "ddx_generated"
    
    results = generator.batch_generate_cases(
        complaints,
        output_dir=str(output_dir),
        adapt_for_level="medical_student"
    )
    
    print(f"\n✅ Batch generation complete!")
    print(f"   Total: {results['total']}")
    print(f"   Successful: {results['successful']}")
    print(f"   Failed: {results['failed']}")
    
    if output_dir.exists():
        files = list(output_dir.glob("*.json"))
        print(f"   Files saved: {len(files)}")


def main():
    """Run all tests."""
    print("\n" + "🧪" * 40)
    print("DDX CASE SEARCH TOOL - COMPREHENSIVE TEST")
    print("🧪" * 40)
    
    try:
        # Test 1: Case generation pipeline
        test_case_generation_pipeline()
        
        # Test 2: LLM tool usage
        test_llm_tool_usage()
        
        # Test 3: Convenience functions
        test_convenience_functions()
        
        # Test 4: Batch generation
        test_batch_generation()
        
        print("\n\n" + "=" * 80)
        print("✅ ALL TESTS COMPLETED")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

