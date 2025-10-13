"""Startup script for MicroTutor V4 FastAPI application.

Run this script to start the FastAPI development server.
"""

import uvicorn
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Starting MicroTutor V4 (FastAPI + Pydantic)")
    print("=" * 60)
    print()
    print("📚 Interactive API Documentation:")
    print("   Swagger UI: http://localhost:5001/api/docs")
    print("   ReDoc:      http://localhost:5001/api/redoc")
    print()
    print("🔧 API Endpoints:")
    print("   POST /api/v1/start_case - Start a new case")
    print("   POST /api/v1/chat       - Send a chat message")
    print("   GET  /health            - Health check")
    print()
    print("=" * 60)
    print()
    
    uvicorn.run(
        "microtutor.api.app:app",
        host="0.0.0.0",
        port=5001,
        reload=True,
        log_level="info"
    )

