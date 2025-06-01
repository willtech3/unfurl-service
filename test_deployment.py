#!/usr/bin/env python3

"""
Quick test to verify brotli functionality after deployment
"""

import json
import boto3
import time


def test_brotli_after_deployment():
    """Test that brotli is working in the deployed Lambda"""

    # Wait for deployment to complete
    print("⏳ Waiting for CDK deployment to complete...")
    time.sleep(60)  # Give deployment time to finish

    # Create simple test payload
    test_payload = {
        "Records": [
            {
                "Sns": {
                    "Message": json.dumps(
                        {
                            "channel": "C123TEST",
                            "message_ts": "1733099999.123",
                            "links": [
                                {
                                    "domain": "instagram.com",
                                    "url": "https://www.instagram.com/p/DBmTv9zPq-4/",
                                }
                            ],
                        }
                    )
                }
            }
        ]
    }

    try:
        # Create Lambda client
        lambda_client = boto3.client("lambda", region_name="us-east-2")

        print("🚀 Invoking Lambda with Instagram test...")

        # Invoke Lambda
        response = lambda_client.invoke(
            FunctionName="unfurl-processor-dev",
            InvocationType="RequestResponse",
            Payload=json.dumps(test_payload),
        )

        # Get response
        response_payload = json.loads(response["Payload"].read())
        print(f"✅ Lambda Response: {response_payload}")

        return response_payload

    except Exception as e:
        print(f"❌ Error invoking Lambda: {e}")
        return None


def check_recent_logs():
    """Check recent CloudWatch logs for brotli status"""
    try:
        logs_client = boto3.client("logs", region_name="us-east-2")

        print("📄 Checking recent CloudWatch logs...")

        # Get recent log events
        response = logs_client.filter_log_events(
            logGroupName="/aws/lambda/unfurl-processor-dev",
            startTime=int((time.time() - 300) * 1000),  # Last 5 minutes
            filterPattern="brotli_available",
        )

        events = response.get("events", [])
        if events:
            for event in events[-3:]:  # Show last 3 relevant events
                print(f"📋 {event['message']}")
        else:
            print("ℹ️  No recent brotli-related logs found")

    except Exception as e:
        print(f"❌ Error checking logs: {e}")


if __name__ == "__main__":
    print("🔧 Testing Lambda deployment with brotli support...")

    # Test the deployment
    result = test_brotli_after_deployment()

    # Check logs
    check_recent_logs()

    print("✅ Test complete!")
