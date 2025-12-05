"""Main configuration module for the Microbiology Tutor application."""

import os
from pathlib import Path
from dotenv import load_dotenv
from .base import BaseConfig

# Load environment file from base of V4_refactor
BASE_DIR = Path(__file__).parent.parent
env_path = BASE_DIR / 'dot_env_microtutor.txt'

if env_path.exists():
    load_dotenv(dotenv_path=str(env_path))
    print(f"✅ Environment file loaded from: {env_path}")
else:
    print(f"⚠️  Environment file not found: {env_path}, using system environment variables only")

class Config(BaseConfig):
    """Main configuration class with environment-specific settings."""
    
    # Application settings
    APP_NAME: str = "Microbiology Tutor"
    APP_VERSION: str = "4.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", "change-this-in-production")
    
    # Database settings
    USE_GLOBAL_DB: bool = os.getenv("USE_GLOBAL_DB", "True").lower() == "true"
    USE_LOCAL_DB: bool = os.getenv("USE_LOCAL_DB", "False").lower() == "true"
    
    GLOBAL_DATABASE_URL: str = os.getenv(
        "GLOBAL_DATABASE_URL",
        'postgresql://microllm_user:t6f7TKRdLESfZ3NdBZUFiZJUi5rE7spQ@dpg-d0m0210dl3ps73bsbmu0-a/microllm'
    )
    LOCAL_DATABASE_URL: str = os.getenv(
        "LOCAL_DATABASE_URL",
        'postgresql://postgres:postgres@localhost:5432/microbiology_feedback'
    )
    
    # Individual DB settings
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_USER: str = os.getenv("DB_USER", "riccardoconci")
    DB_NAME: str = os.getenv("DB_NAME", "microbiology_feedback")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    
    # LLM Configuration - respects USE_AZURE_OPENAI flag
    USE_AZURE_OPENAI: bool = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"
    
    # Azure OpenAI settings
    AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    AZURE_OPENAI_DEPLOYMENT_NAME: str = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "o4-mini-0416")
    
    # Personal OpenAI settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    PERSONAL_OPENAI_MODEL: str = os.getenv("PERSONAL_OPENAI_MODEL", "o4-mini-2025-04-16")
    
    # Determine which model to use based on USE_AZURE_OPENAI flag
    # This is computed at initialization time
    API_MODEL_NAME: str = (
        os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "o4-mini-0416")
        if os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"
        else os.getenv("PERSONAL_OPENAI_MODEL", "o4-mini-2025-04-16")
    )
    
    LLM_BACKEND: str = os.getenv("LLM_BACKEND", "azure")
    LOCAL_MODEL_NAME: str = os.getenv("LOCAL_MODEL_NAME", "distilgpt2")
    
    # Feature flags
    USE_FAISS: bool = os.getenv("USE_FAISS", "False").lower() == "true"
    OUTPUT_TOOL_DIRECTLY: bool = os.getenv("OUTPUT_TOOL_DIRECTLY", "True").lower() == "true"
    REWARD_MODEL_SAMPLING: bool = os.getenv("REWARD_MODEL_SAMPLING", "False").lower() == "true"
    IN_CONTEXT_LEARNING: bool = os.getenv("IN_CONTEXT_LEARNING", "True").lower() == "true"
    TERMINAL_MODE: bool = os.getenv("TERMINAL_MODE", "False").lower() == "true"
    FAST_CLASSIFICATION_ENABLED: bool = os.getenv("FAST_CLASSIFICATION_ENABLED", "False").lower() == "true"
    
    # Default organism for cases
    DEFAULT_ORGANISM: str = os.getenv("DEFAULT_ORGANISM", "staphylococcus aureus")
    
    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    LOGS_DIR: Path = BASE_DIR / "logs"
    
    # Vector database settings
    FAISS_INDEX_PATH: str = os.getenv("FAISS_INDEX_PATH", str(DATA_DIR / "models" / "faiss_indices" / "output_index.faiss"))
    FAISS_DIMENSION: int = int(os.getenv("FAISS_DIMENSION", "1536"))
    
    # Qdrant settings
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    
    @property
    def database_url(self) -> str:
        """Get the database URL based on configuration flags."""
        if self.USE_GLOBAL_DB:
            return self.GLOBAL_DATABASE_URL
        elif self.USE_LOCAL_DB:
            return self.LOCAL_DATABASE_URL
        else:
            return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

# Create global config instance
config = Config()