# Instagram Unfurl Service for Slack

A high-performance, container-based serverless service that automatically unfurls Instagram links posted in Slack channels. Features advanced bot evasion techniques using Playwright browser automation and intelligent fallback strategies.

## 🚀 Key Features

- **🤖 Advanced Bot Evasion**: Playwright browser automation with stealth techniques
- **🔄 Intelligent Fallback**: Multi-layered scraping strategies for maximum success
- **⚡ High Performance**: Container-based Lambda with ARM64 architecture
- **💰 Cost Optimized**: DynamoDB caching and efficient resource usage
- **🔒 Secure**: AWS Secrets Manager integration, no hardcoded credentials

## Architecture Overview

This service uses a modern serverless architecture with container-based Lambda for enhanced capabilities:

- **API Gateway** - Receives Slack events via webhooks
- **Container Lambda** - Processes Instagram URLs using advanced scraping techniques
- **Playwright Browser** - Headless browser automation for bot evasion
- **SNS** - Decouples event reception from processing for reliability  
- **DynamoDB** - Caches unfurled data to minimize scraping requests
- **Secrets Manager** - Securely stores Slack API credentials
- **ECR** - Container registry for Lambda deployment

## 🛠️ Scraping Strategy

The service uses a sophisticated multi-layer approach:

1. **Playwright Browser Automation** (Primary)
   - Headless Chromium with stealth settings
   - Human-like behavior simulation
   - Advanced bot detection evasion
   - ~90% success rate

2. **Enhanced HTTP Scraping** (Secondary)
   - Session-based requests with realistic headers
   - User agent rotation and proxy support
   - Brotli/zstandard decompression handling
   - ~60% success rate

3. **Minimal Fallback** (Last Resort)
   - Basic URL metadata extraction
   - Ensures graceful degradation

## Prerequisites

- Python 3.12+
- [UV Package Manager](https://github.com/astral-sh/uv) for dependency management
- Docker Desktop (for container builds)
- AWS CLI configured with appropriate credentials
- AWS CDK CLI (`npm install -g aws-cdk`)
- Slack App with event subscriptions enabled

## Project Structure

```text
unfurl-service/
├── cdk/                           # CDK infrastructure code
│   ├── app.py                    # CDK app entry point
│   └── stacks/                   # CDK stack definitions
├── src/                          # Lambda function source code
│   ├── event_router/            # Handles incoming Slack events (ZIP-based)
│   └── unfurl_processor/        # Container-based Instagram processor
│       ├── scrapers/           # Modular scraping system
│       │   ├── manager.py      # Orchestrates fallback strategies
│       │   ├── playwright_scraper.py  # Browser automation
│       │   └── http_scraper.py        # Enhanced HTTP scraping
│       ├── url_utils.py        # Consolidated URL handling utilities
│       ├── slack_formatter.py  # Rich Slack unfurl formatting
│       ├── handler_async.py    # Async container Lambda handler
│       └── entrypoint.py       # Container entrypoint (calls AsyncUnfurlHandler)
├── scripts/                     # Development and deployment scripts
│   ├── validate_environment.py # Environment validation
│   ├── test_docker_build.sh   # Local Docker testing
│   └── migrate_to_container.py # Migration assistance
├── tests/                       # Comprehensive test suite
├── Dockerfile                   # Multi-stage container build
├── requirements-docker.txt      # Container dependencies
├── .github/workflows/          # GitHub Actions CI/CD
├── pyproject.toml             # Project configuration
└── cdk.json                   # CDK configuration
```

## 🔧 Development Setup

1. **Environment Validation**:

   ```bash
   # Validate your development environment
   ./scripts/validate_environment.py
   ```

2. **Install Dependencies**:

   ```bash
   # Create virtual environment and install dependencies
   uv venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   uv pip install -e .
   
   # Install Playwright browsers
   python -m playwright install chromium
   ```

3. **Test Docker Build**:

   ```bash
   # Test the container build locally
   ./scripts/test_docker_build.sh
   ```

## 🚢 Deployment

For detailed deployment instructions, see [DEPLOY.md](DEPLOY.md).

### Quick Deploy via GitHub Actions

1. **Configure Secrets**: Set up required GitHub secrets
2. **Push to Main**: Deployment triggers automatically

   ```bash
   git add .
   git commit -m "Deploy container-based unfurl service"
   git push origin main
   ```

### Manual Deployment

```bash
# Deploy the infrastructure
cdk deploy --all

# Or deploy specific stacks
cdk deploy UnfurlServiceStack
```

## 🧪 Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Test specific components
uv run pytest tests/test_scrapers/ -v
```

## 📊 Performance & Monitoring

- **Cold Start**: ~3-5 seconds (container initialization)
- **Warm Start**: ~100-500ms (cached browser)
- **Memory Usage**: 512-1024MB (with Playwright)
- **Success Rate**: 95%+ (with fallback strategies)

### Observability (Logfire)

- Consolidated backend: Logfire for logs, spans/traces, and metrics.
- Cross-Lambda tracing via W3C context in SNS `MessageAttributes`.
- CloudWatch retains JSON-structured logs via Powertools Logger.

Environment variables (set in CDK):

- `LOGFIRE_SERVICE_NAME`: service identifier for Logfire traces/logs.
- `LOGFIRE_TOKEN`: ingestion token (provided via CDK context `logfire_token`).
- `LOG_LEVEL` (optional): controls stdlib root logger level (e.g., `INFO`, `DEBUG`).

Notes:

- API Gateway execution tracing/logging disabled to reduce noisy CloudWatch log groups.
- Lambda X-Ray disabled; Logfire is the source of truth for traces.
- Standard Python logging is bridged to Logfire; CloudWatch still receives logs via Lambda stdout.

## 🔐 Security

- Slack tokens stored in AWS Secrets Manager
- No hardcoded credentials in source code
- IAM roles with least-privilege access
- VPC isolation for sensitive workloads (optional)
- Bot detection evasion respects rate limits

## 🏗️ Architecture Decisions

- **Container Lambda**: Enables Playwright browser dependencies
- **ARM64 Architecture**: Better price/performance ratio
- **Modular Scrapers**: Maintainable fallback strategies
- **Async Processing**: Handles multiple URLs concurrently
- **Rich Media Support**: Video playback in Slack unfurls

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
<!-- Deployment trigger: 2025-06-08 23:59:45 UTC -->
