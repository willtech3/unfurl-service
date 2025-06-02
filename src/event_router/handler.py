"""Event router Lambda handler for Slack events."""

import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, cast

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

# Type imports for boto3
from botocore.client import BaseClient

logger = Logger()
tracer = Tracer()

# Only initialize metrics if not in test mode
metrics = None
if os.environ.get("DISABLE_METRICS") != "true":
    from aws_lambda_powertools import Metrics
    from aws_lambda_powertools.metrics import MetricUnit

    metrics = Metrics()

# Default AWS region to use when creating clients (helps unit tests)
DEFAULT_AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-2")


def get_sns_client() -> BaseClient:
    """Get SNS client."""
    return boto3.client("sns", region_name=DEFAULT_AWS_REGION)


def get_secrets_client() -> BaseClient:
    """Get Secrets Manager client."""
    return boto3.client("secretsmanager", region_name=DEFAULT_AWS_REGION)


def verify_slack_signature(
    body: str, timestamp: str, signature: str, signing_secret: str
) -> bool:
    """Verify the Slack request signature."""
    # Check timestamp to prevent replay attacks
    if abs(time.time() - float(timestamp)) > 60 * 5:
        logger.warning("Request timestamp is too old")
        return False

    # Create the signature base string
    sig_basestring = f"v0:{timestamp}:{body}"

    # Create a new HMAC object and compute the signature
    my_signature = (
        "v0="
        + hmac.new(
            signing_secret.encode(), sig_basestring.encode(), hashlib.sha256
        ).hexdigest()
    )

    # Compare signatures
    return hmac.compare_digest(my_signature, signature)


def get_slack_secret() -> Dict[str, str]:
    """Retrieve Slack secrets from AWS Secrets Manager."""
    secrets_client = get_secrets_client()

    try:
        response = secrets_client.get_secret_value(
            SecretId=os.environ.get("SLACK_SECRET_NAME", "unfurl-service/slack")
        )
        secret_string = json.loads(response["SecretString"])
        return cast(Dict[str, str], secret_string)
    except Exception as e:
        logger.error(f"Error retrieving Slack secret: {str(e)}")
        raise


@logger.inject_lambda_context(correlation_id_path="requestContext.requestId")
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler for Slack event routing."""
    logger.info("Received event", extra={"event": event})

    # Check if this is a URL verification challenge
    body_str = event.get("body", "{}")
    try:
        body = json.loads(body_str) if body_str else {}
    except json.JSONDecodeError:
        body = {}

    if body.get("type") == "url_verification":
        return {
            "statusCode": 200,
            "body": json.dumps({"challenge": body.get("challenge")}),
        }

    # Handle regular Slack events
    try:
        # Parse the request body
        headers = event.get("headers", {})

        # Get Slack signature headers
        slack_signature = headers.get("X-Slack-Signature", "")
        slack_timestamp = headers.get("X-Slack-Request-Timestamp", "")

        # Get signing secret
        secrets = get_slack_secret()
        signing_secret = secrets.get("signing_secret", "")

        if not verify_slack_signature(
            body_str, slack_timestamp, slack_signature, signing_secret
        ):
            logger.warning("Invalid Slack signature")
            return {"statusCode": 401, "body": json.dumps({"error": "Unauthorized"})}

        # Process the event
        event_data = body.get("event", {})
        event_type = event_data.get("type")

        if event_type == "link_shared":
            # Process link_shared events
            links = event_data.get("links", [])
            instagram_links = [
                link
                for link in links
                if link.get("domain") in ["instagram.com", "www.instagram.com"]
            ]

            if instagram_links:
                # Publish to SNS for processing
                sns_client = get_sns_client()
                sns_topic_arn = os.environ.get("SNS_TOPIC_ARN")

                if not sns_topic_arn:
                    logger.error("SNS_TOPIC_ARN not configured")
                    return {
                        "statusCode": 500,
                        "body": json.dumps({"error": "Internal server error"}),
                    }

                message = {
                    "channel": event_data.get("channel"),
                    "message_ts": event_data.get("message_ts"),
                    "unfurl_id": event_data.get("unfurl_id"),
                    "links": instagram_links,
                }

                sns_client.publish(
                    TopicArn=sns_topic_arn,
                    Message=json.dumps(message),
                    MessageAttributes={
                        "event_type": {"DataType": "String", "StringValue": event_type}
                    },
                )

                logger.info(
                    "Published Instagram links to SNS",
                    extra={
                        "links": instagram_links,
                        "channel": event_data.get("channel"),
                    },
                )

                if metrics:
                    metrics.add_metric(
                        name="LinksProcessed",
                        unit=MetricUnit.Count,
                        value=len(instagram_links),
                    )

        return {"statusCode": 200, "body": json.dumps({"status": "ok"})}

    except Exception as e:
        logger.error("Error processing event", extra={"error": str(e)})
        if metrics:
            metrics.add_metric(name="ProcessingErrors", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }
