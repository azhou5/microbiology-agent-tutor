"""Dependency injection for FastAPI.

This module provides dependencies that can be injected into route handlers,
following FastAPI's dependency injection pattern.
"""

from typing import Optional
import logging
import sys
import os

# Add parent directory to path for config import
config_path = os.path.join(os.path.dirname(__file__), '../../../')
sys.path.insert(0, config_path)

try:
    from config.config import config
except ImportError:
    # Fallback to V3 config
    v3_path = os.path.join(os.path.dirname(__file__), '../../../V3_reasoning_multiagent')
    sys.path.insert(0, v3_path)
    import config as v3_config
    config = v3_config

from microtutor.services.tutor_service_v2 import TutorService
from microtutor.services.factory import create_tutor_service
from microtutor.services.case_service import CaseService
from microtutor.services.feedback_service import FeedbackService
from microtutor.services.voice_service import VoiceService
from microtutor.services.background_service import get_background_service, BackgroundTaskService

logger = logging.getLogger(__name__)

# Service singletons (in production, consider using dependency-injector library)
_tutor_service: Optional[TutorService] = None
_case_service: Optional[CaseService] = None
_feedback_service: Optional[FeedbackService] = None
_voice_service: Optional[VoiceService] = None


def get_tutor_service() -> TutorService:
    """Get or create TutorService singleton (now using v2 with clean architecture).
    
    Returns:
        TutorService v2 instance with dependency injection
    """
    global _tutor_service
    if _tutor_service is None:
        _tutor_service = create_tutor_service(
            model_name=getattr(config, 'API_MODEL_NAME', 'o3-mini'),
            enable_feedback=True,
            feedback_dir='data/feedback',
            direct_routing_agents=["socratic", "patient"],  # Enable direct routing for these agents
        )
        logger.info("TutorService v2 singleton created with clean architecture")
    return _tutor_service


def get_case_service() -> CaseService:
    """Get or create CaseService singleton.
    
    Returns:
        CaseService instance
    """
    global _case_service
    if _case_service is None:
        _case_service = CaseService()
        logger.info("CaseService singleton created")
    return _case_service


def get_feedback_service() -> FeedbackService:
    """Get or create FeedbackService singleton.
    
    Returns:
        FeedbackService instance
    """
    global _feedback_service
    if _feedback_service is None:
        _feedback_service = FeedbackService()
        logger.info("FeedbackService singleton created")
    return _feedback_service


def get_voice_service() -> VoiceService:
    """Get or create VoiceService singleton.
    
    Returns:
        VoiceService instance configured from environment
    """
    global _voice_service
    if _voice_service is None:
        # Get OpenAI API key from config or environment
        api_key = getattr(config, 'OPENAI_API_KEY', None)
        if api_key is None:
            import os
            api_key = os.getenv('OPENAI_API_KEY')
        
        if api_key is None:
            logger.warning("No OpenAI API key found - voice service will not work")
            raise ValueError("OpenAI API key required for voice service")
        
        # Get voice configuration from config if available
        tutor_voice = getattr(config, 'VOICE_TUTOR', 'nova')
        patient_voice = getattr(config, 'VOICE_PATIENT', 'echo')
        tts_model = getattr(config, 'VOICE_TTS_MODEL', 'tts-1')
        
        _voice_service = VoiceService(
            api_key=api_key,
            tutor_voice=tutor_voice,  # type: ignore
            patient_voice=patient_voice,  # type: ignore
            tts_model=tts_model,  # type: ignore
        )
        logger.info(f"VoiceService singleton created - Tutor: {tutor_voice}, Patient: {patient_voice}")
    return _voice_service


def get_background_service_dependency() -> BackgroundTaskService:
    """Get background service for dependency injection."""
    return get_background_service()


# Database setup
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

_engine = None
_SessionLocal = None


def init_database():
    """Initialize database engine and session maker (matching V3's approach)."""
    global _engine, _SessionLocal
    
    if _engine is None:
        database_url = getattr(config, 'database_url', None)
        
        if database_url:
            try:
                logger.info(f"Initializing database connection...")
                # Add SSL parameter to the URL for Render PostgreSQL
                db_url_with_ssl = database_url + "?sslmode=require"
                _engine = create_engine(
                    db_url_with_ssl,
                    pool_pre_ping=True,  # Enable connection health checks
                    pool_recycle=3600,   # Recycle connections after 1 hour
                )
                _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
                
                # Test the connection
                from sqlalchemy import text
                with _engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                
                # Create tables if they don't exist
                from microtutor.models.database import Base
                logger.info("Creating database tables...")
                Base.metadata.create_all(bind=_engine)
                
                # Verify tables were created by checking if they exist
                with _engine.connect() as conn:
                    result = conn.execute(text("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name IN ('cases', 'conversation_logs', 'feedback', 'cost_logs')
                    """))
                    tables = [row[0] for row in result.fetchall()]
                    logger.info(f"✅ Database tables created: {tables}")
                
                logger.info("✅ Successfully connected to database and created/verified tables")
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                import traceback
                logger.error(f"Database initialization error: {traceback.format_exc()}")
                logger.warning("⚠️  Falling back to file logging - database will not be used")
                _engine = None
                _SessionLocal = None
        else:
            logger.warning("No database URL configured - using file logging only")


def get_db() -> Session:
    """Get database session.
    
    Yields:
        Database session (or None if not configured)
    """
    if _SessionLocal is None:
        init_database()
    
    if _SessionLocal is None:
        # Database not configured
        yield None
        return
    
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()

