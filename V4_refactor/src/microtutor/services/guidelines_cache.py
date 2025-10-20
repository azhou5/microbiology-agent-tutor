"""
Guidelines Cache Service - Simple async pre-fetching of clinical guidelines.

This service handles:
1. Async pre-fetching of guidelines when case starts
2. Caching guidelines in TutorContext
3. Providing guidelines to tools that need them

The actual ToolUniverse calls are still made by individual tools,
but this service coordinates the pre-fetching for better performance.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

# Import ToolUniverse conditionally - only when needed
try:
    from tooluniverse import ToolUniverse
    TOOLUNIVERSE_AVAILABLE = True
except ImportError:
    ToolUniverse = None
    TOOLUNIVERSE_AVAILABLE = False

logger = logging.getLogger(__name__)

# Global singleton for ToolUniverse to avoid re-initialization
_tooluniverse_instance = None


def get_tooluniverse_singleton():
    """Get or create ToolUniverse singleton instance."""
    global _tooluniverse_instance
    
    if _tooluniverse_instance is None and TOOLUNIVERSE_AVAILABLE:
        _tooluniverse_instance = ToolUniverse()
        _tooluniverse_instance.load_tools()
        logger.info("ToolUniverse singleton initialized with 652 tools")
    elif not TOOLUNIVERSE_AVAILABLE:
        logger.warning("ToolUniverse not available - using mock data")
    
    return _tooluniverse_instance


class GuidelinesCache:
    """
    Simple service for pre-fetching and caching clinical guidelines.
    
    This coordinates async guideline fetching at case start,
    then provides cached guidelines to tools that need them.
    """
    
    def __init__(self, use_tooluniverse: bool = False):
        """
        Initialize guidelines cache.
        
        Args:
            use_tooluniverse: Whether to use ToolUniverse for fetching
        """
        self.use_tooluniverse = use_tooluniverse
        self.cache_ttl = timedelta(hours=24)  # Cache for 24 hours
        
        if use_tooluniverse:
            # Use singleton to avoid re-initializing ToolUniverse
            self.tu = get_tooluniverse_singleton()
            if self.tu is None:
                logger.warning("ToolUniverse not available - using mock data")
                self.use_tooluniverse = False
            else:
                logger.info("Guidelines cache using ToolUniverse singleton")
        else:
            self.tu = None
            logger.info("Guidelines cache initialized (ToolUniverse disabled)")
    
    async def prefetch_guidelines_for_organism(
        self,
        organism: str,
        case_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Pre-fetch guidelines for an organism (async, at case start).
        
        Uses intelligent query generation and multiple search strategies:
        1. Clinical guidelines from authoritative sources
        2. Recent evidence-based research
        3. Case-specific diagnostic approaches
        4. Treatment protocols and management
        
        Args:
            organism: The pathogen/condition
            case_description: Optional case context for more targeted searches
            
        Returns:
            Dict with guidelines data
        """
        logger.info(f"Pre-fetching guidelines for: {organism}")
        
        if not self.use_tooluniverse or not self.tu:
            return {
                "organism": organism,
                "clinical_guidelines": "",
                "diagnostic_approach": "",
                "treatment_protocols": "",
                "recent_evidence": [],
                "fetched_at": datetime.now(),
                "sources": ["ToolUniverse not available"]
            }
        
        try:
            # Generate intelligent queries based on organism and case
            queries = self._generate_intelligent_queries(organism, case_description)
            
            # Run multiple search strategies in parallel
            tasks = [
                self._search_clinical_guidelines(queries["clinical"]),
                self._search_diagnostic_evidence(queries["diagnostic"]),
                self._search_treatment_evidence(queries["treatment"]),
                self._search_recent_research(queries["research"])
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process and combine results
            clinical_guidelines = results[0] if not isinstance(results[0], Exception) else []
            diagnostic_evidence = results[1] if not isinstance(results[1], Exception) else []
            treatment_evidence = results[2] if not isinstance(results[2], Exception) else []
            recent_research = results[3] if not isinstance(results[3], Exception) else []
            
            # Use results directly without filtering
            filtered_guidelines = clinical_guidelines[:3]  # Top 3
            filtered_diagnostic = diagnostic_evidence[:3]  # Top 3
            filtered_treatment = treatment_evidence[:3]  # Top 3
            filtered_research = recent_research[:3]  # Top 3
            
            guidelines = {
                "organism": organism,
                "case_context": case_description,
                "clinical_guidelines": self._format_guidelines(filtered_guidelines, "Clinical Guidelines"),
                "diagnostic_approach": self._format_guidelines(filtered_diagnostic, "Diagnostic Approach"),
                "treatment_protocols": self._format_guidelines(filtered_treatment, "Treatment Protocols"),
                "recent_evidence": filtered_research,
                "fetched_at": datetime.now(),
                "sources": ["EuropePMC", "PubMed", "NICE", "WHO"],
                "query_strategy": "intelligent_multi_source"
            }
            
            logger.info(f"Successfully pre-fetched {len(filtered_guidelines)} guidelines for {organism}")
            return guidelines
            
        except Exception as e:
            logger.error(f"Error pre-fetching guidelines for {organism}: {e}")
            return {
                "organism": organism,
                "clinical_guidelines": "",
                "diagnostic_approach": "",
                "treatment_protocols": "",
                "recent_evidence": [],
                "fetched_at": datetime.now(),
                "sources": ["Error occurred"]
            }
    
    async def _search_diagnostic_guidelines(self, organism: str) -> str:
        """Search for diagnostic guidelines."""
        try:
            # Use ToolUniverse to search for diagnostic guidelines
            result = self.tu.run({
                "name": "EuropePMC_Guidelines_Search",
                "arguments": {
                    "query": f"{organism} diagnosis diagnostic approach guidelines",
                    "limit": 3
                }
            })
            
            # Format the result
            if isinstance(result, list) and result:
                return self._format_guidelines(result, "Diagnostic")
            elif isinstance(result, dict) and result.get('guidelines'):
                return self._format_guidelines(result['guidelines'], "Diagnostic")
            else:
                return f"Diagnostic guidelines for {organism} (search completed)"
                
        except Exception as e:
            logger.warning(f"Error searching diagnostic guidelines: {e}")
            return ""
    
    async def _search_treatment_guidelines(self, organism: str) -> str:
        """Search for treatment guidelines."""
        try:
            result = self.tu.run({
                "name": "EuropePMC_Guidelines_Search",
                "arguments": {
                    "query": f"{organism} treatment management antimicrobial therapy guidelines",
                    "limit": 3
                }
            })
            
            if isinstance(result, list) and result:
                return self._format_guidelines(result, "Treatment")
            elif isinstance(result, dict) and result.get('guidelines'):
                return self._format_guidelines(result['guidelines'], "Treatment")
            else:
                return f"Treatment guidelines for {organism} (search completed)"
                
        except Exception as e:
            logger.warning(f"Error searching treatment guidelines: {e}")
            return ""
    
    async def _search_recent_evidence(self, organism: str) -> list:
        """Search for recent evidence."""
        try:
            result = self.tu.run({
                "name": "PubMed_search_articles",
                "arguments": {
                    "query": f"{organism} recent research clinical outcomes",
                    "limit": 5,
                    "api_key": ""  # Empty API key for demo
                }
            })
            
            if isinstance(result, list):
                return result
            elif isinstance(result, dict) and result.get('articles'):
                return result['articles']
            else:
                return []
                
        except Exception as e:
            logger.warning(f"Error searching recent evidence: {e}")
            return []
    
    def _format_guidelines(self, guidelines: list, category: str) -> str:
        """Format guidelines for display with FULL content and links."""
        if not guidelines:
            return f"{category} guidelines not found"
        
        formatted = []
        for guideline in guidelines[:3]:  # Top 3 guidelines
            if isinstance(guideline, dict):
                title = guideline.get('title', 'Untitled')
                abstract = guideline.get('abstract', guideline.get('content', ''))
                
                # Build the guideline entry with full abstract
                entry = f"**{title}**\n\n{abstract}"
                
                # Add source information
                journal = guideline.get('journal', guideline.get('source', ''))
                year = guideline.get('year', '')
                if journal or year:
                    entry += f"\n\n*Source: {journal} ({year})*"
                
                # Add link (DOI or URL)
                doi = guideline.get('doi', '')
                url = guideline.get('url', '')
                if doi:
                    if not doi.startswith('http'):
                        doi_url = f"https://doi.org/{doi}"
                    else:
                        doi_url = doi
                    entry += f"\n🔗 [View Source]({doi_url})"
                elif url:
                    entry += f"\n🔗 [View Source]({url})"
                
                formatted.append(entry)
        
        return "\n\n---\n\n".join(formatted) if formatted else f"{category} guidelines not found"
    
    def _generate_intelligent_queries(
        self, 
        organism: str, 
        case_description: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        Generate intelligent, targeted queries for different search strategies.
        
        Uses organism-specific terminology and case context to create
        highly relevant search queries.
        """
        # Clean organism name for better search
        clean_organism = organism.replace("_", " ").replace("-", " ")
    
        
        # Clinical guidelines queries (authoritative sources)
        clinical_queries = [
            f'"{clean_organism}" clinical guidelines diagnosis treatment',
            f'"{clean_organism}" NICE guidelines management',
            f'"{clean_organism}" WHO guidelines infection control',
            f'"{clean_organism}" CDC guidelines antimicrobial therapy'
        ]
        
        # Diagnostic evidence queries
        diagnostic_queries = [
            f'"{clean_organism}" diagnostic approach laboratory tests',
            f'"{clean_organism}" differential diagnosis clinical presentation',
            f'"{clean_organism}" imaging diagnosis radiology',
            f'"{clean_organism}" biomarker diagnosis molecular testing'
        ]
        
        # Treatment evidence queries
        treatment_queries = [
            f'"{clean_organism}" antimicrobial therapy treatment guidelines',
            f'"{clean_organism}" antibiotic resistance treatment options',
            f'"{clean_organism}" management protocol clinical care',
            f'"{clean_organism}" therapeutic approach evidence-based'
        ]
        
        # Recent research queries
        research_queries = [
            f'"{clean_organism}" recent research clinical outcomes',
            f'"{clean_organism}" 2023 2024 clinical trial results',
            f'"{clean_organism}" emerging treatment novel therapy',
            f'"{clean_organism}" case study clinical presentation'
        ]
        
        return {
            "clinical": clinical_queries,
            "diagnostic": diagnostic_queries,
            "treatment": treatment_queries,
            "research": research_queries
        }
    
    async def _search_clinical_guidelines(self, queries: List[str]) -> List[Dict]:
        """Search for clinical guidelines using multiple queries."""
        all_results = []
        for query in queries:
            try:
                result = self.tu.run({
                    "name": "EuropePMC_Guidelines_Search",
                    "arguments": {"query": query, "limit": 3}
                })
                if isinstance(result, list):
                    all_results.extend(result)
                elif isinstance(result, dict) and result.get('guidelines'):
                    all_results.extend(result['guidelines'])
            except Exception as e:
                logger.warning(f"Error searching clinical guidelines: {e}")
        return all_results
    
    async def _search_diagnostic_evidence(self, queries: List[str]) -> List[Dict]:
        """Search for diagnostic evidence using multiple queries."""
        all_results = []
        for query in queries:
            try:
                result = self.tu.run({
                    "name": "EuropePMC_search_articles",
                    "arguments": {"query": query, "limit": 3}
                })
                if isinstance(result, list):
                    all_results.extend(result)
            except Exception as e:
                logger.warning(f"Error searching diagnostic evidence: {e}")
        return all_results
    
    async def _search_treatment_evidence(self, queries: List[str]) -> List[Dict]:
        """Search for treatment evidence using multiple queries."""
        all_results = []
        for query in queries:
            try:
                result = self.tu.run({
                    "name": "PubMed_search_articles",
                    "arguments": {"query": query, "limit": 3, "api_key": ""}
                })
                if isinstance(result, list):
                    all_results.extend(result)
            except Exception as e:
                logger.warning(f"Error searching treatment evidence: {e}")
        return all_results
    
    async def _search_recent_research(self, queries: List[str]) -> List[Dict]:
        """Search for recent research using multiple queries."""
        all_results = []
        for query in queries:
            try:
                result = self.tu.run({
                    "name": "EuropePMC_search_articles",
                    "arguments": {"query": query, "limit": 2}
                })
                if isinstance(result, list):
                    # Ensure each result has URL/DOI information
                    for item in result:
                        if not item.get("url") and item.get("doi"):
                            item["url"] = f"https://doi.org/{item['doi']}"
                        elif not item.get("doi") and item.get("url"):
                            # Extract DOI from URL if possible
                            url = item["url"]
                            if "doi.org/" in url:
                                item["doi"] = url.split("doi.org/")[-1]
                    all_results.extend(result)
            except Exception as e:
                logger.warning(f"Error searching recent research: {e}")
        return all_results
    
    
    
    def format_guidelines_for_tool(
        self,
        guidelines: Optional[Dict[str, Any]],
        tool_name: str
    ) -> str:
        """
        Format guidelines for inclusion in tool prompts.
        
        Args:
            guidelines: The guidelines data
            tool_name: Name of the tool requesting guidelines
            
        Returns:
            Formatted string to append to tool prompt
        """
        if not guidelines:
            return ""
        
        if tool_name == "tests_management":
            return f"""
## Pre-fetched Clinical Guidelines

**Organism:** {guidelines.get('organism', 'Unknown')}

**Diagnostic Approach:**
{guidelines.get('diagnostic_guidelines', 'Not available')}

**Treatment Guidelines:**
{guidelines.get('treatment_guidelines', 'Not available')}

Use these evidence-based guidelines to inform your discussion with the student.
"""
        
        elif tool_name == "mcq_tool":
            return f"""
## Evidence-Based Context for MCQ Generation

**Organism:** {guidelines.get('organism', 'Unknown')}

**Key Guidelines:**
- Diagnostic: {guidelines.get('diagnostic_guidelines', 'Not available')}
- Treatment: {guidelines.get('treatment_guidelines', 'Not available')}

Generate MCQs based on current evidence-based practices.
"""
        
        else:
            # Generic format
            return f"\n\n[Clinical Guidelines: {guidelines.get('organism', 'Unknown')}]"


# Global singleton
_guidelines_cache: Optional[GuidelinesCache] = None


def get_guidelines_cache(use_tooluniverse: bool = False) -> GuidelinesCache:
    """Get or create the global guidelines cache."""
    global _guidelines_cache
    if _guidelines_cache is None:
        _guidelines_cache = GuidelinesCache(use_tooluniverse=use_tooluniverse)
    return _guidelines_cache
