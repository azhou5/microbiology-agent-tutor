"""
Tool Registry - ToolUniverse-style dynamic tool discovery and loading.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Type
from pathlib import Path

from microtutor.models.tool_models import BaseTool
from microtutor.models.tool_errors import ToolConfigError

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for tool classes, configs, and instances."""
    
    def __init__(self):
        self._tool_classes: Dict[str, Type[BaseTool]] = {}
        self._tool_configs: Dict[str, Dict[str, Any]] = {}
        self._tool_instances: Dict[str, BaseTool] = {}
    
    def register_tool_class(self, tool_type: str, tool_class: Type[BaseTool]) -> None:
        """Register a tool class by type."""
        if not issubclass(tool_class, BaseTool):
            raise ToolConfigError(f"Tool class must inherit from BaseTool: {tool_class}")
        self._tool_classes[tool_type] = tool_class
        logger.debug(f"Registered tool class: {tool_type}")
    
    def register_tool_config(self, tool_config: Dict[str, Any]) -> None:
        """Register a tool configuration."""
        if "name" not in tool_config:
            raise ToolConfigError("Tool config missing 'name'")
        
        tool_name = tool_config["name"]
        self._tool_configs[tool_name] = tool_config
        logger.debug(f"Registered tool config: {tool_name}")
    
    def load_tool_configs(self, config_dirs: List[Path]) -> int:
        """Load all JSON tool configs from directories."""
        loaded = 0
        for config_dir in config_dirs:
            if not config_dir.exists():
                logger.warning(f"Config directory not found: {config_dir}")
                continue
            
            for json_file in config_dir.glob("*.json"):
                try:
                    with open(json_file, 'r') as f:
                        config = json.load(f)
                        self.register_tool_config(config)
                        loaded += 1
                except Exception as e:
                    logger.error(f"Failed to load {json_file}: {e}")
        
        logger.info(f"Loaded {loaded} tool configs")
        return loaded
    
    def get_tool_config(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get tool configuration by name."""
        return self._tool_configs.get(tool_name)
    
    def get_tool_class(self, tool_type: str) -> Optional[Type[BaseTool]]:
        """Get tool class by type."""
        return self._tool_classes.get(tool_type)
    
    def get_tool_instance(self, tool_name: str) -> Optional[BaseTool]:
        """Get or create tool instance."""
        # Return cached instance
        if tool_name in self._tool_instances:
            return self._tool_instances[tool_name]
        
        # Create new instance
        config = self.get_tool_config(tool_name)
        if not config:
            logger.error(f"No config found for tool: {tool_name}")
            return None
        
        tool_type = config.get("type", "BaseTool")
        tool_class = self.get_tool_class(tool_type)
        
        # If type not found, try to infer from tool name
        if not tool_class:
            # Convert tool_name to class name: "mcq_tool" -> "MCQTool"
            # Handle special cases where tool name already ends with "_tool"
            if tool_name.endswith('_tool'):
                # Remove _tool suffix first
                base_name = tool_name[:-5]  # Remove "_tool"
            else:
                base_name = tool_name
            
            # Special case for common acronyms
            acronyms = {'mcq': 'MCQ', 'ddx': 'DDX', 'api': 'API'}
            if base_name.lower() in acronyms:
                tool_name_type = f"{acronyms[base_name.lower()]}Tool"
            else:
                # Convert to class name format (capitalize each word)
                tool_name_type = f"{base_name.replace('_', ' ').title().replace(' ', '')}Tool"
            
            tool_class = self.get_tool_class(tool_name_type)
            
            if tool_class:
                logger.debug(f"Using inferred tool class {tool_name_type} for {tool_name}")
            else:
                logger.warning(f"No class registered for type: {tool_type}, skipping {tool_name}")
                return None
        
        try:
            instance = tool_class(config)
            self._tool_instances[tool_name] = instance
            logger.info(f"Created tool instance: {tool_name}")
            return instance
        except Exception as e:
            logger.error(f"Failed to create tool {tool_name}: {e}")
            return None
    
    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self._tool_configs.keys())
    
    def clear(self) -> None:
        """Clear all registrations."""
        self._tool_classes.clear()
        self._tool_configs.clear()
        self._tool_instances.clear()


# Global registry (singleton pattern)
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get global tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def register_tool_class(tool_type: str, tool_class: Type[BaseTool]) -> None:
    """Register tool class globally."""
    get_registry().register_tool_class(tool_type, tool_class)


def get_tool_instance(tool_name: str) -> Optional[BaseTool]:
    """Get tool instance globally."""
    return get_registry().get_tool_instance(tool_name)


def register_tool_config(tool_config: Dict[str, Any]) -> None:
    """Register tool config globally."""
    get_registry().register_tool_config(tool_config)


def load_tools_from_json(json_path: str) -> None:
    """Load single tool from JSON file."""
    import json
    with open(json_path, 'r') as f:
        config = json.load(f)
    register_tool_config(config)


def load_tools_from_directory(directory: str) -> int:
    """Load all tools from directory."""
    return get_registry().load_tool_configs([Path(directory)])


def reset_registry() -> None:
    """Reset global registry (for testing)."""
    global _registry
    _registry = None
