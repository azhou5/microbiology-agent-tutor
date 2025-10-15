#!/bin/bash

# MicroTutor V4 Production Startup Script for Render
# This script handles production deployment with proper error handling and logging

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
    echo "🚀 MicroTutor V4 - Production Startup"
    echo "============================================================"
    echo ""
}

# Check if running on Render
is_render() {
    [ -n "$RENDER" ] && [ "$RENDER" = "true" ]
}

# Validate environment variables
validate_environment() {
    log_info "Validating environment configuration..."
    
    local missing_vars=()
    
    # Check LLM configuration
    if [ "$USE_AZURE_OPENAI" = "true" ]; then
        [ -z "$AZURE_OPENAI_API_KEY" ] && missing_vars+=("AZURE_OPENAI_API_KEY")
        [ -z "$AZURE_OPENAI_ENDPOINT" ] && missing_vars+=("AZURE_OPENAI_ENDPOINT")
        log_info "Using Azure OpenAI: $AZURE_OPENAI_O4_MINI_DEPLOYMENT"
    else
        [ -z "$OPENAI_API_KEY" ] && missing_vars+=("OPENAI_API_KEY")
        log_info "Using Personal OpenAI: $PERSONAL_OPENAI_MODEL"
    fi
    
    # Check database configuration
    if [ "$USE_GLOBAL_DB" = "true" ]; then
        [ -z "$GLOBAL_DATABASE_URL" ] && missing_vars+=("GLOBAL_DATABASE_URL")
        log_info "Using Global Database"
    else
        [ -z "$DB_HOST" ] && missing_vars+=("DB_HOST")
        [ -z "$DB_NAME" ] && missing_vars+=("DB_NAME")
        [ -z "$DB_USER" ] && missing_vars+=("DB_USER")
        log_info "Using Local Database: ${DB_HOST:-'not set'}:${DB_PORT:-'not set'}/${DB_NAME:-'not set'}"
    fi
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        log_error "Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        exit 1
    fi
    
    log_success "Environment validation passed"
}

# Setup logging
setup_logging() {
    local log_level="${LOG_LEVEL:-INFO}"
    log_info "Setting up logging with level: $log_level"
    
    # Create logs directory if it doesn't exist
    mkdir -p logs
    
    # Set Python logging level
    export PYTHONUNBUFFERED=1
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
    log_info "Configuration Summary:"
    echo "  Environment: $(is_render && echo "Render" || echo "Local")"
    echo "  Debug Mode: ${DEBUG:-false}"
    echo "  Log Level: ${LOG_LEVEL:-INFO}"
    echo "  LLM Provider: $( [ "$USE_AZURE_OPENAI" = "true" ] && echo "Azure OpenAI" || echo "Personal OpenAI" )"
    echo "  Database: $( [ "$USE_GLOBAL_DB" = "true" ] && echo "Global" || echo "Local" )"
    echo "  Port: ${PORT:-5001}"
    echo ""
}

# Start the application
start_application() {
    local port="${PORT:-5001}"
    
    log_info "Starting MicroTutor V4 application on port $port..."
    
    # Use production startup script
    if [ -f "run_production.py" ]; then
        log_info "Using production startup script"
        exec python3 run_production.py
    else
        log_warning "run_production.py not found, using direct uvicorn"
        exec python3 -m uvicorn microtutor.api.app:app \
            --host 0.0.0.0 \
            --port "$port" \
            --log-level info \
            --access-log
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
    validate_environment
    setup_logging
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
