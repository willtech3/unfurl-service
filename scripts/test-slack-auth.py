#!/usr/bin/env python3
"""
Test Slack API authentication and check OAuth scopes
"""
import json
import boto3
import requests
from typing import Dict, Any


def get_slack_credentials() -> Dict[str, str]:
    """Get Slack credentials from AWS Secrets Manager"""
    secrets_client = boto3.client('secretsmanager', region_name='us-east-2')
    
    try:
        response = secrets_client.get_secret_value(SecretId='unfurl-service/slack')
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"❌ Error getting Slack credentials: {e}")
        return {}


def test_slack_auth(bot_token: str) -> None:
    """Test Slack bot token authentication and scopes"""
    print(f"🧪 Testing bot token: {bot_token[:20]}...")
    
    # Test auth.test endpoint
    auth_response = requests.get(
        'https://slack.com/api/auth.test',
        headers={'Authorization': f'Bearer {bot_token}'}
    )
    
    print(f"\n📊 Auth Test Response:")
    print(f"Status Code: {auth_response.status_code}")
    
    try:
        auth_data = auth_response.json()
        print(f"Response: {json.dumps(auth_data, indent=2)}")
        
        if auth_data.get('ok'):
            print(f"✅ Authentication successful!")
            print(f"Bot User ID: {auth_data.get('user_id')}")
            print(f"Team: {auth_data.get('team')}")
            print(f"Team ID: {auth_data.get('team_id')}")
        else:
            print(f"❌ Authentication failed: {auth_data.get('error')}")
    except Exception as e:
        print(f"❌ Error parsing auth response: {e}")
        print(f"Raw response: {auth_response.text}")
    
    # Test a simple API call to check scopes
    print(f"\n🔍 Testing chat.unfurl permissions:")
    test_response = requests.post(
        'https://slack.com/api/chat.unfurl',
        headers={'Authorization': f'Bearer {bot_token}'},
        json={
            'channel': 'C01H1D9KUGK',  # Test channel from logs
            'ts': '1234567890.123456',  # Dummy timestamp
            'unfurls': {}  # Empty unfurls to test auth
        }
    )
    
    try:
        test_data = test_response.json()
        print(f"Unfurl Test Response: {json.dumps(test_data, indent=2)}")
        
        if test_data.get('error') == 'invalid_auth':
            print("❌ Bot token lacks required OAuth scopes for chat.unfurl")
        elif test_data.get('error') == 'message_not_found':
            print("✅ Bot token has chat.unfurl permission (message not found is expected)")
        else:
            print(f"Unexpected response: {test_data.get('error', 'unknown')}")
            
    except Exception as e:
        print(f"❌ Error testing unfurl: {e}")


def main():
    print("🔧 Slack Authentication Test")
    print("=" * 50)
    
    credentials = get_slack_credentials()
    if not credentials:
        print("❌ Could not retrieve Slack credentials")
        return
    
    bot_token = credentials.get('bot_token')
    if not bot_token:
        print("❌ No bot_token found in credentials")
        return
    
    if not bot_token.startswith('xoxb-'):
        print(f"❌ Invalid bot token format: {bot_token[:10]}...")
        return
    
    test_slack_auth(bot_token)
    
    print(f"\n📋 Next Steps if Authentication Failed:")
    print("1. Go to https://api.slack.com/apps")
    print("2. Select your Instagram Unfurl app")
    print("3. Go to 'OAuth & Permissions'")
    print("4. Ensure these scopes are added:")
    print("   - links:read")
    print("   - links:write") 
    print("   - chat:write")
    print("5. Reinstall the app to your workspace")
    print("6. Copy the new Bot User OAuth Token")
    print("7. Update AWS Secrets Manager with the new token")


if __name__ == "__main__":
    main()
