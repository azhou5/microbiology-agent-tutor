"""
Core utilities for MicroTutor V4.

Clean architecture with native function calling:
- llm_router.py: Public API (chat_complete)
- llm_client.py: LLM client management
- cost_tracker.py: Cost tracking
- tutor_prompt.py: Tutor prompts for native function calling
"""

# LLM - Clean architecture
from microtutor.core.llm_router import chat_complete, get_llm_client
from microtutor.core.llm_client import LLMClient
from microtutor.core.cost_tracker import CostTracker, TokenUsage

# Prompts (V4 - Native Function Calling)
from microtutor.core.tutor_prompt import (
    get_system_message_template,
    get_tool_schemas_for_function_calling,
)

# Backward compatibility aliases
llm_manager = get_llm_client()
LLMManager = LLMClient

__all__ = [
    # LLM
    "chat_complete",
    "get_llm_client",
    "LLMClient",
    "llm_manager",  # Alias
    "LLMManager",   # Alias
    "CostTracker",
    "TokenUsage",
    # Prompts
    "get_system_message_template",
    "get_tool_schemas_for_function_calling",
]
