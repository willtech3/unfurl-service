#!/bin/bash

# Build Lambda layer for dependencies using uv
# This script creates a zip file with all Python dependencies for Lambda

set -e

echo "Building Lambda layer..."

# Clean up any existing build
rm -rf lambda_layers/deps
mkdir -p lambda_layers/deps/python

# Create a temporary requirements file with only production dependencies
echo "Generating production requirements..."
uv pip compile pyproject.toml -o lambda_layers/requirements-prod.txt

# Install dependencies
echo "Installing dependencies..."
pip install -r lambda_layers/requirements-prod.txt -t lambda_layers/deps/python/ --no-deps

# Remove unnecessary files to reduce size
echo "Cleaning up unnecessary files..."
find lambda_layers/deps -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find lambda_layers/deps -type f -name "*.pyc" -delete 2>/dev/null || true
find lambda_layers/deps -type f -name "*.pyo" -delete 2>/dev/null || true
find lambda_layers/deps -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find lambda_layers/deps -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find lambda_layers/deps -type d -name "test" -exec rm -rf {} + 2>/dev/null || true

# Create zip file
echo "Creating zip file..."
cd lambda_layers/deps
zip -r ../deps.zip . -x "*.pyc" -x "*__pycache__*" -x "*.dist-info/*"
cd ../..

# Clean up temporary files
rm -f lambda_layers/requirements-prod.txt

# Show final size
echo "Lambda layer built successfully!"
echo "Layer size: $(du -h lambda_layers/deps.zip | cut -f1)"
