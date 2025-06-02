# Slack App Configuration Guide

## Overview
To enable Instagram link unfurls in Slack, you need to configure your Slack app with the correct Event Subscriptions and OAuth scopes.

## Required Configuration Steps

### 1. Access Your Slack App
1. Go to https://api.slack.com/apps
2. Select your app or create a new one

### 2. Configure Event Subscriptions
1. Navigate to **Event Subscriptions** in the left sidebar
2. Turn on **Enable Events**
3. Set the **Request URL** to:
   ```
   https://kn59lllvqb.execute-api.us-east-2.amazonaws.com/prod/slack/events
   ```

### 3. Subscribe to Bot Events
1. In the **Subscribe to bot events** section, click **Add Bot User Event**
2. Add the following event:
   - `link_shared` - A message was posted containing one or more links relevant to your application

### 4. Configure App Unfurl Domains
1. Still in **Event Subscriptions**, scroll down to **App Unfurl Domains**
2. Click **Add Domain**
3. Add: `instagram.com`

### 5. Configure OAuth Scopes
1. Navigate to **OAuth & Permissions** in the left sidebar
2. In the **Scopes** section under **Bot Token Scopes**, ensure you have:
   - `links:read` - View URLs in messages
   - `links:write` - Show unfurls in channels and conversations
   - `chat:write` - Send messages as app

### 6. Reinstall App (if scopes changed)
If you added new scopes in step 5:
1. Scroll to the top of **OAuth & Permissions**
2. Click **Reinstall App to Workspace**
3. Review and authorize the new permissions

### 7. Save Configuration
1. Make sure to **Save Changes** in Event Subscriptions
2. Wait for Slack to verify the Request URL (should show ✅ Verified)

## Testing
After configuration:
1. Share an Instagram link in a Slack channel
2. You should see a rich preview with video, title, description, and view count
3. If nothing appears, run the test script:
   ```bash
   python scripts/test-slack-events.py
   ```

## Troubleshooting

### No events received
- Check Event Subscriptions is enabled
- Verify Request URL is correct and verified
- Ensure `link_shared` event is subscribed
- Check that `instagram.com` is in App Unfurl Domains

### Missing scopes error
- Add required OAuth scopes: `links:read`, `links:write`, `chat:write`
- Reinstall the app after adding scopes

### API Gateway 502 error
- The Lambda function may have deployment issues
- Check CloudWatch logs for the event router Lambda
- Redeploy the CDK stack if needed

## Current Status
✅ **Instagram Scraping**: Working perfectly  
✅ **Slack Bot Token**: Valid and authenticated  
✅ **AWS Infrastructure**: Deployed and functional  
❌ **Event Subscriptions**: Needs configuration (this guide)  

The infrastructure is ready - you just need to configure the Slack app settings above.
