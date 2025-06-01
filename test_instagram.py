#!/usr/bin/env python3
"""
Test script to trigger Instagram unfurl processing and analyze logs.
"""

import json
import time
import requests
from datetime import datetime


def test_instagram_unfurl():
    """Test Instagram unfurl with a real URL."""

    # Real Instagram post URL
    instagram_url = "https://www.instagram.com/p/DBmTv9zPq-4/"

    # AWS API Gateway endpoint for unfurl-processor
    api_endpoint = "https://hpkllvgmr0.execute-api.us-east-2.amazonaws.com/prod/unfurl"

    # Create event payload similar to what Slack sends
    event_payload = {
        "event": {
            "type": "link_shared",
            "links": [{"domain": "instagram.com", "url": instagram_url}],
            "user": "U123TEST",
            "channel": "C123TEST",
            "message_ts": str(time.time()),
        },
        "type": "event_callback",
        "event_id": f"Ev{int(time.time())}",
        "event_time": int(time.time()),
    }

    print(f"🚀 Testing Instagram unfurl for: {instagram_url}")
    print(f"⏰ Timestamp: {datetime.now().isoformat()}")

    try:
        response = requests.post(
            api_endpoint,
            json=event_payload,
            headers={
                "Content-Type": "application/json",
                "X-Slack-Request-Timestamp": str(int(time.time())),
                "X-Slack-Signature": "v0=test_signature",
            },
            timeout=30,
        )

        print(f"✅ Response Status: {response.status_code}")
        print(f"📄 Response: {response.text}")

        if response.status_code == 200:
            print(
                "\n🔍 Check CloudWatch logs in 30 seconds for detailed brotli debugging..."
            )
            print("📊 Look for logs with:")
            print("   - brotli_available: true/false")
            print("   - content_encoding: br")
            print("   - Manual brotli decompression results")
            print("   - Content validation details")

    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")

    return event_payload


if __name__ == "__main__":
    test_instagram_unfurl()
