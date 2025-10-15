#!/bin/bash

# MicroTutor V4 Development Startup Script
# This script handles local development with auto-reload and debugging

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Print banner
print_banner() {
    echo "============================================================"
    echo "🚀 MicroTutor V4 - Development Mode"
    echo "============================================================"
    echo ""
}

# Check if .env file exists
check_env_file() {
    if [ -f "dot_env_microtutor.txt" ]; then
        log_success "Found environment file: dot_env_microtutor.txt"
    elif [ -f ".env" ]; then
        log_success "Found environment file: .env"
    else
        log_warning "No environment file found. Using system environment variables only."
        log_info "Consider creating dot_env_microtutor.txt or .env for local development"
    fi
}

# Check Python version
check_python() {
    local python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    local required_version="3.10"
    
    log_info "Checking Python version: $python_version"
    
    if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
        log_error "Python $required_version or higher is required. Found: $python_version"
        exit 1
    fi
    
    log_success "Python version check passed"
}

# Install dependencies
install_dependencies() {
    log_info "Installing Python dependencies..."
    
    # Upgrade pip
    python3 -m pip install --upgrade pip
    
    # Install requirements
    if [ -f "requirements.txt" ]; then
        python3 -m pip install -r requirements.txt
        log_success "Dependencies installed successfully"
    else
        log_error "requirements.txt not found"
        exit 1
    fi
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."
    
    mkdir -p logs
    mkdir -p data
    mkdir -p data/models
    mkdir -p data/models/faiss_indices
    
    log_success "Directories created"
}

# Display configuration
display_config() {
    log_info "Development Configuration:"
    echo "  Mode: Development (with auto-reload)"
    echo "  Debug: ${DEBUG:-true}"
    echo "  Port: ${PORT:-5001}"
    echo "  Environment File: $( [ -f "dot_env_microtutor.txt" ] && echo "dot_env_microtutor.txt" || echo "Not found" )"
    echo ""
    echo "📚 Available endpoints:"
    echo "  Swagger UI: http://localhost:${PORT:-5001}/api/docs"
    echo "  ReDoc:      http://localhost:${PORT:-5001}/api/redoc"
    echo "  Health:     http://localhost:${PORT:-5001}/health"
    echo ""
}

# Start the application
start_application() {
    local port="${PORT:-5001}"
    
    log_info "Starting MicroTutor V4 development server on port $port..."
    
    # Use development startup script
    if [ -f "run_v4.py" ]; then
        log_info "Using development startup script"
        exec python3 run_v4.py
    else
        log_warning "run_v4.py not found, using direct uvicorn"
        exec python3 -m uvicorn microtutor.api.app:app \
            --host 0.0.0.0 \
            --port "$port" \
            --reload \
            --log-level info
    fi
}

# Handle signals for graceful shutdown
setup_signal_handlers() {
    trap 'log_info "Received shutdown signal, stopping gracefully..."; exit 0' SIGTERM SIGINT
}

# Main execution
main() {
    print_banner
    
    # Setup signal handlers
    setup_signal_handlers
    
    # Pre-flight checks
    check_python
    check_env_file
    create_directories
    
    # Install dependencies (only if not already installed)
    if [ "$SKIP_INSTALL" != "true" ]; then
        install_dependencies
    else
        log_info "Skipping dependency installation (SKIP_INSTALL=true)"
    fi
    
    # Display configuration
    display_config
    
    # Start the application
    start_application
}

# Run main function
main "$@"
