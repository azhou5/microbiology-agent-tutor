"""
Tool Execution Engine - ToolUniverse-style tool orchestration.
"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from microtutor.tools.registry import get_registry, register_tool_class
from microtutor.models.tool_models import BaseTool

logger = logging.getLogger(__name__)


class MicroTutorToolEngine:
    """Main tool execution engine - loads, manages, and executes tools."""
    
    def __init__(self, auto_load: bool = True, tool_config_dir: Optional[str] = None):
        """Initialize engine and optionally auto-load tools."""
        self.registry = get_registry()
        
        if auto_load:
            self._register_tool_classes()
            self._load_default_configs(tool_config_dir)
    
    def _register_tool_classes(self) -> None:
        """Register concrete tool implementations."""
        try:
            from microtutor.tools.patient import PatientTool
            from microtutor.tools.socratic import SocraticTool
            from microtutor.tools.hint import HintTool
            from microtutor.tools.ddx_case_search import DDXCaseSearchTool
            from microtutor.tools.update_phase import UpdatePhaseTool
            
            register_tool_class("PatientTool", PatientTool)
            register_tool_class("SocraticTool", SocraticTool)
            register_tool_class("HintTool", HintTool)
            register_tool_class("DDXCaseSearchTool", DDXCaseSearchTool)
            register_tool_class("UpdatePhaseTool", UpdatePhaseTool)
            
            logger.info("Registered 5 tool classes")
        except ImportError as e:
            logger.warning(f"Could not import tool classes: {e}")
    
    def _load_default_configs(self, custom_dir: Optional[str] = None) -> None:
        """Load tool configs from default or custom directory."""
        if custom_dir:
            config_dirs = [Path(custom_dir)]
        else:
            # Default: config/tools/ relative to project root
            project_root = Path(__file__).parent.parent.parent.parent
            config_dirs = [project_root / "config" / "tools"]
        
        self.registry.load_tool_configs(config_dirs)
    
    def load_tools(self, config_dirs: Optional[List[Path]] = None) -> int:
        """Load additional tools from directories."""
        if not config_dirs:
            return 0
        return self.registry.load_tool_configs(config_dirs)
    
    def execute_tool(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        validate: bool = True,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a tool by name.
        
        Returns:
            Dict with: result, tool_name, success, cached, execution_time_ms, error (if failed)
        """
        tool = self.registry.get_tool_instance(tool_name)
        
        if not tool:
            return {
                "result": None,
                "tool_name": tool_name,
                "success": False,
                "cached": False,
                "execution_time_ms": 0,
                "error": {
                    "error_type": "ToolNotFoundError",
                    "message": f"Tool '{tool_name}' not found",
                    "tool_name": tool_name
                }
            }
        
        return tool.run(arguments, validate=validate, use_cache=use_cache)
    
    def list_tools(self) -> List[str]:
        """List all available tool names."""
        return self.registry.list_tools()
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get OpenAI-compatible schemas for all tools."""
        schemas = []
        for tool_name in self.list_tools():
            tool = self.registry.get_tool_instance(tool_name)
            if tool:
                schemas.append(tool.get_schema())
        return schemas
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Get tool instance directly."""
        return self.registry.get_tool_instance(tool_name)
    
    def __repr__(self) -> str:
        tools = self.list_tools()
        return f"MicroTutorToolEngine(tools={len(tools)}: {tools})"


# Global engine (singleton pattern)
_engine: Optional[MicroTutorToolEngine] = None


def get_tool_engine() -> MicroTutorToolEngine:
    """Get global tool engine (lazy initialization)."""
    global _engine
    if _engine is None:
        _engine = MicroTutorToolEngine()
    return _engine


def execute_tool(tool_name: str, arguments: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    """Execute tool globally."""
    return get_tool_engine().execute_tool(tool_name, arguments, **kwargs)


def list_tools() -> List[str]:
    """List all tools globally."""
    return get_tool_engine().list_tools()


def get_tool_schemas() -> List[Dict[str, Any]]:
    """Get tool schemas globally."""
    return get_tool_engine().get_tool_schemas()


def reset_engine() -> None:
    """Reset global engine (for testing)."""
    global _engine
    _engine = None
