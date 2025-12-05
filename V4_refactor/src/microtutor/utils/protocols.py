"""
Protocol definitions for MicroTutor services.

This module defines Protocol interfaces (structural subtyping) for
collaborator dependencies, allowing for flexible dependency injection
and testing.
"""

from typing import List, Dict, Any, Optional, Protocol


class ToolEngine(Protocol):
    """Protocol for tool execution engine."""
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get OpenAI-compatible tool schemas for function calling."""
        ...
    
    def list_tools(self) -> List[str]:
        """List all available tool names."""
        ...
    
    def execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with arguments.
        
        Returns:
            Dict with: result, tool_name, success, cached, execution_time_ms, error (if failed)
        """
        ...


class FeedbackClient(Protocol):
    """Protocol for feedback retrieval client."""
    
    def get_examples_for_tool(
        self,
        user_input: str,
        conversation_history: List[Dict[str, str]],
        tool_name: str,
        include_feedback: bool,
        similarity_threshold: Optional[float],
    ) -> str:
        """Get formatted feedback examples string for a tool.
        
        Returns:
            Formatted string with feedback examples
        """
        ...
    
    def retrieve_feedback_examples(
        self,
        current_message: str,
        conversation_history: List[Dict[str, str]],
        message_type: str,
        k: int,
        similarity_threshold: Optional[float],
    ) -> List[Dict[str, Any]]:
        """Retrieve structured feedback examples.
        
        Returns:
            List of feedback example dictionaries
        """
        ...
