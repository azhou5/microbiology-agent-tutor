# config.py
import os
from dotenv import load_dotenv

load_dotenv()
DEFAULT_ORGANISM = os.getenv("DEFAULT_ORGANISM", "staphylococcus aureus")
TERMINAL_MODE = False


LLM_BACKEND = "local" # "azure"
API_MODEL_NAME   = "gpt-4o"
LOCAL_MODEL_NAME = "distilgpt2" #"meta-llama/Llama-3.2-1B" # ""

USE_FAISS = "false"
OUTPUT_TOOL_DIRECTLY  = "true"
REWARD_MODEL_SAMPLING = "false"