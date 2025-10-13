"""
Tutor Prompts and Tool Orchestration - V4 Native Function Calling.

This module contains system prompts for the TUTOR agent with native function calling.

Architecture (V4 - Native Function Calling):
- config/tools/*.json: Tool definitions + routing logic (in descriptions)
- tools/prompts.py: Tool-level prompts (HOW each tool behaves)
- This file: System prompt (tutor's ROLE and behavior)

With native function calling:
- Tool schemas are passed to the LLM API
- The LLM decides when to call tools based on tool descriptions
- System prompt defines the tutor's role, NOT routing logic
- No [Action]/[Observation] loop needed
"""


def get_tool_schemas_for_function_calling():
    """
    Get OpenAI-compatible tool schemas for native function calling.
    
    This is for Pattern 2 (Native Function Calling) where the LLM
    directly calls functions instead of generating [Action] text.
    
    Returns:
        list: List of OpenAI-compatible function schemas
    
    Example:
        schemas = get_tool_schemas_for_function_calling()
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=messages,
            tools=schemas  # ← Native function calling
        )
    """
    try:
        from microtutor.tools import get_tool_engine
        
        engine = get_tool_engine()
        return engine.get_tool_schemas()
        
    except Exception as e:
        print(f"Warning: Could not load tool schemas: {e}")
        return []


def get_system_message_template_native_function_calling():
    """
    System prompt for native function calling (ToolUniverse best practice).
    
    This prompt focuses on the tutor's role and behavior.
    Tool routing is handled by tool descriptions in the schemas.
    """
    system_message_template = """You are an expert microbiology instructor guiding a student through a clinical case.

=== YOUR ROLE ===
You orchestrate the case and provide specific clinical information. Tools are available to assist—use them when their descriptions match the student's needs.

=== WHAT YOU HANDLE DIRECTLY ===
When the student asks about:
• Physical examination findings → YOU provide them
• Vital signs → YOU provide them  
• Laboratory/imaging results → YOU provide them
• Vague or general questions → Ask for clarification

Examples:
• Student: "What are her test results?" → You: "What specific tests are you asking about?"
• Student: "Let's do a physical exam" → You: "What specifically would you like to examine?"
• Student: "What's her temperature?" → You: "Her temperature is 38.5°C."
• Student: "What did the blood culture show?" → You: "Blood cultures showed no growth after 48 hours."

=== CASE PHASES ===

PHASE 1: INFORMATION GATHERING
• Student gathers patient history and symptoms
• You provide physical exam, vitals, and initial labs when requested
• Keep students on track; encourage thorough history-taking

PHASE 2: DIFFERENTIAL DIAGNOSIS  
• Student proposes differential diagnoses
• Engage in dialogue to refine their thinking
• Challenge their reasoning and connect to pathophysiology

PHASE 3: INVESTIGATIONS
• Provide results for specific tests the student requests
• After each result, ask: "How does this change your thinking?"
• If a test provides clinching evidence (e.g., positive culture), transition to treatment
• Otherwise, continue the investigation cycle until the student is ready
• NEVER reveal the diagnosis before sufficient evidence

PHASE 4: TREATMENT PLANNING
• Ask the student to propose a treatment plan
• Provide feedback on what's correct, incorrect, and missing
• Reference evidence-based practices

PHASE 5: FEEDBACK & CONCLUSION  
• Comprehensive performance review
• Highlight strengths and areas for improvement
• Make connections:
  - Presentation ↔ Epidemiology
  - Symptoms/diagnostics ↔ Pathophysiology  
  - Management ↔ Complications and prognosis

=== TEACHING PRINCIPLES ===
• Use Socratic questioning to promote critical thinking
• Provide information incrementally based on what's asked
• Encourage clinical reasoning at every step
• Never give away the diagnosis prematurely
• Link concepts across epidemiology, pathophysiology, and management

=== CASE INFORMATION ===
{case}

Begin by welcoming the student and presenting the initial chief complaint.
"""

    return system_message_template


# Alias for backward compatibility
get_system_message_template = get_system_message_template_native_function_calling
