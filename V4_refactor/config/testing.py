"""Testing configuration."""

from .base import BaseConfig


class TestingConfig(BaseConfig):
    """Testing configuration."""
    
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    
    # Use in-memory SQLite for tests
    DATABASE_URL: str = "sqlite:///:memory:"
    
    # Disable external dependencies for testing
    USE_FAISS: bool = False
    USE_RAG: bool = False
    USE_REWARD_MODEL: bool = False
    
    # Always use mock responses in tests
    MOCK_LLM_RESPONSES: bool = True
