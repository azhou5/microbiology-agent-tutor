"""Base configuration for the Microbiology Tutor application."""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from dot_env_microtutor.txt (V3 compatibility)
dotenv_path = Path(__file__).parent.parent / 'dot_env_microtutor.txt'
if dotenv_path.exists():
    load_dotenv(dotenv_path=str(dotenv_path))
    print(f"✅ Loaded environment variables from: {dotenv_path}")
else:
    print(f"⚠️  Environment file not found: {dotenv_path}")


class BaseConfig(BaseSettings):
    """Base configuration class with common settings."""
    
    # Application settings
    APP_NAME: str = "Microbiology Tutor"
    APP_VERSION: str = "4.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-this-in-production"
    
    # Database settings (matching V3 config)
    USE_GLOBAL_DB: bool = False  # Set to False for local dev, True for production
    USE_LOCAL_DB: bool = True    # Use local DB by default for development
    
    GLOBAL_DATABASE_URL: Optional[str] = "postgresql://microllm_user:t6f7TKRdLESfZ3NdBZUFiZJUi5rE7spQ@dpg-d0m0210dl3ps73bsbmu0-a/microllm"
    LOCAL_DATABASE_URL: Optional[str] = "postgresql://postgres:postgres@localhost:5432/microbiology_feedback"
    
    DATABASE_URL: Optional[str] = None
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "microbiology_feedback"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""
    
    # LLM Configuration (auto-determined from USE_AZURE_OPENAI like V3)
    USE_AZURE_OPENAI: bool = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"
    LLM_BACKEND: str = "azure" if os.getenv("USE_AZURE_OPENAI", "false").lower() == "true" else "openai"
    API_MODEL_NAME: str = os.getenv("AZURE_OPENAI_O4_MINI_DEPLOYMENT", "o4-mini-0416") if os.getenv("USE_AZURE_OPENAI", "false").lower() == "true" else os.getenv("PERSONAL_OPENAI_MODEL", "o4-mini-2025-04-16")
    LOCAL_MODEL_NAME: str = "distilgpt2"
    TEMPERATURE: float = 0.7  # max_tokens removed - always use model default
    
    # Azure OpenAI settings
    AZURE_OPENAI_API_KEY: Optional[str] = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_ENDPOINT: Optional[str] = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-16")
    AZURE_OPENAI_O4_MINI_DEPLOYMENT: Optional[str] = os.getenv("AZURE_OPENAI_O4_MINI_DEPLOYMENT")
    
    # OpenAI settings
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    
    # Feature flags
    USE_FAISS: bool = True
    USE_RAG: bool = True
    USE_REWARD_MODEL: bool = False
    OUTPUT_TOOL_DIRECTLY: bool = True
    IN_CONTEXT_LEARNING: bool = True
    MOCK_LLM_RESPONSES: bool = False
    
    # Default organism for cases
    DEFAULT_ORGANISM: str = "staphylococcus aureus"
    
    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    LOGS_DIR: Path = BASE_DIR / "logs"
    
    # Vector database settings
    FAISS_INDEX_PATH: Optional[str] = None
    FAISS_DIMENSION: int = 1536
    
    # Caching
    ENABLE_RESPONSE_CACHE: bool = True
    CACHE_TTL_SECONDS: int = 3600
    REDIS_URL: Optional[str] = None
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"  # Allow extra fields from environment
        
    def __init__(self, **kwargs):
        """Initialize configuration and create required directories."""
        super().__init__(**kwargs)
        self._create_directories()
        
    def _create_directories(self) -> None:
        """Create required directories if they don't exist."""
        for directory in [self.DATA_DIR, self.LOGS_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
            
    @property
    def database_url(self) -> Optional[str]:
        """Get the database URL, matching V3's logic."""
        # If DATABASE_URL is explicitly set, use it
        if self.DATABASE_URL:
            return self.DATABASE_URL
        
        # Otherwise, use V3's logic: global vs local
        if self.USE_GLOBAL_DB:
            return self.GLOBAL_DATABASE_URL
        elif self.USE_LOCAL_DB:
            return self.LOCAL_DATABASE_URL
        else:
            # No database configured
            return None
