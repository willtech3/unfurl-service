# Claude Development Guidelines

See `AGENTS.md` for commands and tooling. This document covers project-specific rules.

## Critical Rules

1. **Never commit secrets** - Use AWS Secrets Manager
2. **Never use `git add .`** - Always specify files explicitly
3. **Always run tests before committing** - `uv run pytest`
4. **Always use feature branches** - Never commit to main directly
5. **Always create pull requests** - No direct pushes to main

## Project Overview

Instagram link unfurler for Slack. Scrapes Instagram posts and generates rich previews.

**Architecture:**
- Container Lambda (ARM64) with Playwright
- API Gateway -> SNS -> Lambda
- DynamoDB for caching
- Logfire for observability

## Fixed Handler Paths

These are hardcoded in CDK - do not move:

```
src/event_router/handler.py          # API Gateway handler
src/unfurl_processor/handler_async.py  # SNS processor
src/unfurl_processor/entrypoint.py   # Container entrypoint
```

## Scraping Strategy

1. **Playwright** (`src/unfurl_processor/scrapers/playwright_scraper.py`): Browser automation with stealth
2. **HTTP** (`src/unfurl_processor/scrapers/http_scraper.py`): Session-based fallback

## Before Making Changes

- Am I on a feature branch?
- Have I read the relevant code?
- Have I checked existing tests?
- Is Docker running (for container tests)?

## Change Documentation

Every modification should note:
1. What: Changes made
2. Why: Reasoning
3. How: Approach
4. Impact: Effects
5. Testing: Validation done
