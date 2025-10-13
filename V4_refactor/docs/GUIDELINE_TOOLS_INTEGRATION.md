# Guideline Tools Integration Guide

## Overview

This guide shows how to integrate ToolUniverse-style guideline search tools into MicroTutor V4 for searching clinical guidelines, protocols, and evidence-based medicine resources.

## Available Guideline Tools from ToolUniverse

ToolUniverse provides **8 clinical guideline tools**:

### Search Tools (6)

1. **NICE_Clinical_Guidelines_Search** - UK NICE official guidelines
2. **WHO_Guidelines_Search** - WHO international guidelines  
3. **PubMed_Guidelines_Search** - PubMed peer-reviewed guidelines
4. **EuropePMC_Guidelines_Search** - Europe PMC guidelines
5. **TRIP_Database_Guidelines_Search** - TRIP evidence-based database
6. **OpenAlex_Guidelines_Search** - OpenAlex scholarly database

### Full-Text Extraction (2)

7. **NICE_Guideline_Full_Text** - Extract complete NICE guidelines (5,000-20,000+ chars)
8. **WHO_Guideline_Full_Text** - Extract WHO content + PDF links (1,500+ chars)

## Integration Approaches

### Option 1: Direct ToolUniverse Integration (Recommended)

**Pros:**

- ✅ Get 600+ tools including all guideline tools
- ✅ Pre-built, tested, maintained
- ✅ Standardized interface
- ✅ Built-in caching, error handling
- ✅ Easy updates as ToolUniverse improves

**Cons:**

- Additional dependency (~50MB)
- Need API keys for some tools

### Option 2: Adapt ToolUniverse Implementations

**Pros:**

- ✅ No external dependencies
- ✅ Full control over implementation
- ✅ Can customize for MicroTutor needs

**Cons:**

- Need to maintain code yourself
- Need to implement caching, error handling
- Miss out on ToolUniverse updates

### Option 3: Hybrid Approach (Best for MicroTutor)

**Use ToolUniverse for:**

- Guideline search (NICE, WHO, PubMed, etc.)
- Literature search
- Drug information (FDA, DrugBank)

**Keep custom implementations for:**

- MicroTutor-specific agents (Patient, Socratic, Hint)
- Case generation with RAG
- Domain-specific microbiology tools

## Implementation

### 1. Direct ToolUniverse Integration

#### Installation

```bash
cd V4_refactor
pip install tooluniverse
# or
uv pip install tooluniverse
```

#### Create Guideline Service

Create: `src/microtutor/services/guideline_service.py`

```python
"""
Guideline Search Service using ToolUniverse integration.
"""

from typing import Any, Dict, List, Optional
import logging
from tooluniverse import ToolUniverse

logger = logging.getLogger(__name__)


class GuidelineService:
    """Service for searching clinical guidelines across multiple sources."""
    
    def __init__(self):
        """Initialize ToolUniverse and load guideline tools."""
        self.tu = ToolUniverse()
        # Load only guideline tools to keep it lightweight
        self.tu.load_tools(
            tool_names=[
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
            sources: List of sources to search (default: all)
            limit: Max results per source
            
        Returns:
            Dict mapping source name to list of guidelines
        """
        if sources is None:
            sources = ["NICE", "PubMed", "WHO", "EuropePMC"]
        
        results = {}
        
        for source in sources:
            try:
                tool_name = f"{source}_{'Clinical_' if source == 'NICE' else ''}Guidelines_Search"
                
                result = self.tu.run({
                    "name": tool_name,
                    "arguments": {
                        "query": query,
                        "limit": limit,
                        **({"api_key": ""} if source == "PubMed" else {})
                    }
                })
                
                results[source] = result if isinstance(result, list) else [result]
                logger.info(f"Found {len(results[source])} guidelines from {source}")
                
            except Exception as e:
                logger.error(f"Error searching {source}: {e}")
                results[source] = []
        
        return results
    
    async def search_for_organism(
        self,
        organism: str,
        treatment_focus: bool = True
    ) -> Dict[str, Any]:
        """
        Search guidelines specifically for microbiology/infectious disease.
        
        Args:
            organism: Organism name (e.g., "Staphylococcus aureus")
            treatment_focus: Include "treatment" in query
            
        Returns:
            Structured guideline results
        """
        # Build query
        query_parts = [organism]
        if treatment_focus:
            query_parts.append("treatment guidelines")
        
        query = " ".join(query_parts)
        
        # Search guidelines
        results = await self.search_guidelines(
            query=query,
            sources=["NICE", "PubMed", "WHO"],
            limit=3
        )
        
        # Get full text for top NICE guideline if available
        if results.get("NICE") and len(results["NICE"]) > 0:
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
            "total_guidelines": sum(len(v) for v in results.values() if isinstance(v, list))
        }
    
    def get_guideline_summary(
        self,
        guidelines: Dict[str, List[Dict[str, Any]]]
    ) -> str:
        """
        Generate a summary of guideline search results for LLM context.
        
        Args:
            guidelines: Results from search_guidelines()
            
        Returns:
            Formatted summary string
        """
        summary_parts = ["## Clinical Guidelines\n"]
        
        for source, items in guidelines.items():
            if not items or not isinstance(items, list):
                continue
                
            summary_parts.append(f"\n### {source} Guidelines\n")
            
            for idx, item in enumerate(items[:3], 1):  # Top 3 per source
                title = item.get("title", "Untitled")
                url = item.get("url", "")
                summary = item.get("summary", item.get("abstract", ""))
                
                summary_parts.append(f"{idx}. **{title}**")
                if url:
                    summary_parts.append(f"   - URL: {url}")
                if summary:
                    # Truncate summary to 200 chars
                    summary_text = summary[:200] + "..." if len(summary) > 200 else summary
                    summary_parts.append(f"   - {summary_text}")
                summary_parts.append("")
        
        return "\n".join(summary_parts)
```

