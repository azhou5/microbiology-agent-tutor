"""Production startup script for MicroTutor V4 FastAPI application.

This script is optimized for production deployment on Render.com
with proper logging, error handling, and performance settings.
"""

import os
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def setup_logging() -> None:
    """Configure logging for production."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Reduce noise from some libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

def check_environment() -> None:
    """Validate required environment variables."""
    required_vars = []
    
    # Check LLM configuration
    use_azure = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"
    if use_azure:
        required_vars.extend([
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT"
        ])
    else:
        required_vars.append("OPENAI_API_KEY")
    
    # Check database configuration
    use_global_db = os.getenv("USE_GLOBAL_DB", "false").lower() == "true"
    if use_global_db:
        required_vars.append("GLOBAL_DATABASE_URL")
    else:
        required_vars.extend([
            "DB_HOST", "DB_NAME", "DB_USER"
        ])
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logging.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)

def main():
    """Main entry point for production deployment."""
    print("=" * 60)
    print("🚀 Starting MicroTutor V4 (Production Mode)")
    print("=" * 60)
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Check environment
    try:
        check_environment()
        logger.info("✅ Environment validation passed")
    except SystemExit:
        logger.error("❌ Environment validation failed")
        raise
    
    # Display configuration
    use_azure = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"
    llm_provider = "Azure OpenAI" if use_azure else "Personal OpenAI"
    use_global_db = os.getenv("USE_GLOBAL_DB", "false").lower() == "true"
    db_type = "Global Database" if use_global_db else "Local Database"
    
    print(f"🔧 Configuration:")
    print(f"   LLM Provider: {llm_provider}")
    print(f"   Database: {db_type}")
    print(f"   Debug Mode: {os.getenv('DEBUG', 'false')}")
    print(f"   Log Level: {os.getenv('LOG_LEVEL', 'INFO')}")
    print()
    
    # Import and run the application
    try:
        import uvicorn
        from microtutor.api.app import app
        
        # Get port from environment (Render sets this)
        port = int(os.getenv("PORT", "10000"))
        
        logger.info(f"Starting server on port {port}")
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="info",
            access_log=True,
            # Production optimizations
            workers=1,  # Render handles scaling
            loop="uvloop",  # Better performance
            http="httptools"  # Better performance
        )
        
    except ImportError as e:
        logger.error(f"Failed to import application: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
