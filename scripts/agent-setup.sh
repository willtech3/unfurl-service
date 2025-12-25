#!/bin/bash
# AI Agent Environment Bootstrap Script
# Optimized for sandboxed development environments (Google Jules, OpenAI Codex, etc.)
#
# This script is designed to run in ephemeral Linux VMs with pre-installed Python.
# For local development with pyenv, use scripts/setup_environment.sh instead.

set -e

# Minimal output for cleaner agent logs
log() { echo "→ $1"; }
success() { echo "✓ $1"; }
error() { echo "✗ $1" >&2; exit 1; }

# Validate we're in the project root
if [[ ! -f "pyproject.toml" ]]; then
    error "Must run from project root (pyproject.toml not found)"
fi

log "Bootstrapping environment for AI agent..."

# --- 1. Detect/Install Package Manager ---
if command -v uv &>/dev/null; then
    PKG_MANAGER="uv"
    log "Using UV package manager"
elif command -v pip &>/dev/null; then
    PKG_MANAGER="pip"
    log "Using pip (UV not available)"
    
    # Try to install UV for better performance (optional, non-fatal)
    if curl -LsSf https://astral.sh/uv/install.sh 2>/dev/null | sh 2>/dev/null; then
        export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
        if command -v uv &>/dev/null; then
            PKG_MANAGER="uv"
            log "Installed UV successfully"
        fi
    fi
else
    error "No Python package manager found (need pip or uv)"
fi

# --- 2. Create/Activate Virtual Environment ---
VENV_DIR=".venv"
if [[ ! -d "$VENV_DIR" ]]; then
    log "Creating virtual environment..."
    if [[ "$PKG_MANAGER" == "uv" ]]; then
        uv venv
    else
        python -m venv "$VENV_DIR"
    fi
fi

# Activate venv
source "$VENV_DIR/bin/activate"
log "Activated virtual environment"

# --- 3. Install Dependencies ---
log "Installing dependencies..."
if [[ "$PKG_MANAGER" == "uv" ]]; then
    uv pip install -e ".[dev]"
else
    pip install -e ".[dev]"
fi

# --- 4. Install Playwright System Dependencies + Browser ---
# Playwright requires system dependencies on Linux
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    log "Installing Playwright system dependencies..."
    # playwright install-deps installs system packages (requires sudo on some systems)
    python -m playwright install-deps chromium 2>/dev/null || true
fi

log "Installing Playwright Chromium browser..."
python -m playwright install chromium

# --- 5. Validate Installation ---
log "Validating installation..."
python -c "
import sys
failed = []
for pkg in ['boto3', 'aws_lambda_powertools', 'slack_sdk', 'requests', 'bs4', 'playwright']:
    try:
        __import__(pkg)
    except ImportError:
        failed.append(pkg)

if failed:
    print(f'Missing packages: {failed}')
    sys.exit(1)
print('All core packages available')
"

# Verify Playwright browser
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); p.chromium.executable_path; p.stop()" 2>/dev/null \
    && success "Playwright Chromium ready" \
    || log "Playwright browser check skipped (may need manual install)"

success "Environment ready for development"

# --- 6. Print Quick Reference ---
echo ""
echo "Quick Reference:"
echo "  Run tests:    uv run pytest -v"
echo "  Format:       uv run black ."
echo "  Lint:         uv run flake8 ."
echo "  Type check:   uv run mypy . --strict"
