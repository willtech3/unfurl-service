#!/bin/bash

# Test Docker build and functionality for Instagram unfurl service
# This script validates the container build and basic functionality

set -euo pipefail

echo "🚀 Testing Instagram Unfurl Service Docker Build"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="unfurl-service-test"
CONTAINER_NAME="unfurl-test-container"
PLATFORM="linux/arm64"

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}🧹 Cleaning up...${NC}"
    docker rm -f $CONTAINER_NAME 2>/dev/null || true
    docker rmi $IMAGE_NAME 2>/dev/null || true
}

# Set up cleanup on exit
trap cleanup EXIT

echo -e "${BLUE}📋 Step 1: Validating prerequisites...${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker and try again.${NC}"
    exit 1
fi

# Check if required files exist
required_files=(
    "Dockerfile"
    "requirements-docker.txt"
    "src/unfurl_processor/handler_async.py"
    "src/unfurl_processor/entrypoint.py"
    "src/unfurl_processor/scrapers/manager.py"
)

for file in "${required_files[@]}"; do
    if [[ ! -f "$file" ]]; then
        echo -e "${RED}❌ Required file missing: $file${NC}"
        exit 1
    fi
done

echo -e "${GREEN}✅ Prerequisites validated${NC}"

echo -e "\n${BLUE}📦 Step 2: Building Docker image...${NC}"

# Build the Docker image
if docker buildx build --platform $PLATFORM -t $IMAGE_NAME . --load; then
    echo -e "${GREEN}✅ Docker build successful${NC}"
else
    echo -e "${RED}❌ Docker build failed${NC}"
    exit 1
fi

echo -e "\n${BLUE}🔍 Step 3: Inspecting image...${NC}"

# Get image info
IMAGE_SIZE=$(docker images $IMAGE_NAME --format "table {{.Size}}" | tail -1)
echo -e "📏 Image size: ${GREEN}$IMAGE_SIZE${NC}"

# Check image layers
echo -e "\n📋 Image layers:"
docker history $IMAGE_NAME --format "table {{.CreatedBy}}\t{{.Size}}" | head -10

echo -e "\n${BLUE}🧪 Step 4: Testing container startup...${NC}"

# Test container can start
if docker run --name $CONTAINER_NAME --platform $PLATFORM -d $IMAGE_NAME sleep 30; then
    echo -e "${GREEN}✅ Container started successfully${NC}"
else
    echo -e "${RED}❌ Container failed to start${NC}"
    exit 1
fi

echo -e "\n${BLUE}🔧 Step 5: Validating dependencies...${NC}"

# Check Python dependencies are installed
echo "📦 Checking core dependencies..."
docker exec $CONTAINER_NAME python -c "
import sys
dependencies = [
    'playwright',
    'playwright_stealth', 
    'requests',
    'beautifulsoup4',
    'boto3',
    'slack_sdk',
    'aws_lambda_powertools'
]

for dep in dependencies:
    try:
        __import__(dep)
        print(f'✅ {dep}')
    except ImportError as e:
        print(f'❌ {dep}: {e}')
        sys.exit(1)
"

# Check Playwright browsers
echo -e "\n🌐 Checking Playwright browsers..."
docker exec $CONTAINER_NAME python -c "
import os
from pathlib import Path

browsers_path = Path('/tmp/ms-playwright')
if browsers_path.exists():
    print(f'✅ Playwright browsers found at {browsers_path}')
    # List browser directories
    for browser_dir in browsers_path.iterdir():
        if browser_dir.is_dir():
            print(f'   📁 {browser_dir.name}')
else:
    print(f'❌ Playwright browsers not found at {browsers_path}')
    exit(1)
"

echo -e "\n${BLUE}🏃 Step 6: Testing import functionality...${NC}"

# Test that the handler can be imported
docker exec $CONTAINER_NAME python -c "
import sys
sys.path.insert(0, '/var/task/src')

try:
    from unfurl_processor.entrypoint import lambda_handler
    from unfurl_processor.scrapers.manager import ScraperManager
    from unfurl_processor.slack_formatter import SlackFormatter
    print('✅ All modules imported successfully')
    
    # Test scraper manager initialization
    manager = ScraperManager()
    print(f'✅ ScraperManager initialized with {len(manager.scrapers)} scrapers')
    
    # Test slack formatter
    formatter = SlackFormatter()
    print('✅ SlackFormatter initialized')
    
except Exception as e:
    print(f'❌ Import test failed: {e}')
    sys.exit(1)
"

echo -e "\n${BLUE}⚡ Step 7: Performance check...${NC}"

# Check memory usage
MEMORY_USAGE=$(docker stats $CONTAINER_NAME --no-stream --format "table {{.MemUsage}}" | tail -1)
echo -e "💾 Container memory usage: ${GREEN}$MEMORY_USAGE${NC}"

echo -e "\n${GREEN}🎉 All tests passed successfully!${NC}"
echo -e "\n${BLUE}📊 Summary:${NC}"
echo -e "   📦 Image: $IMAGE_NAME"
echo -e "   📏 Size: $IMAGE_SIZE"
echo -e "   💾 Memory: $MEMORY_USAGE"
echo -e "   🏗️  Platform: $PLATFORM"
echo -e "\n${GREEN}✅ Docker container is ready for deployment${NC}"

# Optional: Test with a sample event
echo -e "\n${YELLOW}💡 To test with sample data, run:${NC}"
echo -e "   docker run --rm $IMAGE_NAME python -c \"
import json
from unfurl_processor.entrypoint import lambda_handler

# Sample test event (replace with actual SNS event structure)
test_event = {
    'Records': [{
        'EventSource': 'aws:sns',
        'Sns': {
            'Message': json.dumps({
                'channel': 'C1234567890',
                'message_ts': '1234567890.123456',
                'links': [{'url': 'https://instagram.com/p/test123/', 'domain': 'instagram.com'}]
            })
        }
    }]
}

try:
    result = lambda_handler(test_event, type('Context', (), {'aws_request_id': 'test-id'})())
    print('Handler test:', result.get('statusCode', 'unknown'))
except Exception as e:
    print('Handler test failed:', str(e))
\""
