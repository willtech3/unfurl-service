# Instagram Unfurl Service for Slack

A high-performance, cost-efficient serverless service that automatically unfurls Instagram links posted in Slack channels using AWS Lambda and CDK.

## Architecture Overview

This service uses a fully serverless architecture optimized for speed and cost:

- **API Gateway** - Receives Slack events via webhooks
- **Lambda Functions** - Process events and fetch Instagram metadata via web scraping
- **SNS** - Decouples event reception from processing for reliability
- **DynamoDB** - Caches unfurled data to minimize scraping requests
- **Secrets Manager** - Securely stores Slack API credentials

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) for dependency management
- AWS CLI configured with appropriate credentials
- AWS CDK CLI (`npm install -g aws-cdk`)
- Slack App with event subscriptions enabled

## Project Structure

```
unfurl-service/
├── cdk/                    # CDK infrastructure code
│   ├── app.py             # CDK app entry point
│   └── stacks/            # CDK stack definitions
├── src/                    # Lambda function source code
│   ├── event_router/      # Handles incoming Slack events
│   └── unfurl_processor/  # Processes Instagram URLs via web scraping
├── tests/                  # Unit and integration tests
├── .github/workflows/      # GitHub Actions CI/CD
├── pyproject.toml        # Project configuration and dependencies
└── cdk.json               # CDK configuration
```

## How It Works

1. **Event Reception**: When a user posts an Instagram link in Slack, the Slack Events API sends a webhook to our API Gateway
2. **Event Routing**: The event router Lambda validates the request and publishes it to SNS for asynchronous processing
3. **URL Processing**: The unfurl processor Lambda:
   - Extracts the Instagram post ID from the URL
   - Checks DynamoDB cache for existing data
   - If not cached, scrapes the Instagram page for metadata (image, caption, username)
   - Falls back to oEmbed API if scraping fails
   - Formats the data into a Slack-compatible unfurl
4. **Response**: The formatted unfurl is sent back to Slack via the Web API
5. **Caching**: Successful unfurls are cached in DynamoDB with a 24-hour TTL

## Setup Instructions

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/unfurl-service.git
cd unfurl-service
```

### 2. Set up the development environment
```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
make setup
source .venv/bin/activate
make install-dev
```

### 3. Configure environment variables
Create a `.env` file in the root directory:
```env
AWS_ACCOUNT_ID=your-account-id
AWS_REGION=us-east-2
SLACK_APP_ID=your-slack-app-id
```

### 4. Set up AWS Secrets
Store your secrets in AWS Secrets Manager:
```bash
aws secretsmanager create-secret --name unfurl-service/slack \
    --secret-string '{"signing_secret":"xxx","bot_token":"xoxb-xxx"}'
```

## Local Development

### Running tests
```bash
pytest tests/ -v
```

### Linting and formatting
```bash
black src/ tests/
flake8 src/ tests/
mypy src/
```

## Deployment

For detailed deployment instructions, see [`DEPLOY.md`](./DEPLOY.md).

Quick start:
1. Run `./scripts/bootstrap-deployment.sh` to create AWS deployment user
2. Configure GitHub Secrets with AWS credentials
3. Create Slack app with proper permissions and event subscriptions
4. Store Slack secrets in AWS Secrets Manager
5. Deploy via GitHub Actions or `cdk deploy --all`
6. Configure Slack webhook URL with the deployed API Gateway endpoint

## Maintenance

#### View Logs
```bash
# Event router logs
aws logs tail /aws/lambda/unfurl-service-dev-event-router --region us-east-2

# Unfurl processor logs
aws logs tail /aws/lambda/unfurl-service-dev-unfurl-processor --region us-east-2
```

#### Update Deployment
```bash
# Pull latest changes
git pull origin main

# Deploy updates
cdk deploy --all
```

## Troubleshooting

1. **Slack URL Verification Fails**
   - Check CloudWatch logs for the event router Lambda
   - Ensure signing secret is correct in Secrets Manager

2. **Links Not Unfurling**
   - Verify bot has `links:read` scope
   - Check that app is installed in the workspace
   - Ensure domains are added in App Unfurl Domains

3. **Web Scraping Errors**
   - Verify Instagram page structure hasn't changed
   - Check that scraping fallbacks are working correctly

4. **Missing Secrets Error**
   - Verify secret names match: `unfurl-service/{env}/slack`
   - Check secrets exist in the correct region (us-east-2)

### Security Notes

- Delete `.env.deployment` after adding credentials to GitHub Secrets
- Monitor CloudWatch logs for any security issues

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
