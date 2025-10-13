"""
Tool base classes - ToolUniverse style

Model/interface definitions that define WHAT a tool is.
Concrete implementations in tools/ define HOW they work.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json
import hashlib
import logging
from datetime import datetime
from jsonschema import validate, ValidationError

from microtutor.models.tool_errors import (
    ToolError,
    ToolValidationError,
    ToolExecutionError,
    ToolConfigError,
    ToolLLMError
)

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """
    Base tool class - standardized interface for all tools.
    
    Provides: validation, caching, error handling, execution metrics.
    """
    
    def __init__(self, tool_config: Dict[str, Any]):
        """Initialize tool from JSON config."""
        if "name" not in tool_config or "description" not in tool_config:
            raise ToolConfigError("Missing required fields: name, description")
        
        self.tool_config = tool_config
        self.name = tool_config["name"]
        self.description = tool_config.get("description", "")
        self.parameter_schema = tool_config.get("parameter", {})
        self.cacheable = tool_config.get("cacheable", False)
        self.metadata = tool_config.get("metadata", {})
        self._cache: Dict[str, Any] = {}
    
    def validate_parameters(self, arguments: Dict[str, Any]) -> None:
        """Validate parameters against JSON schema."""
        if not self.parameter_schema:
            return
        
        try:
            validate(instance=arguments, schema=self.parameter_schema)
        except ValidationError as e:
            raise ToolValidationError(
                f"Parameter validation failed: {e.message}",
                tool_name=self.name,
                details={"arguments": arguments, "error_path": list(e.path)}
            )
    
    def get_cache_key(self, arguments: Dict[str, Any]) -> str:
        """Generate cache key from tool name + arguments."""
        cache_str = f"{self.name}:{json.dumps(arguments, sort_keys=True)}"
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    def get_cached_result(self, arguments: Dict[str, Any]) -> Optional[Any]:
        """Get cached result if available."""
        if not self.cacheable:
            return None
        return self._cache.get(self.get_cache_key(arguments))
    
    def cache_result(self, arguments: Dict[str, Any], result: Any) -> None:
        """Cache a result."""
        if self.cacheable:
            self._cache[self.get_cache_key(arguments)] = result
    
    def clear_cache(self) -> None:
        """Clear cache."""
        self._cache.clear()
    
    @abstractmethod
    def _execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute tool logic - must be implemented by subclasses."""
        pass
    
    def run(
        self, 
        arguments: Optional[Dict[str, Any]] = None,
        validate: bool = True,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Execute tool with validation, caching, error handling.
        
        Returns:
            Dict with: result, tool_name, success, cached, execution_time_ms, error (if failed)
        """
        start_time = datetime.now()
        arguments = arguments or {}
        
        try:
            # Validate
            if validate:
                self.validate_parameters(arguments)
            
            # Check cache
            if use_cache and self.cacheable:
                cached = self.get_cached_result(arguments)
                if cached is not None:
                    return {
                        "result": cached,
                        "tool_name": self.name,
                        "success": True,
                        "cached": True,
                        "execution_time_ms": 0
                    }
            
            # Execute
            result = self._execute(arguments)
            
            # Cache
            if use_cache and self.cacheable:
                self.cache_result(arguments, result)
            
            exec_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                "result": result,
                "tool_name": self.name,
                "success": True,
                "cached": False,
                "execution_time_ms": exec_time
            }
            
        except ToolError as e:
            exec_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Tool error in {self.name}: {e}")
            return {
                "result": None,
                "tool_name": self.name,
                "success": False,
                "cached": False,
                "execution_time_ms": exec_time,
                "error": e.to_dict()
            }
            
        except Exception as e:
            exec_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Unexpected error in {self.name}: {e}", exc_info=True)
            return {
                "result": None,
                "tool_name": self.name,
                "success": False,
                "cached": False,
                "execution_time_ms": exec_time,
                "error": {
                    "error_type": "UnexpectedError",
                    "message": str(e),
                    "tool_name": self.name
                }
            }
    
    def get_schema(self) -> Dict[str, Any]:
        """Get OpenAI-compatible function schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameter_schema
            }
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"


class AgenticTool(BaseTool):
    """
    Agentic Tool - powered by LLM calls.
    
    Base class for educational agents (patient, socratic, hint).
    """
    
    def __init__(self, tool_config: Dict[str, Any]):
        super().__init__(tool_config)
        self.prompt_template = tool_config.get("prompt_template", "")
        self.llm_config = tool_config.get("llm_config", {})
    
    def _build_prompt(self, arguments: Dict[str, Any]) -> str:
        """Build LLM prompt from template + arguments."""
        if not self.prompt_template:
            return ""
        try:
            return self.prompt_template.format(**arguments)
        except KeyError as e:
            raise ToolExecutionError(
                f"Missing argument for prompt: {e}",
                tool_name=self.name
            )
    
    @abstractmethod
    def _call_llm(self, prompt: str, **kwargs) -> str:
        """Call LLM - must be implemented by subclasses."""
        pass
    
    def _execute(self, arguments: Dict[str, Any]) -> str:
        """Execute by calling LLM."""
        prompt = self._build_prompt(arguments)
        try:
            return self._call_llm(prompt, **self.llm_config)
        except Exception as e:
            raise ToolLLMError(f"LLM call failed: {e}", tool_name=self.name)
