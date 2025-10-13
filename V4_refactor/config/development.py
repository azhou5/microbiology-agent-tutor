"""Development configuration."""

from .base import BaseConfig


class DevelopmentConfig(BaseConfig):
    """Development configuration."""
    
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    
    # Use SQLite for development by default
    DATABASE_URL: str = "sqlite:///data/microtutor_dev.db"
    
    # Disable some features for faster development
    USE_FAISS: bool = False
    USE_REWARD_MODEL: bool = False
    
    # Enable mock responses for development
    MOCK_LLM_RESPONSES: bool = True
