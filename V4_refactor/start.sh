#!/bin/bash
# MicroTutor V4 - Start Script

set -e

# Load environment from dot_env_microtutor.txt if it exists
if [ -f "dot_env_microtutor.txt" ]; then
    echo "📦 Loading environment from dot_env_microtutor.txt"
    set -a
    source dot_env_microtutor.txt
    set +a
fi

# Set PYTHONPATH
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$(pwd)/src"

# Get port (default 5001)
PORT="${PORT:-5001}"

echo "🚀 Starting MicroTutor V4 on http://localhost:$PORT"
echo "📚 API docs: http://localhost:$PORT/api/docs"

# Start the server
python -m uvicorn microtutor.api.app:app --host 0.0.0.0 --port "$PORT" --reload
