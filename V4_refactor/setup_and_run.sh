#!/bin/bash

# MicroTutor V4 - Complete Setup and Run Script (HTTP)
# This script installs dependencies and runs the application with HTTP support
# Perfect for first-time users who want to get started quickly

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
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

log_step() {
    echo -e "${PURPLE}[STEP]${NC} $1"
}

# Print banner
print_banner() {
    echo "============================================================"
    echo "🚀 MicroTutor V4 - Complete Setup & Run (HTTP)"
    echo "============================================================"
    echo ""
    echo "This script will:"
    echo "  ✅ Check Python version (3.10+ required)"
    echo "  ✅ Install all dependencies from requirements.txt"
    echo "  ✅ Create necessary directories"
    echo "  ✅ Set up environment configuration"
    echo "  ✅ Start the application with HTTP support"
    echo ""
}

# Check Python version
check_python() {
    log_step "Checking Python version..."
    
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed or not in PATH"
        log_info "Please install Python 3.10 or higher:"
        log_info "  macOS: brew install python@3.10"
        log_info "  Ubuntu: sudo apt install python3.10"
        log_info "  Or download from: https://www.python.org/downloads/"
        exit 1
    fi
    
    local python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    local required_version="3.10"
    
    log_info "Found Python version: $python_version"
    
    if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
        log_error "Python $required_version or higher is required. Found: $python_version"
        log_info "Please upgrade Python:"
        log_info "  macOS: brew install python@3.10"
        log_info "  Ubuntu: sudo apt install python3.10"
        exit 1
    fi
    
    log_success "Python version check passed"
}

# Install dependencies
install_dependencies() {
    log_step "Installing Python dependencies..."
    
    # Upgrade pip first
    log_info "Upgrading pip..."
    python3 -m pip install --upgrade pip
    
    # Install requirements
    if [ -f "requirements.txt" ]; then
        log_info "Installing packages from requirements.txt..."
        python3 -m pip install -r requirements.txt
        log_success "Dependencies installed successfully"
    else
        log_error "requirements.txt not found in current directory"
        log_info "Make sure you're running this script from the V4_refactor directory"
        exit 1
    fi
}

# Create necessary directories
create_directories() {
    log_step "Creating necessary directories..."
    
    mkdir -p logs
    mkdir -p data
    mkdir -p data/models
    mkdir -p data/models/faiss_indices
    
    log_success "Directories created"
}

# Setup environment configuration
setup_environment() {
    log_step "Setting up environment configuration..."
    
    if [ -f "dot_env_microtutor.txt" ]; then
        log_success "Found existing environment file: dot_env_microtutor.txt"
        log_info "Using existing configuration"
    elif [ -f ".env" ]; then
        log_success "Found existing environment file: .env"
        log_info "Using existing configuration"
    else
        log_warning "No environment file found"
        log_info "Creating basic .env file from template..."
        
        if [ -f "env.example" ]; then
            cp env.example .env
            log_success "Created .env file from env.example"
            log_warning "⚠️  IMPORTANT: Please edit .env file with your actual API keys and configuration"
            log_info "   Required settings:"
            log_info "   - OPENAI_API_KEY or AZURE_OPENAI_API_KEY"
            log_info "   - Database configuration"
            log_info "   - Other settings as needed"
            echo ""
            log_info "Press Enter to continue with default settings, or Ctrl+C to edit .env first"
            read -r
        else
            log_error "No environment template found (env.example)"
            log_info "Please create a .env file with your configuration"
            exit 1
        fi
    fi
}

# Display configuration
display_config() {
    log_step "Configuration Summary:"
    echo "  Environment: Development with HTTP"
    echo "  Debug Mode: ${DEBUG:-true}"
    echo "  Port: ${PORT:-5001}"
    echo "  HTTPS: Disabled (HTTP only)"
    echo "  Environment File: $( [ -f "dot_env_microtutor.txt" ] && echo "dot_env_microtutor.txt" || echo ".env" )"
    echo ""
    echo "📚 Available endpoints after startup:"
    echo "  Localhost:  http://localhost:${PORT:-5001}"
    echo "  Network IP: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'your-ip'):${PORT:-5001}"
    echo "  Swagger UI: http://localhost:${PORT:-5001}/api/docs"
    echo "  ReDoc:      http://localhost:${PORT:-5001}/api/redoc"
    echo "  Health:     http://localhost:${PORT:-5001}/health"
    echo ""
    echo "🎤 Microphone Access:"
    echo "  ✅ Available on localhost/127.0.0.1"
    echo "  ❌ NOT available on network IP (use setup_and_run_https.sh for network access)"
    echo ""
}

# Start the application
start_application() {
    local port="${PORT:-5001}"
    
    log_step "Starting MicroTutor V4 with HTTP support..."
    echo ""
    
    # Use the development startup script
    if [ -f "run_v4.py" ]; then
        log_info "Using run_v4.py startup script"
        exec python3 run_v4.py
    else
        log_error "run_v4.py not found"
        log_info "Falling back to direct uvicorn..."
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
    
    # Pre-flight checks and setup
    check_python
    install_dependencies
    create_directories
    setup_environment
    
    # Display configuration
    display_config
    
    # Start the application
    start_application
}

# Run main function
main "$@"
