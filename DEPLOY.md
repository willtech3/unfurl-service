# Instagram Unfurl Service - Deployment Guide

This guide provides step-by-step instructions for deploying the Instagram Unfurl Service to AWS.

## Prerequisites

- AWS CLI configured with appropriate credentials
- AWS CDK CLI installed (`npm install -g aws-cdk`)
- Python 3.12+
- GitHub account (for CI/CD)
- Slack workspace with admin access

## Architecture Overview

The service uses AWS serverless components:
- **API Gateway** - Receives Slack event webhooks
- **Lambda Functions** - Process events and scrape Instagram data
- **SNS** - Decouples event processing
- **DynamoDB** - Caches unfurl data
- **Secrets Manager** - Stores Slack credentials

## Deployment Steps

### 1. Create AWS Deployment User

Run the bootstrap script to create an IAM user for deployments:

```bash
./scripts/bootstrap-deployment.sh
```

This will:
- Create an IAM user `unfurl-service-deploy`
- Attach necessary policies
- Generate access keys
- Save credentials to `.env.deployment`

### 2. Configure GitHub Secrets

Add the following secrets to your GitHub repository:

1. Go to Settings → Secrets and variables → Actions
2. Add these repository secrets:
   - `AWS_ACCESS_KEY_ID` - From `.env.deployment`
   - `AWS_SECRET_ACCESS_KEY` - From `.env.deployment`
   - `AWS_ACCOUNT_ID` - Your AWS account ID
   - `SLACK_APP_ID` - Your Slack app ID

### 3. Create Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click "Create New App" → "From scratch"
3. Name it "Instagram Unfurl" and select your workspace

#### Configure OAuth & Permissions:
1. Go to "OAuth & Permissions"
2. Add these Bot Token Scopes:
   - `links:read` - Read URLs in messages
   - `links:write` - Unfurl URLs
   - `chat:write` - Send messages

3. Install the app to your workspace
4. Copy the "Bot User OAuth Token" (starts with `xoxb-`)

#### Configure Event Subscriptions:
1. Go to "Event Subscriptions"
2. Enable Events
3. You'll add the Request URL after deployment
4. Subscribe to bot events:
   - `link_shared`

#### Configure App Unfurl Domains:
1. Go to "Event Subscriptions" → "App Unfurl Domains"
2. Add these domains:
   - `instagram.com`
   - `www.instagram.com`

### 4. Store Slack Secrets in AWS

Create the Slack secret in AWS Secrets Manager:

```bash
# Get your Slack app's signing secret from Basic Information page
aws secretsmanager create-secret \
  --region us-east-2 \
  --name unfurl-service/slack \
  --secret-string '{
    "signing_secret": "YOUR_SIGNING_SECRET",
    "bot_token": "xoxb-YOUR-BOT-TOKEN"
  }'
```

### 5. Deploy the Service

#### Option A: Deploy via GitHub Actions (Recommended)

1. Push your code to the main branch
2. GitHub Actions will automatically:
   - Run tests
   - Build Lambda layers
   - Deploy CDK stacks
   - Output the API Gateway URL

#### Option B: Deploy Manually

```bash
# Bootstrap CDK (first time only)
cdk bootstrap aws://YOUR_ACCOUNT_ID/us-east-2

# Deploy all stacks
cdk deploy --all --require-approval never
```

### 6. Configure Slack Webhook URL

After deployment:

1. Get the API Gateway URL from the CDK output or CloudFormation console
2. In your Slack app settings, go to "Event Subscriptions"
3. Enter the Request URL: `https://YOUR_API_ID.execute-api.us-east-2.amazonaws.com/prod/slack/events`
4. Slack will verify the endpoint
5. Save the settings

### 7. Test the Integration

1. In any Slack channel where the app is installed, post an Instagram link:
   ```
   Check out this post: https://www.instagram.com/p/ABC123/
   ```

2. The service should automatically unfurl the link showing:
   - Post image
   - Caption
   - Username
   - Engagement metrics (if available)

## Environment-Specific Deployments

The service supports multiple environments (dev, staging, prod):

```bash
# Deploy to specific environment
cdk deploy --all -c environment=staging
```

Each environment has isolated resources:
- Separate Lambda functions
- Separate DynamoDB tables
- Environment-specific secrets

## Monitoring & Troubleshooting

### View Lambda Logs

```bash
# Event router logs
aws logs tail /aws/lambda/unfurl-event-router-prod --follow

# Unfurl processor logs
aws logs tail /aws/lambda/unfurl-processor-prod --follow
```

### Common Issues

1. **Slack verification fails**
   - Check the signing secret is correct
   - Verify the Lambda function has internet access
   - Check CloudWatch logs for errors

2. **Links not unfurling**
   - Ensure the app is installed in the workspace
   - Verify domains are added in App Unfurl Domains
   - Check that the bot has proper permissions

3. **Web scraping errors**
   - Instagram's HTML structure may have changed
   - Check if the fallback oEmbed API is working
   - Review CloudWatch logs for specific errors

4. **Performance issues**
   - Check DynamoDB cache hit rate
   - Monitor Lambda cold starts
   - Consider increasing Lambda memory/timeout

### Metrics

The service publishes metrics to CloudWatch:
- `InstagramDataFetched` - Successful scrapes
- `InstagramFetchError` - Failed scrapes
- `UnfurlSuccess` - Successful unfurls sent to Slack
- `SlackAPIError` - Slack API failures

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

To remove all resources:

```bash
# Delete all stacks
cdk destroy --all

# Delete secrets
aws secretsmanager delete-secret \
  --region us-east-2 \
  --secret-id unfurl-service/slack \
  --force-delete-without-recovery

# Delete deployment user (optional)
aws iam delete-access-key \
  --user-name unfurl-service-deploy \
  --access-key-id YOUR_ACCESS_KEY_ID

aws iam delete-user-policy \
  --user-name unfurl-service-deploy \
  --policy-name unfurl-service-deploy-policy

aws iam delete-user --user-name unfurl-service-deploy
```

## Support

For issues or questions:
1. Check CloudWatch logs first
2. Review this guide for common issues
3. Check the README for development setup
4. Open an issue on GitHub with logs and error details
