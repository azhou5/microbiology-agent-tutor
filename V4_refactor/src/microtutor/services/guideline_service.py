"""
Guideline Search Service - Search clinical guidelines across multiple sources.

This service can work with either:
1. ToolUniverse (if installed) - Recommended for 600+ tools
2. Custom implementations - Adapted from ToolUniverse for standalone use
"""

from typing import Any, Dict, List, Optional
import logging
import asyncio

logger = logging.getLogger(__name__)


class GuidelineService:
    """Service for searching clinical guidelines across multiple sources."""
    
    def __init__(self, use_tooluniverse: bool = True):
        """
        Initialize guideline service.
        
        Args:
            use_tooluniverse: If True, use ToolUniverse (if installed).
                            If False, use custom implementations.
        """
        self.use_tooluniverse = use_tooluniverse
        self.tu = None
        
        if use_tooluniverse:
            self._init_tooluniverse()
        else:
            self._init_custom_tools()
    
    def _init_tooluniverse(self) -> None:
        """Initialize ToolUniverse if available."""
        try:
            from tooluniverse import ToolUniverse
            
            self.tu = ToolUniverse()
            # Load only guideline tools to keep it lightweight
            # Using include_tools parameter (correct ToolUniverse API)
            self.tu.load_tools(
                include_tools=[
                    "NICE_Clinical_Guidelines_Search",
                    "WHO_Guidelines_Search", 
                    "PubMed_Guidelines_Search",
                    "EuropePMC_Guidelines_Search",
                    "TRIP_Database_Guidelines_Search",
                    "OpenAlex_Guidelines_Search",
                    "NICE_Guideline_Full_Text",
                    "WHO_Guideline_Full_Text"
                ]
            )
            logger.info("Loaded 8 guideline tools from ToolUniverse")
            
        except ImportError:
            logger.warning(
                "ToolUniverse not installed. Install with: pip install tooluniverse"
            )
            logger.info("Falling back to custom implementations")
            self.use_tooluniverse = False
            self._init_custom_tools()
    
    def _init_custom_tools(self) -> None:
        """Initialize custom guideline search tools."""
        try:
            from microtutor.tools.guideline_tools import (
                NICEGuidelineSearchTool,
                PubMedGuidelineSearchTool
            )
            from microtutor.tools.registry import get_tool_instance, register_tool_config
            
            # Register NICE tool
            nice_config = {
                "name": "NICE_Guideline_Search",
                "type": "NICEGuidelineSearch",
                "description": "Search NICE clinical guidelines",
                "cacheable": True,
                "parameter": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "default": 10}
                    },
                    "required": ["query"]
                }
            }
            register_tool_config(nice_config)
            
            # Register PubMed tool
            pubmed_config = {
                "name": "PubMed_Guideline_Search",
                "type": "PubMedGuidelineSearch",
                "description": "Search PubMed for clinical practice guidelines",
                "cacheable": True,
                "parameter": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "default": 10},
                        "api_key": {"type": "string", "default": ""}
                    },
                    "required": ["query"]
                }
            }
            register_tool_config(pubmed_config)
            
            logger.info("Initialized custom guideline tools (NICE, PubMed)")
            
        except ImportError as e:
            logger.error(f"Failed to initialize custom tools: {e}")
            logger.warning("Guideline search functionality will be limited")
    
    async def search_guidelines(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        limit: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search guidelines across multiple sources.
        
        Args:
            query: Medical condition or topic (e.g., "MRSA treatment")
            sources: List of sources to search (default: all available)
            limit: Max results per source (default: 5)
            
        Returns:
            Dict mapping source name to list of guidelines
            
        Example:
            ```python
            results = await service.search_guidelines(
                query="Staphylococcus aureus treatment",
                sources=["NICE", "PubMed"],
                limit=3
            )
            # Returns: {
            #   "NICE": [{title: "...", url: "...", summary: "..."}, ...],
            #   "PubMed": [{title: "...", pmid: "...", url: "..."}, ...]
            # }
            ```
        """
        if sources is None:
            if self.use_tooluniverse:
                sources = ["NICE", "PubMed", "WHO", "EuropePMC"]
            else:
                sources = ["NICE", "PubMed"]
        
        results = {}
        
        # Search each source
        for source in sources:
            try:
                if self.use_tooluniverse:
                    result = await self._search_with_tooluniverse(source, query, limit)
                else:
                    result = await self._search_with_custom_tools(source, query, limit)
                
                results[source] = result if isinstance(result, list) else [result]
                logger.info(f"Found {len(results[source])} guidelines from {source}")
                
            except Exception as e:
                logger.error(f"Error searching {source}: {e}")
                results[source] = []
        
        return results
    
    async def _search_with_tooluniverse(
        self, 
        source: str, 
        query: str, 
        limit: int
    ) -> List[Dict[str, Any]]:
        """Search using ToolUniverse."""
        if not self.tu:
            return []
        
        tool_name = f"{source}_{'Clinical_' if source == 'NICE' else ''}Guidelines_Search"
        
        result = self.tu.run({
            "name": tool_name,
            "arguments": {
                "query": query,
                "limit": limit,
                **({"api_key": ""} if source == "PubMed" else {})
            }
        })
        
        return result if isinstance(result, list) else [result]
    
    async def _search_with_custom_tools(
        self, 
        source: str, 
        query: str, 
        limit: int
    ) -> List[Dict[str, Any]]:
        """Search using custom tool implementations."""
        from microtutor.tools.registry import get_tool_instance
        
        tool_name_map = {
            "NICE": "NICE_Guideline_Search",
            "PubMed": "PubMed_Guideline_Search"
        }
        
        tool_name = tool_name_map.get(source)
        if not tool_name:
            logger.warning(f"No custom tool available for source: {source}")
            return []
        
        tool = get_tool_instance(tool_name)
        if not tool:
            logger.error(f"Failed to get tool instance: {tool_name}")
            return []
        
        # Execute tool
        result = tool.run(
            arguments={"query": query, "limit": limit},
            use_cache=True
        )
        
        if result.get("success"):
            return result.get("result", [])
        else:
            logger.error(f"Tool execution failed: {result.get('error')}")
            return []
    
    async def search_for_organism(
        self,
        organism: str,
        treatment_focus: bool = True,
        limit: int = 3
    ) -> Dict[str, Any]:
        """
        Search guidelines specifically for microbiology/infectious disease.
        
        Args:
            organism: Organism name (e.g., "Staphylococcus aureus")
            treatment_focus: Include "treatment" in query (default: True)
            limit: Max results per source (default: 3)
            
        Returns:
            Structured guideline results with query, results, and metadata
            
        Example:
            ```python
            result = await service.search_for_organism(
                organism="Staphylococcus aureus",
                treatment_focus=True
            )
            # Returns: {
            #   "organism": "Staphylococcus aureus",
            #   "query": "Staphylococcus aureus treatment guidelines",
            #   "results": {...},
            #   "total_guidelines": 12
            # }
            ```
        """
        # Build query
        query_parts = [organism]
        if treatment_focus:
            query_parts.append("treatment guidelines")
        
        query = " ".join(query_parts)
        
        # Determine sources based on backend
        sources = ["NICE", "PubMed", "WHO"] if self.use_tooluniverse else ["NICE", "PubMed"]
        
        # Search guidelines
        results = await self.search_guidelines(
            query=query,
            sources=sources,
            limit=limit
        )
        
        # Get full text for top NICE guideline if available
        if self.use_tooluniverse and results.get("NICE") and len(results["NICE"]) > 0:
            top_guideline = results["NICE"][0]
            if "url" in top_guideline:
                try:
                    full_text = self.tu.run({
                        "name": "NICE_Guideline_Full_Text",
                        "arguments": {"url": top_guideline["url"]}
                    })
                    results["NICE_full_text"] = full_text
                except Exception as e:
                    logger.error(f"Error fetching full text: {e}")
        
        return {
            "organism": organism,
            "query": query,
            "results": results,
            "total_guidelines": sum(
                len(v) for v in results.values() 
                if isinstance(v, list)
            )
        }
    
    def get_guideline_summary(
        self,
        guidelines: Dict[str, List[Dict[str, Any]]],
        max_per_source: int = 3,
        max_summary_length: int = 200
    ) -> str:
        """
        Generate a summary of guideline search results for LLM context.
        
        Args:
            guidelines: Results from search_guidelines()
            max_per_source: Max guidelines to include per source (default: 3)
            max_summary_length: Max chars for each summary (default: 200)
            
        Returns:
            Formatted markdown summary string
            
        Example:
            ```python
            guidelines = await service.search_guidelines("MRSA")
            summary = service.get_guideline_summary(guidelines)
            # Use in LLM prompt:
            system_prompt = f"Based on these guidelines:\\n{summary}\\n..."
            ```
        """
        summary_parts = ["## Clinical Guidelines\n"]
        
        for source, items in guidelines.items():
            if not items or not isinstance(items, list):
                continue
            
            # Skip metadata entries
            if source.endswith("_full_text"):
                continue
            
            summary_parts.append(f"\n### {source} Guidelines\n")
            
            for idx, item in enumerate(items[:max_per_source], 1):
                title = item.get("title", "Untitled")
                url = item.get("url", "")
                summary = item.get("summary", item.get("abstract", item.get("description", "")))
                
                summary_parts.append(f"{idx}. **{title}**")
                
                if url:
                    summary_parts.append(f"   - URL: {url}")
                
                if summary:
                    # Truncate summary
                    if len(summary) > max_summary_length:
                        summary_text = summary[:max_summary_length] + "..."
                    else:
                        summary_text = summary
                    summary_parts.append(f"   - {summary_text}")
                
                # Add metadata
                if "pmid" in item:
                    summary_parts.append(f"   - PMID: {item['pmid']}")
                if "date" in item and item["date"]:
                    summary_parts.append(f"   - Date: {item['date']}")
                
                summary_parts.append("")
        
        return "\n".join(summary_parts)
    
    def is_available(self) -> bool:
        """Check if guideline search is available."""
        return self.tu is not None or self.use_tooluniverse is False
    
    def get_available_sources(self) -> List[str]:
        """Get list of available guideline sources."""
        if self.use_tooluniverse and self.tu:
            return ["NICE", "WHO", "PubMed", "EuropePMC", "TRIP", "OpenAlex"]
        else:
            return ["NICE", "PubMed"]

