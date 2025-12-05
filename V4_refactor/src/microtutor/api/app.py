"""FastAPI application entry point for MicroTutor V4.

This is the main application file that sets up:
- FastAPI app with middleware
- Exception handlers
- API routes
- Documentation
"""

import logging

# Suppress warnings from third-party libraries
from microtutor.core.config.warning_suppression import setup_warning_suppression
setup_warning_suppression(verbose=False)
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from microtutor.schemas.api.responses import ErrorResponse
from microtutor.api.routes import chat, voice, mcq, assessment
from microtutor.api.routes.admin import analytics, monitoring, config
from microtutor.api.routes.data import database, faiss_management
from microtutor.api.startup import get_lifespan

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import guidelines router (optional)
try:
    from microtutor.api.routes import guidelines
    GUIDELINES_AVAILABLE = True
except ImportError:
    GUIDELINES_AVAILABLE = False
    logger.warning("Guidelines router not available (missing dependencies)")

# Get the directory where this file is located
BASE_DIR = Path(__file__).resolve().parent

# Set up templates and static files
# Jinja2Templates is a FastAPI class for rendering HTML templates
# It allows serving dynamic HTML pages with template variables
# The templates directory should contain .html files with Jinja2 syntax
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
static_dir = BASE_DIR / "static"


# Create FastAPI app with background service lifespan management
app = FastAPI(
    title="MicroTutor API",
    description="AI-powered microbiology tutoring system with interactive cases",
    version="4.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=get_lifespan()
)

# Add middleware
# Add CORS middleware to handle cross-origin requests
# This allows the frontend (running on a different port/domain) to communicate with the API
# - allow_origins=["*"] permits requests from any domain (should be restricted in production)
# - allow_credentials=True enables cookies and authentication headers in cross-origin requests
# - allow_methods=["*"] permits all HTTP methods (GET, POST, PUT, DELETE, etc.)
# - allow_headers=["*"] allows all request headers to be sent
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add GZip compression middleware to reduce response sizes
# Automatically compresses responses larger than 1000 bytes to improve performance
# Particularly useful for JSON responses and static files
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Mount static files
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger.info(f"✅ Static files mounted from: {static_dir}")
else:
    logger.warning(f"⚠️ Static directory not found: {static_dir}")


# Exception handlers
# Define custom exception handlers for different types of errors
# - RequestValidationError: handles Pydantic validation errors
# - ValueError: handles value errors (e.g., invalid input parameters)
# - Exception: handles all other unhandled exceptions
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with detailed messages."""
    logger.warning(f"Validation error on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="Invalid request data",
            error_code="VALIDATION_ERROR",
            details={"errors": exc.errors()}
        ).model_dump()
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError exceptions."""
    logger.error(f"ValueError on {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            error=str(exc),
            error_code="VALUE_ERROR"
        ).model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions."""
    logger.error(f"Unhandled exception on {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            error_code="INTERNAL_ERROR"
        ).model_dump()
    )


# Include routers
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(voice.router, prefix="/api/v1", tags=["voice"])
app.include_router(mcq.router, prefix="/api/v1", tags=["mcq"])
app.include_router(assessment.router, prefix="/api/v1", tags=["assessment"])

# Admin routes
app.include_router(monitoring.router, prefix="/api/v1", tags=["monitoring"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(config.router, prefix="/api/v1", tags=["config"])

# Data routes - try real database first, fallback to mock
try:
    from microtutor.api.dependencies import test_db_connection
    # Test if database is available using context manager (ensures proper cleanup)
    with test_db_connection() as db:
        if db is not None:
            app.include_router(database.router, prefix="/api/v1/db", tags=["database"])
            logger.info("✅ Real database routes enabled")
        else:
            logger.warning("⚠️  Database routes disabled (database not available)")
except Exception as e:
    logger.warning(f"⚠️  Database routes disabled (database error: {e})")

# Include FAISS management routes
app.include_router(faiss_management.router, prefix="/api/v1/faiss", tags=["faiss-management"])
logger.info("✅ FAISS management routes enabled")

# Include optional guidelines router
if GUIDELINES_AVAILABLE:
    app.include_router(guidelines.router, tags=["guidelines"])
    logger.info("✅ Guidelines API routes enabled")
else:
    logger.info("ℹ️  Guidelines API routes disabled (install dependencies to enable)")


# Root endpoints
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main frontend application."""
    return templates.TemplateResponse(request, "index.html")


@app.get("/api")
async def api_root():
    """API information endpoint."""
    return {
        "name": "MicroTutor API",
        "version": "4.0.0",
        "status": "operational",
        "docs": "/api/docs",
        "redoc": "/api/redoc"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "service": "microtutor",
        "version": "4.0.0"
    }


@app.get("/api/v1/info")
async def api_info():
    """API information endpoint."""
    endpoints_info = {
        "start_case": "POST /api/v1/start_case",
        "chat": "POST /api/v1/chat",
        "voice_transcribe": "POST /api/v1/voice/transcribe",
        "voice_synthesize": "POST /api/v1/voice/synthesize",
        "voice_chat": "POST /api/v1/voice/chat",
        "health": "GET /health",
        "docs": "GET /api/docs"
    }
    
    # Add guidelines endpoints if available
    if GUIDELINES_AVAILABLE:
        endpoints_info.update({
            "guidelines_search": "POST /api/v1/guidelines/search",
            "guidelines_organism": "GET /api/v1/guidelines/organism/{organism}",
            "guidelines_sources": "GET /api/v1/guidelines/sources",
            "guidelines_health": "GET /api/v1/guidelines/health"
        })
    
    return {
        "name": "MicroTutor API",
        "version": "4.0.0",
        "description": "AI-powered microbiology tutoring system",
        "features": {
            "tutoring": True,
            "voice": True,
            "guidelines": GUIDELINES_AVAILABLE
        },
        "endpoints": endpoints_info
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "microtutor.api.app:app",
        host="0.0.0.0",
        port=5001,
        reload=True,
        log_level="info"
    )

