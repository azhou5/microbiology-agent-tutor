# config.py
import os
from dotenv import load_dotenv

# Construct path to the .env file in the same directory as this script
dotenv_path = os.path.join(os.path.dirname(__file__), 'dot_env_microtutor.txt')
load_dotenv(dotenv_path=dotenv_path)

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
# Automatically determine backend based on USE_AZURE_OPENAI environment variable
USE_AZURE_OPENAI = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"
LLM_BACKEND = "azure" if USE_AZURE_OPENAI else "openai"
API_MODEL_NAME = "o4-mini-0416" if USE_AZURE_OPENAI else "gpt-5-mini-2025-08-07"
LOCAL_MODEL_NAME = "distilgpt2"

# --- Feature flags ---
USE_FAISS = False
OUTPUT_TOOL_DIRECTLY = True
REWARD_MODEL_SAMPLING = False
IN_CONTEXT_LEARNING = True