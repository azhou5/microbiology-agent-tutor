"""Configuration management for the Microbiology Tutor."""

# Import the main config from config.py
from .config import Config, config
from .base import BaseConfig

__all__ = ["config", "Config", "BaseConfig"]
