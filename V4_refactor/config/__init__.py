"""Configuration management for the Microbiology Tutor."""

import os
from typing import Type
from .base import BaseConfig


def get_config() -> Type[BaseConfig]:
    """Get configuration based on environment."""
    env = os.getenv("FLASK_ENV", "development").lower()
    
    if env == "production":
        from .production import ProductionConfig
        return ProductionConfig
    elif env == "testing":
        from .testing import TestingConfig
        return TestingConfig
    else:
        from .development import DevelopmentConfig
        return DevelopmentConfig


# Global config instance
config = get_config()()

__all__ = ["config", "get_config", "BaseConfig"]
