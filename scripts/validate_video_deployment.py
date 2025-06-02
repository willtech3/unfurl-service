#!/usr/bin/env python3
"""
Video proxy deployment validation script.

This script validates that the video proxy deployment is working correctly
by testing the API endpoints and verifying functionality.
"""

import argparse
import json
import time
import urllib.parse
from typing import Any, Dict

import boto3
import requests


class VideoProxyValidator:
    """Validates video proxy deployment."""

    def __init__(self, api_base_url: str, environment: str = "dev"):
        """Initialize validator with API base URL."""
        self.api_base_url = api_base_url.rstrip("/")
        self.environment = environment
        self.session = requests.Session()

        # Test video URLs
        self.test_video_urls = [
            "https://scontent.cdninstagram.com/o1/v/t16/test.mp4",
            "https://video.cdninstagram.com/test.mp4",
            "https://scontent.xx.fbcdn.net/test.mp4",
        ]

    def validate_deployment(self) -> Dict[str, Any]:
        """Run complete deployment validation."""
        results = {
            "timestamp": time.time(),
            "environment": self.environment,
            "api_base_url": self.api_base_url,
            "tests": {},
            "overall_status": "unknown",
        }

        print(f"🔍 Validating video proxy deployment for {self.environment}")
        print(f"📡 API Base URL: {self.api_base_url}")
        print("-" * 60)

        # Test 1: API Gateway Health
        results["tests"]["api_health"] = self._test_api_health()

        # Test 2: Video Proxy Endpoint
        results["tests"]["video_proxy"] = self._test_video_proxy_endpoint()

        # Test 3: Lambda Function Health
        results["tests"]["lambda_health"] = self._test_lambda_health()

        # Test 4: DynamoDB Cache Access
        results["tests"]["dynamodb_cache"] = self._test_dynamodb_cache()

        # Test 5: Video URL Validation
        results["tests"]["url_validation"] = self._test_video_url_validation()

        # Test 6: Error Handling
        results["tests"]["error_handling"] = self._test_error_handling()

        # Calculate overall status
        passed_tests = sum(
            1 for test in results["tests"].values() if test.get("status") == "pass"
        )
        total_tests = len(results["tests"])

        if passed_tests == total_tests:
            results["overall_status"] = "pass"
        elif passed_tests > 0:
            results["overall_status"] = "partial"
        else:
            results["overall_status"] = "fail"

        self._print_summary(results)
        return results

    def _test_api_health(self) -> Dict[str, Any]:
        """Test API Gateway health."""
        print("🏥 Testing API Gateway health...")

        try:
            response = self.session.get(f"{self.api_base_url}/health", timeout=10)

            if response.status_code == 200:
                print("  ✅ API Gateway is healthy")
                return {"status": "pass", "response_code": response.status_code}
            else:
                print(f"  ❌ API Gateway unhealthy: {response.status_code}")
                return {"status": "fail", "response_code": response.status_code}

        except Exception as e:
            print(f"  ❌ API Gateway connection failed: {e}")
            return {"status": "fail", "error": str(e)}

    def _test_video_proxy_endpoint(self) -> Dict[str, Any]:
        """Test video proxy endpoint functionality."""
        print("🎬 Testing video proxy endpoint...")

        test_url = self.test_video_urls[0]
        encoded_url = urllib.parse.quote(test_url, safe="")
        proxy_url = f"{self.api_base_url}/video/{encoded_url}"

        try:
            response = self.session.get(proxy_url, timeout=15)

            if response.status_code == 200:
                if "text/html" in response.headers.get("Content-Type", ""):
                    if "<video" in response.text and test_url in response.text:
                        print("  ✅ Video proxy endpoint working correctly")
                        return {
                            "status": "pass",
                            "response_code": response.status_code,
                            "content_type": response.headers.get("Content-Type"),
                        }
                    else:
                        print("  ❌ Video proxy returned invalid HTML")
                        return {"status": "fail", "error": "Invalid HTML content"}
                else:
                    print("  ❌ Video proxy returned wrong content type")
                    return {"status": "fail", "error": "Wrong content type"}
            else:
                print(f"  ❌ Video proxy failed: {response.status_code}")
                return {
                    "status": "fail",
                    "response_code": response.status_code,
                    "body": response.text[:200],
                }

        except Exception as e:
            print(f"  ❌ Video proxy request failed: {e}")
            return {"status": "fail", "error": str(e)}

    def _test_lambda_health(self) -> Dict[str, Any]:
        """Test Lambda function health via AWS API."""
        print("🔧 Testing Lambda function health...")

        try:
            lambda_client = boto3.client("lambda")
            function_name = f"video-proxy-{self.environment}"

            response = lambda_client.get_function(FunctionName=function_name)

            if response["Configuration"]["State"] == "Active":
                print("  ✅ Lambda function is active and healthy")
                return {
                    "status": "pass",
                    "state": response["Configuration"]["State"],
                    "runtime": response["Configuration"]["Runtime"],
                    "memory_size": response["Configuration"]["MemorySize"],
                }
            else:
                print(
                    "  ❌ Lambda function not active: "
                    f"{response['Configuration']['State']}"
                )
                return {
                    "status": "fail",
                    "state": response["Configuration"]["State"],
                }

        except Exception as e:
            print(f"  ⚠️  Lambda health check failed (may be permissions): {e}")
            return {"status": "skip", "error": str(e)}

    def _test_dynamodb_cache(self) -> Dict[str, Any]:
        """Test DynamoDB cache table access."""
        print("📊 Testing DynamoDB cache access...")

        try:
            dynamodb = boto3.resource("dynamodb")
            table_name = f"unfurl-cache-{self.environment}"
            table = dynamodb.Table(table_name)

            # Test table access
            response = table.describe_table()

            if response["Table"]["TableStatus"] == "ACTIVE":
                print("  ✅ DynamoDB cache table is active")
                return {
                    "status": "pass",
                    "table_status": response["Table"]["TableStatus"],
                    "item_count": response["Table"]["ItemCount"],
                }
            else:
                print(
                    f"  ❌ DynamoDB table not active: {response['Table']['TableStatus']}"
                )
                return {
                    "status": "fail",
                    "table_status": response["Table"]["TableStatus"],
                }

        except Exception as e:
            print(f"  ⚠️  DynamoDB access failed (may be permissions): {e}")
            return {"status": "skip", "error": str(e)}

    def _test_video_url_validation(self) -> Dict[str, Any]:
        """Test video URL validation logic."""
        print("🔍 Testing video URL validation...")

        test_cases = [
            {
                "url": "https://scontent.cdninstagram.com/test.mp4",
                "should_work": True,
                "description": "Instagram CDN URL",
            },
            {
                "url": "https://example.com/video.mp4",
                "should_work": False,
                "description": "Non-Instagram URL",
            },
            {
                "url": "invalid-url",
                "should_work": False,
                "description": "Invalid URL format",
            },
        ]

        results = []
        for test_case in test_cases:
            encoded_url = urllib.parse.quote(test_case["url"], safe="")
            proxy_url = f"{self.api_base_url}/video/{encoded_url}"

            try:
                response = self.session.get(proxy_url, timeout=10)

                if test_case["should_work"]:
                    success = response.status_code == 200
                else:
                    success = response.status_code in [400, 403, 404]

                results.append(
                    {
                        "url": test_case["url"],
                        "description": test_case["description"],
                        "expected_to_work": test_case["should_work"],
                        "response_code": response.status_code,
                        "success": success,
                    }
                )

            except Exception as e:
                results.append(
                    {
                        "url": test_case["url"],
                        "description": test_case["description"],
                        "expected_to_work": test_case["should_work"],
                        "error": str(e),
                        "success": False,
                    }
                )

        all_passed = all(result["success"] for result in results)

        if all_passed:
            print("  ✅ URL validation working correctly")
        else:
            print("  ❌ URL validation has issues")

        return {"status": "pass" if all_passed else "fail", "test_cases": results}

    def _test_error_handling(self) -> Dict[str, Any]:
        """Test error handling scenarios."""
        print("⚠️  Testing error handling...")

        error_tests = [
            {
                "url": "/video/",  # Missing video URL
                "expected_code": 400,
                "description": "Missing video URL parameter",
            },
            {
                "url": "/video/%ZZ%invalid",  # Invalid encoding
                "expected_code": 400,
                "description": "Invalid URL encoding",
            },
        ]

        results = []
        for test in error_tests:
            try:
                response = self.session.get(
                    f"{self.api_base_url}{test['url']}", timeout=10
                )

                success = response.status_code == test["expected_code"]
                results.append(
                    {
                        "test": test["description"],
                        "expected_code": test["expected_code"],
                        "actual_code": response.status_code,
                        "success": success,
                    }
                )

            except Exception as e:
                results.append(
                    {
                        "test": test["description"],
                        "error": str(e),
                        "success": False,
                    }
                )

        all_passed = all(result["success"] for result in results)

        if all_passed:
            print("  ✅ Error handling working correctly")
        else:
            print("  ❌ Error handling has issues")

        return {"status": "pass" if all_passed else "fail", "tests": results}

    def _print_summary(self, results: Dict[str, Any]) -> None:
        """Print validation summary."""
        print("\n" + "=" * 60)
        print("📋 DEPLOYMENT VALIDATION SUMMARY")
        print("=" * 60)

        status_emoji = {
            "pass": "✅",
            "fail": "❌",
            "skip": "⚠️",
            "partial": "🟡",
        }

        for test_name, test_result in results["tests"].items():
            status = test_result.get("status", "unknown")
            emoji = status_emoji.get(status, "❓")
            print(f"{emoji} {test_name.replace('_', ' ').title()}: {status.upper()}")

        print("-" * 60)
        overall_status = results["overall_status"]
        overall_emoji = status_emoji.get(overall_status, "❓")
        print(f"{overall_emoji} OVERALL STATUS: {overall_status.upper()}")

        if overall_status == "pass":
            print("\n🎉 Video proxy deployment is working correctly!")
            print("✨ You can now enable playable Instagram videos in Slack.")
        elif overall_status == "partial":
            print("\n⚠️  Video proxy deployment has some issues.")
            print("🔧 Review failed tests and check configuration.")
        else:
            print("\n💥 Video proxy deployment has significant issues.")
            print("🚨 Please review deployment and fix errors before proceeding.")


def main():
    """Main validation script."""
    parser = argparse.ArgumentParser(description="Validate video proxy deployment")
    parser.add_argument(
        "--api-url",
        required=True,
        help=(
            "Base URL of the API Gateway "
            "(e.g., https://api-id.execute-api.region.amazonaws.com/prod)"
        ),
    )
    parser.add_argument(
        "--environment",
        default="dev",
        help="Environment name (default: dev)",
    )
    parser.add_argument(
        "--output",
        help="Output file for detailed results (JSON)",
    )

    args = parser.parse_args()

    # Run validation
    validator = VideoProxyValidator(args.api_url, args.environment)
    results = validator.validate_deployment()

    # Save detailed results if requested
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n📄 Detailed results saved to: {args.output}")

    # Exit with appropriate code
    if results["overall_status"] == "pass":
        exit(0)
    elif results["overall_status"] == "partial":
        exit(1)
    else:
        exit(2)


if __name__ == "__main__":
    main()
