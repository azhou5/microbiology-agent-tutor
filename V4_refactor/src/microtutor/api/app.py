"""FastAPI application entry point for MicroTutor V4.

This is the main application file that sets up:
- FastAPI app with middleware
- Exception handlers
- API routes
- Documentation
"""

import logging
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

from microtutor.models.responses import ErrorResponse
from microtutor.api.routes import chat

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get the directory where this file is located
BASE_DIR = Path(__file__).resolve().parent

# Set up templates and static files
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
static_dir = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Lifespan context manager for startup and shutdown events.
    
    This replaces the old @app.on_event decorators with modern async context manager.
    """
    # Startup
    logger.info("🚀 Starting MicroTutor API v4.0.0...")
    logger.info("✅ MicroTutor API is ready!")
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down MicroTutor API...")


# Create FastAPI app
app = FastAPI(
    title="MicroTutor API",
    description="AI-powered microbiology tutoring system with interactive cases",
    version="4.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Mount static files
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger.info(f"✅ Static files mounted from: {static_dir}")
else:
    logger.warning(f"⚠️ Static directory not found: {static_dir}")


# Exception handlers
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
        ).dict()
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
        ).dict()
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
        ).dict()
    )


# Include routers
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])


# Root endpoints
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main frontend application."""
    return templates.TemplateResponse("index.html", {"request": request})


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
    return {
        "name": "MicroTutor API",
        "version": "4.0.0",
        "description": "AI-powered microbiology tutoring system",
        "endpoints": {
            "start_case": "POST /api/v1/start_case",
            "chat": "POST /api/v1/chat",
            "health": "GET /health",
            "docs": "GET /api/docs"
        }
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

