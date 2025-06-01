#!/usr/bin/env python3

"""
Direct brotli import test to send to Lambda
"""

import json


def lambda_handler(event, context):
    """Test handler for checking brotli import directly"""

    result = {"timestamp": "2025-06-01T06:05:00Z", "test_type": "brotli_import_test"}

    # Test 1: Direct import
    try:
        import brotli

        result["direct_import"] = "SUCCESS"
        result["brotli_version"] = getattr(brotli, "__version__", "unknown")
        result["brotli_file"] = str(brotli.__file__)

        # Test basic functionality
        test_data = b"Hello World!"
        compressed = brotli.compress(test_data)
        decompressed = brotli.decompress(compressed)
        result["compression_test"] = (
            "SUCCESS" if decompressed == test_data else "FAILED"
        )

    except Exception as e:
        result["direct_import"] = f"FAILED: {e}"
        result["brotli_version"] = None
        result["brotli_file"] = None
        result["compression_test"] = None

    # Test 2: Check sys.path
    import sys

    result["python_path"] = sys.path[:5]  # First 5 entries

    # Test 3: Check if brotli is available in site-packages
    try:
        import pkg_resources

        installed_packages = [d.project_name for d in pkg_resources.working_set]
        result["has_brotli_package"] = "brotli" in installed_packages
        result["installed_packages"] = [
            p for p in installed_packages if "brotli" in p.lower()
        ]
    except:
        result["has_brotli_package"] = "unknown"
        result["installed_packages"] = []

    # Test 4: Check available modules
    import pkgutil

    available_modules = [
        name
        for importer, name, ispkg in pkgutil.iter_modules()
        if "brotli" in name.lower()
    ]
    result["available_brotli_modules"] = available_modules

    print(f"🔍 BROTLI DEBUG RESULTS: {json.dumps(result, indent=2)}")

    return {"statusCode": 200, "body": json.dumps(result, indent=2)}


if __name__ == "__main__":
    print("Testing locally...")
    result = lambda_handler({}, None)
    print(result)
