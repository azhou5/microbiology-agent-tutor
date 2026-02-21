import json
import logging
from pathlib import Path
import os

logger = logging.getLogger(__name__)

class CaseLoader:
    def __init__(self, cache_path: str = "data/cases/cached/case_cache.json", manual_cases_dir: str = "ID_Images"):
        self.cache_path = cache_path
        self.manual_cases_dir = manual_cases_dir
        self.project_root = Path(__file__).resolve().parents[2]
        self.cases = {}
        self.manual_cases = {}
        self.load_cases()
        self.load_manual_cases()

    def load_cases(self):
        try:
            path = Path(self.cache_path)
            if not path.exists():
                # Try relative to project root
                potential_path = Path("V4_refactor") / self.cache_path
                if potential_path.exists():
                    path = potential_path
                else:
                    project_path = self.project_root / self.cache_path
                    if project_path.exists():
                        path = project_path
            
            if path.exists():
                with open(path, 'r') as f:
                    self.cases = json.load(f)
                logger.info(f"Loaded {len(self.cases)} cases from {path}")
            else:
                logger.error(f"Case cache file not found: {self.cache_path}")
        except Exception as e:
            logger.error(f"Failed to load case cache: {e}")

    def load_manual_cases(self):
        try:
            path = Path(self.manual_cases_dir)
            if not path.exists():
                potential_path = Path("V4_refactor") / self.manual_cases_dir
                if potential_path.exists():
                    path = potential_path
                else:
                    project_path = self.project_root / self.manual_cases_dir
                    if project_path.exists():
                        path = project_path
            
            if path.exists():
                for case_dir in path.iterdir():
                    if case_dir.is_dir() and case_dir.name.startswith("Case_"):
                        case_text_path = case_dir / "case_text.txt"
                        if case_text_path.exists():
                            with open(case_text_path, 'r') as f:
                                content = f.read()
                                # Store with case ID as key
                                self.manual_cases[case_dir.name] = {
                                    "content": content,
                                    "images": [f.name for f in case_dir.glob("*.jpg")] + [f.name for f in case_dir.glob("*.png")],
                                    "path": str(case_dir)
                                }
                logger.info(f"Loaded {len(self.manual_cases)} manual cases from {path}")
        except Exception as e:
            logger.error(f"Failed to load manual cases: {e}")

    def get_case(self, key: str) -> str:
        if key in self.manual_cases:
            return self.manual_cases[key]["content"]
        return self.cases.get(key, f"Case for {key} not found.")

    def get_case_data(self, key: str) -> dict:
        if key in self.manual_cases:
            return self.manual_cases[key]
        return {"content": self.cases.get(key, ""), "images": []}

    def list_available_organisms(self) -> list[str]:
        return list(self.cases.keys()) + list(self.manual_cases.keys())
