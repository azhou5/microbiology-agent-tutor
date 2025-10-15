"""Development startup script for MicroTutor V4 FastAPI application.

Run this script to start the FastAPI development server.
For production deployment, use run_production.py instead.
"""

import uvicorn
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def main():
    """Main entry point for development server."""
    print("=" * 60)
    print("🚀 Starting MicroTutor V4 (Development Mode)")
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
    print("💡 For production deployment:")
    print("   python run_production.py")
    print()
    print("=" * 60)
    print()
    
    # Check if .env file exists
    env_file = Path(__file__).parent / "dot_env_microtutor.txt"
    if env_file.exists():
        print(f"✅ Using environment file: {env_file}")
    else:
        print(f"⚠️  Environment file not found: {env_file}")
        print("   Using system environment variables only")
    
    uvicorn.run(
        "microtutor.api.app:app",
        host="0.0.0.0",
        port=5001,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()

