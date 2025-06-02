# Slack Video Block Setup Guide

This guide explains how to enable playable Instagram videos in Slack unfurls using Slack's Video Block feature.

## Prerequisites

- Instagram unfurl service deployed with video proxy Lambda
- Slack app with proper OAuth scopes configured
- API Gateway endpoint accessible from the internet

## Required OAuth Scopes

Your Slack app **must** have the following OAuth scopes:

### Bot Token Scopes
- `links:read` - Read link sharing events
- `links:write` - Post unfurls to channels  
- `links:embed:write` - **NEW REQUIREMENT** - Embed videos using Video Block
- `chat:write` - Send messages (for unfurls)

### User Token Scopes
- `links:embed:write` - **NEW REQUIREMENT** - Required for video embedding

## Setup Instructions

### 1. Update Slack App Configuration

1. Go to [Slack API Apps](https://api.slack.com/apps)
2. Select your Instagram unfurl app
3. Navigate to **OAuth & Permissions**
4. Add the new required scopes:
   - `links:embed:write` (both Bot and User scopes)
5. **Reinstall the app** to your workspace to get updated permissions

### 2. Configure Unfurl Domains

1. In your Slack app settings, go to **Event Subscriptions**
2. Under **App Unfurl Domains**, add your API Gateway domain:
   - Format: `your-api-id.execute-api.region.amazonaws.com`
   - Example: `hpkllvgmr0.execute-api.us-east-2.amazonaws.com`

### 3. Update Slack Bot Token

After reinstalling the app with new scopes:

1. Copy the new **Bot User OAuth Token** from the OAuth & Permissions page
2. Update your AWS Secrets Manager secret with the new token:
   ```bash
   aws secretsmanager update-secret \
     --secret-id unfurl-service-slack-credentials-dev \
     --secret-string '{"bot_token":"xoxb-new-token-here","signing_secret":"your-signing-secret"}'
   ```

### 4. Deploy Updated Service

Deploy the updated service with video proxy support:

```bash
cd unfurl-service
cdk deploy
```

## How It Works

### Video Block Architecture

1. **Instagram Video Detection**: Service identifies video posts from Instagram
2. **Video Proxy**: Creates a secure proxy URL for the Instagram video
3. **Slack Video Block**: Uses Block Kit Video Block to embed playable videos
4. **iFrame Rendering**: Slack renders videos in embedded iframes

### Video Proxy Flow

```
Instagram Video URL → Video Proxy Lambda → HTML5 Player → Slack Video Block
```

### Example Video Block Structure

```json
{
  "type": "video",
  "video_url": "https://api-gateway.com/video/encoded-instagram-url",
  "alt_text": "Instagram video",
  "title": {
    "type": "plain_text",
    "text": "Video title"
  },
  "thumbnail_url": "https://instagram-thumbnail.jpg",
  "provider_name": "Instagram"
}
```

## Security Considerations

### Video URL Validation
- Only Instagram CDN URLs are proxied
- All video URLs are validated before proxying
- URL encoding prevents injection attacks

### Domain Restrictions
- Video proxy only serves to Slack domains
- `X-Frame-Options: ALLOWALL` enables iframe embedding
- Cache control headers optimize performance

### Access Control
- Videos maintain original Instagram access restrictions
- No authentication bypass - videos must be publicly accessible
- Proxy adds no additional access to private content

## Troubleshooting

### Videos Not Playing

1. **Check OAuth Scopes**: Ensure `links:embed:write` is granted
2. **Verify Unfurl Domains**: API Gateway domain must be in unfurl domains list
3. **Test Video URLs**: Check if Instagram videos are publicly accessible
4. **Check Logs**: Review CloudWatch logs for video proxy errors

### Common Issues

**Error: `invalid_blocks`**
- Solution: Verify Video Block structure matches Slack specification
- Check that `video_url` points to your proxy endpoint

**Error: `missing_scope`**  
- Solution: Add `links:embed:write` scope and reinstall app

**Error: `cannot_unfurl_message`**
- Solution: Ensure unfurl domain includes your API Gateway domain

### Testing Video Playback

1. Share an Instagram video link in Slack
2. Verify unfurl appears with video thumbnail
3. Click play button to test embedded playback
4. Check that video plays within Slack interface

## Performance Notes

- **Video Proxy Cache**: 6-hour TTL for video metadata
- **Memory Usage**: Video proxy uses 256MB (lightweight)
- **Latency**: ~200-500ms additional latency for video processing
- **Concurrency**: 50 concurrent video proxy executions

## Limitations

- **Instagram Authentication**: Only publicly accessible videos work
- **Video Size**: Large videos may load slowly in Slack
- **Browser Support**: Depends on Slack client video support
- **Mobile**: Video playback varies by mobile Slack app version

## Monitoring

Monitor video proxy performance:

```bash
# CloudWatch metrics
aws logs tail /aws/lambda/video-proxy-dev --follow

# Video proxy errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/video-proxy-dev \
  --filter-pattern "ERROR"
```

## Rollback Plan

If video playback causes issues:

1. **Disable Video Blocks**: Set `VIDEO_PROXY_BASE_URL=""` in Lambda environment
2. **Remove OAuth Scope**: Remove `links:embed:write` from app (optional)
3. **Fallback Mode**: Service automatically falls back to thumbnail + link

Video functionality is designed to fail gracefully - removing video support doesn't break existing unfurl functionality.
