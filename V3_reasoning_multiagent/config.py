# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# --- Defaults ---
DEFAULT_ORGANISM = os.getenv("DEFAULT_ORGANISM", "staphylococcus aureus")
TERMINAL_MODE = False

# --- Database ---
# Toggle which database to use: global (on Render) or local (for dev)
USE_GLOBAL_DB = True
USE_LOCAL_DB  = not USE_GLOBAL_DB

GLOBAL_DATABASE_URL = os.getenv(
    "GLOBAL_DATABASE_URL",
    'postgresql://microllm_user:t6f7TKRdLESfZ3NdBZUFiZJUi5rE7spQ@dpg-d0m0210dl3ps73bsbmu0-a/microllm'
)
LOCAL_DATABASE_URL  = os.getenv(
    "LOCAL_DATABASE_URL",
    'postgresql://postgres:postgres@localhost:5432/microbiology_feedback'
)
# Individual DB settings
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "riccardoconci")
DB_NAME = os.getenv("DB_NAME", "microbiology_feedback")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


# --- Model & backend ---
LLM_BACKEND = "azure"          # or "openai", etc.
API_MODEL_NAME = "gpt-4o"      # default Azure model
LOCAL_MODEL_NAME = "distilgpt2"

# --- Feature flags ---
USE_FAISS = False
OUTPUT_TOOL_DIRECTLY = True
REWARD_MODEL_SAMPLING = False