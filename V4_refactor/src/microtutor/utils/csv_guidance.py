"""
Helper module to load and query the pathogen history domains CSV.
"""
import pandas as pd
from pathlib import Path
import logging
import difflib
import os

logger = logging.getLogger(__name__)

class CSVGuidance:
    _instance = None
    _df = None
    _csv_path = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CSVGuidance, cls).__new__(cls)
        return cls._instance

    def load_csv(self, csv_path: str):
        """Load the CSV file."""
        try:
            path = Path(csv_path)
            if not path.exists():
                # Try relative to project root if absolute path fails
                # Assuming project root is 3 levels up from this file: src/microtutor/utils/ -> src/microtutor/ -> src/ -> root
                # Actually, 4 levels: utils -> microtutor -> src -> V4_refactor
                # But let's try to find it relative to current working directory first
                if not path.is_absolute():
                     # Try looking in data/
                     potential_path = Path("data") / csv_path
                     if potential_path.exists():
                         path = potential_path
            
            if not path.exists():
                logger.error(f"CSV file not found: {csv_path}")
                return

            self._csv_path = str(path)
            # Read CSV
            self._df = pd.read_csv(path)
            # Normalize column names
            self._df.columns = [c.strip() for c in self._df.columns]
            # Normalize concept column for easier matching
            if 'concept' in self._df.columns:
                self._df['concept_normalized'] = self._df['concept'].astype(str).str.lower().str.replace(" ", "_").str.strip()
            
            logger.info(f"Loaded CSV guidance from {path} with {len(self._df)} rows.")
        except Exception as e:
            logger.error(f"Failed to load CSV guidance: {e}")
            self._df = None

    def get_crucial_factors(self, organism_name: str) -> list[str]:
        """
        Get list of crucial factors (columns with value 1.0) for a given organism.
        Handles fuzzy matching of organism name.
        """
        if self._df is None:
            # Try to load default path if not loaded
            default_path = "data/pathogen_history_domains_complete.csv"
            self.load_csv(default_path)
            
            if self._df is None:
                logger.warning("CSV guidance not loaded and default load failed.")
                return []

        if not organism_name:
            return []

        # Normalize organism name
        target_name = organism_name.lower().replace(" ", "_").strip()
        
        # Find best match in 'concept' column
        # We use the normalized column we created
        concepts = self._df['concept_normalized'].tolist()
        
        # Try exact match first
        match_idx = -1
        try:
            match_idx = concepts.index(target_name)
        except ValueError:
            pass
        
        # Try close match if no exact match
        if match_idx == -1:
            # simple mapping for common abbreviations
            mappings = {
                "staphylococcus": "staph",
                "streptococcus": "strep",
                "escherichia": "e", # for e. coli but csv has ETEC/EHEC etc.
                "haemophilus": "haemophilus",
            }
            
            search_name = target_name
            for k, v in mappings.items():
                if k in search_name:
                    search_name = search_name.replace(k, v)
            
            # Use difflib to find closest match
            matches = difflib.get_close_matches(search_name, concepts, n=1, cutoff=0.6)
            if matches:
                match_idx = concepts.index(matches[0])

        if match_idx == -1:
            logger.warning(f"No match found in CSV for organism: {organism_name}")
            return []

        matched_concept = self._df.iloc[match_idx]['concept']
        logger.info(f"Found CSV match for '{organism_name}': '{matched_concept}'")
        
        # Get the row
        row = self._df.iloc[match_idx]
        
        # Find columns with 1.0
        crucial_factors = []
        for col in self._df.columns:
            if col in ['concept', 'comments', 'concept_normalized']:
                continue
            
            # Check for 1.0 or '1.0' or 1
            val = row[col]
            try:
                if pd.notna(val) and (float(val) == 1.0):
                    crucial_factors.append(col)
            except ValueError:
                continue
                
        return crucial_factors

# Global instance
csv_guidance = CSVGuidance()
