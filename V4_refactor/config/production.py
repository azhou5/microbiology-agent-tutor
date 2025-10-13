"""Production configuration."""

from .base import BaseConfig


class ProductionConfig(BaseConfig):
    """Production configuration."""
    
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # Production features enabled
    USE_FAISS: bool = True
    USE_RAG: bool = True
    USE_REWARD_MODEL: bool = True
    
    # No mock responses in production
    MOCK_LLM_RESPONSES: bool = False
