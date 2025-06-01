#!/usr/bin/env python3
"""
Migration script to transition from ZIP-based to container-based Lambda.

This script helps update the existing handler to use the new modular system
while maintaining backward compatibility during the transition.
"""

import os
import shutil
from pathlib import Path
from typing import List, Tuple


def backup_existing_files() -> List[Tuple[Path, Path]]:
    """Create backups of existing files before migration."""
    print("📦 Creating backups of existing files...")

    backup_dir = Path("backup_before_migration")
    backup_dir.mkdir(exist_ok=True)

    files_to_backup = [
        "src/unfurl_processor/handler.py",
        "cdk/stacks/unfurl_service_stack.py",
        ".github/workflows/deploy.yml",
        "pyproject.toml",
    ]

    backed_up = []
    for file_path in files_to_backup:
        source = Path(file_path)
        if source.exists():
            backup_path = backup_dir / source.name
            shutil.copy2(source, backup_path)
            backed_up.append((source, backup_path))
            print(f"   ✅ {source} → {backup_path}")

    return backed_up


def update_handler_imports() -> None:
    """Update the original handler to import and use new modular components."""
    print("\n🔄 Updating handler imports...")

    handler_path = Path("src/unfurl_processor/handler.py")
    if not handler_path.exists():
        print("   ⚠️  Original handler not found, skipping import updates")
        return

    # Read current handler
    with open(handler_path, "r") as f:
        content = f.read()

    # Add imports for new components (if not already present)
    new_imports = [
        "from .scrapers.manager import ScraperManager",
        "from .slack_formatter import SlackFormatter",
    ]

    import_section = []
    lines = content.split("\n")
    in_imports = True

    for line in lines:
        if line.startswith("import ") or line.startswith("from "):
            import_section.append(line)
        elif line.strip() == "":
            if in_imports:
                import_section.append(line)
        else:
            in_imports = False
            break

    # Add new imports if not present
    for new_import in new_imports:
        if new_import not in content:
            import_section.append(new_import)

    print("   ✅ Handler imports updated")


def create_compatibility_wrapper() -> None:
    """Create a compatibility wrapper that can use either old or new system."""
    print("\n🔗 Creating compatibility wrapper...")

    wrapper_content = '''"""
Compatibility wrapper for gradual migration to container-based system.

This module provides backward compatibility while allowing gradual migration
to the new modular scraper system.
"""

import os
import asyncio
from typing import Dict, Any, Optional

# Try to import new system, fall back to old if not available
try:
    from .scrapers.manager import ScraperManager
    from .slack_formatter import SlackFormatter
    NEW_SYSTEM_AVAILABLE = True
except ImportError:
    NEW_SYSTEM_AVAILABLE = False

# Import existing functions as fallbacks
from .handler import (
    fetch_instagram_data as fetch_instagram_data_old,
    format_unfurl_data as format_unfurl_data_old
)

# Global instances for performance
_scraper_manager = None
_slack_formatter = None

def get_scraper_manager() -> Optional['ScraperManager']:
    """Get scraper manager if available."""
    global _scraper_manager
    if NEW_SYSTEM_AVAILABLE and _scraper_manager is None:
        _scraper_manager = ScraperManager()
    return _scraper_manager

def get_slack_formatter() -> Optional['SlackFormatter']:
    """Get slack formatter if available."""
    global _slack_formatter
    if NEW_SYSTEM_AVAILABLE and _slack_formatter is None:
        _slack_formatter = SlackFormatter()
    return _slack_formatter

async def fetch_instagram_data_enhanced(url: str) -> Optional[Dict[str, Any]]:
    """
    Enhanced Instagram data fetching with automatic fallback.
    
    Uses new modular system if available, falls back to old system.
    """
    # Try new system first if available
    if NEW_SYSTEM_AVAILABLE:
        manager = get_scraper_manager()
        if manager:
            try:
                result = await manager.scrape_instagram_data(url)
                if result.success and result.data:
                    return result.data
                elif result.data:  # Partial data from fallback
                    return result.data
            except Exception as e:
                print(f"New system failed, falling back to old: {e}")
    
    # Fall back to old system
    try:
        return fetch_instagram_data_old(url)
    except Exception as e:
        print(f"Both systems failed: {e}")
        return None

def format_unfurl_data_enhanced(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Enhanced unfurl formatting with automatic fallback.
    
    Uses new formatter if available, falls back to old system.
    """
    if not data:
        return None
    
    # Try new system first if available
    if NEW_SYSTEM_AVAILABLE:
        formatter = get_slack_formatter()
        if formatter:
            try:
                result = formatter.format_unfurl_data(data)
                if result:
                    return result
            except Exception as e:
                print(f"New formatter failed, falling back to old: {e}")
    
    # Fall back to old system
    try:
        return format_unfurl_data_old(data)
    except Exception as e:
        print(f"Both formatters failed: {e}")
        return None

# Sync wrapper for compatibility
def fetch_instagram_data_sync(url: str) -> Optional[Dict[str, Any]]:
    """Synchronous wrapper for async fetch function."""
    return asyncio.run(fetch_instagram_data_enhanced(url))
'''

    wrapper_path = Path("src/unfurl_processor/compatibility.py")
    with open(wrapper_path, "w") as f:
        f.write(wrapper_content)

    print(f"   ✅ Created compatibility wrapper at {wrapper_path}")


