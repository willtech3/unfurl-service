# Instagram Unfurl Service for Slack

Serverless service that unfurls Instagram links in Slack channels. Uses Playwright for browser-based scraping with HTTP fallback.

## Architecture

```
API Gateway -> Event Router Lambda (ZIP) -> SNS -> Unfurl Processor Lambda (Container)
                                                          |
                                                    DynamoDB (cache)
```

- **Event Router**: Receives Slack webhooks, publishes to SNS
- **Unfurl Processor**: Container Lambda with Playwright, scrapes Instagram, posts unfurls to Slack
- **DynamoDB**: Caches unfurled data (24h TTL)
- **Secrets Manager**: Stores Slack credentials

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Docker
- AWS CLI configured
- AWS CDK CLI (`npm install -g aws-cdk`)

## Project Structure

```
unfurl-service/
├── cdk/                        # CDK infrastructure
│   └── stacks/                 # Stack definitions
├── src/
│   ├── event_router/           # Slack event handler (ZIP Lambda)
│   │   └── handler.py
│   └── unfurl_processor/       # Instagram processor (Container Lambda)
│       ├── scrapers/           # Scraping strategies
│       │   ├── manager.py      # Orchestration
│       │   ├── playwright_scraper.py
│       │   └── http_scraper.py
│       ├── handler_async.py    # Main handler
│       ├── entrypoint.py       # Container entrypoint
│       ├── url_utils.py        # URL normalization
│       └── slack_formatter.py  # Unfurl formatting
├── tests/
├── scripts/
├── Dockerfile
└── pyproject.toml
```

## Development Setup

```bash
# Install dependencies
uv venv
source .venv/bin/activate
uv pip install -e ".[dev,cdk]"

# Install Playwright browsers (for local testing)
python -m playwright install chromium

# Run tests
uv run pytest

# Lint and format
uv run black src/ tests/
uv run flake8 src/ tests/
uv run mypy src/
```

See `Makefile` for common commands.

## Deployment

Deployment is automated via GitHub Actions on push to `main`. See [docs/deployment.md](docs/deployment.md) for manual deployment and Slack app setup.

## Observability

Uses Logfire for logs, traces, and metrics. CloudWatch receives logs via Lambda stdout. See [docs/LOGFIRE.md](docs/LOGFIRE.md).

## Scraping Strategy

1. **Playwright** (primary): Headless browser with stealth settings
2. **HTTP** (fallback): Session-based requests with header rotation

Both extract metadata from Instagram's HTML. No API credentials required.

## Documentation

- [Deployment Guide](docs/deployment.md) - AWS and Slack setup
- [Slack Configuration](docs/slack_configuration.md) - Slack app settings
- [Logfire Setup](docs/LOGFIRE.md) - Observability configuration
- [URL Normalization](docs/url-normalization.md) - URL handling details

## License

MIT - see [LICENSE](LICENSE)
