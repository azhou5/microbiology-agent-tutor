# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# --- Defaults ---
DEFAULT_ORGANISM = os.getenv("DEFAULT_ORGANISM", "staphylococcus aureus")
TERMINAL_MODE = False

# --- Model & backend ---
LLM_BACKEND = "azure"          # or "openai", etc.
API_MODEL_NAME = "gpt-4o"      # default Azure model
LOCAL_MODEL_NAME = "distilgpt2"

# --- Feature flags ---
USE_FAISS = False
OUTPUT_TOOL_DIRECTLY = True
REWARD_MODEL_SAMPLING = False