# Unfurl Service - Agent Guidelines

This document serves as the primary source of truth for all AI Agents (Claude, Cursor, Windsurf, etc.) working on this codebase.

## ⚡️ Quick Start for Agents

1.  **Package Manager**: We use **UV** for everything. Do NOT use pip directly.
2.  **Formatter**: Black.
3.  **Linter**: Flake8.
4.  **Type Checker**: Mypy (Strict).
5.  **Test Runner**: Pytest.

## 🛠 Project Environment

-   **Language**: Python 3.12.3
-   **Infrastructure**: AWS CDK
-   **Dependency Management**: UV

### 📦 Dependency Management (UV)

-   **Install Dependencies**: `uv pip install -e .` or `uv pip install -r requirements-docker.txt`
-   **Add Package**: `uv add <package>`
-   **Run Commands**: `uv run <command>` (e.g., `uv run pytest`)
-   **Lock Dependencies**: `uv pip freeze > requirements.lock`

## 🚨 Development Rules (Critical)

1.  **Explanation Requirement**: Every code change MUST be accompanied by a clear explanation (What/Why/How/Impact/Testing) in the PR description or commit message.
    -   *Example*: "Refactoring `scraper.py` to handle 404s (Why: reduce noise, How: try/except block, Impact: cleaner logs, Testing: unit tests added)."
2.  **Command Explanation**: Every terminal command executed must be explained.
    -   *Example*: "`uv run pytest` - Running unit tests to verify changes."
3.  **No Secrets**: NEVER commit API keys or secrets. Use `.env` or AWS Secrets Manager.
4.  **Feature Branches**: NEVER commit directly to `main`. Use `feature/<name>` branches.
5.  **Tests**: All changes must include tests. run `uv run pytest` before finishing.

## 🔍 Code Quality Standards

Before declaring a task complete, ensure these pass:

1.  **Format**: `uv run black .` (Line length: 88)
2.  **Lint**: `uv run flake8 .` (Max line length: 88, ignore E203, W503)
3.  **Types**: `uv run mypy . --strict`
4.  **Tests**: `uv run pytest` (Coverage > 80%)

### Configuration References

-   `pyproject.toml`: Configuration for Black, Mypy, Pytest.
-   `.flake8`: Configuration for Flake8.

## 📝 Commit Standards

-   **Type**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
-   **Format**: `type(scope): description`
-   **Example**: `fix(scraper): handle instagram redirect loops`

## 🏗 Architecture Context

-   **Event Router**: Lambda receiving Slack events (Fast, Sync).
-   **Unfurl Processor**: Container-based Lambda running Playwright (Slow/Async).
-   **Scrapers**: Modular strategy pattern (`PlaywrightScraper`, `HttpScraper`).
-   **Database**: DynamoDB for caching.

## 🧪 Testing Guidelines

-   **Unit Tests**: `tests/unit/` - Fast, mock external calls.
-   **Integration Tests**: `tests/integration/` - Can use local Docker/services.
-   **Usage**: `uv run pytest -v`
