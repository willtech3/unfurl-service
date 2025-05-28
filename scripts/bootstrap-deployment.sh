#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Instagram Unfurl Service - Deployment Bootstrap${NC}"
echo "================================================"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    echo "Please install AWS CLI: https://aws.amazon.com/cli/"
    exit 1
fi

# Check if AWS credentials are configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}Error: AWS credentials not configured${NC}"
    echo "Please run 'aws configure' with your AWS root or admin credentials"
    exit 1
fi

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=${AWS_REGION:-us-east-2}

echo -e "${YELLOW}AWS Account ID:${NC} $ACCOUNT_ID"
echo -e "${YELLOW}Region:${NC} $REGION"
echo ""

# Create minimal IAM policy for CDK deployment
echo -e "${GREEN}Creating IAM policy for CDK deployment...${NC}"
POLICY_ARN=$(aws iam create-policy \
    --policy-name UnfurlServiceCDKDeploymentPolicy \
    --description "Minimal policy for deploying Instagram Unfurl Service via CDK" \
    --policy-document '{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sts:AssumeRole"
      ],
      "Resource": [
        "arn:aws:iam::*:role/cdk-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:*"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:*"
      ],
      "Resource": [
        "arn:aws:s3:::cdk-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:*"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter"
      ],
      "Resource": [
        "arn:aws:ssm:*:*:parameter/cdk-bootstrap/*"
      ]
    }
  ]
}' \
    --query 'Policy.Arn' \
    --output text 2>/dev/null || \
    aws iam list-policies --query "Policies[?PolicyName=='UnfurlServiceCDKDeploymentPolicy'].Arn | [0]" --output text)

echo -e "${GREEN}Policy ARN:${NC} $POLICY_ARN"

# Create IAM user
echo -e "${GREEN}Creating IAM user for CDK deployment...${NC}"
aws iam create-user --user-name unfurl-service-cdk-deploy 2>/dev/null || echo "User already exists"

# Attach policies
echo -e "${GREEN}Attaching policies...${NC}"
aws iam attach-user-policy \
    --user-name unfurl-service-cdk-deploy \
    --policy-arn "$POLICY_ARN"

aws iam attach-user-policy \
    --user-name unfurl-service-cdk-deploy \
    --policy-arn "arn:aws:iam::aws:policy/PowerUserAccess"

# Create access key
echo -e "${GREEN}Creating access key...${NC}"
ACCESS_KEY_JSON=$(aws iam create-access-key --user-name unfurl-service-cdk-deploy --query 'AccessKey')

ACCESS_KEY_ID=$(echo "$ACCESS_KEY_JSON" | jq -r '.AccessKeyId')
SECRET_ACCESS_KEY=$(echo "$ACCESS_KEY_JSON" | jq -r '.SecretAccessKey')

# Save to .env file
echo -e "${GREEN}Saving credentials to .env.deployment${NC}"
cat > .env.deployment << EOF
# CDK Deployment Credentials
# IMPORTANT: Keep this file secure and never commit to git!
AWS_ACCESS_KEY_ID=$ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=$SECRET_ACCESS_KEY
AWS_REGION=$REGION
CDK_DEFAULT_ACCOUNT=$ACCOUNT_ID
CDK_DEFAULT_REGION=$REGION
EOF

chmod 600 .env.deployment

echo ""
echo -e "${GREEN}✅ Bootstrap complete!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Add these to your GitHub Secrets:"
echo "   AWS_ACCOUNT_ID=$ACCOUNT_ID"
echo "   AWS_ACCESS_KEY_ID=$ACCESS_KEY_ID"
echo "   AWS_SECRET_ACCESS_KEY=$SECRET_ACCESS_KEY"
echo ""
echo "2. For local deployment, run:"
echo "   source .env.deployment"
echo "   cdk bootstrap aws://$ACCOUNT_ID/$REGION"
echo "   cdk deploy --all"
echo ""
echo -e "${RED}⚠️  Security Notes:${NC}"
echo "- The .env.deployment file contains sensitive credentials"
echo "- It's already added to .gitignore"
echo "- Delete it after adding to GitHub Secrets"
echo "- The deployment user has PowerUserAccess (can create any AWS resource)"
echo "- For production, consider using more restrictive policies"
