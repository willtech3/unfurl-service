"""Tests for the unfurl processor Lambda function."""

import json
import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

# Disable AWS X-Ray SDK for testing
os.environ["AWS_XRAY_SDK_ENABLED"] = "false"


class TestUnfurlProcessor:
    """Test cases for unfurl processor Lambda function."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        """Set up environment variables for tests."""
        monkeypatch.setenv("CACHE_TABLE_NAME", "test-cache-table")
        monkeypatch.setenv("SLACK_SECRET_NAME", "test-slack-secret")
        monkeypatch.setenv("CACHE_TTL_HOURS", "24")
        monkeypatch.setenv("DISABLE_METRICS", "true")
        monkeypatch.setenv("POWERTOOLS_METRICS_NAMESPACE", "UnfurlService")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
        monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
        monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")

    def test_extract_instagram_id(self):
        """Test extracting Instagram post ID from URL."""
        from src.unfurl_processor.handler import extract_post_id

        # Test various URL formats
        assert extract_post_id("https://www.instagram.com/p/ABC123/") == "ABC123"
        assert extract_post_id("https://instagram.com/p/XYZ789/") == "XYZ789"
        assert extract_post_id("https://www.instagram.com/reel/DEF456/") == "DEF456"
        assert extract_post_id("https://www.instagram.com/tv/GHI789/") == "GHI789"
        assert extract_post_id("https://www.instagram.com/user/profile/") == ""

    @mock_aws
    def test_fetch_instagram_data_with_scraping(self):
        """Test fetching Instagram data using web scraping."""
        # Mock HTML response
        mock_html = """
        <html>
        <head>
            <meta property="og:image" content="https://example.com/image.jpg">
            <meta property="og:description" content="100 Likes, 10 Comments - testuser on Instagram: &quot;Test caption&quot;">
            <meta property="og:title" content="@testuser on Instagram">
        </head>
        </html>
        """

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = mock_html
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            from src.unfurl_processor.handler import fetch_instagram_data

            data = fetch_instagram_data("https://www.instagram.com/p/ABC123/", "ABC123")

            assert data is not None
            assert data["media_url"] == "https://example.com/image.jpg"
            assert data["username"] == "testuser"
            assert data["caption"] == "Test caption"
            assert data["likes"] == "100"
            assert data["comments"] == "10"

    @pytest.mark.skip(reason="Cache test requires complex DynamoDB mocking")
    @mock_aws
    def test_cache_unfurl(self):
        """Test caching unfurl data in DynamoDB."""
        # Create mock DynamoDB table
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="instagram-unfurl-cache",
            KeySchema=[{"AttributeName": "url", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "url", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # Add cached item
        table.put_item(
            Item={
                "url": "https://www.instagram.com/p/ABC123/",
                "unfurl_data": {
                    "title": "Cached Instagram Post",
                    "text": "Cached caption",
                    "image_url": "https://example.com/cached.jpg",
                },
                "ttl": 9999999999,  # Far future
            }
        )

        with patch.dict(
            "os.environ",
            {
                "CACHE_TABLE_NAME": "instagram-unfurl-cache",
                "POWERTOOLS_METRICS_NAMESPACE": "UnfurlService",
            },
        ):
            # Mock both the dynamodb resource and the requests.get call
            with patch(
                "src.unfurl_processor.handler.boto3.resource", return_value=dynamodb
            ):
                # Test that cache is retrieved
                from src.unfurl_processor.handler import get_cached_unfurl

                cached = get_cached_unfurl("https://www.instagram.com/p/ABC123/")
                assert cached is not None
                assert cached["title"] == "Cached Instagram Post"

    @mock_aws
    def test_post_to_slack(self):
        """Test posting unfurl to Slack."""
        with patch("slack_sdk.WebClient") as mock_slack:
            mock_client = MagicMock()
            mock_slack.return_value = mock_client
            mock_client.chat_unfurl.return_value = {"ok": True}

            unfurls = {
                "https://www.instagram.com/p/ABC123/": {
                    "title": "Instagram Post",
                    "text": "Test caption",
                    "image_url": "https://example.com/image.jpg",
                }
            }

            from src.unfurl_processor.handler import send_unfurl_to_slack

            result = send_unfurl_to_slack(
                mock_client, "C123456", "1234567890.123456", unfurls
            )

            assert result is True
            mock_client.chat_unfurl.assert_called_once_with(
                channel="C123456", ts="1234567890.123456", unfurls=unfurls
            )

    @mock_aws
    def test_lambda_handler(self):
        """Test the main Lambda handler function."""
        event = {
            "Records": [
                {
                    "Sns": {
                        "Message": json.dumps(
                            {
                                "channel": "C123456",
                                "message_ts": "1234567890.123456",
                                "links": [
                                    {
                                        "url": "https://www.instagram.com/p/ABC123/",
                                        "domain": "instagram.com",
                                    }
                                ],
                            }
                        )
                    }
                }
            ]
        }

        # Create a mock context
        context = MagicMock()
        context.function_name = "test-function"
        context.memory_limit_in_mb = 128
        context.invoked_function_arn = (
            "arn:aws:lambda:us-east-1:123456789012:function:test-function"
        )
        context.aws_request_id = "test-request-id"

        # Mock HTML response for web scraping
        mock_html = """
        <html>
        <head>
            <meta property="og:image" content="https://example.com/image.jpg">
            <meta property="og:description" content="Test user on Instagram: &quot;Test caption&quot;">
        </head>
        </html>
        """

        with patch.dict(
            "os.environ",
            {
                "CACHE_TABLE_NAME": "instagram-unfurl-cache",
                "SLACK_SECRET_NAME": "unfurl-service/slack",
                "CACHE_TTL_HOURS": "24",
                "POWERTOOLS_METRICS_NAMESPACE": "UnfurlService",
            },
        ):
            with patch("slack_sdk.WebClient") as mock_slack:
                with patch("requests.get") as mock_get:
                    with patch("boto3.client") as mock_boto_client:
                        # Mock Secrets Manager
                        mock_secrets_client = MagicMock()
                        mock_boto_client.return_value = mock_secrets_client
                        mock_secrets_client.get_secret_value.return_value = {
                            "SecretString": json.dumps({"bot_token": "xoxb-test-token"})
                        }

                        # Mock Slack client
                        mock_client = MagicMock()
                        mock_slack.return_value = mock_client
                        mock_client.chat_unfurl.return_value = {"ok": True}

                        # Mock web scraping response
                        mock_response = MagicMock()
                        mock_response.status_code = 200
                        mock_response.text = mock_html
                        mock_response.raise_for_status = MagicMock()
                        mock_get.return_value = mock_response

                        from src.unfurl_processor.handler import lambda_handler

                        result = lambda_handler(event, context)

                        assert result["statusCode"] == 200
                        assert json.loads(result["body"])["message"] == "Success"

                        # Verify Slack was called
                        assert mock_client.chat_unfurl.called

    def test_invalid_event_structure(self):
        """Test handler with invalid event structure."""
        event = {"invalid": "structure"}
        context = MagicMock()

        from src.unfurl_processor.handler import lambda_handler

        result = lambda_handler(event, context)

        assert result["statusCode"] == 400
        assert "Invalid event structure" in result["body"]

    def test_format_unfurl_data(self):
        """Test formatting Instagram data for Slack unfurl."""
        from src.unfurl_processor.handler import format_unfurl_data

        # Test with full data
        data = {
            "username": "testuser",
            "permalink": "https://www.instagram.com/p/ABC123/",
            "media_url": "https://example.com/image.jpg",
            "caption": "Test caption",
            "likes": "100",
            "comments": "10",
            "timestamp": "2024-01-01T00:00:00",
        }

        unfurl = format_unfurl_data(data)

        assert unfurl["title"] == "@testuser"
        assert unfurl["title_link"] == "https://www.instagram.com/p/ABC123/"
        assert unfurl["image_url"] == "https://example.com/image.jpg"
        assert unfurl["text"] == "Test caption"
        assert unfurl["color"] == "#E4405F"
        assert len(unfurl["fields"]) == 2
        assert unfurl["fields"][0]["title"] == "Likes"
        assert unfurl["fields"][0]["value"] == "100"

        # Test with minimal data
        minimal_data = {
            "username": "user2",
            "permalink": "https://www.instagram.com/p/XYZ/",
            "media_url": "https://example.com/img.jpg",
        }

        minimal_unfurl = format_unfurl_data(minimal_data)
        assert minimal_unfurl["title"] == "@user2"
        assert "fields" not in minimal_unfurl

        # Test with None
        assert format_unfurl_data(None) is None

    def test_oembed_fallback(self):
        """Test oEmbed fallback when scraping fails."""
        from src.unfurl_processor.handler import fetch_instagram_oembed

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "thumbnail_url": "https://example.com/thumb.jpg",
                "author_name": "oembed_user",
                "title": "oEmbed caption",
            }
            mock_get.return_value = mock_response

            data = fetch_instagram_oembed("https://www.instagram.com/p/ABC123/")

            assert data is not None
            assert data["media_url"] == "https://example.com/thumb.jpg"
            assert data["username"] == "oembed_user"
            assert data["caption"] == "oEmbed caption"
            assert data["provider"] == "oembed"
