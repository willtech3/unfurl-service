.PHONY: help install install-dev test lint format clean deploy build-layer setup

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

setup:
	@echo "Installing uv..."
	@command -v uv >/dev/null 2>&1 || (echo "Installing uv..." && curl -LsSf https://astral.sh/uv/install.sh | sh)
	@echo "Creating virtual environment..."
	uv venv
	@echo "Virtual environment created. Run 'source .venv/bin/activate' to activate."

install:
	uv pip install -e .

install-dev:
	uv pip install -e ".[dev,cdk]"

test:
	pytest tests/ -v --cov=src --cov-report=term-missing

lint:
	black --check src/ tests/
	flake8 src/ tests/
	mypy src/
	bandit -r src/

format:
	black src/ tests/
	isort src/ tests/

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
