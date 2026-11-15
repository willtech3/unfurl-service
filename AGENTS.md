# Unfurl Service - Agent Guidelines

Reference for AI agents (Claude, Cursor, etc.) working on this codebase.

## Quick Start

- **Package Manager**: uv (not pip directly)
- **Formatter**: Black (line length 88)
- **Linter**: Flake8
- **Type Checker**: mypy (lenient config - see pyproject.toml)
- **Test Runner**: pytest

## Environment Setup

For sandboxed environments (Jules, Codex, etc.):

```bash
bash scripts/agent-setup.sh
```

For local development with pyenv:

```bash
./scripts/setup_environment.sh
```

## Common Commands

```bash
# Install dependencies
uv pip install -e ".[dev,cdk]"

# Run tests
uv run pytest

# Format code
uv run black src/ tests/

# Lint
uv run flake8 src/ tests/

# Type check
uv run mypy src/
```

## Development Rules

1. **Explain changes**: Every code change needs What/Why/How/Impact/Testing in commit or PR
2. **No secrets**: Use `.env` locally or AWS Secrets Manager in production
3. **Feature branches**: Never commit directly to `main`
4. **Tests required**: Run `uv run pytest` before finishing

## Code Quality

Before completing a task:

```bash
uv run black .          # Format
uv run flake8 .         # Lint
uv run mypy src/        # Type check (lenient)
uv run pytest           # Tests
```

Configuration in `pyproject.toml` and `.flake8`.

## Commit Format

```
type(scope): description
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Example: `fix(scraper): handle instagram redirect loops`

## Architecture

- **Event Router** (`src/event_router/`): ZIP Lambda receiving Slack events
- **Unfurl Processor** (`src/unfurl_processor/`): Container Lambda with Playwright
- **Scrapers** (`src/unfurl_processor/scrapers/`): PlaywrightScraper, HttpScraper
- **Cache**: DynamoDB

## Testing

Tests are in `tests/` directory:

```bash
uv run pytest -v
uv run pytest --cov=src  # With coverage
```

CDK stack tests (`tests/test_infrastructure_assets.py`) are skipped unless `RUN_CDK_TESTS=true`, and CI skips them too. Run `RUN_CDK_TESTS=true uv run pytest` after touching `cdk/`.

## Deploy Pipeline

- PR CI runs lint and tests only. Merging to `main` deploys to production (`UnfurlService-us-east-2`) via `.github/workflows/deploy.yml`, so check that run after merging.
- The `aws-cdk` CLI version (`cdk/package.json` and its lockfile) and the `aws-cdk-lib` cap (`pyproject.toml` `[cdk]` extra) move together. PR CI never synthesizes the stack, so a lib that emits a newer cloud-assembly schema than the CLI reads only fails on main, with "Cloud assembly schema version mismatch".
