#!/usr/bin/env python3
"""
Test script for guideline search functionality.

This script demonstrates how to use the GuidelineService to search
clinical guidelines for microbiology education.

Usage:
    python scripts/test_guideline_search.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from microtutor.services.guideline_service import GuidelineService
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_basic_search():
    """Test basic guideline search."""
    print("\n" + "="*80)
    print("TEST 1: Basic Guideline Search")
    print("="*80)
    
    service = GuidelineService(use_tooluniverse=True)
    
    if not service.is_available():
        print("⚠️  Guideline service not available")
        print("💡 Install ToolUniverse: pip install tooluniverse")
        return
    
    print(f"\n✅ Guideline service initialized")
    print(f"📚 Backend: {'ToolUniverse' if service.use_tooluniverse else 'Custom'}")
    print(f"🔍 Available sources: {', '.join(service.get_available_sources())}")
    
    # Search for MRSA
    print("\n🔎 Searching for: MRSA treatment")
    results = await service.search_guidelines(
        query="MRSA treatment",
        sources=["NICE", "PubMed"],
        limit=3
    )
    
    # Print results
    for source, guidelines in results.items():
        print(f"\n📖 {source} Guidelines ({len(guidelines)} found):")
        for idx, guideline in enumerate(guidelines, 1):
            print(f"\n  {idx}. {guideline.get('title', 'Untitled')}")
            print(f"     URL: {guideline.get('url', 'N/A')}")
            summary = guideline.get('summary', guideline.get('abstract', ''))
            if summary:
                print(f"     Summary: {summary[:150]}...")


async def test_organism_search():
    """Test organism-specific guideline search."""
    print("\n" + "="*80)
    print("TEST 2: Organism-Specific Search")
    print("="*80)
    
    service = GuidelineService(use_tooluniverse=True)
    
    if not service.is_available():
        print("⚠️  Guideline service not available")
        return
    
    # Search for specific organism
    organism = "Staphylococcus aureus"
    print(f"\n🦠 Searching guidelines for: {organism}")
    
    result = await service.search_for_organism(
        organism=organism,
        treatment_focus=True,
        limit=2
    )
    
    print(f"\n✅ Query: {result['query']}")
    print(f"📊 Total guidelines found: {result['total_guidelines']}")
    
    # Print results by source
    for source, guidelines in result['results'].items():
        if not isinstance(guidelines, list):
            continue
        
        print(f"\n📖 {source} ({len(guidelines)} guidelines):")
        for guideline in guidelines:
            print(f"  • {guideline.get('title', 'Untitled')}")


async def test_guideline_summary():
    """Test guideline summary generation for LLM context."""
    print("\n" + "="*80)
    print("TEST 3: Guideline Summary for LLM Context")
    print("="*80)
    
    service = GuidelineService(use_tooluniverse=True)
    
    if not service.is_available():
        print("⚠️  Guideline service not available")
        return
    
    # Search guidelines
    print("\n🔎 Searching for: Escherichia coli treatment")
    results = await service.search_guidelines(
        query="Escherichia coli urinary tract infection treatment",
        sources=["NICE", "PubMed"],
        limit=2
    )
    
    # Generate summary
    summary = service.get_guideline_summary(results, max_per_source=2)
    
    print("\n📄 Generated Summary for LLM Context:")
    print("-" * 80)
    print(summary)
    print("-" * 80)
    
    print(f"\n✅ Summary length: {len(summary)} characters")
    print("💡 This summary can be included in LLM system prompts")


async def test_custom_tools():
    """Test custom tool implementations (without ToolUniverse)."""
    print("\n" + "="*80)
    print("TEST 4: Custom Tool Implementations")
    print("="*80)
    
    print("\n🔧 Initializing service with custom tools...")
    service = GuidelineService(use_tooluniverse=False)
    
    if not service.is_available():
        print("⚠️  Custom tools not available")
        return
    
    print(f"✅ Using custom implementations")
    print(f"🔍 Available sources: {', '.join(service.get_available_sources())}")
    
    # Search with custom tools
    print("\n🔎 Searching with custom tools: Pneumonia treatment")
    results = await service.search_guidelines(
        query="Pneumonia treatment guidelines",
        limit=2
    )
    
    total = sum(len(g) for g in results.values() if isinstance(g, list))
    print(f"\n✅ Found {total} guidelines using custom tools")
    
    for source, guidelines in results.items():
        if isinstance(guidelines, list):
            print(f"\n📖 {source}: {len(guidelines)} guidelines")


async def test_tutoring_integration():
    """Test how guidelines integrate into tutoring workflow."""
    print("\n" + "="*80)
    print("TEST 5: Tutoring Integration Example")
    print("="*80)
    
    service = GuidelineService(use_tooluniverse=True)
    
    if not service.is_available():
        print("⚠️  Guideline service not available")
        return
    
    # Simulate case start
    organism = "Neisseria meningitidis"
    print(f"\n🎓 Student starting case about: {organism}")
    
    # Fetch guidelines
    print(f"📚 Fetching treatment guidelines...")
    guidelines = await service.search_for_organism(
        organism=organism,
        treatment_focus=True,
        limit=2
    )
    
    # Generate context for LLM
    guideline_context = service.get_guideline_summary(guidelines['results'])
    
    # Build system prompt
    system_prompt = f"""
You are a medical microbiology tutor using the Socratic method.

The student is learning about {organism}.

## Current Clinical Guidelines

{guideline_context}

## Your Role

- Use the guidelines above to inform your teaching
- Ask probing questions rather than giving direct answers
- Guide the student to discover information themselves
- Ensure teaching aligns with current clinical evidence

Begin the tutoring session.
"""
    
    print("\n📝 Generated System Prompt for Tutor:")
    print("-" * 80)
    print(system_prompt[:800] + "..." if len(system_prompt) > 800 else system_prompt)
    print("-" * 80)
    
    print(f"\n✅ System prompt length: {len(system_prompt)} characters")
    print("💡 This prompt now includes evidence-based guidelines!")


async def run_all_tests():
    """Run all tests."""
    print("\n" + "="*80)
    print("🧪 GUIDELINE SEARCH SERVICE TESTS")
    print("="*80)
    
    try:
        await test_basic_search()
        await asyncio.sleep(1)  # Be respectful with API calls
        
        await test_organism_search()
        await asyncio.sleep(1)
        
        await test_guideline_summary()
        await asyncio.sleep(1)
        
        await test_tutoring_integration()
        await asyncio.sleep(1)
        
        # Optionally test custom tools
        # await test_custom_tools()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS COMPLETED")
        print("="*80)
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        print(f"\n❌ Test failed: {e}")


def main():
    """Main entry point."""
    print("\n🚀 Starting guideline search tests...")
    print("="*80)
    
    # Check dependencies
    try:
        import requests
        import bs4
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("💡 Install with: pip install requests beautifulsoup4")
        return
    
    # Run tests
    asyncio.run(run_all_tests())
    
    print("\n📚 For more information:")
    print("  - Documentation: docs/GUIDELINE_TOOLS_INTEGRATION.md")
    print("  - ToolUniverse: https://github.com/mims-harvard/ToolUniverse")


if __name__ == "__main__":
    main()

