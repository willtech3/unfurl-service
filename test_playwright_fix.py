#!/usr/bin/env python3
"""
Test script to validate Playwright async_api import fix
This script tests the exact import that was failing in the CI/CD pipeline
"""
import sys
import traceback

def test_playwright_imports():
    """Test Playwright imports that were failing"""
    print("🧪 Testing Playwright imports...")
    
    try:
        # Test 1: Base playwright import
        print("1. Testing base playwright import...")
        import playwright
        
        # Try multiple methods to get Playwright version
        version = getattr(playwright, '__version__', None)
        if version is None:
            try:
                import importlib.metadata as im
                version = im.version('playwright')
            except Exception:
                version = 'unknown'
        
        print(f"   ✅ playwright imported successfully, version: {version}")
        
        # Test 2: async_api import (this was failing)
        print("2. Testing playwright.async_api import...")
        from playwright.async_api import async_playwright
        print("   ✅ async_playwright imported successfully")
        
        # Test 3: Other async_api components
        print("3. Testing other async_api components...")
        from playwright.async_api import Browser, BrowserContext
        print("   ✅ Browser and BrowserContext imported successfully")
        
        # Test 4: Stealth import (optional)
        print("4. Testing playwright-stealth import...")
        try:
            from playwright_stealth import stealth_async
            print("   ✅ playwright_stealth imported successfully")
        except ImportError as e:
            print(f"   ⚠️  playwright_stealth import failed (optional): {e}")
        
        print("\n🎉 All critical Playwright imports working!")
        return True
        
    except ImportError as e:
        print(f"\n❌ Import failed: {e}")
        print(f"Error type: {type(e)}")
        print(f"Full traceback:\n{traceback.format_exc()}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        print(f"Error type: {type(e)}")
        print(f"Full traceback:\n{traceback.format_exc()}")
        return False

def print_environment_info():
    """Print environment information for debugging"""
    import os
    
    print("🔍 Environment Information:")
    print(f"   Python version: {sys.version}")
    print(f"   Python executable: {sys.executable}")
    print(f"   PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")
    print(f"   PLAYWRIGHT_BROWSERS_PATH: {os.environ.get('PLAYWRIGHT_BROWSERS_PATH', 'Not set')}")
    print(f"   LAMBDA_TASK_ROOT: {os.environ.get('LAMBDA_TASK_ROOT', 'Not set')}")
    print(f"   AWS_LAMBDA_FUNCTION_NAME: {os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'Not set')}")
    print()

if __name__ == "__main__":
    print("=" * 60)
    print("PLAYWRIGHT ASYNC_API IMPORT TEST")
    print("=" * 60)
    
    print_environment_info()
    
    success = test_playwright_imports()
    
    print("\n" + "=" * 60)
    if success:
        print("RESULT: ✅ All tests passed - Playwright is ready for use!")
        sys.exit(0)
    else:
        print("RESULT: ❌ Tests failed - Playwright async_api import issues remain")
        sys.exit(1)