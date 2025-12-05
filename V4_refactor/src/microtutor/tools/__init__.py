"""
MicroTutor Tools Module - ToolUniverse-style tool system.

This module provides the complete tool infrastructure following ToolUniverse
best practices.

Organization:
- schemas/tools/tool_models.py: BaseTool, AgenticTool (structural definitions)
- schemas/tools/tool_errors.py: ToolError classes
- tools/registry.py: Tool registry for discovery and loading
- tools/engine.py: Main execution engine
- prompts/: Agent prompts (patient, socratic, hint, tests_management, feedback)
- tools/{tool_name}/: Concrete tool implementations

Tools:
- patient: Simulates patient responses during case investigation
- socratic: Socratic questioning to guide student thinking
- hint: Provides progressive hints without giving answers
- tests_management: Guides test selection and management planning
- feedback: Provides comprehensive feedback on student performance
- post_case_assessment: Generates targeted MCQs after case completion

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
    
    # Method 4: Post-case assessment (after case completion)
    from microtutor.tools.post_case_assessment import run_post_case_assessment
    result = run_post_case_assessment(case, conversation_history, num_questions=5)
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
from microtutor.tools.tests_management import TestsManagementTool, run_tests_management
from microtutor.tools.feedback import FeedbackTool, run_feedback
from microtutor.tools.post_case_assessment import PostCaseAssessmentTool, run_post_case_assessment

# Legacy MCQ tool (kept for backward compatibility, but prefer post_case_assessment)
from microtutor.tools.mcq import MCQTool

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
    'TestsManagementTool',
    'FeedbackTool',
    'PostCaseAssessmentTool',
    'MCQTool',  # Legacy, prefer PostCaseAssessmentTool
    
    # Legacy/convenience functions
    'run_patient',
    'run_socratic',
    'run_hint',
    'run_tests_management',
    'run_feedback',
    'run_post_case_assessment',
]
