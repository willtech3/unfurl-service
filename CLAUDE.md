# Claude Development Guidelines for Unfurl Service

**Primary Reference for Mechanical Rules**: See `AGENTS.md` for formatting, linting, testing, and UV commands.

## 🧠 Context Management

**For long conversations, review this document:**

- Before starting any new task
- When switching between components (scrapers/handlers/infrastructure)
- If you feel context drifting (~3000 tokens)
- Before any git operations or deployments

## 🚨 CRITICAL RULES - NEVER VIOLATE

1.  **🔐 NEVER commit secrets** - Use AWS Secrets Manager for all credentials
2.  **📁 NEVER use `git add .`** - Always specify files explicitly
3.  **🧪 ALWAYS run tests before committing** - `uv run pytest`
4.  **📝 ALWAYS explain changes** - What/Why/How/Impact/Testing format
5.  **🚀 ALWAYS use GitHub Actions for deployment** - Never deploy manually
6.  **🌿 ALWAYS use feature branches** - Never commit directly to main
7.  **🔄 ALWAYS create pull requests** - All changes go through PR review

## Project: Instagram Unfurl Service for Slack

### Overview

Serverless Instagram link unfurler that generates rich previews in Slack channels using advanced scraping strategies with intelligent fallbacks.

### Architecture

```yaml
Type: Container-based Lambda (ARM64)
Flow: API Gateway → SNS → Lambda processors
Storage: DynamoDB (caching) + S3 (static assets)
Observability: Logfire (logs/traces/metrics) + CloudWatch
Deployment: AWS CDK + GitHub Actions CI/CD
```

## 🏗️ Architecture Constraints (IMMUTABLE)

### Fixed Lambda Handler Locations

```text
src/event_router/handler.py          # API Gateway → SNS (< 3s response)
src/unfurl_processor/handler_async.py  # Container-based async processor
src/unfurl_processor/entrypoint.py   # Container initialization
```

**These paths are hardcoded in CDK - DO NOT MOVE**

### Component Dependencies (One Direction Only)

```text
Scrapers ← Handler ← Infrastructure ← CDK
(Core)     (Async)   (AWS/Slack)     (Deploy)
```

## 🎯 Current Focus Tracking

When working on a feature, maintain context:

```python
# CURRENT TASK: [Describe current work]
# STATUS: [Current progress]
# NEXT: [Next step]
# BLOCKERS: [Any issues]
```

## 🚦 Go/No-Go Checklist

Before implementing ANYTHING:

- [ ] Am I on a feature branch (not main)?
- [ ] Do I understand the scraping strategy?
- [ ] Have I checked existing tests?
- [ ] Have I explained what I'm about to do?
- [ ] Is Docker running (for container tests)?

## 📦 Scraping Strategy (Priority Order)

```yaml
1. Playwright Browser:
   - Path: src/unfurl_processor/scrapers/playwright_scraper.py
   - Stealth techniques, human-like behavior
   - Success rate: ~90%

2. Enhanced HTTP:
   - Path: src/unfurl_processor/scrapers/http_scraper.py
   - Session management, header rotation
   - Success rate: ~60%

3. Minimal Fallback:
   - Basic URL metadata
   - Always succeeds (graceful degradation)
```

## 🔍 Architecture Quick Reference

```text
src/
├── event_router/         # Receives Slack events (ZIP Lambda)
├── unfurl_processor/     # Container Lambda with scrapers
│   ├── scrapers/        # Modular scraping strategies
│   │   ├── manager.py   # Orchestration & fallback logic
│   │   ├── playwright_scraper.py  # Browser automation
│   │   ├── http_scraper.py        # Session-based HTTP
# oEmbed scraper removed per #30
│   ├── handler_async.py   # Async Lambda handler
│   └── entrypoint.py    # Container initialization
└── observability/        # Logfire integration
```

## 📝 Memory Aid

**U.N.F.U.R.L.**

- **U**V package manager activated
- **N**ever commit to main directly
- **F**ormat with black always
- **U**nit tests must pass
- **R**eview PR before merge
- **L**ogfire for observability

## Code Change Protocol

Every modification MUST include:

1.  **What**: Exact changes made
2.  **Why**: Business/technical reasoning
3.  **How**: Implementation approach
4.  **Impact**: Performance/security/UX effects
5.  **Testing**: Validation performed

---

*Remember: This document contains essential rules for the Unfurl Service. Always follow the CRITICAL RULES and use feature branches for all development work.*
