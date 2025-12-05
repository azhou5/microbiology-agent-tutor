"""Core functionality for MicroTutor.

This module provides core infrastructure including:
- Base agent class
- LLM clients and routing
- Configuration management
- Logging
- Cost tracking
- Feedback retrieval
"""

# Base agent (moved from agents/)
from .base_agent import BaseAgent

# Core submodules
from . import llm
from . import config
from . import cost
from . import logging
from . import feedback

__all__ = [
    "BaseAgent",
    "llm",
    "config",
    "cost",
    "logging",
    "feedback",
]
