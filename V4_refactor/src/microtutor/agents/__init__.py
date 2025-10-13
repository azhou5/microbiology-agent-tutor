"""
Agents module for MicroTutor.

This module contains all the agent implementations that simulate different
aspects of the tutoring experience:
- Patient simulation (patient.py)
- Socratic dialogue (socratic.py)
- Hint generation (hint.py)
- Case management (case.py, case_generator_rag.py)
"""

from microtutor.agents.patient import run_patient, get_patient_system_prompt
from microtutor.agents.socratic import run_socratic, get_socratic_system_prompt
from microtutor.agents.hint import run_hint, get_hint_system_prompt
from microtutor.agents.case import get_case

__all__ = [
    "run_patient",
    "get_patient_system_prompt",
    "run_socratic",
    "get_socratic_system_prompt",
    "run_hint",
    "get_hint_system_prompt",
    "get_case",
]

