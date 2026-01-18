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

**Web scraping errors:**
- Instagram's HTML structure may have changed
- Review CloudWatch logs for specific errors
- Check Logfire traces for scraper fallback patterns

**Performance issues:**
- Check DynamoDB cache hit rate
- Monitor Lambda cold starts
- Consider increasing Lambda memory/timeout

### Metrics

Metrics are consolidated in Logfire. Custom CloudWatch metrics have been
removed to reduce duplication and cost. See `docs/LOGFIRE.md` and the
centralized instruments in `src/observability/metrics.py`.

## Security Considerations

- Secrets are stored in AWS Secrets Manager
- Lambda functions have minimal IAM permissions
- All traffic is encrypted via HTTPS
- DynamoDB encryption at rest is enabled
- CloudWatch logs are retained for 7 days

## Cost Optimization

The service is designed to be cost-efficient:
- Lambda functions only run when links are shared
- DynamoDB uses on-demand billing
- 24-hour cache reduces redundant scraping
- Reserved concurrency prevents runaway costs

Estimated monthly cost for moderate usage (10K unfurls):
- Lambda: ~$2
- DynamoDB: ~$1
- API Gateway: ~$3
- Total: ~$6/month

## Updating the Service

To update the deployed service:

1. Make code changes
2. Push to main branch (for GitHub Actions)
3. Or run `cdk deploy --all` manually

CDK will only update changed resources, minimizing deployment time.

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
