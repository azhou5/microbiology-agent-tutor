"""
Custom guideline search tools adapted from ToolUniverse.

These tools provide standalone guideline search capabilities without requiring
ToolUniverse as a dependency. Implementations are adapted from:
https://github.com/mims-harvard/ToolUniverse/blob/main/src/tooluniverse/unified_guideline_tools.py
"""

import requests
import time
import logging
import json
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

from microtutor.core.tool_base import BaseTool, ToolExecutionError

logger = logging.getLogger(__name__)


class NICEGuidelineSearchTool(BaseTool):
    """
    Search NICE (National Institute for Health and Care Excellence) clinical guidelines.
    
    Uses web scraping to search official NICE website for evidence-based clinical guidance.
    Adapted from ToolUniverse's NICEWebScrapingTool.
    
    Returns:
        List of guidelines with title, URL, summary, date, and category.
    """
    
    def __init__(self, tool_config: Dict[str, Any]):
        """Initialize NICE guideline search tool."""
        super().__init__(tool_config)
        self.base_url = "https://www.nice.org.uk"
        self.search_url = f"{self.base_url}/search"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
    
    def _execute(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute NICE guideline search.
        
        Args:
            arguments: Must contain 'query' (str) and optionally 'limit' (int, default 10)
            
        Returns:
            List of guideline dictionaries with title, url, summary, date, source
        """
        query = arguments.get("query", "")
        limit = arguments.get("limit", 10)
        
        if not query:
            raise ToolExecutionError(
                "Query parameter is required",
                tool_name=self.name,
                details={"provided_arguments": arguments}
            )
        
        try:
            # Respectful rate limiting
            time.sleep(1)
            
            # Search NICE
            params = {"q": query, "type": "guidance"}
            response = self.session.get(self.search_url, params=params, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Find JSON data embedded in Next.js script tag
            script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
            if not script_tag:
                logger.warning("No NICE search results found (missing __NEXT_DATA__)")
                return []
            
            # Parse JSON data
            data = json.loads(script_tag.string)
            documents = (
                data.get("props", {})
                .get("pageProps", {})
                .get("results", {})
                .get("documents", [])
            )
            
            if not documents:
                logger.info(f"No NICE guidelines found for query: {query}")
                return []
            
            # Process results
            results = []
            for doc in documents[:limit]:
                try:
                    title = doc.get("title", "").replace("<b>", "").replace("</b>", "")
                    url = doc.get("url", "")
                    
                    # Make URL absolute
                    if url.startswith("/"):
                        url = self.base_url + url
                    
                    # Extract summary from multiple possible fields
                    summary = (
                        doc.get("abstract", "")
                        or doc.get("staticAbstract", "")
                        or doc.get("metaDescription", "")
                        or doc.get("teaser", "")
                        or ""
                    )
                    
                    # Extract date
                    publication_date = doc.get("publicationDate", "")
                    last_updated = doc.get("lastUpdated", "")
                    date = last_updated or publication_date
                    
                    # Extract type/category
                    nice_result_type = doc.get("niceResultType", "")
                    nice_guidance_type = doc.get("niceGuidanceType", [])
                    guideline_type = nice_result_type or (
                        nice_guidance_type[0] if nice_guidance_type else "NICE Guideline"
                    )
                    
                    # Determine category
                    category = "Clinical Guidelines"
                    if "quality standard" in guideline_type.lower():
                        category = "Quality Standards"
                    elif "technology appraisal" in guideline_type.lower():
                        category = "Technology Appraisal"
                    
                    results.append({
                        "title": title,
                        "url": url,
                        "summary": summary,
                        "date": date,
                        "type": guideline_type,
                        "category": category,
                        "source": "NICE"
                    })
                
                except Exception as e:
                    logger.warning(f"Failed to parse NICE guideline item: {e}")
                    continue
            
            logger.info(f"Found {len(results)} NICE guidelines for: {query}")
            return results
            
        except requests.exceptions.RequestException as e:
            raise ToolExecutionError(
                f"Failed to search NICE guidelines: {str(e)}",
                tool_name=self.name,
                details={"query": query, "limit": limit}
            )
        except Exception as e:
            raise ToolExecutionError(
                f"Error parsing NICE response: {str(e)}",
                tool_name=self.name,
                details={"query": query}
            )


class PubMedGuidelineSearchTool(BaseTool):
    """
    Search PubMed for clinical practice guidelines.
    
    Uses NCBI E-utilities API to search PubMed with guideline publication type filters.
    Adapted from ToolUniverse's PubMedGuidelinesTool.
    
    Returns:
        List of guidelines with title, PMID, URL, authors, journal, and date.
    """
    
    def __init__(self, tool_config: Dict[str, Any]):
        """Initialize PubMed guideline search tool."""
        super().__init__(tool_config)
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.session = requests.Session()
    
    def _execute(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute PubMed guideline search.
        
        Args:
            arguments: Must contain 'query' (str), optionally 'limit' (int), 'api_key' (str)
            
        Returns:
            List of guideline dictionaries with title, pmid, url, authors, journal, date
        """
        query = arguments.get("query", "")
        limit = arguments.get("limit", 10)
        api_key = arguments.get("api_key", "")
        
        if not query:
            raise ToolExecutionError(
                "Query parameter is required",
                tool_name=self.name,
                details={"provided_arguments": arguments}
            )
        
        try:
            # Add guideline publication type filter
            guideline_query = (
                f"{query} AND (guideline[Publication Type] OR "
                f"practice guideline[Publication Type])"
            )
            
            # Step 1: Search for PMIDs
            search_params = {
                "db": "pubmed",
                "term": guideline_query,
                "retmode": "json",
                "retmax": limit,
            }
            if api_key:
                search_params["api_key"] = api_key
            
            search_response = self.session.get(
                f"{self.base_url}/esearch.fcgi",
                params=search_params,
                timeout=30
            )
            search_response.raise_for_status()
            search_data = search_response.json()
            
            pmids = search_data.get("esearchresult", {}).get("idlist", [])
            if not pmids:
                logger.info(f"No PubMed guidelines found for query: {query}")
                return []
            
            # Step 2: Get details for PMIDs
            time.sleep(0.5)  # Respectful rate limiting
            
            detail_params = {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "json"
            }
            if api_key:
                detail_params["api_key"] = api_key
            
            detail_response = self.session.get(
                f"{self.base_url}/esummary.fcgi",
                params=detail_params,
                timeout=30
            )
            detail_response.raise_for_status()
            detail_data = detail_response.json()
            
            # Step 3: Parse results
            results = []
            result_items = detail_data.get("result", {})
            
            for pmid in pmids:
                try:
                    item = result_items.get(pmid, {})
                    if not item or isinstance(item, list):
                        continue
                    
                    # Extract authors (max 3)
                    authors_list = item.get("authors", [])
                    authors = ", ".join([
                        a.get("name", "") 
                        for a in authors_list[:3]
                    ])
                    if len(authors_list) > 3:
                        authors += " et al."
                    
                    results.append({
                        "title": item.get("title", ""),
                        "pmid": pmid,
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        "authors": authors,
                        "journal": item.get("fulljournalname", ""),
                        "date": item.get("pubdate", ""),
                        "source": "PubMed"
                    })
                
                except Exception as e:
                    logger.warning(f"Failed to parse PubMed item {pmid}: {e}")
                    continue
            
            logger.info(f"Found {len(results)} PubMed guidelines for: {query}")
            return results
            
        except requests.exceptions.RequestException as e:
            raise ToolExecutionError(
                f"Failed to search PubMed: {str(e)}",
                tool_name=self.name,
                details={"query": query, "limit": limit}
            )
        except Exception as e:
            raise ToolExecutionError(
                f"Error parsing PubMed response: {str(e)}",
                tool_name=self.name,
                details={"query": query}
            )


# Tool registration
def register_guideline_tools() -> None:
    """Register guideline tools with the tool registry."""
    from microtutor.tools.registry import register_tool_class
    
    register_tool_class("NICEGuidelineSearch", NICEGuidelineSearchTool)
    register_tool_class("PubMedGuidelineSearch", PubMedGuidelineSearchTool)
    
    logger.info("Registered guideline tools: NICE, PubMed")


# Auto-register when module is imported
try:
    register_guideline_tools()
except Exception as e:
    logger.warning(f"Failed to auto-register guideline tools: {e}")

