#!/usr/bin/env python3
"""
Test script to verify Slack app configuration is working.
"""
import boto3
from datetime import datetime, timedelta


def check_recent_events():
    """Check for recent events in CloudWatch logs."""
    logs_client = boto3.client("logs", region_name="us-east-2")

    # Check last 10 minutes
    start_time = int((datetime.now() - timedelta(minutes=10)).timestamp() * 1000)

    log_groups = [
        "/aws/lambda/unfurl-event-router-dev",
        "/aws/lambda/unfurl-processor-dev-v2",
    ]

    print("🔍 Checking recent Slack events…")
    print("⏰ Looking for events in last 10 minutes")
    print()

    for log_group in log_groups:
        try:
            response = logs_client.filter_log_events(
                logGroupName=log_group,
                startTime=start_time,
                filterPattern="instagram.com",
            )

            events = response.get("events", [])
            print(
                f"📋 {log_group}: {len(events)} Instagram events found"
            )

            for event in events[-3:]:  # Show last 3 events
                timestamp = datetime.fromtimestamp(event["timestamp"] / 1000)
                message = event["message"].strip()
                print(
                    f"  {timestamp.strftime('%H:%M:%S')} - {message}"
                )

            if events:
                print("✅ Events are being received!")

        except Exception as e:
            print(f"❌ Error checking {log_group}: {e}")

    print()


def check_api_gateway():
    """Check API Gateway health."""
    import requests
    import json  # noqa: F401   # used for response.json() debugging if needed

    endpoint = (
        "https://kn59lllvqb.execute-api.us-east-2.amazonaws.com/prod/slack/events"
    )

    print("🌐 Testing API Gateway endpoint...")

    # Test URL verification (what Slack sends first)
    test_payload = {"type": "url_verification", "challenge": "test_challenge_12345"}

    try:
        response = requests.post(
            endpoint,
            json=test_payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        print(f"📡 Response Status: {response.status_code}")
        print(f"📄 Response Body: {response.text}")

        if response.status_code == 200:
            try:
                data = response.json()
                if data.get("challenge") == "test_challenge_12345":
                    print("✅ URL verification working correctly")
                    return True
            except Exception:
                # Slack returned non-JSON or malformed response; ignore for this test
                pass

        print("❌ URL verification not working as expected")
        return False

    except Exception as e:
        print(f"❌ API Gateway test failed: {e}")
        return False


def main():
    print("🧪 Slack Events Test")
    print("=" * 40)
    print()

    # Check API Gateway
    api_working = check_api_gateway()
    print()

    # Check recent events
    check_recent_events()

    print("📋 Instructions:")
    print("1. Configure your Slack app at https://api.slack.com/apps")
    print("2. Share an Instagram link in Slack")
    print("3. Run this script again to see if events are received")
    print()

    if api_working:
        print("✅ API Gateway is ready to receive Slack events")
    else:
        print("❌ API Gateway configuration needs attention")


if __name__ == "__main__":
    main()
