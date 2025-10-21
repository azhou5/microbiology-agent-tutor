"""Factory for creating TutorService instances with proper dependency injection."""

import os
import logging
from typing import Optional, List
from microtutor.services.tutor_service_v2 import TutorService, ServiceConfig
from microtutor.services.feedback_adapter import FeedbackClientAdapter
from microtutor.tools import get_tool_engine
from microtutor.core.config_helper import config

logger = logging.getLogger(__name__)

# Lazy loading: Don't import feedback at module level to avoid early import issues
# We'll import it inside the function when actually needed
FEEDBACK_AVAILABLE = None  # Will be determined lazily

def _lazy_import_feedback():
    """Lazy import of feedback module to avoid early import issues on Render.

    If the first import attempt fails with a ModuleNotFoundError, we log the
    current sys.path, attempt to add the expected `src` path, and retry once.
    """
    global FEEDBACK_AVAILABLE

    if FEEDBACK_AVAILABLE is not None:
        return FEEDBACK_AVAILABLE

    import sys
    import traceback
    import os as _os

    def _try_import() -> bool:
        try:
            from microtutor.feedback import create_feedback_retriever  # noqa: F401
            return True
        except ModuleNotFoundError as e:
            logger.error(f"[FEEDBACK_INIT] ModuleNotFoundError: {e}")
            logger.error(f"[FEEDBACK_INIT] sys.path: {sys.path}")
            return False
        except ImportError as e:  # Other import errors (deps inside feedback)
            logger.error(f"[FEEDBACK_INIT] ImportError during feedback import: {e}")
            logger.error(f"[FEEDBACK_INIT] Traceback: {traceback.format_exc()}")
            # Even if inner deps fail, the feedback package provides fallbacks; treat as available
            return True

    if _try_import():
        FEEDBACK_AVAILABLE = True
        logger.info("[FEEDBACK_INIT] Feedback module imported successfully (lazy)")
        return True

    # Attempt one-time path fix then retry
    guessed_src = _os.getenv("PYTHONPATH") or _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", "..", "..", "src"))
    if guessed_src and guessed_src not in sys.path:
        sys.path.insert(0, guessed_src)
        logger.warning(f"[FEEDBACK_INIT] Added to sys.path and retrying: {guessed_src}")

    if _try_import():
        FEEDBACK_AVAILABLE = True
        logger.info("[FEEDBACK_INIT] Feedback module imported successfully after path fix")
        return True

    FEEDBACK_AVAILABLE = False
    logger.error("[FEEDBACK_INIT] Feedback module still unavailable after retry")
    logger.error(f"[FEEDBACK_INIT] Final sys.path: {sys.path}")
    return False


def create_tutor_service(
    model_name: Optional[str] = None,
    enable_feedback: bool = True,
    feedback_dir: Optional[str] = None,
    direct_routing_agents: Optional[List[str]] = None,
    project_root: Optional[str] = None,
) -> TutorService:
    """
    Create a TutorService instance with proper dependency injection.
    
    Args:
        model_name: Model name to use (defaults to config.API_MODEL_NAME)
        enable_feedback: Whether to enable feedback retrieval
        feedback_dir: Directory containing feedback data
        direct_routing_agents: List of agents that should receive direct routing
        project_root: Root directory of the project (for finding HPI JSON)
    
    Returns:
        Configured TutorService instance
    """
    # Get logger for this function
    func_logger = logging.getLogger(__name__)
    # Create service configuration
    cfg = ServiceConfig(
        model_name=model_name or config.API_MODEL_NAME,
        enable_feedback=enable_feedback,
        direct_routing_agents=tuple(direct_routing_agents or []),
    )
    
    # Create tool engine
    tool_engine = get_tool_engine()
    
    # Create feedback client if enabled (lazy import)
    feedback_client = None
    if enable_feedback and _lazy_import_feedback():
        try:
            feedback_path = feedback_dir or config.get('FEEDBACK_DIR', 'data/feedback')
            func_logger.info(f"[FEEDBACK_INIT] Initializing feedback client with path: {feedback_path}")
            
            # Check if feedback files exist
            feedback_index_path = os.path.join(feedback_path, 'feedback_index.faiss')
            if not os.path.exists(feedback_index_path):
                func_logger.warning(f"[FEEDBACK_INIT] Feedback index not found at {feedback_index_path}")
                func_logger.warning(f"[FEEDBACK_INIT] Attempting to regenerate feedback index...")
                try:
                    # Try to regenerate the feedback index
                    from microtutor.feedback.feedback_processor import FeedbackProcessor
                    processor = FeedbackProcessor()
                    processor.create_faiss_index(feedback_path)
                    func_logger.info(f"[FEEDBACK_INIT] Successfully regenerated feedback index")
                except Exception as regen_error:
                    func_logger.error(f"[FEEDBACK_INIT] Failed to regenerate feedback index: {regen_error}")
                    raise Exception(f"Feedback index not found and could not be regenerated: {regen_error}")
            
            from microtutor.feedback import create_feedback_retriever
            feedback_retriever = create_feedback_retriever(feedback_path)
            feedback_client = FeedbackClientAdapter(feedback_retriever)
            func_logger.info(f"[FEEDBACK_INIT] Feedback client initialized successfully")
        except Exception as e:
            func_logger.error(f"[FEEDBACK_INIT] Failed to initialize feedback retriever: {e}")
            import traceback
            func_logger.error(f"[FEEDBACK_INIT] Traceback: {traceback.format_exc()}")
            # Continue without feedback
    elif enable_feedback and not _lazy_import_feedback():
        func_logger.warning("[FEEDBACK_INIT] Feedback requested but feedback module not available (missing dependencies)")
    else:
        func_logger.info(f"[FEEDBACK_INIT] Feedback disabled: enable_feedback={enable_feedback}, FEEDBACK_AVAILABLE={FEEDBACK_AVAILABLE}")
    
    # Log final feedback status
    if feedback_client:
        func_logger.info(f"[FEEDBACK_INIT] ✅ Feedback system initialized successfully")
    else:
        func_logger.warning(f"[FEEDBACK_INIT] ❌ Feedback system not available - feedback will be disabled")
    
    # Set project root to V4_refactor directory if not specified
    if project_root is None:
        # Go up from services/factory.py to V4_refactor root
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    
    return TutorService(
        cfg=cfg,
        tool_engine=tool_engine,
        feedback_client=feedback_client,
        project_root=project_root,
    )