#### Integrate into FastAPI

Update `src/microtutor/api/dependencies.py`:

```python
from microtutor.services.guideline_service import GuidelineService

_guideline_service: Optional[GuidelineService] = None

def get_guideline_service() -> GuidelineService:
    """Get guideline service singleton."""
    global _guideline_service
    if _guideline_service is None:
        _guideline_service = GuidelineService()
    return _guideline_service
```

Create new route: `src/microtutor/api/routes/guidelines.py`

```python
"""
Guidelines API routes.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel

from microtutor.services.guideline_service import GuidelineService
from microtutor.api.dependencies import get_guideline_service

router = APIRouter(prefix="/api/v1/guidelines", tags=["guidelines"])


class GuidelineSearchRequest(BaseModel):
    """Request to search guidelines."""
    query: str
    sources: Optional[List[str]] = None
    limit: int = 5


class GuidelineSearchResponse(BaseModel):
    """Response from guideline search."""
    query: str
    results: dict
    total: int
    summary: str


@router.post("/search", response_model=GuidelineSearchResponse)
async def search_guidelines(
    request: GuidelineSearchRequest,
    service: GuidelineService = Depends(get_guideline_service)
):
    """
    Search clinical guidelines across multiple sources.
    
    Example:
    ```json
    {
        "query": "MRSA treatment",
        "sources": ["NICE", "PubMed"],
        "limit": 5
    }
    ```
    """
    results = await service.search_guidelines(
        query=request.query,
        sources=request.sources,
        limit=request.limit
    )
    
    summary = service.get_guideline_summary(results)
    total = sum(len(v) for v in results.values() if isinstance(v, list))
    
    return GuidelineSearchResponse(
        query=request.query,
        results=results,
        total=total,
        summary=summary
    )


@router.get("/organism/{organism}", response_model=GuidelineSearchResponse)
async def search_for_organism(
    organism: str,
    treatment_focus: bool = True,
    service: GuidelineService = Depends(get_guideline_service)
):
    """
    Search guidelines for specific organism.
    
    Example: GET /api/v1/guidelines/organism/staphylococcus%20aureus
    """
    result = await service.search_for_organism(
        organism=organism,
        treatment_focus=treatment_focus
    )
    
    summary = service.get_guideline_summary(result["results"])
    
    return GuidelineSearchResponse(
        query=result["query"],
        results=result["results"],
        total=result["total_guidelines"],
        summary=summary
    )
```

Register route in `src/microtutor/api/app.py`:

```python
from microtutor.api.routes import chat, guidelines

app.include_router(guidelines.router)
```

### 2. Custom Implementation (Adapt from ToolUniverse)

If you prefer not to add ToolUniverse as a dependency, here's how to adapt the implementations:

Create: `src/microtutor/tools/guideline_tools.py`

