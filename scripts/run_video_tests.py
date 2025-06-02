#!/usr/bin/env python3
"""
Test runner for video proxy functionality.

This script runs comprehensive tests for the video proxy implementation
and provides detailed output about test results.
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd: list, description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n🔧 {description}")
    print(f"Running: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(
            cmd,
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
            timeout=300,
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print(f"✅ {description} - PASSED")
            return True
        else:
            print(f"❌ {description} - FAILED (exit code: {result.returncode})")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} - TIMEOUT")
        return False
    except Exception as e:
        print(f"💥 {description} - ERROR: {e}")
        return False


def main():
    """Run all video proxy tests."""
    print("🎬 Instagram Video Proxy Test Suite")
    print("=" * 60)
    
    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    test_results = []
    
    # Test 1: Code Quality Checks
    test_results.append(
        run_command(
            ["uv", "run", "black", "--check", "src/unfurl_processor/video_proxy.py"],
            "Black formatting check for video proxy"
        )
    )
    
    test_results.append(
        run_command(
            ["uv", "run", "flake8", "src/unfurl_processor/video_proxy.py"],
            "Flake8 linting for video proxy"
        )
    )
    
    test_results.append(
        run_command(
            ["uv", "run", "mypy", "src/unfurl_processor/video_proxy.py"],
            "MyPy type checking for video proxy"
        )
    )
    
    # Test 2: Unit Tests
    test_results.append(
        run_command(
            ["uv", "run", "pytest", "tests/test_video_proxy.py", "-v"],
            "Video proxy unit tests"
        )
    )
    
    # Test 3: Integration Tests
    test_results.append(
        run_command(
            ["uv", "run", "pytest", "tests/test_video_proxy.py::TestVideoProxyIntegration", "-v"],
            "Video proxy integration tests"
        )
    )
    
    # Test 4: Slack Formatter Tests (updated)
    test_results.append(
        run_command(
            ["uv", "run", "pytest", "tests/", "-k", "slack_formatter", "-v"],
            "Slack formatter tests (including video support)"
        )
    )
    
    # Test 5: Code Coverage for Video Proxy
    test_results.append(
        run_command(
            ["uv", "run", "pytest", "tests/test_video_proxy.py", "--cov=src.unfurl_processor.video_proxy", "--cov-report=term-missing"],
            "Video proxy code coverage"
        )
    )
    
    # Test 6: Import Validation
    test_results.append(
        run_command(
            ["uv", "run", "python", "-c", "from src.unfurl_processor.video_proxy import VideoProxy; print('✅ Video proxy imports successfully')"],
            "Video proxy import validation"
        )
    )
    
    # Test 7: Lambda Handler Validation
    test_results.append(
        run_command(
            ["uv", "run", "python", "-c", """
import json
from src.unfurl_processor.video_proxy import VideoProxy
proxy = VideoProxy()
event = {'pathParameters': {'video_url': 'https%3A//scontent.cdninstagram.com/test.mp4'}}
result = proxy.lambda_handler(event, None)
print(f'✅ Lambda handler test: {result["statusCode"]}')
"""],
            "Lambda handler smoke test"
        )
    )
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed_tests = sum(test_results)
    total_tests = len(test_results)
    
    test_names = [
        "Black formatting",
        "Flake8 linting", 
        "MyPy type checking",
        "Unit tests",
        "Integration tests",
        "Slack formatter tests",
        "Code coverage",
        "Import validation",
        "Lambda handler test",
    ]
    
    for i, (name, passed) in enumerate(zip(test_names, test_results)):
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {name}")
    
    print("-" * 60)
    print(f"TOTAL: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 All video proxy tests PASSED!")
        print("✨ Video proxy implementation is ready for deployment.")
        return 0
    else:
        print(f"\n⚠️  {total_tests - passed_tests} test(s) FAILED!")
        print("🔧 Please fix failing tests before deployment.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
