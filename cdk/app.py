#!/usr/bin/env python3
import os
from aws_cdk import App, Environment, Tags, DefaultStackSynthesizer
from stacks.unfurl_service_stack import UnfurlServiceStack

app = App()

# Get environment from context or environment variables
env_name = app.node.try_get_context("env") or os.environ.get("CDK_ENV", "dev")
account = app.node.try_get_context("account") or os.environ.get("CDK_DEFAULT_ACCOUNT")
region = app.node.try_get_context("region") or os.environ.get(
    "CDK_DEFAULT_REGION", "us-east-2"
)

# Create the stack
stack = UnfurlServiceStack(
    app,
    f"UnfurlService-{env_name}",
    env=Environment(account=account, region=region),
    description="Instagram link unfurl service for Slack",
    synthesizer=DefaultStackSynthesizer(
        qualifier=os.environ.get("CDK_QUALIFIER", "unfurl")
    ),
)

# Add tags
Tags.of(stack).add("Project", "unfurl-service")
Tags.of(stack).add("Environment", env_name)
Tags.of(stack).add("ManagedBy", "CDK")

app.synth()
