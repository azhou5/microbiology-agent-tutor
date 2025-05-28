#!/usr/bin/env python3
"""
Script to pregenerate cases for all supported organisms.
This will populate the case cache so users don't have to wait for generation.
"""

import os
import sys
import time
from typing import List
from dotenv import load_dotenv

# Add the project root to the path so we can import agents
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.case_generator_rag import CaseGeneratorRAGAgent

# Load environment variables
load_dotenv()

# List of organisms from the HTML template
ORGANISMS = [
    # Bacteria
    "staphylococcus aureus",
    "escherichia coli", 
    "nocardia species",
    "borrelia burgdorferi",
    "streptococcus pneumoniae",
    
    # Viruses
    "hsv-1",
    "influenza a",
    "hiv",
    "ebv",
    
    # Fungi
    "candida albicans",
    "aspergillus fumigatus",
    
    # Parasites
    "plasmodium falciparum",
    "taenia solium"
]

def pregenerate_all_cases(organisms: List[str] = None, force_regenerate: bool = False):
    """
    Pregenerate cases for all specified organisms.
    
    Args:
        organisms: List of organism names. If None, uses the default list.
        force_regenerate: If True, regenerates even if cached cases exist.
    """
    if organisms is None:
        organisms = ORGANISMS
    
    print(f"Starting case pregeneration for {len(organisms)} organisms...")
    print(f"Force regenerate: {force_regenerate}")
    print("-" * 60)
    
    # Initialize the case generator
    try:
        case_generator = CaseGeneratorRAGAgent()
        print("Successfully initialized CaseGeneratorRAGAgent")
    except Exception as e:
        print(f"Error initializing CaseGeneratorRAGAgent: {e}")
        return
    
    # Get existing cached organisms if not force regenerating
    existing_cache = set()
    if not force_regenerate:
        try:
            existing_cache = set(case_generator.get_cached_organisms())
            print(f"Found {len(existing_cache)} existing cached cases")
        except Exception as e:
            print(f"Error getting existing cache: {e}")
    
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    for i, organism in enumerate(organisms, 1):
        print(f"\n[{i}/{len(organisms)}] Processing: {organism}")
        
        # Check if already cached (unless force regenerating)
        normalized_name = case_generator._normalize_organism_name(organism)
        if not force_regenerate and normalized_name in existing_cache:
            print(f"  ✓ Already cached, skipping...")
            skipped_count += 1
            continue
        
        try:
            start_time = time.time()
            
            if force_regenerate:
                # Force regeneration (clears cache first)
                case_text = case_generator.regenerate_case(organism)
            else:
                # Normal generation (will use cache if exists)
                case_text = case_generator.generate_case(organism)
            
            end_time = time.time()
            duration = end_time - start_time
            
            if case_text and len(case_text.strip()) > 100:  # Basic validation
                print(f"  ✓ Generated successfully ({duration:.1f}s)")
                print(f"    Case length: {len(case_text)} characters")
                success_count += 1
            else:
                print(f"  ✗ Generated case seems too short or empty")
                error_count += 1
                
        except Exception as e:
            print(f"  ✗ Error generating case: {e}")
            error_count += 1
        
        # Add a small delay to be nice to the API
        if i < len(organisms):
            time.sleep(1)
    
    # Summary
    print("\n" + "=" * 60)
    print("PREGENERATION SUMMARY")
    print("=" * 60)
    print(f"Total organisms: {len(organisms)}")
    print(f"Successfully generated: {success_count}")
    print(f"Errors: {error_count}")
    print(f"Skipped (already cached): {skipped_count}")
    print(f"Cache location: {case_generator.case_cache_file}")
    
    # Show final cache status
    try:
        final_cache = case_generator.get_cached_organisms()
        print(f"Total cached cases: {len(final_cache)}")
        print("\nCached organisms:")
        for org in sorted(final_cache):
            print(f"  - {org}")
    except Exception as e:
        print(f"Error getting final cache status: {e}")

def list_cached_cases():
    """List all currently cached cases."""
    try:
        case_generator = CaseGeneratorRAGAgent()
        cached_organisms = case_generator.get_cached_organisms()
        
        print(f"Currently cached cases ({len(cached_organisms)}):")
        print("-" * 40)
        if cached_organisms:
            for org in sorted(cached_organisms):
                print(f"  - {org}")
        else:
            print("  No cached cases found.")
    except Exception as e:
        print(f"Error listing cached cases: {e}")

def clear_all_cache():
    """Clear all cached cases."""
    try:
        case_generator = CaseGeneratorRAGAgent()
        case_generator.clear_cache()
        print("All cached cases cleared successfully.")
    except Exception as e:
        print(f"Error clearing cache: {e}")

def main():
    """Main function with command line argument handling."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Pregenerate cases for microbiology organisms",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pregenerate_cases.py                    # Generate cases for all organisms
  python pregenerate_cases.py --force            # Force regenerate all cases
  python pregenerate_cases.py --list             # List cached cases
  python pregenerate_cases.py --clear            # Clear all cached cases
  python pregenerate_cases.py --organisms "staph aureus" "e coli"  # Generate specific organisms
        """
    )
    
    parser.add_argument(
        "--force", 
        action="store_true",
        help="Force regeneration of cases even if they already exist in cache"
    )
    
    parser.add_argument(
        "--list",
        action="store_true", 
        help="List all currently cached cases and exit"
    )
    
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear all cached cases and exit"
    )
    
    parser.add_argument(
        "--organisms",
        nargs="+",
        help="Specific organisms to generate cases for (space-separated)"
    )
    
    args = parser.parse_args()
    
    # Handle different modes
    if args.list:
        list_cached_cases()
        return
    
    if args.clear:
        confirm = input("Are you sure you want to clear all cached cases? (y/N): ")
        if confirm.lower() == 'y':
            clear_all_cache()
        else:
            print("Cancelled.")
        return
    
    # Determine which organisms to process
    organisms_to_process = args.organisms if args.organisms else ORGANISMS
    
    # Run pregeneration
    pregenerate_all_cases(organisms_to_process, args.force)

if __name__ == "__main__":
    main() 