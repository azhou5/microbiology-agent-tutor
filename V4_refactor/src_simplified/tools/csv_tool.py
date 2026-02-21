import pandas as pd
from pathlib import Path
import logging
import difflib

logger = logging.getLogger(__name__)

class CSVTool:
    def __init__(self, csv_path: str = "data/pathogen_history_domains_complete.csv"):
        self.csv_path = csv_path
        self.df = None
        self.load_csv()

    def load_csv(self):
        try:
            path = Path(self.csv_path)
            if not path.exists():
                # Try relative to project root
                potential_path = Path("V4_refactor") / self.csv_path
                if potential_path.exists():
                    path = potential_path
            
            if path.exists():
                self.df = pd.read_csv(path)
                self.df.columns = [c.strip() for c in self.df.columns]
                if 'concept' in self.df.columns:
                    self.df['concept_normalized'] = self.df['concept'].astype(str).str.lower().str.replace(" ", "_").str.strip()
                logger.info(f"Loaded CSV from {path}")
            else:
                logger.error(f"CSV file not found: {self.csv_path}")
        except Exception as e:
            logger.error(f"Failed to load CSV: {e}")

    def get_crucial_factors(self, organism_name: str) -> list[str]:
        if self.df is None:
            return []
        
        target_name = organism_name.lower().replace(" ", "_").strip()
        concepts = self.df['concept_normalized'].tolist()
        
        match_idx = -1
        try:
            match_idx = concepts.index(target_name)
        except ValueError:
            matches = difflib.get_close_matches(target_name, concepts, n=1, cutoff=0.6)
            if matches:
                match_idx = concepts.index(matches[0])
        
        if match_idx == -1:
            return []

        row = self.df.iloc[match_idx]
        crucial_factors = []
        for col in self.df.columns:
            if col in ['concept', 'comments', 'concept_normalized']:
                continue
            val = row[col]
            try:
                if pd.notna(val) and float(val) == 1.0:
                    crucial_factors.append(col)
            except ValueError:
                continue
        return crucial_factors

