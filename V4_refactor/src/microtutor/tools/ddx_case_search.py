"""
DDX Case Search Tool - Search and retrieve real clinical cases from DDX Learners dataset.

This tool searches through the Virtual Morning Report episodes from clinicalproblemsolving.com,
finds relevant cases based on presenting complaints, and extracts case content from PDFs.
"""

import logging
import os
import re
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from difflib import SequenceMatcher

from microtutor.models.tool_models import BaseTool
from microtutor.models.tool_errors import ToolExecutionError, ToolValidationError

logger = logging.getLogger(__name__)


class DDXCaseSearchTool(BaseTool):
    """
    Search and retrieve clinical cases from DDX Learners Virtual Morning Report episodes.
    
    Features:
    - Fuzzy matching on presenting complaints
    - PDF caching and extraction
    - Returns formatted case content for LLM consumption
    """
    
    def __init__(self, tool_config: Dict[str, Any]):
        super().__init__(tool_config)
        
        # Get paths from config
        pdf_dir_config = tool_config.get("pdf_directory", "../Datasets/vmr_pdfs")
        cache_dir_config = tool_config.get("cache_directory", "../Datasets/vmr_cache")
        
        self.pdf_directory = Path(pdf_dir_config)
        self.cache_directory = Path(cache_dir_config)
        
        # Search parameters
        self.similarity_threshold = tool_config.get("similarity_threshold", 0.6)
        self.max_results = tool_config.get("max_results", 5)
        
        # Make paths absolute if relative
        if not self.pdf_directory.is_absolute():
            # Resolve relative to V4_refactor directory
            # __file__ is in: V4_refactor/src/microtutor/tools/ddx_case_search.py
            # V4_refactor is at: parent.parent.parent.parent
            # microbiology-agent-tutor is at: parent.parent.parent.parent.parent
            v4_root = Path(__file__).parent.parent.parent.parent
            microbio_root = v4_root.parent
            self.pdf_directory = (microbio_root / "Datasets" / "vmr_pdfs").resolve()
        
        if not self.cache_directory.is_absolute():
            v4_root = Path(__file__).parent.parent.parent.parent
            microbio_root = v4_root.parent
            self.cache_directory = (microbio_root / "Datasets" / "vmr_cache").resolve()
            self.cache_directory.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"DDX Tool initialized - PDF dir: {self.pdf_directory}")
        logger.info(f"Cache dir: {self.cache_directory}")
    
    def _extract_episode_info(self, filename: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extract episode number, date, and presenting complaint from filename.
        
        Args:
            filename: PDF filename (e.g., "Episode_1594_-_Virtual_Morning_Report_-_April_2,_2025_-_Failure_to_thrive.pdf")
        
        Returns:
            Tuple of (episode_number, date, presenting_complaint)
        """
        # Pattern: Episode_XXXX_-_...._-_DATE_-_COMPLAINT.pdf
        pattern = r'Episode_(\d+)_-_.*?_-_(.*?)_-_(.*?)\.pdf'
        match = re.match(pattern, filename)
        
        if match:
            episode_num = match.group(1)
            date = match.group(2).strip().replace(',', '').replace('_', ' ')
            complaint = match.group(3).strip().replace('_', ' ')
            return episode_num, date, complaint
        
        return None, None, None
    
    def _calculate_similarity(self, query: str, text: str) -> float:
        """
        Calculate similarity between query and text using sequence matching.
        
        Args:
            query: Search query (presenting complaint)
            text: Text to compare against (episode complaint)
        
        Returns:
            Similarity score between 0 and 1
        """
        query_lower = query.lower().strip()
        text_lower = text.lower().strip()
        
        # Exact match gets perfect score
        if query_lower in text_lower or text_lower in query_lower:
            return 1.0
        
        # Check for keyword overlap
        query_words = set(query_lower.split())
        text_words = set(text_lower.split())
        word_overlap = len(query_words & text_words) / max(len(query_words), len(text_words))
        
        # Use SequenceMatcher for fuzzy matching
        sequence_sim = SequenceMatcher(None, query_lower, text_lower).ratio()
        
        # Combine scores (weighted average)
        return 0.6 * word_overlap + 0.4 * sequence_sim
    
    def _search_episodes(self, presenting_complaint: str) -> List[Dict[str, Any]]:
        """
        Search through available episodes for matching presenting complaints.
        
        Args:
            presenting_complaint: The symptom/complaint to search for
        
        Returns:
            List of matching episodes with metadata
        """
        if not self.pdf_directory.exists():
            logger.error(f"PDF directory not found: {self.pdf_directory}")
            return []
        
        results = []
        
        # Scan all PDF files
        for pdf_file in self.pdf_directory.glob("Episode_*.pdf"):
            episode_num, date, complaint = self._extract_episode_info(pdf_file.name)
            
            if complaint:
                similarity = self._calculate_similarity(presenting_complaint, complaint)
                
                if similarity >= self.similarity_threshold:
                    results.append({
                        "filename": pdf_file.name,
                        "filepath": str(pdf_file),
                        "episode_number": episode_num,
                        "date": date,
                        "presenting_complaint": complaint,
                        "similarity_score": round(similarity, 3)
                    })
        
        # Sort by similarity score (descending)
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        # Limit results
        return results[:self.max_results]
    
    def _extract_pdf_text(self, pdf_path: Path) -> str:
        """
        Extract text content from PDF file.
        
        Preference order:
        1. Check for .md file from OlmoOCR (best quality)
        2. Check cache (.txt)
        3. Fall back to pypdf extraction (not OCR, text-only)
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            Extracted text content
        """
        # Priority 1: Check for OlmoOCR markdown file
        markdown_dir = self.cache_directory.parent / "vmr_markdown"
        md_file = markdown_dir / f"{pdf_path.stem}.md"
        
        if md_file.exists():
            logger.debug(f"Using OlmoOCR markdown for {pdf_path.name}")
            return md_file.read_text(encoding='utf-8')
        
        # Priority 2: Check cache
        cache_file = self.cache_directory / f"{pdf_path.stem}.txt"
        
        if cache_file.exists():
            logger.debug(f"Using cached text for {pdf_path.name}")
            return cache_file.read_text(encoding='utf-8')
        
        # Priority 3: Extract using pypdf (NOT OCR - only extracts embedded text)
        logger.warning(
            f"No markdown/cache found for {pdf_path.name}. "
            "Using pypdf fallback (not OCR). For best results, run: "
            "python scripts/batch_convert_pdfs_olmo.py"
        )
        
        try:
            import pypdf
            
            logger.debug(f"Extracting text from {pdf_path.name} using pypdf (not OCR)")
            reader = pypdf.PdfReader(str(pdf_path))
            
            text_parts = []
            text_parts.append(f"[Extracted with pypdf - NOT OCR. For better quality, use OlmoOCR]\n\n")
            
            for page in reader.pages:
                text_parts.append(page.extract_text())
            
            full_text = "\n".join(text_parts)
            
            # Cache the result
            cache_file.write_text(full_text, encoding='utf-8')
            logger.debug(f"Cached text to {cache_file}")
            
            return full_text
            
        except ImportError:
            raise ToolExecutionError(
                "pypdf not installed. Please either:\n"
                "1. Run: python scripts/batch_convert_pdfs_olmo.py (recommended)\n"
                "2. Install pypdf: pip install pypdf (fallback only)",
                tool_name=self.name
            )
        
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to extract text from PDF: {e}",
                tool_name=self.name,
                details={"pdf_path": str(pdf_path)}
            )
    
    def _format_case_for_llm(self, episode_data: Dict[str, Any], case_text: str) -> str:
        """
        Format the case information for LLM consumption.
        
        Args:
            episode_data: Episode metadata
            case_text: Extracted case text
        
        Returns:
            Formatted case description
        """
        formatted = f"""# Clinical Case from DDX Learners

**Episode:** {episode_data['episode_number']}
**Date:** {episode_data['date']}
**Presenting Complaint:** {episode_data['presenting_complaint']}
**Source:** Virtual Morning Report (clinicalproblemsolving.com)

---

## Case Details

{case_text}

---

*This case was retrieved from the DDX Learners Virtual Morning Report archive.*
"""
        return formatted
    
    def _execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute DDX case search tool.
        
        Args:
            arguments: Dict with keys:
                - presenting_complaint: str (required)
                - return_top_n: int (optional, default from config)
                - extract_full_text: bool (optional, default True)
        
        Returns:
            Dict containing:
                - matches: List of matching episodes with metadata
                - top_match: Full case text of best match (if extract_full_text=True)
                - search_query: Original search query
        """
        presenting_complaint = arguments.get("presenting_complaint")
        if not presenting_complaint:
            raise ToolValidationError(
                "Missing required parameter: presenting_complaint",
                tool_name=self.name
            )
        
        return_top_n = arguments.get("return_top_n", self.max_results)
        extract_full_text = arguments.get("extract_full_text", True)
        
        logger.info(f"Searching for cases with complaint: '{presenting_complaint}'")
        
        # Search for matching episodes
        matches = self._search_episodes(presenting_complaint)
        
        if not matches:
            logger.warning(f"No matches found for: '{presenting_complaint}'")
            return {
                "matches": [],
                "top_match": None,
                "search_query": presenting_complaint,
                "message": f"No episodes found matching '{presenting_complaint}'. Try different keywords."
            }
        
        logger.info(f"Found {len(matches)} matching episodes")
        
        # Limit results
        matches = matches[:return_top_n]
        
        result = {
            "matches": matches,
            "search_query": presenting_complaint,
            "top_match": None
        }
        
        # Extract full text of top match if requested
        if extract_full_text and matches:
            top_episode = matches[0]
            pdf_path = Path(top_episode["filepath"])
            
            try:
                case_text = self._extract_pdf_text(pdf_path)
                formatted_case = self._format_case_for_llm(top_episode, case_text)
                
                result["top_match"] = {
                    "metadata": top_episode,
                    "case_text": case_text,
                    "formatted_case": formatted_case
                }
                
                logger.info(f"Extracted case text from Episode {top_episode['episode_number']}")
                
            except Exception as e:
                logger.error(f"Failed to extract text for top match: {e}")
                result["top_match_error"] = str(e)
        
        return result


# Legacy wrapper for backward compatibility
def search_ddx_cases(
    presenting_complaint: str,
    return_top_n: int = 3,
    extract_full_text: bool = True
) -> Dict[str, Any]:
    """
    Legacy function - search for DDX clinical cases.
    
    Args:
        presenting_complaint: The symptom/complaint to search for
        return_top_n: Number of results to return
        extract_full_text: Whether to extract full text of top match
    
    Returns:
        Dict with matches and case details
    """
    from microtutor.tools.registry import get_tool_instance
    from pathlib import Path
    import json
    
    tool = get_tool_instance('ddx_case_search')
    
    # Fallback: load config manually if not registered
    if not tool:
        logger.warning("DDX tool not registered, loading config manually")
        project_root = Path(__file__).parent.parent.parent.parent
        config_path = project_root / "config" / "tools" / "ddx_case_search_tool.json"
        
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
            tool = DDXCaseSearchTool(config)
        else:
            raise RuntimeError("DDX tool not available and config not found")
    
    result = tool.run({
        'presenting_complaint': presenting_complaint,
        'return_top_n': return_top_n,
        'extract_full_text': extract_full_text
    })
    
    if result['success']:
        return result['result']
    else:
        raise RuntimeError(f"DDX tool failed: {result.get('error', {}).get('message', 'Unknown error')}")

