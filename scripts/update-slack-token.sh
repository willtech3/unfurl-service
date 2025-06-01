#!/bin/bash

# Script to update Slack bot token in AWS Secrets Manager
# Usage: ./update-slack-token.sh <new_bot_token> <signing_secret>

set -e

NEW_BOT_TOKEN="$1"
SIGNING_SECRET="$2"

if [ -z "$NEW_BOT_TOKEN" ] || [ -z "$SIGNING_SECRET" ]; then
    echo "❌ Usage: $0 <new_bot_token> <signing_secret>"
    echo ""
    echo "Example:"
    echo "  $0 xoxb-1234567890-abcdef... abc123def456..."
    echo ""
    echo "📋 To get these values:"
    echo "1. Go to https://api.slack.com/apps"
    echo "2. Select your Instagram Unfurl app" 
    echo "3. Bot Token: OAuth & Permissions > Bot User OAuth Token"
    echo "4. Signing Secret: Basic Information > Signing Secret"
    exit 1
fi

if [[ ! "$NEW_BOT_TOKEN" =~ ^xoxb- ]]; then
    echo "❌ Invalid bot token format. Must start with 'xoxb-'"
    exit 1
fi

echo "🔧 Updating Slack credentials in AWS Secrets Manager..."

# Create the secret JSON
SECRET_JSON=$(cat <<EOF
{
    "bot_token": "$NEW_BOT_TOKEN",
    "signing_secret": "$SIGNING_SECRET"
}
EOF
)

# Update the secret
aws secretsmanager update-secret \
    --region us-east-2 \
    --secret-id unfurl-service/slack \
    --secret-string "$SECRET_JSON"

echo "✅ Slack credentials updated successfully!"
echo ""
echo "🚀 Next steps:"
echo "1. Test the new token:"
echo "   python scripts/test-slack-auth.py"
echo ""
echo "2. If the test passes, redeploy the service:"
echo "   git add ."
echo "   git commit -m 'Update Slack bot token'"
echo "   git push"
echo ""
echo "3. Test with a real Instagram link in your Slack channel"
