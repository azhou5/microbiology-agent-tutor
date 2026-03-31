import os
from dotenv import load_dotenv

# Load environment variables from .env file or dot_env_microtutor.txt
load_dotenv("dot_env_microtutor.txt")

class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    MODEL_NAME = os.getenv("MODEL_NAME", "gpt-5-mini")
    TEACHING_MODEL_NAME = os.getenv("TEACHING_MODEL_NAME", "gpt-5-mini")
    CSV_PATH = os.getenv("CSV_PATH", "data/pathogen_history_domains_complete.csv")
    FEEDBACK_INDEX_DIR = os.getenv("FEEDBACK_INDEX_DIR", "data/feedback_auto")
    FEEDBACK_INDEXING_ENABLED = os.getenv("FEEDBACK_INDEXING_ENABLED", "false").lower() in {"1", "true", "yes", "on"}

config = Config()

