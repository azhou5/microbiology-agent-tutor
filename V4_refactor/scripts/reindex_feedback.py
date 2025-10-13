"""Reindex feedback into FAISS.

This is a tiny script entrypoint that wraps the existing index builder
to use V4 data/log paths. Intended for manual runs or CI/cron.
"""

import os
from pathlib import Path
from typing import Tuple

# Reuse the existing job logic
from scripts.create_feedback_index import convert_logs_to_faiss_index

# Derive default paths from V4 structure
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "feedback"
LOGS_DIR = BASE_DIR / "logs"

DEFAULT_LOG_FILE = LOGS_DIR / "feedback.log"
DEFAULT_INDEX_FILE = DATA_DIR / "processed" / "output_index.faiss"


def main(log_file: str | os.PathLike | None = None,
         index_file: str | os.PathLike | None = None) -> Tuple[object, list[str]]:
    log_path = Path(log_file) if log_file else DEFAULT_LOG_FILE
    index_path = Path(index_file) if index_file else DEFAULT_INDEX_FILE

    index_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Reindexing feedback from: {log_path}")
    print(f"Saving index to: {index_path}")

    return convert_logs_to_faiss_index(str(log_path), str(index_path))


if __name__ == "__main__":
    main()
