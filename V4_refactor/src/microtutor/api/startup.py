"""
Application startup and shutdown handlers.

This module handles the initialization and cleanup of background services
when the FastAPI application starts and stops.

NOTE: Imports are done inside functions to avoid circular import issues.
The import chain: startup -> background -> factory -> TutorService -> ... -> startup
would cause circular imports if done at module level.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown.
    
    This function is called by FastAPI to handle application startup and shutdown.
    It ensures background services are properly initialized and cleaned up.
    
    Args:
        app: FastAPI application instance
        
    Yields:
        None (control is yielded to the application)
    """
    # Lazy imports to avoid circular import issues
    from microtutor.services.infrastructure.background import get_background_service, shutdown_background_service
    from microtutor.api.dependencies import init_database
    
    # Startup
    logger.info("🚀 Starting MicroTutor application...")
    
    try:
        # Initialize database
        init_database()
        logger.info("✅ Database initialized")
        
        # Initialize background service
        background_service = get_background_service()
        logger.info("✅ Background service initialized")
        
        # Initialize other services if needed
        # (Add other service initialization here)
        
        logger.info("✅ Application startup complete")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize application: {e}")
        raise
    
    # Yield control to the application
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down MicroTutor application...")
    
    try:
        # Shutdown background service
        shutdown_background_service()
        logger.info("✅ Background service shutdown complete")
        
        # Shutdown other services if needed
        # (Add other service cleanup here)
        
        logger.info("✅ Application shutdown complete")
        
    except Exception as e:
        logger.error(f"❌ Error during shutdown: {e}")


def get_lifespan():
    """Get the lifespan context manager for FastAPI.
    
    Returns:
        Lifespan context manager
    """
    return lifespan
