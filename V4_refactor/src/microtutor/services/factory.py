"""Factory for creating TutorService instances with proper dependency injection."""

import os
from typing import Optional, List
from microtutor.services.tutor_service_v2 import TutorService, ServiceConfig
from microtutor.services.feedback_adapter import FeedbackClientAdapter
from microtutor.tools import get_tool_engine
from microtutor.core.config_helper import config

# Try to import feedback functions, provide fallback if not available
try:
    from microtutor.feedback import create_feedback_retriever
    FEEDBACK_AVAILABLE = True
    logger.info("[FEEDBACK_INIT] Feedback module imported successfully")
except ImportError as e:
    FEEDBACK_AVAILABLE = False
    logger.error(f"[FEEDBACK_INIT] Failed to import feedback module: {e}")
    import traceback
    logger.error(f"[FEEDBACK_INIT] Import traceback: {traceback.format_exc()}")
    def create_feedback_retriever(*args, **kwargs):
        return None


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
    # Create service configuration
    cfg = ServiceConfig(
        model_name=model_name or config.API_MODEL_NAME,
        enable_feedback=enable_feedback,
        direct_routing_agents=tuple(direct_routing_agents or []),
    )
    
    # Create tool engine
    tool_engine = get_tool_engine()
    
    # Create feedback client if enabled
    feedback_client = None
    if enable_feedback and FEEDBACK_AVAILABLE:
        try:
            feedback_path = feedback_dir or config.get('FEEDBACK_DIR', 'data/feedback')
            logger.info(f"[FEEDBACK_INIT] Initializing feedback client with path: {feedback_path}")
            
            # Check if feedback files exist
            import os
            feedback_index_path = os.path.join(feedback_path, 'feedback_index.faiss')
            if not os.path.exists(feedback_index_path):
                logger.warning(f"[FEEDBACK_INIT] Feedback index not found at {feedback_index_path}")
                logger.warning(f"[FEEDBACK_INIT] Attempting to regenerate feedback index...")
                try:
                    # Try to regenerate the feedback index
                    from microtutor.feedback.feedback_processor import FeedbackProcessor
                    processor = FeedbackProcessor()
                    processor.create_faiss_index(feedback_path)
                    logger.info(f"[FEEDBACK_INIT] Successfully regenerated feedback index")
                except Exception as regen_error:
                    logger.error(f"[FEEDBACK_INIT] Failed to regenerate feedback index: {regen_error}")
                    raise Exception(f"Feedback index not found and could not be regenerated: {regen_error}")
            
            feedback_retriever = create_feedback_retriever(feedback_path)
            feedback_client = FeedbackClientAdapter(feedback_retriever)
            logger.info(f"[FEEDBACK_INIT] Feedback client initialized successfully")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"[FEEDBACK_INIT] Failed to initialize feedback retriever: {e}")
            import traceback
            logger.error(f"[FEEDBACK_INIT] Traceback: {traceback.format_exc()}")
            # Continue without feedback
    elif enable_feedback and not FEEDBACK_AVAILABLE:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("[FEEDBACK_INIT] Feedback requested but feedback module not available (missing dependencies)")
    else:
        logger.info(f"[FEEDBACK_INIT] Feedback disabled: enable_feedback={enable_feedback}, FEEDBACK_AVAILABLE={FEEDBACK_AVAILABLE}")
    
    # Log final feedback status
    if feedback_client:
        logger.info(f"[FEEDBACK_INIT] ✅ Feedback system initialized successfully")
    else:
        logger.warning(f"[FEEDBACK_INIT] ❌ Feedback system not available - feedback will be disabled")
    
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
