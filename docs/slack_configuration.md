# Slack App Configuration

## Setup Steps

### 1. Create or Access Your App

Go to https://api.slack.com/apps and select your app or create a new one.

### 2. Configure OAuth Scopes

Navigate to **OAuth & Permissions** and add these Bot Token Scopes:

- `links:read` - View URLs in messages
- `links:write` - Show unfurls in channels
- `chat:write` - Send messages

### 3. Enable Event Subscriptions

Navigate to **Event Subscriptions**:

1. Turn on **Enable Events**
2. Set **Request URL** to your API Gateway endpoint:
   ```
   https://<api-id>.execute-api.<region>.amazonaws.com/prod/slack/events
   ```
3. Wait for Slack to verify the endpoint

### 4. Subscribe to Bot Events

In **Subscribe to bot events**, add:

- `link_shared`

### 5. Add Unfurl Domains

In **App Unfurl Domains**, add:

- `instagram.com`

### 6. Install App

1. Go to **OAuth & Permissions**
2. Click **Install App to Workspace** (or reinstall if scopes changed)
3. Authorize the permissions

### 7. Save Changes

Click **Save Changes** in Event Subscriptions.

## Testing

1. Post an Instagram link in a Slack channel where the app is installed
2. The link should unfurl with a preview

## Troubleshooting

**No events received:**
- Verify Event Subscriptions is enabled and URL is verified
- Check `link_shared` event is subscribed
- Confirm `instagram.com` is in App Unfurl Domains

**Missing scopes error:**
- Add required OAuth scopes
- Reinstall the app after adding scopes

**502 errors:**
- Check CloudWatch logs for the event router Lambda
- Verify AWS infrastructure is deployed
