"""Factory for creating TutorService instances with proper dependency injection."""

import os
import logging
from typing import Optional
from microtutor.services.tutor.service import TutorService, ServiceConfig
from microtutor.services.adapters.feedback_adapter import FeedbackClientAdapter
from microtutor.tools import get_tool_engine
from microtutor.core.config.config_helper import config

logger = logging.getLogger(__name__)


def create_tutor_service(
    model_name: Optional[str] = None,
    enable_feedback: bool = True,
    feedback_dir: Optional[str] = None,  # Deprecated - feedback now comes from database
    project_root: Optional[str] = None,
) -> TutorService:
    """
    Create a TutorService instance with proper dependency injection.
    
    Args:
        model_name: Model name to use (defaults to config.API_MODEL_NAME)
        enable_feedback: Whether to enable feedback retrieval
        feedback_dir: DEPRECATED - feedback is now auto-generated from database
        project_root: Root directory of the project (for finding HPI JSON)
    
    Returns:
        Configured TutorService instance
    """
    func_logger = logging.getLogger(__name__)
    
    # Create service configuration
    cfg = ServiceConfig(
        model_name=model_name or config.API_MODEL_NAME,
        enable_feedback=enable_feedback,
    )
    
    # Create tool engine
    tool_engine = get_tool_engine()
    
    # Create feedback client using the new auto-generated system
    feedback_client = None
    if enable_feedback:
        try:
            from microtutor.core.feedback import get_auto_feedback_retriever
            
            func_logger.info("[FEEDBACK_INIT] Initializing auto feedback retriever...")
            feedback_retriever = get_auto_feedback_retriever()
            
            if feedback_retriever:
                feedback_client = FeedbackClientAdapter(feedback_retriever)
                stats = feedback_retriever.get_index_stats()
                func_logger.info(f"[FEEDBACK_INIT] ✅ Feedback system initialized: {stats}")
            else:
                func_logger.warning("[FEEDBACK_INIT] Auto feedback retriever returned None")
                
        except Exception as e:
            func_logger.error(f"[FEEDBACK_INIT] Failed to initialize feedback retriever: {e}")
            import traceback
            func_logger.error(f"[FEEDBACK_INIT] Traceback: {traceback.format_exc()}")
    else:
        func_logger.info("[FEEDBACK_INIT] Feedback disabled by configuration")
    
    # Log final feedback status
    if feedback_client:
        func_logger.info("[FEEDBACK_INIT] ✅ Feedback system ready")
    else:
        func_logger.warning("[FEEDBACK_INIT] ❌ Feedback system not available")
    
    # Set project root to V4_refactor directory if not specified
    if project_root is None:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    
    return TutorService(
        cfg=cfg,
        tool_engine=tool_engine,
        feedback_client=feedback_client,
        project_root=project_root,
    )