```python
"""
Custom guideline search tools adapted from ToolUniverse.
"""

import requests
import time
import logging
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

from microtutor.models.tool_models import BaseTool
from microtutor.models.tool_errors import ToolExecutionError

logger = logging.getLogger(__name__)


class NICEGuidelineSearchTool(BaseTool):
    """
    Search NICE clinical guidelines.
    Adapted from ToolUniverse's unified_guideline_tools.py
    """
    
    def __init__(self, tool_config: Dict[str, Any]):
        super().__init__(tool_config)
        self.base_url = "https://www.nice.org.uk"
        self.search_url = f"{self.base_url}/search"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
    
    def _execute(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute NICE guideline search."""
        query = arguments.get("query", "")
        limit = arguments.get("limit", 10)
        
        if not query:
            raise ToolExecutionError("Query parameter required", tool_name=self.name)
        
        try:
            # Respectful rate limiting
            time.sleep(1)
            
            # Search NICE
            params = {"q": query, "type": "guidance"}
            response = self.session.get(self.search_url, params=params, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Find JSON data in script tag
            script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
            if not script_tag:
                return []
            
            import json
            data = json.loads(script_tag.string)
            documents = (
                data.get("props", {})
                .get("pageProps", {})
                .get("results", {})
                .get("documents", [])
            )
            
            if not documents:
                return []
            
            # Process results
            results = []
            for doc in documents[:limit]:
                title = doc.get("title", "").replace("<b>", "").replace("</b>", "")
                url = doc.get("url", "")
                
                if url.startswith("/"):
                    url = self.base_url + url
                
                summary = (
                    doc.get("abstract", "")
                    or doc.get("staticAbstract", "")
                    or doc.get("metaDescription", "")
                    or ""
                )
                
                results.append({
                    "title": title,
                    "url": url,
                    "summary": summary,
                    "date": doc.get("lastUpdated", doc.get("publicationDate", "")),
                    "source": "NICE"
                })
            
            return results
            
        except requests.exceptions.RequestException as e:
            raise ToolExecutionError(f"Failed to search NICE: {e}", tool_name=self.name)
        except Exception as e:
            raise ToolExecutionError(f"Error parsing NICE results: {e}", tool_name=self.name)


class PubMedGuidelineSearchTool(BaseTool):
    """
    Search PubMed for clinical practice guidelines.
    Adapted from ToolUniverse's unified_guideline_tools.py
    """
    
    def __init__(self, tool_config: Dict[str, Any]):
        super().__init__(tool_config)
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.session = requests.Session()
    
    def _execute(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute PubMed guideline search."""
        query = arguments.get("query", "")
        limit = arguments.get("limit", 10)
        api_key = arguments.get("api_key", "")
        
        if not query:
            raise ToolExecutionError("Query parameter required", tool_name=self.name)
        
        try:
            # Add guideline filter
            guideline_query = f"{query} AND (guideline[Publication Type] OR practice guideline[Publication Type])"
            
            # Search for PMIDs
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
                return []
            
            # Get details
            time.sleep(0.5)
            detail_params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "json"}
            if api_key:
                detail_params["api_key"] = api_key
            
            detail_response = self.session.get(
                f"{self.base_url}/esummary.fcgi",
                params=detail_params,
                timeout=30
            )
            detail_response.raise_for_status()
            detail_data = detail_response.json()
            
            # Parse results
            results = []
            result_items = detail_data.get("result", {})
            
            for pmid in pmids:
                item = result_items.get(pmid, {})
                if not item:
                    continue
                
                results.append({
                    "title": item.get("title", ""),
                    "pmid": pmid,
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "authors": ", ".join([a.get("name", "") for a in item.get("authors", [])[:3]]),
                    "journal": item.get("fulljournalname", ""),
                    "date": item.get("pubdate", ""),
                    "source": "PubMed"
                })
            
            return results
            
        except requests.exceptions.RequestException as e:
            raise ToolExecutionError(f"Failed to search PubMed: {e}", tool_name=self.name)
        except Exception as e:
            raise ToolExecutionError(f"Error parsing PubMed results: {e}", tool_name=self.name)
```

Register tools:

```python
# In src/microtutor/tools/__init__.py
from microtutor.tools.guideline_tools import NICEGuidelineSearchTool, PubMedGuidelineSearchTool
from microtutor.tools.registry import register_tool_class

register_tool_class("NICEGuidelineSearch", NICEGuidelineSearchTool)
register_tool_class("PubMedGuidelineSearch", PubMedGuidelineSearchTool)
```

Create tool configs in `config/tools/`:

```json
// config/tools/nice_guideline_search.json
{
  "name": "NICE_Guideline_Search",
  "type": "NICEGuidelineSearch",
  "description": "Search NICE clinical guidelines",
  "cacheable": true,
  "parameter": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Medical condition or topic"
      },
      "limit": {
        "type": "integer",
        "default": 10
      }
    },
    "required": ["query"]
  }
}
```

## Usage Examples

### In Tutoring Workflow

Enhance case presentation with guidelines:

```python
# In tutor_service.py
from microtutor.services.guideline_service import GuidelineService

class TutorService:
    def __init__(self):
        self.guideline_service = GuidelineService()
    
    async def start_case_with_guidelines(
        self,
        organism: str,
        case_id: str
    ) -> Dict[str, Any]:
        """Start case and fetch relevant guidelines."""
        
        # Get case
        case = await self.case_service.get_case(organism, case_id)
        
        # Search guidelines
        guidelines = await self.guideline_service.search_for_organism(
            organism=organism,
            treatment_focus=True
        )
        
        # Add guidelines to LLM context
        guideline_context = self.guideline_service.get_guideline_summary(
            guidelines["results"]
        )
        
        # Build system message with guidelines
        system_message = f"""
You are a medical tutor. The student is working on a case about {organism}.

{guideline_context}

Use these guidelines to inform your teaching, but don't simply give answers.
Guide the student to discover the information themselves.
"""
        
        return {
            "case": case,
            "guidelines": guidelines,
            "system_message": system_message
        }
```

