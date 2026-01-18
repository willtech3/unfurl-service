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
