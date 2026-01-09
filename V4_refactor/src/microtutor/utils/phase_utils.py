"""
Phase management utilities for MicroTutor.

This module provides utilities for:
- Phase state mappings (display names, agents, tools)
- Phase transitions and validation
- Phase completion detection
"""

from typing import Optional, Tuple
from microtutor.schemas.domain.domain import TutorState

# -------- Phase Mappings --------

PHASE_DISPLAY_MAPPING = {
    "Information Gathering": TutorState.INFORMATION_GATHERING,
    "Differential Diagnosis": TutorState.DIFFERENTIAL_DIAGNOSIS,
    "Differential Diagnosis & Clinical Reasoning": TutorState.DIFFERENTIAL_DIAGNOSIS,
    "Tests & Management": TutorState.TESTS_MANAGEMENT,
    "Feedback": TutorState.FEEDBACK,
}

PHASE_AGENT_MAPPING = {
    TutorState.INFORMATION_GATHERING: "patient",
    TutorState.DIFFERENTIAL_DIAGNOSIS: "socratic",
    TutorState.TESTS_MANAGEMENT: "tests_management",
    TutorState.FEEDBACK: "feedback",
}

TOOL_TO_PHASE = {
    "patient": TutorState.INFORMATION_GATHERING,
    "socratic": TutorState.DIFFERENTIAL_DIAGNOSIS,
    "tests_management": TutorState.TESTS_MANAGEMENT,
    "feedback": TutorState.FEEDBACK,
}

# Standard phase order
PHASE_ORDER = [
    TutorState.INITIALIZING,
    TutorState.INFORMATION_GATHERING,
    TutorState.DIFFERENTIAL_DIAGNOSIS,
    TutorState.TESTS_MANAGEMENT,
    TutorState.FEEDBACK,
]

# Completion tokens for phase completion detection
# NOTE: User now controls phase transitions via UI buttons.
# Agents no longer emit completion signals automatically.
PHASE_COMPLETION_TOKENS = {
    # Empty - user controls when to move on
}


# -------- Phase Utilities --------

def determine_phase_from_tools(tools_used: list[str], current: TutorState) -> TutorState:
    """Determine new phase based on tools used.
    
    Args:
        tools_used: List of tool names that were called
        current: Current phase state
        
    Returns:
        New phase state (or current if no tools or unknown tool)
    """
    if not tools_used:
        return current
    
    proposed_phase = TOOL_TO_PHASE.get(tools_used[0], current)
    
    # Enforce forward-only flow for implicit transitions too
    if is_forward_transition(current, proposed_phase):
        return proposed_phase
    
    return current


def validate_phase_transition(phase_name: str) -> Tuple[bool, Optional[TutorState], Optional[str]]:
    """Validate a phase transition command.
    
    Args:
        phase_name: Phase name from user command (e.g., "Tests & Management")
        
    Returns:
        Tuple of (is_valid, new_state, error_message)
        - is_valid: True if phase name is valid
        - new_state: TutorState if valid, None otherwise
        - error_message: Error message if invalid, None otherwise
    """
    if not phase_name or not isinstance(phase_name, str):
        return False, None, "Phase name must be a non-empty string"
    
    pn = phase_name.strip()
    if pn not in PHASE_DISPLAY_MAPPING:
        available = ', '.join(PHASE_DISPLAY_MAPPING.keys())
        return False, None, f"Unknown phase '{pn}'. Available: {available}"
    
    return True, PHASE_DISPLAY_MAPPING[pn], None


def get_next_phase(current: TutorState) -> Optional[TutorState]:
    """Get the next phase in the standard sequence.
    
    Args:
        current: Current phase state
        
    Returns:
        Next phase state, or None if at the end
    """
    try:
        # Use PHASE_ORDER directly, filtering out INITIALIZING if current is not INITIALIZING
        # effectively PHASE_ORDER covers it
        if current not in PHASE_ORDER:
            return None
            
        i = PHASE_ORDER.index(current)
        return PHASE_ORDER[i + 1] if i + 1 < len(PHASE_ORDER) else None
    except ValueError:
        return None


def is_forward_transition(current: TutorState, target: TutorState) -> bool:
    """Check if the transition is forward or staying same (not backward).
    
    Args:
        current: Current phase state
        target: Target phase state
        
    Returns:
        True if target is same or later in sequence than current.
    """
    if current == target:
        return True
        
    try:
        curr_idx = PHASE_ORDER.index(current)
        targ_idx = PHASE_ORDER.index(target)
        return targ_idx > curr_idx
    except ValueError:
        return False


def get_completion_token(agent_name: str) -> Optional[str]:
    """Get completion token for an agent.
    
    Args:
        agent_name: Agent name (e.g., "tests_management")
        
    Returns:
        Completion token string if agent has one, None otherwise
    """
    return PHASE_COMPLETION_TOKENS.get(agent_name)


def is_phase_complete(content: str, agent_name: str) -> bool:
    """Check if phase completion token is present in content.
    
    Args:
        content: Response content to check
        agent_name: Agent name to get completion token for
        
    Returns:
        True if completion token found, False otherwise
    """
    token = get_completion_token(agent_name)
    return bool(token and token in content)
