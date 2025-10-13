"""
Test script for DDX Case Search Tool.

Run this test to verify the DDX case search functionality.
"""

import sys
from pathlib import Path
import logging

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from microtutor.tools import get_tool_engine, search_ddx_cases

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_ddx_search_via_engine():
    """Test DDX search using the tool engine."""
    logger.info("=" * 80)
    logger.info("Test 1: DDX Case Search via Tool Engine")
    logger.info("=" * 80)
    
    # Get the tool engine
    engine = get_tool_engine()
    
    # List all available tools
    logger.info(f"Available tools: {engine.list_tools()}")
    
    # Search for a case with chest pain
    logger.info("\n>>> Searching for cases with 'chest pain'...")
    result = engine.execute_tool(
        'ddx_case_search',
        {
            'presenting_complaint': 'chest pain',
            'return_top_n': 3,
            'extract_full_text': False  # Don't extract full text for this test
        }
    )
    
    if result['success']:
        data = result['result']
        logger.info(f"\n✅ Found {len(data['matches'])} matching cases:")
        
        for i, match in enumerate(data['matches'], 1):
            logger.info(f"\n  {i}. Episode {match['episode_number']}")
            logger.info(f"     Date: {match['date']}")
            logger.info(f"     Complaint: {match['presenting_complaint']}")
            logger.info(f"     Similarity: {match['similarity_score']}")
            logger.info(f"     File: {match['filename']}")
    else:
        logger.error(f"❌ Tool execution failed: {result.get('error')}")
    
    return result


def test_ddx_search_with_extraction():
    """Test DDX search with full text extraction."""
    logger.info("\n" + "=" * 80)
    logger.info("Test 2: DDX Case Search with Full Text Extraction")
    logger.info("=" * 80)
    
    # Get the tool engine
    engine = get_tool_engine()
    
    # Search for a case with fever
    logger.info("\n>>> Searching for cases with 'fever' and extracting full text...")
    result = engine.execute_tool(
        'ddx_case_search',
        {
            'presenting_complaint': 'fever',
            'return_top_n': 1,
            'extract_full_text': True
        }
    )
    
    if result['success']:
        data = result['result']
        
        if data.get('top_match'):
            top_match = data['top_match']
            metadata = top_match['metadata']
            
            logger.info(f"\n✅ Top match extracted:")
            logger.info(f"   Episode: {metadata['episode_number']}")
            logger.info(f"   Complaint: {metadata['presenting_complaint']}")
            logger.info(f"   Date: {metadata['date']}")
            logger.info(f"   Text length: {len(top_match['case_text'])} characters")
            
            # Show first 500 characters of case text
            preview = top_match['case_text'][:500]
            logger.info(f"\n   Case preview:\n   {preview}...")
            
            # Show formatted version
            logger.info(f"\n   Formatted case ready for LLM:")
            logger.info(f"   {top_match['formatted_case'][:800]}...")
        else:
            logger.warning("⚠️ No matches found")
    else:
        logger.error(f"❌ Tool execution failed: {result.get('error')}")
    
    return result


def test_legacy_function():
    """Test the legacy function wrapper."""
    logger.info("\n" + "=" * 80)
    logger.info("Test 3: Legacy Function Wrapper")
    logger.info("=" * 80)
    
    logger.info("\n>>> Using search_ddx_cases() function...")
    
    try:
        result = search_ddx_cases(
            presenting_complaint='shortness of breath',
            return_top_n=2,
            extract_full_text=False
        )
        
        logger.info(f"\n✅ Found {len(result['matches'])} matches:")
        for match in result['matches']:
            logger.info(f"   - Episode {match['episode_number']}: {match['presenting_complaint']}")
    
    except Exception as e:
        logger.error(f"❌ Function call failed: {e}")


def test_fuzzy_matching():
    """Test fuzzy matching capabilities."""
    logger.info("\n" + "=" * 80)
    logger.info("Test 4: Fuzzy Matching")
    logger.info("=" * 80)
    
    engine = get_tool_engine()
    
    # Test various search queries
    test_queries = [
        'SOB',  # Shorthand for shortness of breath
        'difficulty breathing',
        'belly pain',  # Colloquial for abdominal pain
        'weakness',
        'syncope',
    ]
    
    for query in test_queries:
        logger.info(f"\n>>> Searching for: '{query}'")
        result = engine.execute_tool(
            'ddx_case_search',
            {
                'presenting_complaint': query,
                'return_top_n': 2,
                'extract_full_text': False
            }
        )
        
        if result['success'] and result['result']['matches']:
            matches = result['result']['matches']
            logger.info(f"   Found {len(matches)} matches:")
            for match in matches:
                logger.info(f"   - {match['presenting_complaint']} (score: {match['similarity_score']})")
        else:
            logger.info(f"   No matches found")


def main():
    """Run all tests."""
    logger.info("Starting DDX Case Search Tool Tests\n")
    
    try:
        # Run tests
        test_ddx_search_via_engine()
        test_ddx_search_with_extraction()
        test_legacy_function()
        test_fuzzy_matching()
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ All tests completed!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"\n❌ Test failed with error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

