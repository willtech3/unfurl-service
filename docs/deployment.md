# Deployment Guide

## Prerequisites

- AWS CLI configured with credentials
- AWS CDK CLI (`npm install -g aws-cdk`)
- Python 3.12+
- Docker
- Slack workspace admin access

## AWS Setup

### 1. Configure GitHub Secrets

Add these to your GitHub repository (Settings -> Secrets -> Actions):

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `LOGFIRE_TOKEN` (optional, for observability)

### 2. Store Slack Credentials

Create secret in AWS Secrets Manager:

```bash
aws secretsmanager create-secret \
  --region us-east-2 \
  --name unfurl-service/slack \
  --secret-string '{
    "signing_secret": "YOUR_SIGNING_SECRET",
    "bot_token": "xoxb-YOUR-BOT-TOKEN"
  }'
```

Get these values from your Slack app's Basic Information and OAuth pages.

### 3. Bootstrap CDK (first time only)

```bash
cdk bootstrap aws://ACCOUNT_ID/us-east-2
```

## Deployment

### Automated (Recommended)

Push to `main` branch. GitHub Actions will:
1. Run tests
2. Build container
3. Deploy via CDK

### Manual

```bash
# Deploy all stacks
cdk deploy --all --require-approval never
```

## Slack App Setup

See [slack_configuration.md](slack_configuration.md) for detailed Slack app settings.

Quick checklist:
1. Create Slack app at https://api.slack.com/apps
2. Add OAuth scopes: `links:read`, `links:write`, `chat:write`
3. Enable Event Subscriptions
4. Subscribe to `link_shared` event
5. Add `instagram.com` to App Unfurl Domains
6. Set Request URL to your API Gateway endpoint (from CDK output)
7. Install app to workspace

## Post-Deployment

### Get API Gateway URL

After deployment, find the URL in CDK output or CloudFormation console. Format:
```
https://{api-id}.execute-api.us-east-2.amazonaws.com/prod/slack/events
```

### Verify Slack Integration

1. Post an Instagram link in a Slack channel
2. Check CloudWatch logs if unfurl doesn't appear:
   ```bash
   aws logs tail /aws/lambda/unfurl-event-router-prod --follow
   aws logs tail /aws/lambda/unfurl-processor-prod --follow
   ```

## Troubleshooting

**Slack verification fails:**
- Check signing secret matches Secrets Manager value
- Check Lambda has internet access

**Links not unfurling:**
- Verify app is installed in workspace
- Check `instagram.com` is in App Unfurl Domains
- Verify OAuth scopes are correct

**Lambda timeouts:**
- Check CloudWatch logs for errors
- Default timeout may need adjustment in CDK stack

## Cleanup

```bash
# Delete stacks
cdk destroy --all

# Delete secrets
aws secretsmanager delete-secret \
  --region us-east-2 \
  --secret-id unfurl-service/slack \
  --force-delete-without-recovery
```
