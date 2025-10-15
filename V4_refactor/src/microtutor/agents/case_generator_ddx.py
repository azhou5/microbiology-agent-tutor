"""
DDX-Based Case Generator - Generate cases from real DDX Learners episodes.

This module provides a case generation pipeline that searches and retrieves
real clinical cases from the DDX Learners archive and formats them for use
with the MicroTutor system.
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from microtutor.tools.ddx_case_search import DDXCaseSearchTool, search_ddx_cases
from microtutor.core.llm_router import chat_complete

logger = logging.getLogger(__name__)


class DDXCaseGenerator:
    """
    Generate educational cases from DDX Learners archive.
    
    This class provides a high-level interface for case generation,
    combining case search with optional LLM-based adaptation and formatting.
    """
    
    def __init__(
        self,
        pdf_directory: Optional[str] = None,
        cache_directory: Optional[str] = None,
        llm_model: str = None  # Will use config default
    ):
        """
        Initialize the DDX case generator.
        
        Args:
            pdf_directory: Path to VMR PDFs (defaults to ../../Datasets/vmr_pdfs)
            cache_directory: Path to cache directory (defaults to ../../Datasets/vmr_cache)
            llm_model: Model to use for case adaptation
        """
        # Use config model if not provided
        if llm_model is None:
            from microtutor.core.config_helper import config
            llm_model = config.API_MODEL_NAME
        
        # Initialize the search tool
        tool_config = {
            "name": "ddx_case_search",
            "description": "DDX case search for case generation",
            "pdf_directory": pdf_directory or "../Datasets/vmr_pdfs",
            "cache_directory": cache_directory or "../Datasets/vmr_cache",
            "similarity_threshold": 0.6,
            "max_results": 5
        }
        
        self.search_tool = DDXCaseSearchTool(tool_config)
        self.llm_model = llm_model
        logger.info("DDXCaseGenerator initialized")
    
    def search_cases(
        self,
        presenting_complaint: str,
        max_results: int = 3
    ) -> Dict[str, Any]:
        """
        Search for cases matching a presenting complaint.
        
        Args:
            presenting_complaint: The symptom/complaint to search for
            max_results: Maximum number of results to return
        
        Returns:
            Dict with search results and metadata
        """
        logger.info(f"Searching for cases: '{presenting_complaint}'")
        
        result = self.search_tool.run({
            "presenting_complaint": presenting_complaint,
            "return_top_n": max_results,
            "extract_full_text": True
        })
        
        if not result["success"]:
            logger.error(f"Search failed: {result.get('error')}")
            return {
                "success": False,
                "error": result.get("error"),
                "matches": []
            }
        
        return {
            "success": True,
            "data": result["result"]
        }
    
    def generate_case_from_ddx(
        self,
        presenting_complaint: str,
        adapt_for_level: Optional[str] = None,
        focus_areas: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate a case from DDX archive, optionally adapted for specific learning level.
        
        Args:
            presenting_complaint: The symptom/complaint to search for
            adapt_for_level: Educational level (e.g., "medical_student", "resident", "attending")
            focus_areas: Specific topics to emphasize (e.g., ["microbiology", "pharmacology"])
        
        Returns:
            Dict containing:
                - success: bool
                - case: Formatted case description
                - metadata: Source information
                - original_case: Raw case text
        """
        # Search for matching cases
        search_result = self.search_cases(presenting_complaint, max_results=1)
        
        if not search_result["success"]:
            return {
                "success": False,
                "error": "No matching cases found",
                "case": None
            }
        
        data = search_result["data"]
        
        # Check if we got a match
        if not data.get("matches"):
            return {
                "success": False,
                "error": f"No cases found for '{presenting_complaint}'",
                "case": None
            }
        
        top_match = data.get("top_match")
        if not top_match:
            return {
                "success": False,
                "error": "Could not extract case content",
                "case": None
            }
        
        original_case = top_match["case_text"]
        metadata = top_match["metadata"]
        
        # If no adaptation requested, return the raw case
        if not adapt_for_level and not focus_areas:
            return {
                "success": True,
                "case": top_match["formatted_case"],
                "original_case": original_case,
                "metadata": metadata,
                "adapted": False
            }
        
        # Adapt case using LLM
        logger.info(f"Adapting case for level: {adapt_for_level}, focus: {focus_areas}")
        adapted_case = self._adapt_case(
            original_case,
            metadata,
            adapt_for_level,
            focus_areas
        )
        
        return {
            "success": True,
            "case": adapted_case,
            "original_case": original_case,
            "metadata": metadata,
            "adapted": True
        }
    
    def _adapt_case(
        self,
        case_text: str,
        metadata: Dict[str, Any],
        level: Optional[str] = None,
        focus_areas: Optional[List[str]] = None
    ) -> str:
        """
        Adapt case for specific educational level and focus areas using LLM.
        
        Args:
            case_text: Original case text
            metadata: Case metadata
            level: Educational level
            focus_areas: Topics to emphasize
        
        Returns:
            Adapted case text
        """
        system_prompt = """You are an expert medical educator who adapts clinical cases 
for educational purposes. You maintain clinical accuracy while tailoring complexity 
and emphasis to the learner's level and focus areas."""
        
        level_guidance = ""
        if level:
            level_map = {
                "medical_student": "3rd-year medical student level - focus on basic clinical reasoning, fundamental concepts",
                "resident": "Internal medicine resident level - include diagnostic challenges, management considerations",
                "attending": "Attending physician level - emphasize nuanced decision-making, evidence-based practices"
            }
            level_guidance = f"\n\nTarget Level: {level_map.get(level, level)}"
        
        focus_guidance = ""
        if focus_areas:
            focus_guidance = f"\n\nEmphasize these topics: {', '.join(focus_areas)}"
        
        user_prompt = f"""Please adapt the following clinical case for educational use.

Original Case:
{case_text}

Source: DDX Learners Episode {metadata.get('episode_number')} - {metadata.get('presenting_complaint')}
{level_guidance}
{focus_guidance}

Instructions:
1. Maintain clinical accuracy and essential details
2. Format clearly with appropriate sections (presentation, history, exam, labs, etc.)
3. Adjust complexity and emphasis based on the target level
4. Highlight relevant teaching points for the focus areas
5. Ensure the case flows naturally for a tutoring session

Provide the adapted case below:"""
        
        try:
            adapted = chat_complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=self.llm_model
            )
            return adapted
            
        except Exception as e:
            logger.error(f"Failed to adapt case: {e}")
            # Return original formatted case as fallback
            return f"""# Clinical Case from DDX Learners

**Episode:** {metadata.get('episode_number')}
**Presenting Complaint:** {metadata.get('presenting_complaint')}

{case_text}
"""
    
    def batch_generate_cases(
        self,
        presenting_complaints: List[str],
        output_dir: Optional[str] = None,
        adapt_for_level: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate multiple cases in batch.
        
        Args:
            presenting_complaints: List of complaints to search for
            output_dir: Directory to save generated cases (optional)
            adapt_for_level: Educational level for adaptation
        
        Returns:
            Dict with generation results and statistics
        """
        import json
        from datetime import datetime
        
        results = {
            "total": len(presenting_complaints),
            "successful": 0,
            "failed": 0,
            "cases": []
        }
        
        output_path = None
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
        
        for complaint in presenting_complaints:
            logger.info(f"Generating case for: {complaint}")
            
            try:
                case_result = self.generate_case_from_ddx(
                    complaint,
                    adapt_for_level=adapt_for_level
                )
                
                if case_result["success"]:
                    results["successful"] += 1
                    results["cases"].append({
                        "presenting_complaint": complaint,
                        "status": "success",
                        "metadata": case_result.get("metadata"),
                        "case": case_result.get("case")
                    })
                    
                    # Save to file if output directory specified
                    if output_path:
                        filename = f"case_{complaint.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                        filepath = output_path / filename
                        
                        with open(filepath, 'w') as f:
                            json.dump(case_result, f, indent=2)
                        
                        logger.info(f"Saved case to: {filepath}")
                else:
                    results["failed"] += 1
                    results["cases"].append({
                        "presenting_complaint": complaint,
                        "status": "failed",
                        "error": case_result.get("error")
                    })
                    
            except Exception as e:
                logger.error(f"Error generating case for '{complaint}': {e}")
                results["failed"] += 1
                results["cases"].append({
                    "presenting_complaint": complaint,
                    "status": "error",
                    "error": str(e)
                })
        
        logger.info(f"Batch generation complete: {results['successful']}/{results['total']} successful")
        return results


# Convenience functions for common use cases

def generate_case(
    presenting_complaint: str,
    level: Optional[str] = None,
    focus_areas: Optional[List[str]] = None
) -> Optional[str]:
    """
    Quick function to generate a case from DDX archive.
    
    Args:
        presenting_complaint: The symptom/complaint to search for
        level: Educational level (optional)
        focus_areas: Topics to emphasize (optional)
    
    Returns:
        Formatted case text, or None if not found
    
    Example:
        >>> case = generate_case("chest pain", level="medical_student")
        >>> print(case)
    """
    generator = DDXCaseGenerator()
    result = generator.generate_case_from_ddx(
        presenting_complaint,
        adapt_for_level=level,
        focus_areas=focus_areas
    )
    
    if result["success"]:
        return result["case"]
    else:
        logger.warning(f"Case generation failed: {result.get('error')}")
        return None


def list_available_complaints(
    pdf_directory: Optional[str] = None
) -> List[str]:
    """
    List all available presenting complaints in the DDX archive.
    
    Args:
        pdf_directory: Path to PDF directory
    
    Returns:
        List of unique presenting complaints
    """
    import re
    from pathlib import Path
    
    if pdf_directory:
        pdf_dir = Path(pdf_directory)
    else:
        # __file__ is in: V4_refactor/src/microtutor/agents/case_generator_ddx.py
        v4_root = Path(__file__).parent.parent.parent.parent
        microbio_root = v4_root.parent
        pdf_dir = microbio_root / "Datasets" / "vmr_pdfs"
    
    complaints = set()
    
    if not pdf_dir.exists():
        logger.warning(f"PDF directory not found: {pdf_dir}")
        return []
    
    for pdf_file in pdf_dir.glob("Episode_*.pdf"):
        pattern = r'Episode_\d+_-_.*?_-_.*?_-_(.*?)\.pdf'
        match = re.match(pattern, pdf_file.name)
        if match:
            complaint = match.group(1).strip().replace('_', ' ')
            complaints.add(complaint)
    
    return sorted(list(complaints))

