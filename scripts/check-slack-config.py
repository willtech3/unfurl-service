#!/usr/bin/env python3
"""
Check Slack app configuration for Instagram unfurl service.
"""
import json
import boto3
import requests


def get_slack_token():
    """Get Slack bot token from AWS Secrets Manager."""
    try:
        secrets_client = boto3.client("secretsmanager", region_name="us-east-2")
        response = secrets_client.get_secret_value(SecretId="unfurl-service/slack")
        secret = json.loads(response["SecretString"])
        return secret.get("bot_token")
    except Exception as e:
        print(f"❌ Could not retrieve Slack token: {e}")
        return None


def check_slack_scopes(token):
    """Check current OAuth scopes."""
    headers = {"Authorization": f"Bearer {token}"}

    # Get app info
    response = requests.post("https://slack.com/api/auth.test", headers=headers)

    if response.status_code == 200:
        data = response.json()
        if data.get("ok"):
            print("🔍 Current Slack App Configuration:")
            print(f"  App: {data.get('team')} ({data.get('team_id')})")
            print(f"  Bot User: {data.get('user')} ({data.get('user_id')})")
            print(f"  Bot ID: {data.get('bot_id')}")

            # Try to get more detailed info about scopes
            scopes_response = requests.post(
                "https://slack.com/api/apps.permissions.scopes.list", headers=headers
            )

            if scopes_response.status_code == 200:
                scopes_data = scopes_response.json()
                if scopes_data.get("ok"):
                    print("\n🔐 Current OAuth Scopes:")
                    scopes = scopes_data.get("scopes", {})
                    bot_scopes = scopes.get("bot", [])
                    for scope in bot_scopes:
                        print(f"  ✅ {scope}")

                    # Check required scopes
                    required_scopes = ["links:read", "links:write", "chat:write"]
                    missing_scopes = [s for s in required_scopes if s not in bot_scopes]

                    if missing_scopes:
                        print(f"\n⚠️  Missing required scopes: {missing_scopes}")
                        return False
                    else:
                        print("\n✅ All required scopes are present!")
                        return True
                else:
                    print(f"❌ Failed to get scopes: {scopes_data.get('error')}")
            else:
                print("⚠️  Could not retrieve detailed scope information")
                print("   This is normal - checking basic permissions instead...")

                # Test basic permissions
                test_response = requests.post(
                    "https://slack.com/api/chat.unfurl",
                    headers=headers,
                    json={"channel": "test", "ts": "1234567890.123456", "unfurls": {}},
                )

                if test_response.status_code == 200:
                    test_data = test_response.json()
                    if test_data.get("error") == "channel_not_found":
                        print("✅ chat.unfurl permission confirmed")
                        return True
                    elif test_data.get("error") == "missing_scope":
                        print("❌ Missing chat:write or links:write scope")
                        return False

                return True
        else:
            print(f"❌ Auth test failed: {data.get('error')}")
            return False
    else:
        print(f"❌ HTTP error: {response.status_code}")
        return False


def main():
    print("🔧 Slack App Configuration Checker")
    print("=" * 50)

    # Get API Gateway endpoint
    api_endpoint = (
        "https://kn59lllvqb.execute-api.us-east-2.amazonaws.com/prod/slack/events"
    )
    print(f"📡 API Gateway Endpoint: {api_endpoint}")

    # Get Slack token
    token = get_slack_token()
    if not token:
        return

    print(f"🔑 Slack Bot Token: {token[:12]}...")

    # Check scopes
    scopes_ok = check_slack_scopes(token)

    print("\n📋 Next Steps:")
    print("1. Go to https://api.slack.com/apps")
    print("2. Select your Instagram Unfurl app")
    print("3. Check these configurations:")
    print()
    print("   🔗 Event Subscriptions:")
    print(f"     Request URL: {api_endpoint}")
    print("     Subscribe to Bot Events:")
    print("       - link_shared")
    print()
    print("   🌐 App Unfurl Domains:")
    print("     Add domain: instagram.com")
    print()

    if not scopes_ok:
        print("   🔐 OAuth & Permissions:")
        print("     Bot Token Scopes:")
        print("       - links:read")
        print("       - links:write")
        print("       - chat:write")
        print("     Then reinstall app to workspace")

    print()
    print("4. Test with Instagram link in Slack")


if __name__ == "__main__":
    main()
