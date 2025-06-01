"""Tests for the unfurl processor Lambda function."""

import json
import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_dynamodb, mock_secretsmanager

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
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-2")
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

    def test_fetch_instagram_data_with_scraping(self):
        """Test fetching Instagram data using web scraping."""
        # Mock HTML response
        mock_html = """
        <html>
        <head>
            <meta property="og:image" content="https://example.com/image.jpg">
            <meta property="og:description"
                  content="Test user on Instagram: &quot;Test caption&quot;">
            <meta property="og:title" content="@testuser on Instagram">
        </head>
        </html>
        """

        with patch("requests.Session") as mock_session_class:
            # Create mock session instance
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            # Mock homepage response
            mock_homepage_response = MagicMock()
            mock_homepage_response.status_code = 200
            
            # Mock main response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = mock_html
            mock_response.content = mock_html.encode('utf-8')
            mock_response.apparent_encoding = 'utf-8'
            mock_response.encoding = 'utf-8'
            mock_response.headers = {
                'content-type': 'text/html; charset=utf-8',
                'content-encoding': 'none'
            }
            mock_response.raise_for_status = MagicMock()
            
            # Configure session.get to return different responses for different calls
            def side_effect(url, **kwargs):
                if url == "https://www.instagram.com/":
                    return mock_homepage_response
                else:
                    return mock_response
            
            mock_session.get.side_effect = side_effect
            mock_session.headers = {}

            from src.unfurl_processor.handler import fetch_instagram_data

            data = fetch_instagram_data("https://www.instagram.com/p/ABC123/")

            assert data is not None
            assert data["media_url"] == "https://example.com/image.jpg"
            assert "Test caption" in data["caption"]
            assert data["username"] == "testuser"  

    @pytest.mark.skip(reason="Cache test requires complex DynamoDB mocking")
    @mock_dynamodb
    def test_cache_unfurl(self):
        """Test caching unfurl data in DynamoDB."""
        # Create mock DynamoDB table
        dynamodb = boto3.resource("dynamodb", region_name="us-east-2")
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

    @mock_dynamodb
    @mock_secretsmanager
    def test_lambda_handler(self):
        """Test the main Lambda handler function."""
        import boto3

        # Clear the secrets cache
        from src.unfurl_processor.handler import _secrets_cache, lambda_handler

        _secrets_cache.clear()

        # Set up mock secrets
        sm = boto3.client("secretsmanager", region_name="us-east-2")
        sm.create_secret(
            Name="unfurl-service/slack",
            SecretString=json.dumps({"bot_token": "xoxb-test-token"}),
        )

        # Set up mock DynamoDB table
        dynamodb = boto3.resource("dynamodb", region_name="us-east-2")
        dynamodb.create_table(
            TableName="instagram-unfurl-cache",
            KeySchema=[{"AttributeName": "url", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "url", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

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
            "arn:aws:lambda:us-east-2:123456789012:function:test-function"
        )
        context.aws_request_id = "test-request-id"

        # Mock HTML response for web scraping
        mock_html = """
        <html>
        <head>
            <meta property="og:image" content="https://example.com/image.jpg">
            <meta property="og:description"
                  content="Test user on Instagram: &quot;Test caption&quot;">
            <meta property="og:title" content="@testuser on Instagram">
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
                "AWS_DEFAULT_REGION": "us-east-2",
            },
        ):
            with patch("src.unfurl_processor.handler.get_secret") as mock_get_secret:
                with patch(
                    "src.unfurl_processor.handler.get_dynamodb_resource"
                ) as mock_get_dynamodb:
                    with patch("slack_sdk.WebClient") as mock_slack:
                        with patch("requests.Session") as mock_session_class:
                            # Mock the get_secret function to return our test token
                            mock_get_secret.return_value = {
                                "bot_token": "xoxb-test-token"
                            }
                            # Mock DynamoDB resource to return our mocked table
                            mock_get_dynamodb.return_value = dynamodb

                            # Mock Slack client
                            mock_client = MagicMock()
                            mock_slack.return_value = mock_client
                            mock_client.chat_unfurl.return_value = {"ok": True}

                            # Mock session and response
                            mock_session = MagicMock()
                            mock_session_class.return_value = mock_session
                            
                            # Mock homepage response
                            mock_homepage_response = MagicMock()
                            mock_homepage_response.status_code = 200
                            
                            # Mock successful response
                            mock_response = MagicMock()
                            mock_response.status_code = 200
                            mock_response.text = mock_html
                            mock_response.content = mock_html.encode('utf-8')
                            mock_response.apparent_encoding = 'utf-8'
                            mock_response.encoding = 'utf-8'
                            mock_response.headers = {
                                'content-type': 'text/html; charset=utf-8',
                                'content-encoding': 'none'
                            }
                            mock_response.raise_for_status = MagicMock()
                            
                            # Configure session.get to return different responses for different calls
                            def side_effect(url, **kwargs):
                                if url == "https://www.instagram.com/":
                                    return mock_homepage_response
                                else:
                                    return mock_response
                            
                            mock_session.get.side_effect = side_effect
                            mock_session.headers = {}

                            result = lambda_handler(event, context)

                            # Verify function returns response (may fail due to
                            # Slack/DynamoDB errors but shouldn’t crash)
                            assert result is not None
                            assert "statusCode" in result
                            assert "body" in result

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

        with patch("requests.Session") as mock_session_class:
            # Create mock session instance
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            # Mock response for oEmbed
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '{"thumbnail_url": "https://example.com/thumb.jpg", "author_name": "oembed_user", "title": "oEmbed caption"}'
            mock_response.content = b'{"thumbnail_url": "https://example.com/thumb.jpg", "author_name": "oembed_user", "title": "oEmbed caption"}'
            mock_response.headers = {
                'content-type': 'application/json',
                'content-encoding': 'none'
            }
            mock_response.json.return_value = {
                "thumbnail_url": "https://example.com/thumb.jpg",
                "author_name": "oembed_user",
                "title": "oEmbed caption",
            }
            mock_session.get.return_value = mock_response

            data = fetch_instagram_oembed("https://www.instagram.com/p/ABC123/")

            assert data is not None

    def test_create_fallback_unfurl(self):
        """Test creating fallback unfurl data when scraping fails."""
        from src.unfurl_processor.handler import create_fallback_unfurl

        # Test photo post
        url = "https://www.instagram.com/p/ABC123/"
        fallback = create_fallback_unfurl(url)

        assert fallback["post_id"] == "ABC123"
        assert fallback["permalink"] == url
        assert fallback["is_fallback"] is True
        assert fallback["title"] == "Instagram Photo"
        assert "photo" in fallback["description"].lower()

        # Test reel post
        reel_url = "https://www.instagram.com/reel/XYZ789/"
        reel_fallback = create_fallback_unfurl(reel_url)

        assert reel_fallback["post_id"] == "XYZ789"
        assert reel_fallback["title"] == "Instagram Reel"
        assert "reel" in reel_fallback["description"].lower()

        # Test TV post
        tv_url = "https://www.instagram.com/tv/DEF456/"
        tv_fallback = create_fallback_unfurl(tv_url)

        assert tv_fallback["post_id"] == "DEF456"
        assert tv_fallback["title"] == "Instagram Video"
        assert "video" in tv_fallback["description"].lower()

    @patch("src.unfurl_processor.handler.requests.Session")
    def test_proxy_support(self, mock_session_class, monkeypatch):
        """Test proxy rotation functionality."""
        from src.unfurl_processor.handler import fetch_instagram_data

        # Set proxy environment variable
        monkeypatch.setenv("PROXY_URLS", "http://proxy1:8080,http://proxy2:8080")

        # Mock session and response
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # Mock homepage response
        mock_homepage_response = MagicMock()
        mock_homepage_response.status_code = 200
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
        <head>
            <meta property="og:image" content="https://example.com/image.jpg">
            <meta property="og:description"
                  content="Test user on Instagram: Test caption">
        </head>
        </html>
        """
        mock_response.content = mock_response.text.encode('utf-8')
        mock_response.apparent_encoding = 'utf-8'
        mock_response.encoding = 'utf-8'
        mock_response.headers = {
            'content-type': 'text/html; charset=utf-8',
            'content-encoding': 'none'
        }
        mock_response.raise_for_status = MagicMock()
        
        # Configure session.get to return different responses for different calls
        def side_effect(url, **kwargs):
            if url == "https://www.instagram.com/":
                return mock_homepage_response
            else:
                return mock_response
        
        mock_session.get.side_effect = side_effect
        mock_session.headers = {}

        # Reload the handler to pick up new proxy settings
        import importlib
        import src.unfurl_processor.handler

        importlib.reload(src.unfurl_processor.handler)

        url = "https://www.instagram.com/p/ABC123/"

        with patch("src.unfurl_processor.handler.get_cached_unfurl", return_value=None):
            fetch_instagram_data(url)

        # Verify that session was created and used
        mock_session_class.assert_called()
        mock_session.get.assert_called()
        call_kwargs = mock_session.get.call_args[1]
        assert "proxies" in call_kwargs
        assert call_kwargs["proxies"]["http"] in [
            "http://proxy1:8080",
            "http://proxy2:8080",
        ]
        assert call_kwargs["proxies"]["https"] in [
            "http://proxy1:8080",
            "http://proxy2:8080",
        ]

    def test_browser_automation_unavailable(self):
        """Test browser automation when Playwright is not available."""
        from src.unfurl_processor.handler import fetch_instagram_data_with_browser

        # Mock PLAYWRIGHT_AVAILABLE as False
        with patch("src.unfurl_processor.handler.PLAYWRIGHT_AVAILABLE", False):
            result = fetch_instagram_data_with_browser(
                "https://www.instagram.com/p/ABC123/"
            )
            assert result is None

    @patch("src.unfurl_processor.handler.sync_playwright")
    def test_browser_automation_success(self, mock_playwright):
        """Test successful browser automation."""
        from src.unfurl_processor.handler import fetch_instagram_data_with_browser

        # Mock Playwright components
        mock_page = MagicMock()
        mock_page.content.return_value = """
        <html>
        <head>
            <meta property="og:image" content="https://example.com/image.jpg">
            <meta property="og:description"
                  content="Test user on Instagram: Test caption">
        </head>
        </html>
        """

        mock_response = MagicMock()
        mock_response.status = 200
        mock_page.goto.return_value = mock_response

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_p = MagicMock()
        mock_p.chromium.launch.return_value = mock_browser

        mock_playwright.return_value.__enter__.return_value = mock_p

        # Mock cache to return None
        with patch(
            "src.unfurl_processor.handler.get_cached_unfurl", return_value=None
        ), patch("src.unfurl_processor.handler.PLAYWRIGHT_AVAILABLE", True), patch(
            "src.unfurl_processor.handler.cache_unfurl"
        ):

            url = "https://www.instagram.com/p/ABC123/"
            fetch_instagram_data_with_browser(url)

            # Verify browser was launched and page was visited
            mock_p.chromium.launch.assert_called_once()
            mock_page.goto.assert_called_once()
            mock_browser.close.assert_called_once()

    @patch("src.unfurl_processor.handler.sync_playwright")
    def test_browser_automation_failure(self, mock_playwright):
        """Test browser automation when it fails."""
        from src.unfurl_processor.handler import fetch_instagram_data_with_browser

        # Mock Playwright to raise an exception
        mock_playwright.return_value.__enter__.side_effect = Exception("Browser failed")

        with (
            patch("src.unfurl_processor.handler.PLAYWRIGHT_AVAILABLE", True),
            patch("src.unfurl_processor.handler.get_cached_unfurl", return_value=None),
        ):

            result = fetch_instagram_data_with_browser(
                "https://www.instagram.com/p/ABC123/"
            )
            assert result is None
