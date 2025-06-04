# Detailed Setup Guide

This guide provides step-by-step instructions for setting up the Instagram Unfurl Service.

## Prerequisites

### 1. AWS Account Setup
- Create an AWS account if you don't have one
- Configure AWS CLI with your credentials:
  ```bash
  aws configure
  ```
- Ensure you have appropriate IAM permissions for:
  - Lambda
  - API Gateway
  - DynamoDB
  - SNS
  - Secrets Manager
  - CloudFormation (for CDK)

### 2. Instagram App Setup

1. Go to [Facebook Developers](https://developers.facebook.com)
2. Create a new app or use an existing one
3. Add Instagram Basic Display product:
   - Go to Products → Add Product → Instagram Basic Display → Set Up
4. Configure Instagram Basic Display:
   - Add OAuth Redirect URIs (can be https://localhost for testing)
   - Add Deauthorize Callback URL
   - Add Data Deletion Request URL
5. Create an Instagram Test User:
   - Go to Roles → Test Users
   - Create a test user and get an access token
6. Generate Long-Lived Access Token:
   ```bash
   curl -X GET \
     "https://graph.instagram.com/access_token?grant_type=ig_exchange_token&client_secret={app-secret}&access_token={short-lived-access-token}"
   ```
7. Submit for App Review (for production):
   - Request `instagram_basic` permission

### 3. Slack App Setup

1. Go to [Slack API](https://api.slack.com/apps)
2. Create a new Slack App
3. Configure OAuth & Permissions:
   - Add Bot Token Scopes:
     - `links:read`
     - `links:write`
     - `chat:write`
4. Enable Event Subscriptions:
   - Turn on Enable Events
   - Add Bot Events:
     - `link_shared`
   - Add App Unfurl Domains:
     - `instagram.com`
     - `www.instagram.com`
5. Install App to Workspace
6. Save your credentials:
   - Bot User OAuth Token (starts with `xoxb-`)
   - Signing Secret

## Local Development Setup

### 1. Clone and Setup Repository
```bash
git clone https://github.com/yourusername/unfurl-service.git
cd unfurl-service
```

### 2. Install uv (Python Package Manager)
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using pip
pip install uv
```

### 3. Create Virtual Environment and Install Dependencies
```bash
# Setup virtual environment
make setup

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install all dependencies (including dev and CDK)
make install-dev
```

### 4. Setup Pre-commit Hooks
```bash
pre-commit install
```

### 5. Configure Environment Variables
Create a `.env` file:
```env
AWS_ACCOUNT_ID=123456789012
AWS_REGION=us-east-2
CDK_DEFAULT_ACCOUNT=123456789012
CDK_DEFAULT_REGION=us-east-2
```

### 6. Store Secrets in AWS

Store Slack secrets:
```bash
aws secretsmanager create-secret \
    --name unfurl-service/slack \
    --secret-string '{
        "signing_secret": "your-slack-signing-secret",
        "bot_token": "xoxb-your-bot-token"
    }'
```

Store Instagram secrets:
```bash
aws secretsmanager create-secret \
    --name unfurl-service/instagram \
    --secret-string '{
        "app_id": "your-instagram-app-id",
        "app_secret": "your-instagram-app-secret",
        "access_token": "your-long-lived-access-token"
    }'
```

## Deployment

### 1. Build Lambda Layer
```bash
make build-layer
```

### 2. Bootstrap CDK (first time only)
```bash
cdk bootstrap aws://ACCOUNT-NUMBER/REGION
```

### 3. Deploy Infrastructure
```bash
make deploy
# or with specific environment:
cdk deploy -c env=prod
```

### 4. Update Slack App Configuration
After deployment, get your API Gateway URL from the CDK output and update your Slack app:
1. Go to Event Subscriptions
2. Update Request URL to: `https://{api-id}.execute-api.{region}.amazonaws.com/prod/slack/events`
3. Slack will send a verification challenge - ensure it shows "Verified"

## Testing

### Run Unit Tests
```bash
make test
```

### Test Slack Integration
1. Post a message with an Instagram link in a channel where the bot is present
2. The bot should unfurl the link with a preview

### Monitor Logs
```bash
# Event Router logs
aws logs tail /aws/lambda/unfurl-event-router-prod --follow

# Unfurl Processor logs
aws logs tail /aws/lambda/unfurl-processor-prod --follow
```

## Development Workflow

### Code Formatting
```bash
# Check formatting
make lint

# Auto-format code
make format
```

### Generate Requirements Files
```bash
# Generate locked requirements files
make lock
```

### Clean Build Artifacts
```bash
make clean
```

## Python/Playwright Compatibility Matrix

This service uses Playwright for web scraping with specific compatibility requirements:

| Python Version | Playwright Version | Status | Notes |
|---|---|---|---|
| Python 3.12 | Playwright >= 1.45.0 | ✅ Supported | Full async_api support |
| Python 3.12 | Playwright < 1.45.0 | ❌ Not Supported | async_api import fails |
| Python 3.11 | Playwright >= 1.40.0 | ✅ Supported | Fully compatible |
| Python 3.10 | Playwright >= 1.40.0 | ✅ Supported | Fully compatible |

### Current Configuration
- **Python**: 3.12.9 (AWS Lambda base image)
- **Playwright**: 1.45.0 (requirements-docker.txt)
- **Docker Image**: mcr.microsoft.com/playwright/python:v1.45.0-jammy

### Key Requirements
1. **Version Alignment**: Dockerfile build stage and requirements.txt must specify the same Playwright version
2. **Python 3.12 Support**: Requires Playwright >= 1.45.0 for full async_api compatibility
3. **Browser Installation**: Uses official Playwright Docker image for proper browser setup

## Troubleshooting

### Common Issues

1. **Slack signature verification fails**
   - Ensure the signing secret in Secrets Manager matches your Slack app
   - Check that the request timestamp is within 5 minutes

2. **Instagram API errors**
   - Verify your access token is valid
   - Check Instagram API rate limits
   - Ensure the Instagram post is public

3. **Lambda timeouts**
   - Check CloudWatch logs for errors
   - Increase Lambda timeout in CDK stack if needed

4. **DynamoDB errors**
   - Ensure the Lambda has proper IAM permissions
   - Check if the table exists and is in the correct region

5. **uv installation issues**
   - Ensure you have curl installed
   - Try alternative installation methods from [uv documentation](https://github.com/astral-sh/uv)

6. **Playwright async_api import errors**
   - Ensure Playwright version in Dockerfile matches requirements-docker.txt
   - For Python 3.12, use Playwright >= 1.45.0
   - Run the included test: `python test_playwright_fix.py`
   - Check that browser installation completed successfully

7. **Playwright browser execution failures**
   - Verify browsers are installed in correct path: `/var/task/playwright-browsers`
   - Check PLAYWRIGHT_BROWSERS_PATH environment variable
   - Ensure browser executables have proper permissions
   - For Lambda, verify required system dependencies are installed

### Debug Mode
Enable debug logging by setting environment variable:
```bash
LOG_LEVEL=DEBUG
```

## Monitoring

### CloudWatch Dashboards
Create a custom dashboard to monitor:
- Lambda invocations and errors
- API Gateway requests
- DynamoDB read/write capacity
- SNS message publishing

### Alarms
The stack creates alarms for:
- Lambda error rates
- API Gateway 4xx/5xx errors
- DynamoDB throttling

## Cost Optimization Tips

1. **Use Lambda Reserved Concurrency** - Set appropriate limits to prevent runaway costs
2. **Enable DynamoDB Auto-scaling** - For production workloads
3. **Set CloudWatch Log Retention** - Don't keep logs forever
4. **Monitor AWS Cost Explorer** - Set up budget alerts

## Security Best Practices

1. **Rotate Secrets Regularly** - Use AWS Secrets Manager rotation
2. **Least Privilege IAM** - Review and minimize Lambda permissions
3. **Enable AWS GuardDuty** - For threat detection
4. **Use AWS WAF** - Protect API Gateway from common attacks
5. **Enable VPC Flow Logs** - If using VPC endpoints

## Using uv for Dependency Management

This project uses [uv](https://github.com/astral-sh/uv) for fast, reliable Python dependency management.

### Common uv Commands
```bash
# Install a package
uv pip install package-name

# Install from pyproject.toml
uv pip install -e .

# Install with extras
uv pip install -e ".[dev,cdk]"

# Compile requirements
uv pip compile pyproject.toml -o requirements.txt

# Create virtual environment
uv venv
```

### Benefits of uv
- **Fast**: 10-100x faster than pip
- **Reliable**: Consistent dependency resolution
- **Compatible**: Drop-in replacement for pip
- **Modern**: Built with Rust for performance
