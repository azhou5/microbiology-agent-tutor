"""
Respiratory Audio Matcher for MicroTutor.

This module matches clinical cases to appropriate respiratory sound audio files
using LLM-based analysis of case presentations and patient demographics.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import random

from microtutor.core.llm_router import chat_complete

logger = logging.getLogger(__name__)

class RespiratoryAudioMatcher:
    """Matches clinical cases to respiratory sound audio files."""
    
    def __init__(self, dataset_path: Optional[str] = None):
        """Initialize the audio matcher.
        
        Args:
            dataset_path: Path to the respiratory sound dataset metadata
        """
        self.project_root = Path(__file__).parent.parent.parent.parent.parent
        self.dataset_path = dataset_path or str(self.project_root / "data" / "respiratory_sounds")
        self.metadata_file = Path(self.dataset_path) / "dataset_metadata.json"
        self.cache_file = self.project_root / "V4_refactor" / "data" / "cases" / "cached" / "audio_matches.json"
        
        # Load dataset metadata
        self.metadata = self._load_metadata()
        self.audio_files = self.metadata.get("metadata", {}).get("audio_files", [])
        self.matching_schema = self.metadata.get("matching_schema", {})
        
        # Load existing cache
        self.cache = self._load_cache()
        
        logger.info(f"RespiratoryAudioMatcher initialized with {len(self.audio_files)} audio files")
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load dataset metadata from JSON file."""
        try:
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.debug(f"Metadata file not found: {self.metadata_file}")
            return {"metadata": {"audio_files": []}, "matching_schema": {}}
        except Exception as e:
            logger.error(f"Error loading metadata: {e}")
            return {"metadata": {"audio_files": []}, "matching_schema": {}}
    
    def _load_cache(self) -> Dict[str, Any]:
        """Load existing audio matches cache."""
        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.info("No existing cache found, starting fresh")
            return {}
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            return {}
    
    def _save_cache(self) -> None:
        """Save audio matches cache to file."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
            logger.info(f"Cache saved to: {self.cache_file}")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
    
    def _analyze_case_with_llm(self, hpi: str, organism: str) -> Dict[str, Any]:
        """Use LLM to analyze case and extract respiratory findings.
        
        Args:
            hpi: History of present illness text
            organism: The organism causing the infection
            
        Returns:
            Dictionary with extracted respiratory findings and demographics
        """
        system_prompt = """You are an expert pulmonologist analyzing a clinical case to determine appropriate respiratory sounds for educational purposes.

Your task is to analyze the case and determine:
1. What respiratory/lung findings would be present on physical examination
2. Patient demographics (age, sex) 
3. The most likely respiratory sound category that would be heard

Focus on findings that would be audible on lung auscultation such as:
- Crackles (fine or coarse)
- Wheezes 
- Stridor
- Rhonchi
- Normal/clear lung sounds
- Decreased breath sounds

Respond in JSON format with these fields:
{
    "respiratory_findings": "description of lung findings",
    "primary_sound_category": "Crackles|Wheezes|Both|Healthy|Stridor|Rhonchi",
    "patient_age": number,
    "patient_sex": "Male|Female",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation of the match"
}"""

        user_prompt = f"""Analyze this clinical case for respiratory sound matching:

**Organism**: {organism}
**Case Presentation**: {hpi}