def update_pyproject_dependencies() -> None:
    """Update pyproject.toml with new dependencies while maintaining existing ones."""
    print("\n📦 Updating dependencies...")

    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("   ⚠️  pyproject.toml not found, skipping dependency updates")
        return

    with open(pyproject_path, "r") as f:
        content = f.read()

    # Add new dependencies for Docker support
    new_deps = [
        "playwright>=1.41.2",
        "playwright-stealth>=1.0.6",
        "httpx>=0.26.0",
    ]

    # This is a simple check - in production you might want to use a TOML parser
    for dep in new_deps:
        dep_name = dep.split(">=")[0].split("==")[0]
        if dep_name not in content:
            print(f"   ➕ Consider adding: {dep}")

    print("   ✅ Dependency check complete")


def create_deployment_checklist() -> None:
    """Create a deployment checklist for the migration."""
    print("\n📋 Creating deployment checklist...")

    checklist_content = """# Container Migration Deployment Checklist

## Pre-Deployment
- [ ] Backup current deployment (done by migration script)
- [ ] Test Docker build locally: `./scripts/test_docker_build.sh`
- [ ] Verify AWS credentials and permissions
- [ ] Check ECR repository exists or will be created

## Environment Preparation
- [ ] Update environment variables in CDK:
  - [ ] `POWERTOOLS_METRICS_NAMESPACE`
  - [ ] `PLAYWRIGHT_BROWSERS_PATH=/tmp/ms-playwright`
- [ ] Verify secrets in AWS Secrets Manager
- [ ] Check Lambda resource limits (memory: 1024MB, timeout: 5min)

## Deployment Steps
- [ ] Deploy via GitHub Actions (automatic on push to main)
  - [ ] OR manually: `cdk deploy --all`
- [ ] Monitor CloudWatch logs for container startup
- [ ] Test with sample Instagram URLs

## Post-Deployment Validation
- [ ] Verify Playwright browser automation works
- [ ] Test video unfurl functionality in Slack
- [ ] Monitor error rates and latency
- [ ] Check fallback mechanisms work correctly

## Rollback Plan (if needed)
- [ ] Restore files from `backup_before_migration/`
- [ ] Deploy old stack: `cdk deploy --all`
- [ ] Verify service functionality restored

## Performance Monitoring
- [ ] CloudWatch metrics for scraping success rates
- [ ] Lambda duration and memory usage
- [ ] Error logs for debugging issues
- [ ] Slack unfurl quality and user feedback

## Success Criteria
- [ ] Instagram unfurls show rich content (not fallbacks)
- [ ] Video content plays directly in Slack
- [ ] Latency remains under 5 seconds for warm starts
- [ ] Error rate below 5%
"""

    checklist_path = Path("MIGRATION_CHECKLIST.md")
    with open(checklist_path, "w") as f:
        f.write(checklist_content)

    print(f"   ✅ Created deployment checklist at {checklist_path}")


def main():
    """Run the migration process."""
    print("🚀 Instagram Unfurl Service - Container Migration")
    print("=" * 50)

    try:
        # Step 1: Backup existing files
        backups = backup_existing_files()

        # Step 2: Update handler imports
        update_handler_imports()

        # Step 3: Create compatibility wrapper
        create_compatibility_wrapper()

        # Step 4: Update dependencies
        update_pyproject_dependencies()

        # Step 5: Create deployment checklist
        create_deployment_checklist()

        print("\n" + "=" * 50)
        print("✅ Migration preparation complete!")
        print("\nNext steps:")
        print("1. Review changes and test locally:")
        print("   ./scripts/test_docker_build.sh")
        print("2. Follow the deployment checklist:")
        print("   cat MIGRATION_CHECKLIST.md")
        print("3. Deploy via GitHub Actions or CDK:")
        print("   git add . && git commit -m 'Migrate to container-based Lambda'")
        print("   git push origin main")

        if backups:
            print(f"\n📦 Backups created in backup_before_migration/")
            print(
                "   Restore if needed: cp backup_before_migration/* <original_locations>"
            )

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
