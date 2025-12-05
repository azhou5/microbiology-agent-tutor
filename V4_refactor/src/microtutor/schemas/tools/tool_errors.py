"""Structured tool exceptions - ToolUniverse style."""

from typing import Dict, Any, Optional


class ToolError(Exception):
    """Base tool error."""
    def __init__(self, message: str, tool_name: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.tool_name = tool_name
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "tool_name": self.tool_name,
            "details": self.details
        }


class ToolValidationError(ToolError):
    """Parameter validation failed."""
    pass


class ToolExecutionError(ToolError):
    """Tool execution failed."""
    pass


class ToolConfigError(ToolError):
    """Invalid tool configuration."""
    pass


class ToolLLMError(ToolError):
    """LLM call failed."""
    pass
