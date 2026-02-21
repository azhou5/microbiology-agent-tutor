#!/bin/bash



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
export PYTHONPATH=$PYTHONPATH:$(pwd)

python src_simplified/app.py
