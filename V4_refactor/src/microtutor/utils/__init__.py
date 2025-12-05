"""
Utility modules for the Microbiology Tutor application.
"""

# Import embedding utilities directly to avoid circular imports
try:
    from .embedding_utils import get_embedding, get_embeddings_batch, get_embedding_model_name, get_embedding_dimension
    __all__ = ["get_embedding", "get_embeddings_batch", "get_embedding_model_name", "get_embedding_dimension"]
except ImportError as e:
    # If there are import issues, we'll handle them gracefully
    print(f"Warning: Could not import embedding utilities: {e}")
    __all__ = []

# Import conversation utilities
from .conversation_utils import (
    filter_system_messages,
    prepare_llm_messages,
    normalize_organism_name,
    get_cached_first_pt_sentence,
    has_cached_case
)

# Import phase utilities
from .phase_utils import (
    PHASE_DISPLAY_MAPPING,
    PHASE_AGENT_MAPPING,
    TOOL_TO_PHASE,
    PHASE_COMPLETION_TOKENS,
    determine_phase_from_tools,
    validate_phase_transition,
    get_next_phase,
    get_completion_token,
    is_phase_complete,
)

# Import protocols
from .protocols import ToolEngine, FeedbackClient

__all__.extend([
    # Conversation utilities
    "filter_system_messages",
    "prepare_llm_messages",
    "normalize_organism_name",
    "get_cached_first_pt_sentence",
    "has_cached_case",
    # Phase utilities
    "PHASE_DISPLAY_MAPPING",
    "PHASE_AGENT_MAPPING",
    "TOOL_TO_PHASE",
    "PHASE_COMPLETION_TOKENS",
    "determine_phase_from_tools",
    "validate_phase_transition",
    "get_next_phase",
    "get_completion_token",
    "is_phase_complete",
    # Protocols
    "ToolEngine",
    "FeedbackClient",
])
