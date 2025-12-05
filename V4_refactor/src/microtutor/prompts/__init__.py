"""
Prompts module for MicroTutor V4.

This module contains all prompts for the tutor and agent tools.

Agents:
- patient: Simulates patient responses
- socratic: Socratic questioning
- hint: Progressive hints
- tests_management: Test selection and management guidance
- feedback: Final feedback on performance
- post_case_assessment: Targeted MCQ generation after case
"""

# Tutor prompts
from microtutor.prompts.tutor_prompt import (
    get_system_message_template,
    get_system_message_template_native_function_calling,
    get_tool_schemas_for_function_calling,
    get_first_pt_sentence_generation_system_prompt,
    get_first_pt_sentence_generation_user_prompt,
)

# Agent prompts
from microtutor.prompts.patient_prompts import (
    get_patient_system_prompt,
)

from microtutor.prompts.socratic_prompts import (
    get_socratic_system_prompt,
)

from microtutor.prompts.hint_prompts import (
    get_hint_system_prompt,
)

from microtutor.prompts.tests_management_prompts import (
    get_tests_management_system_prompt,
)

from microtutor.prompts.final_feedback_agent_prompts import (
    get_feedback_system_prompt,
)

from microtutor.prompts.post_case_assessment_prompts import (
    get_post_case_assessment_system_prompt,
    get_weakness_analysis_prompt,
)

__all__ = [
    # Tutor prompts
    "get_system_message_template",
    "get_system_message_template_native_function_calling",
    "get_tool_schemas_for_function_calling",
    "get_first_pt_sentence_generation_system_prompt",
    "get_first_pt_sentence_generation_user_prompt",
    # Patient prompts
    "get_patient_system_prompt",
    # Socratic prompts
    "get_socratic_system_prompt",
    # Hint prompts
    "get_hint_system_prompt",
    # Tests management prompts
    "get_tests_management_system_prompt",
    # Feedback prompts
    "get_feedback_system_prompt",
    # Post-case assessment prompts
    "get_post_case_assessment_system_prompt",
    "get_weakness_analysis_prompt",
]
