"""Event router Lambda handler for Slack events.

Uses Logfire for unified observability - logs appear in both CloudWatch
(via console output) and Logfire platform (via OTLP).
"""

import hashlib
import hmac
import html
import json
import os
import time
from typing import Any, Dict, cast

import boto3
import logfire

# Type imports for boto3
from botocore.client import BaseClient
from opentelemetry.propagate import inject

# Configure Logfire with console output for CloudWatch
logfire.configure(
    service_name=os.getenv("LOGFIRE_SERVICE_NAME", "unfurl-service"),
    environment=os.getenv("LOGFIRE_ENV", os.getenv("ENV", "dev")),
    token=os.getenv("LOGFIRE_TOKEN"),
    distributed_tracing=True,  # Connect traces across API Gateway, Lambda, and SNS
    console=logfire.ConsoleOptions(
        colors="always",
        include_timestamps=True,
        verbose=True,
    ),
)

metrics = None  # consolidated metrics in Logfire

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
        logfire.warning("Request timestamp is too old")
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
    except Exception:
        logfire.exception("Error retrieving Slack secret")
        raise


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for Slack event routing."""
    logfire.info("Received event", event=event)

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
            logfire.warning("Invalid Slack signature")
            return {"statusCode": 401, "body": json.dumps({"error": "Unauthorized"})}

        # Process the event
        event_data = body.get("event", {})
        event_type = event_data.get("type")

        if event_type == "link_shared":
            # Slack emits a preliminary link_shared event while the user is still
            # composing their message. These events have `channel="COMPOSER"` as a
            # placeholder and **must not** be unfurled — attempting to do so results
            # in Slack returning `cannot_unfurl_message` and prevents the real
            # unfurl for the actual channel.  We therefore short-circuit early and
            # mark the event as handled.

            channel_id = event_data.get("channel")

            if channel_id == "COMPOSER":
                logfire.info(
                    "Ignoring COMPOSER link_shared event",
                    links=event_data.get("links", []),
                )

                # metrics consolidated in Logfire; no CloudWatch EMF emission

                return {
                    "statusCode": 200,
                    "body": json.dumps({"ignored": "COMPOSER channel"}),
                }

            # Process link_shared events
            links = event_data.get("links", [])
            instagram_links = [
                {
                    **link,
                    "url": html.unescape(
                        link.get("url", "")
                    ),  # Decode HTML entities like &amp; -> &
                }
                for link in links
                if link.get("domain") in ["instagram.com", "www.instagram.com"]
            ]

            if instagram_links:
                # Publish to SNS for processing
                sns_client = get_sns_client()
                sns_topic_arn = os.environ.get("SNS_TOPIC_ARN")

                if not sns_topic_arn:
                    logfire.error("SNS_TOPIC_ARN not configured")
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

                # Inject W3C trace context into SNS attributes for cross-Lambda tracing
                carrier: dict[str, str] = {}
                inject(carrier)
                msg_attrs = {
                    k: {"DataType": "String", "StringValue": v}
                    for k, v in carrier.items()
                }
                msg_attrs["event_type"] = {
                    "DataType": "String",
                    "StringValue": event_type,
                }

                sns_client.publish(
                    TopicArn=sns_topic_arn,
                    Message=json.dumps(message),
                    MessageAttributes=msg_attrs,
                )

                logfire.info(
                    "Published Instagram links to SNS",
                    links=instagram_links,
                    channel=event_data.get("channel"),
                )

                # Example Logfire metric
                logfire.metric_counter("links_processed").add(len(instagram_links))

        return {"statusCode": 200, "body": json.dumps({"status": "ok"})}

    except Exception:
        logfire.exception("Error processing event")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


# Wrap handler with Logfire's AWS Lambda instrumentation (in-place)
logfire.instrument_aws_lambda(lambda_handler)
