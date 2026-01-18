"""Tests for the event router Lambda handler."""

import base64
import hashlib
import hmac
import json
import time
from unittest.mock import patch

from moto import mock_secretsmanager, mock_sns

from src.event_router.handler import lambda_handler, verify_slack_signature


class MockLambdaContext:
    """Mock Lambda context for testing."""

    def __init__(self):
        self.function_name = "test-function"
        self.function_version = "1"
        self.invoked_function_arn = (
            "arn:aws:lambda:us-east-1:123456789012:function:test-function"
        )
        self.memory_limit_in_mb = 128
        self.aws_request_id = "test-request-id"
        self.log_group_name = "/aws/lambda/test-function"
        self.log_stream_name = "2021/01/01/[$LATEST]test-stream"


class TestEventRouter:
    """Test cases for the event router Lambda function."""

    def test_verify_slack_signature_valid(self):
        """Test signature verification with valid signature."""
        body = "test body"
        timestamp = str(int(time.time()))
        secret = "test_secret"

        # Generate valid signature
        sig_basestring = f"v0:{timestamp}:{body}"
        expected_sig = (
            "v0="
            + hmac.new(
                secret.encode(), sig_basestring.encode(), hashlib.sha256
            ).hexdigest()
        )

        assert verify_slack_signature(body, timestamp, expected_sig, secret) is True

    def test_verify_slack_signature_invalid(self):
        """Test signature verification with invalid signature."""
        body = "test body"
        timestamp = str(int(time.time()))
        secret = "test_secret"

        # Invalid signature
        invalid_sig = "v0=invalid_signature"

        assert verify_slack_signature(body, timestamp, invalid_sig, secret) is False

    def test_verify_slack_signature_old_timestamp(self):
        """Test signature verification with old timestamp."""
        body = "test body"
        # Timestamp from 10 minutes ago
        timestamp = str(int(time.time()) - 600)
        secret = "test_secret"

        sig_basestring = f"v0:{timestamp}:{body}"
        sig = (
            "v0="
            + hmac.new(
                secret.encode(), sig_basestring.encode(), hashlib.sha256
            ).hexdigest()
        )

        assert verify_slack_signature(body, timestamp, sig, secret) is False

    def test_verify_slack_signature_invalid_timestamp(self):
        """Test signature verification with invalid timestamp."""
        assert (
            verify_slack_signature(
                body="{}",
                timestamp="not-a-timestamp",
                signature="v0=x",
                signing_secret="x",
            )
            is False
        )

    @mock_secretsmanager
    def test_get_slack_secret(self):
        """Test retrieving Slack secrets from Secrets Manager."""
        import boto3

        from src.event_router.handler import get_slack_secret

        # Setup mock secret
        sm = boto3.client("secretsmanager", region_name="us-east-2")
        secret_data = {
            "signing_secret": "test_signing_secret",
            "bot_token": "xoxb-test-token",
        }
        sm.create_secret(
            Name="unfurl-service/slack", SecretString=json.dumps(secret_data)
        )

        with patch.dict(
            "os.environ",
            {
                "SLACK_SECRET_NAME": "unfurl-service/slack",
                "AWS_DEFAULT_REGION": "us-east-2",
            },
        ):
            result = get_slack_secret()
            assert result == secret_data

    @mock_secretsmanager
    def test_lambda_handler_url_verification(self):
        """Test handling URL verification challenge."""
        import boto3

        # Setup mock secret
        sm = boto3.client("secretsmanager", region_name="us-east-2")
        sm.create_secret(
            Name="unfurl-service/slack",
            SecretString=json.dumps(
                {"signing_secret": "test_secret", "bot_token": "xoxb-test"}
            ),
        )

        # Create test event
        challenge = "test_challenge_value"
        body = json.dumps({"type": "url_verification", "challenge": challenge})

        timestamp = str(int(time.time()))
        sig_basestring = f"v0:{timestamp}:{body}"
        signature = (
            "v0="
            + hmac.new(
                b"test_secret", sig_basestring.encode(), hashlib.sha256
            ).hexdigest()
        )

        event = {
            "body": body,
            "headers": {
                "X-Slack-Signature": signature,
                "X-Slack-Request-Timestamp": timestamp,
            },
        }

        with patch.dict(
            "os.environ",
            {
                "SLACK_SECRET_NAME": "unfurl-service/slack",
                "SNS_TOPIC_ARN": "arn:aws:sns:us-east-2:123456789012:test-topic",
                "POWERTOOLS_METRICS_NAMESPACE": "UnfurlService",
                "DISABLE_METRICS": "true",
                "AWS_DEFAULT_REGION": "us-east-2",
            },
        ):
            response = lambda_handler(event, MockLambdaContext())

        assert response["statusCode"] == 200
        assert json.loads(response["body"])["challenge"] == challenge

    @mock_secretsmanager
    def test_lambda_handler_url_verification_base64_body(self):
        """Test handling base64-encoded URL verification challenge."""
        import boto3

        sm = boto3.client("secretsmanager", region_name="us-east-2")
        sm.create_secret(
            Name="unfurl-service/slack",
            SecretString=json.dumps(
                {"signing_secret": "test_secret", "bot_token": "xoxb-test"}
            ),
        )

        challenge = "test_challenge_value"
        raw_body = json.dumps({"type": "url_verification", "challenge": challenge})
        body_b64 = base64.b64encode(raw_body.encode("utf-8")).decode("utf-8")

        timestamp = str(int(time.time()))
        sig_basestring = f"v0:{timestamp}:{raw_body}"
        signature = (
            "v0="
            + hmac.new(
                b"test_secret", sig_basestring.encode(), hashlib.sha256
            ).hexdigest()
        )

        event = {
            "body": body_b64,
            "isBase64Encoded": True,
            "headers": {
                "X-Slack-Signature": signature,
                "X-Slack-Request-Timestamp": timestamp,
            },
        }

        with patch.dict(
            "os.environ",
            {
                "SLACK_SECRET_NAME": "unfurl-service/slack",
                "SNS_TOPIC_ARN": "arn:aws:sns:us-east-2:123456789012:test-topic",
                "POWERTOOLS_METRICS_NAMESPACE": "UnfurlService",
                "DISABLE_METRICS": "true",
                "AWS_DEFAULT_REGION": "us-east-2",
            },
        ):
            response = lambda_handler(event, MockLambdaContext())

        assert response["statusCode"] == 200
        assert json.loads(response["body"])["challenge"] == challenge

    @mock_secretsmanager
    @mock_sns
    def test_lambda_handler_link_shared_event(self):
        """Test handling link_shared event with Instagram URL."""
        import boto3

        # Setup mock secret
        sm = boto3.client("secretsmanager", region_name="us-east-2")
        sm.create_secret(
            Name="unfurl-service/slack",
            SecretString=json.dumps(
                {"signing_secret": "test_secret", "bot_token": "xoxb-test"}
            ),
        )

        # Create test event
        slack_event = {
            "type": "event_callback",
            "event_id": "Ev123456",
            "team_id": "T123456",
            "event": {
                "type": "link_shared",
                "channel": "C123456",
                "message_ts": "1234567890.123456",
                "links": [
                    {
                        "url": "https://www.instagram.com/p/ABC123/",
                        "domain": "instagram.com",
                    },
                    {
                        "url": "https://www.google.com",
                        "domain": "google.com",
                    },  # Non-Instagram URL
                ],
            },
        }

        # Create SNS topic for mock
        import boto3

        sns = boto3.client("sns", region_name="us-east-2")
        topic_response = sns.create_topic(Name="test-topic")
        topic_arn = topic_response["TopicArn"]

        with patch.dict(
            "os.environ",
            {
                "SLACK_SECRET_NAME": "unfurl-service/slack",
                "SNS_TOPIC_ARN": topic_arn,
                "POWERTOOLS_METRICS_NAMESPACE": "UnfurlService",
                "DISABLE_METRICS": "true",
                "AWS_DEFAULT_REGION": "us-east-2",
            },
        ):
            # Create test event with signature
            body = json.dumps(slack_event)
            timestamp = str(int(time.time()))
            sig_basestring = f"v0:{timestamp}:{body}"
            signature = (
                "v0="
                + hmac.new(
                    b"test_secret", sig_basestring.encode(), hashlib.sha256
                ).hexdigest()
            )

            event = {
                "body": body,
                "headers": {
                    "X-Slack-Signature": signature,
                    "X-Slack-Request-Timestamp": timestamp,
                },
            }

            response = lambda_handler(event, MockLambdaContext())

        assert response["statusCode"] == 200
        assert json.loads(response["body"]) == {"status": "ok"}

    @mock_secretsmanager
    @mock_sns
    def test_lambda_handler_link_shared_event_lowercase_headers(self):
        """Test handling link_shared when API Gateway lowercases header keys."""
        import boto3

        sm = boto3.client("secretsmanager", region_name="us-east-2")
        sm.create_secret(
            Name="unfurl-service/slack",
            SecretString=json.dumps(
                {"signing_secret": "test_secret", "bot_token": "xoxb-test"}
            ),
        )

        slack_event = {
            "type": "event_callback",
            "event_id": "Ev123456",
            "team_id": "T123456",
            "event": {
                "type": "link_shared",
                "channel": "C123456",
                "message_ts": "1234567890.123456",
                "links": [
                    {
                        "url": "https://www.instagram.com/p/ABC123/",
                        "domain": "instagram.com",
                    }
                ],
            },
        }

        sns = boto3.client("sns", region_name="us-east-2")
        topic_response = sns.create_topic(Name="test-topic")
        topic_arn = topic_response["TopicArn"]

        with patch.dict(
            "os.environ",
            {
                "SLACK_SECRET_NAME": "unfurl-service/slack",
                "SNS_TOPIC_ARN": topic_arn,
                "POWERTOOLS_METRICS_NAMESPACE": "UnfurlService",
                "DISABLE_METRICS": "true",
                "AWS_DEFAULT_REGION": "us-east-2",
            },
        ):
            body = json.dumps(slack_event)
            timestamp = str(int(time.time()))
            sig_basestring = f"v0:{timestamp}:{body}"
            signature = (
                "v0="
                + hmac.new(
                    b"test_secret", sig_basestring.encode(), hashlib.sha256
                ).hexdigest()
            )

            event = {
                "body": body,
                "headers": {
                    "x-slack-signature": signature,
                    "x-slack-request-timestamp": timestamp,
                },
            }

            response = lambda_handler(event, MockLambdaContext())

        assert response["statusCode"] == 200
        assert json.loads(response["body"]) == {"status": "ok"}

    @mock_secretsmanager
    def test_lambda_handler_simple_event(self):
        """Test handling a simple non-link event."""
        import boto3

        # Setup mock secret
        sm = boto3.client("secretsmanager", region_name="us-east-2")
        sm.create_secret(
            Name="unfurl-service/slack",
            SecretString=json.dumps(
                {"signing_secret": "test_secret", "bot_token": "xoxb-test"}
            ),
        )

        # Create test event with no links
        slack_event = {
            "type": "event_callback",
            "event_id": "Ev123456",
            "team_id": "T123456",
            "event": {"type": "message", "channel": "C123456", "text": "Hello world"},
        }

        body = json.dumps(slack_event)
        timestamp = str(int(time.time()))
        sig_basestring = f"v0:{timestamp}:{body}"
        signature = (
            "v0="
            + hmac.new(
                b"test_secret", sig_basestring.encode(), hashlib.sha256
            ).hexdigest()
        )

        event = {
            "body": body,
            "headers": {
                "X-Slack-Signature": signature,
                "X-Slack-Request-Timestamp": timestamp,
            },
        }

        with patch.dict(
            "os.environ",
            {
                "SLACK_SECRET_NAME": "unfurl-service/slack",
                "SNS_TOPIC_ARN": "arn:aws:sns:us-east-2:123456789012:test-topic",
                "POWERTOOLS_METRICS_NAMESPACE": "UnfurlService",
                "DISABLE_METRICS": "true",
                "AWS_DEFAULT_REGION": "us-east-2",
            },
        ):
            response = lambda_handler(event, MockLambdaContext())

        assert response["statusCode"] == 200
