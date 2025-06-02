#!/usr/bin/env python3
"""
Environment validation script for Instagram unfurl service.

Validates local development environment, dependencies, and configuration
before deployment to ensure everything is properly set up.
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from typing import List, Tuple


# Color codes for output
class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    PURPLE = "\033[0;35m"
    NC = "\033[0m"  # No Color


def print_header(title: str) -> None:
    """Print a formatted header."""
    print(f"\n{Colors.BLUE}{'=' * 60}{Colors.NC}")
    print(f"{Colors.BLUE}{title.center(60)}{Colors.NC}")
    print(f"{Colors.BLUE}{'=' * 60}{Colors.NC}")


def print_success(message: str) -> None:
    """Print success message."""
    print(f"{Colors.GREEN}✅ {message}{Colors.NC}")


def print_warning(message: str) -> None:
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.NC}")


def print_error(message: str) -> None:
    """Print error message."""
    print(f"{Colors.RED}❌ {message}{Colors.NC}")


def print_info(message: str) -> None:
    """Print info message."""
    print(f"{Colors.PURPLE}ℹ️  {message}{Colors.NC}")


def run_command(cmd: List[str], capture_output: bool = True) -> Tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd, capture_output=capture_output, text=True, timeout=30
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except FileNotFoundError:
        return 1, "", f"Command not found: {cmd[0]}"


def check_python_version() -> bool:
    """Check Python version compatibility."""
    print("\n🐍 Checking Python version...")

    version = sys.version_info
    required_version = (3, 12)

    if version >= required_version:
        print_success(f"Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print_error(
            f"Python {version.major}.{version.minor}.{version.micro} - "
            f"Required: {required_version[0]}.{required_version[1]}+"
        )
        return False


def check_docker() -> bool:
    """Check Docker installation and status."""
    print("\n🐳 Checking Docker...")

    # Check if Docker is installed
    exit_code, stdout, stderr = run_command(["docker", "--version"])
    if exit_code != 0:
        print_error("Docker not installed or not in PATH")
        return False

    print_success(f"Docker installed: {stdout.strip()}")

    # Check if Docker is running
    exit_code, _, stderr = run_command(["docker", "info"])
    if exit_code != 0:
        print_error("Docker is not running")
        print_info("Start Docker Desktop or Docker daemon")
        return False

    print_success("Docker is running")

    # Check Docker Buildx
    exit_code, stdout, _ = run_command(["docker", "buildx", "version"])
    if exit_code == 0:
        print_success(f"Docker Buildx available: {stdout.strip().split()[1]}")
    else:
        print_warning("Docker Buildx not available (needed for ARM64 builds)")

    return True


def check_aws_cli() -> bool:
    """Check AWS CLI installation and configuration."""
    print("\n☁️  Checking AWS CLI...")

    # Check AWS CLI installation
    exit_code, stdout, _ = run_command(["aws", "--version"])
    if exit_code != 0:
        print_error("AWS CLI not installed")
        return False

    print_success(f"AWS CLI: {stdout.strip()}")

    # Check AWS credentials
    exit_code, stdout, stderr = run_command(["aws", "sts", "get-caller-identity"])
    if exit_code != 0:
        print_error("AWS credentials not configured")
        print_info("Run: aws configure")
        return False

    try:
        identity = json.loads(stdout)
        account_id = identity.get("Account", "unknown")
        user_arn = identity.get("Arn", "unknown")
        print_success(f"AWS Account: {account_id}")
        print_info(f"Identity: {user_arn}")
    except json.JSONDecodeError:
        print_warning("Could not parse AWS identity")

    return True


def check_cdk() -> bool:
    """Check AWS CDK installation."""
    print("\n🏗️  Checking AWS CDK...")

    exit_code, stdout, _ = run_command(["cdk", "--version"])
    if exit_code != 0:
        print_error("AWS CDK not installed")
        print_info("Install: npm install -g aws-cdk")
        return False

    print_success(f"CDK: {stdout.strip()}")
    return True


def check_node_npm() -> bool:
    """Check Node.js and npm installation."""
    print("\n📦 Checking Node.js and npm...")

    # Check Node.js
    exit_code, stdout, _ = run_command(["node", "--version"])
    if exit_code != 0:
        print_error("Node.js not installed")
        return False
    print_success(f"Node.js: {stdout.strip()}")

    # Check npm
    exit_code, stdout, _ = run_command(["npm", "--version"])
    if exit_code != 0:
        print_error("npm not installed")
        return False
    print_success(f"npm: {stdout.strip()}")

    return True


def check_python_dependencies() -> bool:
    """Check Python dependencies installation."""
    print("\n📚 Checking Python dependencies...")

    required_packages = [
        "boto3",
        "aws_lambda_powertools",
        "slack_sdk",
        "requests",
        "beautifulsoup4",
        "playwright",
        "aws_cdk",
    ]

    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
            print_success(f"{package}")
        except ImportError:
            print_error(f"{package} - not installed")
            missing_packages.append(package)

    if missing_packages:
        print_info(
            f"Install missing packages: uv pip install {' '.join(missing_packages)}"
        )
        return False

    return True


def check_playwright_browsers() -> bool:
    """Check if Playwright browsers are installed."""
    print("\n🌐 Checking Playwright browsers...")

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            # Try to get browser path
            browser_path = p.chromium.executable_path
            if browser_path and Path(browser_path).exists():
                print_success(f"Chromium browser: {browser_path}")
                return True
            else:
                print_error("Chromium browser not found")
                print_info("Install: python -m playwright install chromium")
                return False

    except ImportError:
        print_error("Playwright not installed")
        return False
    except Exception as e:
        print_error(f"Playwright browser check failed: {e}")
        print_info("Install: python -m playwright install chromium")
        return False


def check_project_structure() -> bool:
    """Check if project structure is complete."""
    print("\n📁 Checking project structure...")

    required_files = [
        "Dockerfile",
        "requirements-docker.txt",
        "pyproject.toml",
        "src/unfurl_processor/handler_new.py",
        "src/unfurl_processor/scrapers/__init__.py",
        "src/unfurl_processor/scrapers/manager.py",
        "src/unfurl_processor/scrapers/playwright_scraper.py",
        "src/unfurl_processor/scrapers/http_scraper.py",
        "src/unfurl_processor/scrapers/oembed_scraper.py",
        "src/unfurl_processor/slack_formatter.py",
        "cdk/stacks/unfurl_service_stack.py",
        ".github/workflows/deploy.yml",
    ]

    missing_files = []

    for file_path in required_files:
        if Path(file_path).exists():
            print_success(file_path)
        else:
            print_error(f"{file_path} - missing")
            missing_files.append(file_path)

    return len(missing_files) == 0


def check_environment_variables() -> bool:
    """Check required environment variables."""
    print("\n🔧 Checking environment variables...")

    recommended_vars = {
        "AWS_REGION": "us-east-2",
        "CDK_DEFAULT_REGION": "us-east-2",
        "POWERTOOLS_METRICS_NAMESPACE": "UnfurlService",
    }

    all_good = True

    for var, default in recommended_vars.items():
        value = os.environ.get(var)
        if value:
            print_success(f"{var}={value}")
        else:
            print_warning(f"{var} not set (recommended: {default})")
            all_good = False

    return all_good


def check_git_status() -> bool:
    """Check git repository status."""
    print("\n📝 Checking git status...")

    # Check if we're in a git repository
    exit_code, _, _ = run_command(["git", "status", "--porcelain"])
    if exit_code != 0:
        print_error("Not in a git repository")
        return False

    # Check for uncommitted changes
    exit_code, stdout, _ = run_command(["git", "status", "--porcelain"])
    if stdout.strip():
        print_warning("Uncommitted changes detected")
        print_info("Consider committing changes before deployment")
    else:
        print_success("Working directory clean")

    # Check current branch
    exit_code, stdout, _ = run_command(["git", "branch", "--show-current"])
    if exit_code == 0:
        branch = stdout.strip()
        print_info(f"Current branch: {branch}")
        if branch != "main":
            print_warning("Not on main branch - deployment may not trigger")

    return True


def main() -> int:
    """Run all validation checks."""
    print_header("Instagram Unfurl Service - Environment Validation")

    checks = [
        ("Python Version", check_python_version),
        ("Docker", check_docker),
        ("AWS CLI", check_aws_cli),
        ("Node.js/npm", check_node_npm),
        ("AWS CDK", check_cdk),
        ("Python Dependencies", check_python_dependencies),
        ("Playwright Browsers", check_playwright_browsers),
        ("Project Structure", check_project_structure),
        ("Environment Variables", check_environment_variables),
        ("Git Status", check_git_status),
    ]

    results = []

    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print_error(f"{check_name} check failed: {e}")
            results.append((check_name, False))

    # Summary
    print_header("Validation Summary")

    passed = 0
    failed = 0

    for check_name, result in results:
        if result:
            print_success(f"{check_name}")
            passed += 1
        else:
            print_error(f"{check_name}")
            failed += 1

    print(f"\n📊 Results: {passed} passed, {failed} failed")

    if failed == 0:
        print_success("Environment is ready for deployment! 🚀")
        print_info("Next steps:")
        print_info("  1. Test Docker build: ./scripts/test_docker_build.sh")
        print_info("  2. Deploy: git push origin main")
        return 0
    else:
        print_error("Environment has issues that need to be resolved")
        print_info("Fix the failed checks above before deployment")
        return 1


if __name__ == "__main__":
    exit(main())
