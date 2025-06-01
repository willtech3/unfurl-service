#!/bin/bash

# Setup script for Instagram unfurl service development environment
# Automates Python version setup, dependency installation, and environment configuration

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
REQUIRED_PYTHON_VERSION="3.12.3"
PROJECT_DIR="$(pwd)"
VENV_DIR=".venv"

print_header() {
    echo -e "\n${BLUE}$1${NC}"
    echo -e "${BLUE}$(printf '=%.0s' {1..60})${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${PURPLE}ℹ️  $1${NC}"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if pyenv is installed and install if needed
setup_pyenv() {
    if command_exists pyenv; then
        print_success "pyenv is already installed"
        return 0
    fi
    
    print_info "Installing pyenv..."
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command_exists brew; then
            brew install pyenv
        else
            print_error "Homebrew not found. Please install Homebrew first:"
            print_info "https://brew.sh/"
            return 1
        fi
    else
        # Linux
        curl https://pyenv.run | bash
        
        # Add to shell profile
        echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
        echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
        echo 'eval "$(pyenv init -)"' >> ~/.bashrc
        
        print_warning "Please restart your shell or run: source ~/.bashrc"
    fi
    
    print_success "pyenv installed"
}

# Install and set Python version
setup_python() {
    print_header "Setting up Python $REQUIRED_PYTHON_VERSION"
    
    # Setup pyenv if needed
    if ! command_exists pyenv; then
        setup_pyenv
    fi
    
    # Initialize pyenv for current session
    if [[ -d "$HOME/.pyenv" ]]; then
        export PYENV_ROOT="$HOME/.pyenv"
        export PATH="$PYENV_ROOT/bin:$PATH"
        eval "$(pyenv init -)"
    fi
    
    # Check if required Python version is installed
    if pyenv versions --bare | grep -q "^${REQUIRED_PYTHON_VERSION}$"; then
        print_success "Python $REQUIRED_PYTHON_VERSION already installed"
    else
        print_info "Installing Python $REQUIRED_PYTHON_VERSION..."
        pyenv install $REQUIRED_PYTHON_VERSION
        print_success "Python $REQUIRED_PYTHON_VERSION installed"
    fi
    
    # Set local Python version
    pyenv local $REQUIRED_PYTHON_VERSION
    print_success "Set Python $REQUIRED_PYTHON_VERSION for this project"
    
    # Verify Python version
    python_version=$(python --version 2>&1 | cut -d' ' -f2)
    if [[ "$python_version" == "$REQUIRED_PYTHON_VERSION" ]]; then
        print_success "Python version verified: $python_version"
    else
        print_warning "Expected $REQUIRED_PYTHON_VERSION, got $python_version"
        print_info "You may need to restart your shell and run this script again"
    fi
}

# Install UV package manager
setup_uv() {
    print_header "Setting up UV package manager"
    
    if command_exists uv; then
        print_success "UV is already installed: $(uv --version)"
        return 0
    fi
    
    print_info "Installing UV package manager..."
    
    if [[ "$OSTYPE" == "darwin"* ]] || [[ "$OSTYPE" == "linux-gnu"* ]]; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        
        # Add to PATH for current session
        export PATH="$HOME/.cargo/bin:$PATH"
        
        if command_exists uv; then
            print_success "UV installed: $(uv --version)"
        else
            print_error "UV installation failed"
            return 1
        fi
    else
        print_error "Unsupported operating system: $OSTYPE"
        print_info "Please install UV manually: https://github.com/astral-sh/uv"
        return 1
    fi
}

# Create virtual environment and install dependencies
setup_dependencies() {
    print_header "Setting up virtual environment and dependencies"
    
    # Remove existing virtual environment if it exists
    if [[ -d "$VENV_DIR" ]]; then
        print_info "Removing existing virtual environment..."
        rm -rf "$VENV_DIR"
    fi
    
    # Create new virtual environment with UV
    print_info "Creating virtual environment with UV..."
    uv venv --python python
    
    # Activate virtual environment
    print_info "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    
    # Install project dependencies
    print_info "Installing project dependencies..."
    uv pip install -e .
    
    # Install development dependencies
    print_info "Installing development dependencies..."
    uv pip install -e ".[dev]"
    
    # Install Playwright browsers
    print_info "Installing Playwright browsers..."
    python -m playwright install chromium
    
    print_success "Dependencies installed successfully"
}

# Set up environment variables
setup_environment_vars() {
    print_header "Setting up environment variables"
    
    # Create .env file if it doesn't exist
    if [[ ! -f ".env" ]]; then
        print_info "Creating .env file..."
        cat > .env << EOF
# AWS Configuration
AWS_REGION=us-east-2
CDK_DEFAULT_REGION=us-east-2

# Lambda Powertools Configuration
POWERTOOLS_METRICS_NAMESPACE=UnfurlService
POWERTOOLS_SERVICE_NAME=instagram-unfurl

# Development Configuration
NODE_ENV=development
DISABLE_METRICS=true

# Optional: Silence Node.js version warnings
JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1
EOF
        print_success "Created .env file"
    else
        print_info ".env file already exists"
    fi
    
    # Source environment variables
    if [[ -f ".env" ]]; then
        print_info "Loading environment variables..."
        set -a
        source .env
        set +a
        print_success "Environment variables loaded"
    fi
}

# Run tests to verify setup
verify_setup() {
    print_header "Verifying setup"
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Run a quick test
    print_info "Running quick dependency check..."
    python -c "
import sys
print(f'Python version: {sys.version}')

deps = ['boto3', 'aws_lambda_powertools', 'slack_sdk', 'requests', 'beautifulsoup4', 'playwright']
for dep in deps:
    try:
        __import__(dep)
        print(f'✅ {dep}')
    except ImportError:
        print(f'❌ {dep}')
        sys.exit(1)
"
    
    # Check Playwright browsers
    print_info "Checking Playwright browsers..."
    python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser_path = p.chromium.executable_path
    print(f'✅ Chromium browser: {browser_path}')
"
    
    print_success "Setup verification complete!"
}

# Main execution
main() {
    print_header "Instagram Unfurl Service - Environment Setup"
    
    # Check if we're in the right directory
    if [[ ! -f "pyproject.toml" ]] || [[ ! -f "Dockerfile" ]]; then
        print_error "Please run this script from the project root directory"
        exit 1
    fi
    
    # Run setup steps
    setup_python
    setup_uv
    setup_dependencies
    setup_environment_vars
    verify_setup
    
    print_header "Setup Complete!"
    print_success "Environment is ready for development"
    
    print_info "Next steps:"
    print_info "1. Activate the virtual environment: source .venv/bin/activate"
    print_info "2. Test Docker build: ./scripts/test_docker_build.sh"
    print_info "3. Run tests: uv run pytest"
    print_info "4. Validate environment: python scripts/validate_environment.py"
    print_info "5. Deploy: git add . && git commit -m 'Setup environment' && git push"
    
    if [[ -f ".env" ]]; then
        print_warning "Don't forget to configure your AWS credentials and Slack secrets"
        print_info "See DEPLOY.md for detailed deployment instructions"
    fi
}

# Run main function
main "$@"
