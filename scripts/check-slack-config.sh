#!/bin/bash

# Script to check and update Slack configuration in AWS Secrets Manager
# This script helps diagnose the 'invalid_auth' error

set -e

# Configuration
SECRET_NAME="unfurl-service/slack"
REGION="us-east-2"

echo "🔍 Checking Instagram Unfurl Service Slack Configuration..."
echo "============================================================"

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS CLI not configured or no valid credentials"
    exit 1
fi

echo "✅ AWS CLI configured"

# Check if secret exists
echo
echo "📋 Checking if Slack secret exists in AWS Secrets Manager..."
if aws secretsmanager describe-secret --region $REGION --secret-id $SECRET_NAME &> /dev/null; then
    echo "✅ Secret '$SECRET_NAME' exists"
    
    # Get secret value (masked for security)
    echo
    echo "🔐 Current secret structure:"
    SECRET_VALUE=$(aws secretsmanager get-secret-value --region $REGION --secret-id $SECRET_NAME --query SecretString --output text)
    
    # Parse JSON and check for required fields
    if echo "$SECRET_VALUE" | jq -e '.bot_token' > /dev/null 2>&1; then
        BOT_TOKEN=$(echo "$SECRET_VALUE" | jq -r '.bot_token')
        if [[ $BOT_TOKEN == xoxb-* ]]; then
            echo "✅ bot_token exists and starts with 'xoxb-'"
        else
            echo "❌ bot_token exists but doesn't start with 'xoxb-' (invalid format)"
        fi
    else
        echo "❌ bot_token field missing"
    fi
    
    if echo "$SECRET_VALUE" | jq -e '.signing_secret' > /dev/null 2>&1; then
        echo "✅ signing_secret exists"
    else
        echo "❌ signing_secret field missing"
    fi
    
else
    echo "❌ Secret '$SECRET_NAME' does not exist"
    echo
    echo "To create the secret, follow these steps:"
    echo "1. Go to https://api.slack.com/apps"
    echo "2. Select your Instagram Unfurl app"
    echo "3. Get the Bot User OAuth Token from 'OAuth & Permissions'"
    echo "4. Get the Signing Secret from 'Basic Information'"
    echo "5. Run: aws secretsmanager create-secret --region $REGION --name $SECRET_NAME --secret-string '{\"signing_secret\":\"YOUR_SIGNING_SECRET\",\"bot_token\":\"xoxb-YOUR-BOT-TOKEN\"}'"
    exit 1
fi

echo
echo "🔧 Next steps to fix 'invalid_auth' error:"
echo "=========================================="
echo "1. Verify your Slack app has these OAuth scopes:"
echo "   - links:read"
echo "   - links:write" 
echo "   - chat:write"
echo
echo "2. Ensure the app is installed to your workspace"
echo
echo "3. If you've updated the app, reinstall it to get a new bot token"
echo
echo "4. Update the secret if needed:"
echo "   aws secretsmanager update-secret --region $REGION --secret-id $SECRET_NAME --secret-string '{\"signing_secret\":\"NEW_SIGNING_SECRET\",\"bot_token\":\"xoxb-NEW-BOT-TOKEN\"}'"
echo
echo "5. Check the app installation URL:"
echo "   https://slack.com/apps/YOUR_APP_ID"
echo
echo "6. After updating, redeploy the service to pick up changes"
