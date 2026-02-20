#!/usr/bin/env python3
"""
MicroTutor V4 - Run Script
Simplified entry point for the application.
"""
import os
import sys
import uvicorn
from pathlib import Path

def load_env_file(filepath):
    """Load environment variables from a file."""
    path = Path(filepath)
    if not path.exists():
        return False
    
    print(f"📦 Loading environment from {filepath}")
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes if present
                value = value.strip('"\'')
                os.environ[key.strip()] = value
    return True

def main():
    # Set base directory
    base_dir = Path(__file__).parent.resolve()
    
    # Load environment
    env_file = base_dir / "dot_env_microtutor.txt"
    if not load_env_file(env_file):
        print("⚠️  Warning: dot_env_microtutor.txt not found")

    # Add src to python path
    src_path = base_dir / "src"
    sys.path.insert(0, str(src_path))
    os.environ["PYTHONPATH"] = f"{os.environ.get('PYTHONPATH', '')}:{src_path}"

    # Get port
    port = int(os.environ.get("PORT", 5001))

    print(f"🚀 Starting MicroTutor V4 on http://localhost:{port}")
    print(f"📚 API docs: http://localhost:{port}/api/docs")

    # Run uvicorn
    uvicorn.run(
        "microtutor.api.app:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()

