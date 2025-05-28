"""Event router Lambda handler for Slack events."""

import json
import os
import hmac
import hashlib
import time
from typing import Dict, Any

import boto3
from botocore.exceptions import ClientError

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
tracer = Tracer()

# Only initialize metrics if not in test mode
if os.environ.get("DISABLE_METRICS") != "true":
    from aws_lambda_powertools import Metrics
    from aws_lambda_powertools.metrics import MetricUnit
    metrics = Metrics()
else:
    metrics = None


def get_sns_client():
    """Get SNS client."""
    return boto3.client("sns")


def get_secrets_client():
    """Get Secrets Manager client."""
    return boto3.client("secretsmanager")


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
            signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
    )
    
    # Compare signatures
    return hmac.compare_digest(my_signature, signature)


def get_slack_secret() -> Dict[str, str]:
    """Retrieve Slack secrets from AWS Secrets Manager."""
    secrets_client = get_secrets_client()
    
    try:
        response = secrets_client.get_secret_value(SecretId=os.environ.get("SLACK_SECRET_NAME", "unfurl-service/slack"))
        return json.loads(response["SecretString"])
    except Exception as e:
        logger.error(f"Error retrieving Slack secret: {str(e)}")
        raise


def lambda_handler_impl(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Handle incoming Slack events and route Instagram links to SNS."""
    try:
        # Parse the request body
        body = event.get("body", "")
        headers = event.get("headers", {})
        
        # Get Slack signature headers
        slack_signature = headers.get("X-Slack-Signature", "")
        slack_timestamp = headers.get("X-Slack-Request-Timestamp", "")
        
        # Get signing secret
        secrets = get_slack_secret()
        signing_secret = secrets.get("signing_secret", "")
        
        if not verify_slack_signature(body, slack_timestamp, slack_signature, signing_secret):
            logger.warning("Invalid Slack signature")
            if metrics:
                metrics.add_metric(name="InvalidSignature", unit=MetricUnit.Count, value=1)
            return {
                "statusCode": 403,
                "body": json.dumps({"error": "Invalid signature"})
            }
        
        # Parse the Slack event
        slack_event = json.loads(body)
        event_type = slack_event.get("type")
        
        # Handle URL verification challenge
        if event_type == "url_verification":
            challenge = slack_event.get("challenge")
            logger.info("Handling URL verification challenge")
            return {
                "statusCode": 200,
                "body": json.dumps({"challenge": challenge})
            }
        
        # Handle event callbacks
        if event_type == "event_callback":
            event_data = slack_event.get("event", {})
            
            # Only process link_shared events
            if event_data.get("type") == "link_shared":
                links = event_data.get("links", [])
                
                # Filter for Instagram links
                instagram_links = [
                    link for link in links
                    if link.get("domain") in ["instagram.com", "www.instagram.com"]
                ]
                
                if instagram_links:
                    # Publish to SNS for processing
                    sns_client = get_sns_client()
                    sns_topic_arn = os.environ.get("SNS_TOPIC_ARN", "")
                    
                    if not sns_topic_arn:
                        logger.error("SNS_TOPIC_ARN environment variable not set")
                        raise ValueError("SNS_TOPIC_ARN not configured")
                    
                    message = {
                        "channel": event_data.get("channel"),
                        "message_ts": event_data.get("message_ts"),
                        "links": instagram_links
                    }
                    
                    try:
                        response = sns_client.publish(
                            TopicArn=sns_topic_arn,
                            Message=json.dumps(message),
                            Subject="Instagram Link Unfurl Request"
                        )
                        logger.info(f"Published to SNS with MessageId: {response['MessageId']}")
                    except Exception as sns_error:
                        logger.error(f"Failed to publish to SNS: {str(sns_error)}")
                        raise
                    
                    logger.info(f"Published {len(instagram_links)} Instagram links to SNS")
                    if metrics:
                        metrics.add_metric(name="LinkSharedEvent", unit=MetricUnit.Count, value=1)
        
        return {
            "statusCode": 200,
            "body": json.dumps({"ok": True})
        }
        
    except Exception as e:
        logger.error(f"Error processing event: {str(e)}")
        if metrics:
            metrics.add_metric(name="ProcessingError", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"})
        }


@logger.inject_lambda_context(correlation_id_path="requestContext.requestId")
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler with decorators."""
    if metrics:
        # Apply metrics decorator
        @metrics.log_metrics(capture_cold_start_metric=True)
        def handler_with_metrics(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
            return lambda_handler_impl(event, context)
        return handler_with_metrics(event, context)
    else:
        # No metrics decorator
        return lambda_handler_impl(event, context)
