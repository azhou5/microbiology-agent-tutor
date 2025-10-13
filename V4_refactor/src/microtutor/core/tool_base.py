"""BaseTool - ToolUniverse-style base class for all MicroTutor tools."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json
import hashlib
import logging
from datetime import datetime
from jsonschema import validate, ValidationError

logger = logging.getLogger(__name__)


class ToolError(Exception):
    """Base exception for tool errors."""
    def __init__(self, message: str, tool_name: str = None, details: Dict[str, Any] = None):
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
    """Tool configuration invalid."""
    pass


class ToolLLMError(ToolError):
    """LLM call failed."""
    pass


class BaseTool(ABC):
    """Base class for all MicroTutor tools following ToolUniverse patterns."""
    
    def __init__(self, tool_config: Dict[str, Any]):
        """Initialize tool with configuration."""
        self._validate_config(tool_config)
        
        self.tool_config = tool_config
        self.name = tool_config["name"]
        self.description = tool_config.get("description", "")
        self.parameter_schema = tool_config.get("parameter", {})
        self.cacheable = tool_config.get("cacheable", False)
        self.metadata = tool_config.get("metadata", {})
        self._cache: Dict[str, Any] = {}
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate tool configuration."""
        for field in ["name", "description"]:
            if field not in config:
                raise ToolConfigError(f"Missing required field: {field}", details={"config": config})
        
        if "parameter" in config and not isinstance(config["parameter"], dict):
            raise ToolConfigError("Parameter schema must be a dict", tool_name=config["name"])
    
    def validate_parameters(self, arguments: Dict[str, Any]) -> None:
        """Validate parameters against JSON schema."""
        if not self.parameter_schema:
            return
        
        try:
            validate(instance=arguments, schema=self.parameter_schema)
        except ValidationError as e:
            raise ToolValidationError(
                f"Validation failed: {e.message}",
                tool_name=self.name,
                details={"arguments": arguments, "error_path": list(e.path)}
            )
    
    def get_cache_key(self, arguments: Dict[str, Any]) -> str:
        """Generate cache key from arguments."""
        cache_str = f"{self.name}:{json.dumps(arguments, sort_keys=True)}"
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    def get_cached_result(self, arguments: Dict[str, Any]) -> Optional[Any]:
        """Get cached result if available."""
        return self._cache.get(self.get_cache_key(arguments)) if self.cacheable else None
    
    def cache_result(self, arguments: Dict[str, Any], result: Any) -> None:
        """Cache a tool result."""
        if self.cacheable:
            self._cache[self.get_cache_key(arguments)] = result
    
    def clear_cache(self) -> None:
        """Clear cache."""
        self._cache.clear()
    
    @abstractmethod
    def _execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute the tool's core logic. Must be implemented by subclasses."""
        pass
    
    def run(self, arguments: Optional[Dict[str, Any]] = None, validate: bool = True, 
            use_cache: bool = True) -> Dict[str, Any]:
        """Execute tool with validation, caching, and error handling."""
        start_time = datetime.now()
        arguments = arguments or {}
        
        try:
            if validate:
                self.validate_parameters(arguments)
            
            # Check cache
            if use_cache and self.cacheable:
                cached_result = self.get_cached_result(arguments)
                if cached_result is not None:
                    return {"result": cached_result, "tool_name": self.name, 
                           "success": True, "cached": True, "execution_time_ms": 0}
            
            # Execute
            result = self._execute(arguments)
            if use_cache and self.cacheable:
                self.cache_result(arguments, result)
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            return {"result": result, "tool_name": self.name, "success": True, 
                   "cached": False, "execution_time_ms": execution_time}
            
        except ToolError as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Tool error in {self.name}: {e}")
            return {"result": None, "tool_name": self.name, "success": False, 
                   "cached": False, "execution_time_ms": execution_time, "error": e.to_dict()}
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Unexpected error in {self.name}: {e}", exc_info=True)
            return {"result": None, "tool_name": self.name, "success": False, 
                   "cached": False, "execution_time_ms": execution_time,
                   "error": {"error_type": "UnexpectedError", "message": str(e), 
                            "tool_name": self.name}}
    
    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for LLM function calling."""
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
    """Agentic Tool - A tool powered by LLM calls (patient, socratic, hint agents)."""
    
    def __init__(self, tool_config: Dict[str, Any]):
        """Initialize agentic tool with prompt template and LLM config."""
        super().__init__(tool_config)
        self.prompt_template = tool_config.get("prompt_template", "")
        self.llm_config = tool_config.get("llm_config", {})
        
        if not self.prompt_template:
            logger.warning(f"AgenticTool {self.name} has no prompt_template")
    
    def _build_prompt(self, arguments: Dict[str, Any]) -> str:
        """Build LLM prompt from template and arguments."""
        try:
            return self.prompt_template.format(**arguments)
        except KeyError as e:
            raise ToolExecutionError(
                f"Missing argument for prompt: {e}",
                tool_name=self.name,
                details={"arguments": arguments}
            )
    
    @abstractmethod
    def _call_llm(self, prompt: str, **kwargs) -> str:
        """Call LLM with prompt. Must be implemented by subclasses."""
        pass
    
    def _execute(self, arguments: Dict[str, Any]) -> str:
        """Execute agentic tool by calling LLM."""
        prompt = self._build_prompt(arguments)
        try:
            return self._call_llm(prompt, **self.llm_config)
        except Exception as e:
            raise ToolLLMError(
                f"LLM call failed: {e}",
                tool_name=self.name,
                details={"prompt": prompt[:200]}
            )

