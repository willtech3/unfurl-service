#!/usr/bin/env python3

"""
Test script to check if brotli is available in the Lambda environment
"""

import json


def lambda_handler(event, context):
    """Test Lambda handler to check brotli availability"""

    result = {"brotli_available": False, "brotli_module_path": None, "error": None}

    try:
        import brotli

        result["brotli_available"] = True
        result["brotli_module_path"] = str(brotli.__file__)
        print(f"✅ Brotli module successfully imported from: {brotli.__file__}")

        # Test basic functionality
        test_data = b"Hello, World!"
        compressed = brotli.compress(test_data)
        decompressed = brotli.decompress(compressed)

        if decompressed == test_data:
            result["brotli_functional"] = True
            print("✅ Brotli compression/decompression test PASSED")
        else:
            result["brotli_functional"] = False
            print("❌ Brotli compression/decompression test FAILED")

    except ImportError as e:
        result["error"] = f"ImportError: {str(e)}"
        print(f"❌ Failed to import brotli: {e}")
    except Exception as e:
        result["error"] = f"Error: {str(e)}"
        print(f"❌ Error testing brotli: {e}")

    return {"statusCode": 200, "body": json.dumps(result, indent=2)}


if __name__ == "__main__":
    # Test locally
    result = lambda_handler({}, None)
    print("Local test result:")
    print(result["body"])