### Direct API Usage

```python
import requests

# Search guidelines
response = requests.post(
    "http://localhost:5001/api/v1/guidelines/search",
    json={
        "query": "MRSA treatment",
        "sources": ["NICE", "PubMed", "WHO"],
        "limit": 5
    }
)

guidelines = response.json()
print(f"Found {guidelines['total']} guidelines")
print(guidelines['summary'])
```

### For organism-specific search

```bash
curl http://localhost:5001/api/v1/guidelines/organism/staphylococcus%20aureus
```

## Best Practices

### 1. Caching

Guidelines don't change frequently - enable caching:

```python
# Enable caching for guideline tools
tool_config["cacheable"] = True
```

### 2. Rate Limiting

Be respectful to external APIs:

```python
import time

# Add delays between requests
time.sleep(1)  # 1 second between NICE requests
time.sleep(0.5)  # 0.5 seconds between PubMed requests
```

### 3. Error Handling

Always handle search failures gracefully:

```python
try:
    guidelines = await service.search_guidelines(query)
except Exception as e:
    logger.error(f"Guideline search failed: {e}")
    # Continue without guidelines
    guidelines = {}
```

### 4. LLM Context Management

Don't overwhelm the LLM with too many guidelines:

```python
# Limit to top 3 results per source
for source in sources:
    results[source] = results[source][:3]

# Truncate summaries
summary = summary[:200] + "..." if len(summary) > 200 else summary
```

### 5. API Keys

Store API keys securely:

```python
# .env
PUBMED_API_KEY=your_key_here
NCBI_API_KEY=your_key_here

# Load in service
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("PUBMED_API_KEY", "")
```

## Testing

Create tests for guideline tools:

```python
# tests/test_guideline_service.py
import pytest
from microtutor.services.guideline_service import GuidelineService

@pytest.mark.asyncio
async def test_search_guidelines():
    service = GuidelineService()
    
    results = await service.search_guidelines(
        query="diabetes",
        sources=["NICE"],
        limit=2
    )
    
    assert "NICE" in results
    assert len(results["NICE"]) > 0
    assert "title" in results["NICE"][0]
    assert "url" in results["NICE"][0]

@pytest.mark.asyncio
async def test_search_for_organism():
    service = GuidelineService()
    
    result = await service.search_for_organism(
        organism="Staphylococcus aureus",
        treatment_focus=True
    )
    
    assert result["organism"] == "Staphylococcus aureus"
    assert "treatment" in result["query"].lower()
    assert result["total_guidelines"] > 0
```

## Monitoring

Track guideline search usage:

```python
# Add to logging_config.py
import logging

guideline_logger = logging.getLogger("microtutor.guidelines")
guideline_logger.setLevel(logging.INFO)

# Log searches
guideline_logger.info(
    "Guideline search",
    extra={
        "query": query,
        "sources": sources,
        "results_count": len(results),
        "execution_time_ms": execution_time
    }
)
```

## Next Steps

1. **Install ToolUniverse** (recommended): `pip install tooluniverse`
2. **Create GuidelineService**: Copy implementation from above
3. **Add API routes**: Create guidelines router
4. **Test**: Try searching for common organisms
5. **Integrate into tutoring**: Add guidelines to case context
6. **Monitor**: Track usage and performance

## Resources

- **ToolUniverse Docs**: <https://zitniklab.hms.harvard.edu/ToolUniverse/>
- **Clinical Guidelines Tools**: <https://zitniklab.hms.harvard.edu/ToolUniverse/guide/clinical_guidelines_tools.html>
- **ToolUniverse GitHub**: <https://github.com/mims-harvard/ToolUniverse>
- **NICE Guidelines**: <https://www.nice.org.uk/guidance>
- **PubMed Guidelines**: <https://pubmed.ncbi.nlm.nih.gov/>

## Summary

✅ **Option 1 (Recommended)**: Install ToolUniverse and use GuidelineService wrapper
✅ **Option 2**: Adapt implementations to V4's BaseTool architecture
✅ **Best Practice**: Use hybrid approach - ToolUniverse for guidelines, custom for MicroTutor agents
✅ **Integration**: Add to case generation, socratic questioning, knowledge assessment
✅ **Caching**: Enable for better performance
✅ **Testing**: Write tests for guideline searches
