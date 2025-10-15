"""
MicroTutor Tools Module - ToolUniverse-style tool system.

This module provides the complete tool infrastructure following ToolUniverse
best practices.

Organization:
- models/tool_models.py: BaseTool, AgenticTool (structural definitions)
- models/tool_errors.py: ToolError classes
- tools/registry.py: Tool registry for discovery and loading
- tools/engine.py: Main execution engine
- tools/prompts.py: Centralized prompts for all tools
- tools/patient.py, socratic.py, hint.py: Concrete tool implementations

Usage Examples:
    # Method 1: Use the tool engine (ToolUniverse-style)
    from microtutor.tools import get_tool_engine
    
    engine = get_tool_engine()
    result = engine.execute_tool('patient', {
        'input_text': "How long have you had this?",
        'case': case_description
    })
    
    # Method 2: Direct tool access (like ToolUniverse.tools)
    result_text = engine.tools.patient(
        input_text="How long have you had this?",
        case=case_description
    )
    
    # Method 3: Legacy function wrappers (backward compatibility)
    from microtutor.tools.patient import run_patient
    response = run_patient("How long?", case_description)
"""

# Core exports
from microtutor.tools.engine import (
    MicroTutorToolEngine,
    get_tool_engine,
    execute_tool,
    list_tools,
    get_tool_schemas
)

from microtutor.tools.registry import (
    ToolRegistry,
    get_registry,
    register_tool_class,
    register_tool_config,
    load_tools_from_json,
    load_tools_from_directory,
    get_tool_instance
)

# Tool implementations (for direct import if needed)
from microtutor.tools.patient import PatientTool, run_patient
from microtutor.tools.socratic import SocraticTool, run_socratic  
from microtutor.tools.hint import HintTool, run_hint
from microtutor.tools.ddx_case_search import DDXCaseSearchTool, search_ddx_cases
from microtutor.tools.problem_representation import ProblemRepresentationTool, run_problem_representation
from microtutor.tools.tests_management import TestsManagementTool, run_tests_management
from microtutor.tools.feedback import FeedbackTool, run_feedback

# Prompts (for customization if needed)
from microtutor.tools import prompts

__all__ = [
    # Engine
    'MicroTutorToolEngine',
    'get_tool_engine',
    'execute_tool',
    'list_tools',
    'get_tool_schemas',
    
    # Registry
    'ToolRegistry',
    'get_registry',
    'register_tool_class',
    'register_tool_config',
    'load_tools_from_json',
    'load_tools_from_directory',
    'get_tool_instance',
    
    # Tools
    'PatientTool',
    'SocraticTool',
    'HintTool',
    'DDXCaseSearchTool',
    'ProblemRepresentationTool',
    'TestsManagementTool',
    'FeedbackTool',
    
    # Legacy functions
    'run_patient',
    'run_socratic',
    'run_hint',
    'search_ddx_cases',
    'run_problem_representation',
    'run_tests_management',
    'run_feedback',
    
    # Prompts module
    'prompts'
]