Determine what respiratory sounds would be heard on lung auscultation and provide the best match category."""

        try:
            response = chat_complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model="gpt-4"
            )
            
            # Parse JSON response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                logger.warning("Could not parse LLM response as JSON")
                return self._get_fallback_analysis(organism)
                
        except Exception as e:
            logger.error(f"Error in LLM analysis: {e}")
            return self._get_fallback_analysis(organism)
    
    def _get_fallback_analysis(self, organism: str) -> Dict[str, Any]:
        """Provide fallback analysis when LLM fails."""
        # Simple organism-based fallbacks
        organism_fallbacks = {
            "streptococcus_pneumoniae": {
                "respiratory_findings": "Crackles in lower lobes, decreased breath sounds",
                "primary_sound_category": "Crackles",
                "patient_age": 65,
                "patient_sex": "Male",
                "confidence": 0.7,
                "reasoning": "Pneumonia typically presents with crackles"
            },
            "staphylococcus_aureus": {
                "respiratory_findings": "Variable lung sounds depending on presentation",
                "primary_sound_category": "Crackles",
                "patient_age": 45,
                "patient_sex": "Female", 
                "confidence": 0.6,
                "reasoning": "Staph infections can cause various respiratory findings"
            },
            "influenza_a": {
                "respiratory_findings": "Wheezes, possible crackles",
                "primary_sound_category": "Wheezes",
                "patient_age": 60,
                "patient_sex": "Male",
                "confidence": 0.6,
                "reasoning": "Influenza can cause wheezing and respiratory complications"
            }
        }
        
        return organism_fallbacks.get(organism, {
            "respiratory_findings": "Variable respiratory findings",
            "primary_sound_category": "Crackles",
            "patient_age": 50,
            "patient_sex": "Male",
            "confidence": 0.5,
            "reasoning": "Generic fallback for unknown organism"
        })
    
    def _find_matching_audio_files(self, analysis: Dict[str, Any], top_n: int = 5) -> List[Dict[str, Any]]:
        """Find audio files that match the case analysis.
        
        Args:
            analysis: LLM analysis results
            top_n: Number of top matches to return
            
        Returns:
            List of matching audio file information
        """
        primary_category = analysis.get("primary_sound_category", "Crackles")
        patient_age = analysis.get("patient_age", 50)
        patient_sex = analysis.get("patient_sex", "Male")
        
        # Get files from the primary category
        category_files = self.matching_schema.get("audio_files_by_category", {}).get(primary_category, [])
        
        if not category_files:
            # Fallback to any available files
            logger.warning(f"No files found for category {primary_category}, using all files")
            category_files = self.audio_files
        
        # Score files based on various factors
        scored_files = []
        for file_info in category_files:
            score = 0.0
            
            # Base score for category match
            score += 0.5
            
            # Try to extract age/sex from filename if available
            filename = file_info.get("filename", "").lower()
            
            # Age matching (very rough heuristic)
            if "young" in filename or "child" in filename:
                if patient_age < 30:
                    score += 0.2
            elif "old" in filename or "elderly" in filename:
                if patient_age > 60:
                    score += 0.2
            
            # Sex matching (very rough heuristic)
            if patient_sex.lower() in filename:
                score += 0.1
            
            # File quality (prefer larger files, assume better quality)
            file_size = file_info.get("file_size", 0)
            if file_size > 100000:  # > 100KB
                score += 0.1
            
            scored_files.append({
                **file_info,
                "match_score": score,
                "category": primary_category,
                "analysis": analysis
            })
        
        # Sort by score and return top N
        scored_files.sort(key=lambda x: x["match_score"], reverse=True)
        return scored_files[:top_n]
    
    def match_case_to_audio(self, organism: str, hpi: str, use_cache: bool = True) -> Dict[str, Any]:
        """Match a clinical case to appropriate respiratory audio files.
        
        Args:
            organism: The organism causing the infection
            hpi: History of present illness text
            use_cache: Whether to use cached results if available
            
        Returns:
            Dictionary with matching audio files and metadata
        """
        # Check cache first
        cache_key = f"{organism}_{hash(hpi)}"
        if use_cache and cache_key in self.cache:
            logger.info(f"Using cached result for {organism}")
            return self.cache[cache_key]
        
        logger.info(f"Matching audio for organism: {organism}")
        
        # Analyze case with LLM
        analysis = self._analyze_case_with_llm(hpi, organism)
        
        # Find matching audio files
        matching_files = self._find_matching_audio_files(analysis)
        
        # Prepare result
        result = {
            "organism": organism,
            "analysis": analysis,
            "matching_files": matching_files,
            "best_match": matching_files[0] if matching_files else None,
            "total_matches": len(matching_files),
            "cache_key": cache_key
        }
        
        # Cache the result
        self.cache[cache_key] = result
        self._save_cache()
        
        logger.info(f"Found {len(matching_files)} matching audio files for {organism}")
        return result
    
    def get_audio_for_respiratory_exam(self, organism: str, hpi: str) -> Optional[Dict[str, Any]]:
        """Get audio data for respiratory examination.
        
        Args:
            organism: The organism causing the infection
            hpi: History of present illness text
            
        Returns:
            Audio data dictionary or None if no match found
        """
        match_result = self.match_case_to_audio(organism, hpi)
        
        if not match_result["best_match"]:
            logger.warning(f"No audio match found for {organism}")
            return None
        
        best_match = match_result["best_match"]
        
        return {
            "file_path": best_match["relative_path"],
            "filename": best_match["filename"],
            "finding_type": best_match["category"].lower(),
            "description": f"Lung sounds: {match_result['analysis']['respiratory_findings']}",
            "confidence": match_result["analysis"]["confidence"],
            "match_score": best_match["match_score"]
        }
    
    def pregenerate_all_matches(self, hpi_data: Dict[str, str]) -> Dict[str, Any]:
        """Pre-generate audio matches for all organisms.
        
        Args:
            hpi_data: Dictionary mapping organisms to HPI text
            
        Returns:
            Dictionary with all generated matches
        """
        logger.info(f"Pre-generating audio matches for {len(hpi_data)} organisms")
        
        all_matches = {}
        
        for organism, hpi in hpi_data.items():
            try:
                logger.info(f"Processing {organism}...")
                match_result = self.match_case_to_audio(organism, hpi, use_cache=False)
                all_matches[organism] = match_result
            except Exception as e:
                logger.error(f"Error processing {organism}: {e}")
                all_matches[organism] = {"error": str(e)}
        
        # Save all matches
        self.cache.update(all_matches)
        self._save_cache()
        
        logger.info("Pre-generation complete")
        return all_matches
