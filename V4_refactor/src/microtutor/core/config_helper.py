"""
Config Helper - Provides unified config access for V4.

This module handles importing config in a way that works with V4's structure.
"""

import os
import sys
from pathlib import Path

# Add config directory to path if not already there
config_dir = Path(__file__).parent.parent.parent.parent / "config"
if str(config_dir) not in sys.path:
    sys.path.insert(0, str(config_dir))

# Import config
try:
    from config import Config
    config = Config()
except ImportError:
    # Fallback: create config from environment variables
    from dotenv import load_dotenv
    
    # Try to load .env from project root
    env_path = Path(__file__).parent.parent.parent.parent / "dot_env_microtutor.txt"
    if env_path.exists():
        load_dotenv(env_path)
    
    class Config:
        """Fallback config class that reads from environment."""
        
        # LLM Configuration
        API_MODEL_NAME = os.getenv("API_MODEL_NAME", "gpt-4")
        LLM_BACKEND = os.getenv("LLM_BACKEND", "azure")
        
        # Azure OpenAI
        AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
        AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        
        # OpenAI
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        
        # Database
        USE_GLOBAL_DB = os.getenv("USE_GLOBAL_DB", "True").lower() == "true"
        USE_LOCAL_DB = os.getenv("USE_LOCAL_DB", "False").lower() == "true"
        
        # Feature flags
        USE_FAISS = os.getenv("USE_FAISS", "False").lower() == "true"
        OUTPUT_TOOL_DIRECTLY = os.getenv("OUTPUT_TOOL_DIRECTLY", "True").lower() == "true"
        REWARD_MODEL_SAMPLING = os.getenv("REWARD_MODEL_SAMPLING", "False").lower() == "true"
    
    config = Config()

# Export config instance
__all__ = ["config"]

