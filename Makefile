.PHONY: help install install-dev test lint format clean deploy build-layer setup ci

# Add uv to PATH if installed in user directory
export PATH := $(HOME)/.local/bin:$(PATH)

help:
	@echo "Available commands:"
	@echo "  make setup        - Install uv and create virtual environment"
	@echo "  make install      - Install production dependencies"
	@echo "  make install-dev  - Install development dependencies"
	@echo "  make test         - Run tests with pytest"
	@echo "  make lint         - Run linting"
	@echo "  make format       - Format code"
	@echo "  make clean        - Clean up generated files"
	@echo "  make build-layer  - Build Lambda layer"
	@echo "  make deploy       - Deploy to AWS"
	@echo "  make ci           - Run all quality gates"

setup:
	@echo "Installing uv (if missing)..."
	@command -v uv >/dev/null 2>&1 || (echo "Installing uv..." && curl -LsSf https://astral.sh/uv/install.sh | sh)
	@echo "Creating Python 3.12 virtual environment with uv..."
	uv venv --python=python3.12 .venv
	@echo "Virtual environment .venv ready (Python 3.12)."
	uv pip install -e ".[dev,cdk]"
	@echo "Development dependencies installed."
	@echo "Run 'source .venv/bin/activate' to activate or simply use 'uv run <cmd>'."

install:
	uv pip install -e .

install-dev:
	uv pip install -e ".[dev,cdk]"

test:
	uv run pytest -v --cov=src --cov-branch \
	  --cov-report=term-missing:skip-covered --cov-report=html --cov-report=xml

lint:
	uv run black --check src/ tests/
	uv run flake8 src/ tests/
	uv run mypy src/
	uv run bandit -r src/

format:
	uv run black src/ tests/
	uv run isort src/ tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ cdk.out/ lambda_layers/
	rm -f .coverage coverage.xml

build-layer:
	chmod +x scripts/build_lambda_layer.sh
	./scripts/build_lambda_layer.sh

deploy:
	@echo "Deploying to AWS..."
	cdk bootstrap
	cdk deploy --all --require-approval never

synth:
	cdk synth

diff:
	cdk diff

lock:
	uv pip compile pyproject.toml -o requirements.txt
	uv pip compile pyproject.toml --extra dev --extra cdk -o requirements-dev.txt

ci: format lint test
