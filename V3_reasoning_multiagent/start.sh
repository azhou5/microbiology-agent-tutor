#!/bin/bash
# MicroTutor startup script for Render
# Runs validation before starting the application

echo "🎓 MicroTutor - Starting Up"
echo "================================"

# Make sure we're in the right directory
cd "$(dirname "$0")"

# Run the Python startup script
python3 start_app.py
