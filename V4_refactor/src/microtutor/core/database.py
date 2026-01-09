"""Database connection and session management."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
import logging
import sys
import os

from microtutor.core.config_helper import config

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None


def init_database():
    """Initialize database engine and session maker."""
    global _engine, _SessionLocal
    
    if _engine is not None:
        return

    database_url = getattr(config, 'database_url', None)
    
    if not database_url:
        logger.warning("No database URL configured - using file logging only")
        return

    try:
        logger.info("Initializing database connection...")
        
        # Add SSL parameter to the URL for Render PostgreSQL
        db_url_with_ssl = database_url
        if "postgresql" in db_url_with_ssl and "sslmode" not in db_url_with_ssl:
             db_url_with_ssl += "?sslmode=require"

        _engine = create_engine(
            db_url_with_ssl,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        
        # Test the connection
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        # Create tables if they don't exist
        from microtutor.models.database import Base
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=_engine)
        
        logger.info("✅ Successfully connected to database and created/verified tables")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        logger.warning("⚠️  Falling back to file logging - database will not be used")
        _engine = None
        _SessionLocal = None

def get_db():
    """Get database session as a generator.
    
    Yields:
        Database session (or None if not configured)
    """
    if _SessionLocal is None:
        init_database()
    
    if _SessionLocal is None:
        yield None
        return
    
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_engine():
    """Get the database engine."""
    if _engine is None:
        init_database()
    return _engine
