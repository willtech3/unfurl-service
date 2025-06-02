#!/usr/bin/env python3
"""Test Event Router Lambda dependencies for import verification."""

import sys
import os

def test_import(module_name):
    """Test if a module can be imported successfully."""
    try:
        __import__(module_name)
        print(f"✅ {module_name} - imported successfully")
        return True
    except ImportError as e:
        print(f"❌ {module_name} - import failed: {e}")
        return False
    except Exception as e:
        print(f"⚠️  {module_name} - unexpected error: {e}")
        return False

def main():
    """Test all required Event Router dependencies."""
    print("🔍 Testing Event Router Lambda Dependencies...")
    print("=" * 50)
    
    # Core dependencies for Event Router
    dependencies = [
        "boto3",
        "slack_sdk", 
        "aws_lambda_powertools",
        "aws_xray_sdk",
        "requests",
        "dateutil"
    ]
    
    success_count = 0
    total_count = len(dependencies)
    
    for dep in dependencies:
        if test_import(dep):
            success_count += 1
    
    print("=" * 50)
    print(f"📊 Results: {success_count}/{total_count} dependencies imported successfully")
    
    if success_count == total_count:
        print("🎉 All Event Router dependencies are available!")
        return 0
    else:
        print("💥 Some dependencies are missing - deployment will fail")
        return 1

if __name__ == "__main__":
    sys.exit(main())
