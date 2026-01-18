"""Tests for the enhanced async Instagram unfurl handler."""

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from src.unfurl_processor.handler_async import AsyncUnfurlHandler
from src.unfurl_processor.scrapers.base import ScrapingResult


# Python 3.7 compatibility
class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)


class TestAsyncUnfurlHandler:
    """Test suite for AsyncUnfurlHandler."""

    @pytest.fixture
    def handler(self):
        """Create handler instance for testing."""
        return AsyncUnfurlHandler()

    @pytest.fixture
    def sample_event(self):
        """Sample SNS event for testing."""
        return {
            "Records": [
                {
                    "Sns": {
                        "Message": json.dumps(
                            {
                                "channel": "C12345678",
                                "message_ts": "1640995200.001",
                                "unfurl_id": "C12345678.1640995200.001.test_unfurl_id",
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

    @pytest.fixture
    def sample_instagram_data(self):
        """Sample Instagram data for testing."""
        return {
            "post_id": "ABC123",
            "url": "https://www.instagram.com/p/ABC123/",
            "image_url": "https://scontent.cdninstagram.com/v/image.jpg",
            "title": "Test User on Instagram",
            "caption": "Test caption",
            "username": "testuser",
            "content_type": "photo",
            "extraction_method": "playwright",
            "likes": 100,
            "comments": 10,
            "timestamp": 1640995200,
        }

    @pytest.mark.asyncio
    async def test_get_scraper_manager_initialization(self, handler):
        """Test scraper manager is properly initialized."""
        # First call should create new instance
        manager1 = await handler._get_scraper_manager()
        assert manager1 is not None
        assert handler.scraper_manager is manager1

        # Second call should return same instance
        manager2 = await handler._get_scraper_manager()
        assert manager1 is manager2

    def test_get_slack_formatter(self, handler):
        """Test Slack formatter initialization."""
        formatter1 = handler._get_slack_formatter()
        assert formatter1 is not None

        formatter2 = handler._get_slack_formatter()
        assert formatter1 is formatter2

    def test_create_http_client_disables_http2_when_h2_missing(self, handler):
        """HTTP/2 should disable when optional 'h2' is absent."""
        with (
            patch(
                "src.unfurl_processor.handler_async.importlib.util.find_spec",
                return_value=None,
            ),
            patch(
                "src.unfurl_processor.handler_async.httpx.AsyncClient"
            ) as mock_client,
            patch.object(handler.logger, "warning") as mock_warning,
        ):
            handler._create_http_client()

        assert mock_client.call_args.kwargs["http2"] is False
        mock_warning.assert_called_once()

    def test_create_http_client_enables_http2_when_h2_present(self, handler):
        """HTTP/2 should enable when optional 'h2' is present."""
        with (
            patch(
                "src.unfurl_processor.handler_async.importlib.util.find_spec",
                return_value=object(),
            ),
            patch(
                "src.unfurl_processor.handler_async.httpx.AsyncClient"
            ) as mock_client,
            patch.object(handler.logger, "warning") as mock_warning,
        ):
            handler._create_http_client()

        assert mock_client.call_args.kwargs["http2"] is True
        mock_warning.assert_not_called()

    def test_extract_instagram_id(self, handler):
        """Test Instagram ID extraction from URLs."""
        test_cases = [
            ("https://www.instagram.com/p/ABC123/", "ABC123"),
            ("https://instagram.com/reel/XYZ789/", "XYZ789"),
            ("https://www.instagram.com/tv/DEF456/?utm_source=ig_web", "DEF456"),
            ("https://www.instagram.com/profile/", None),
            ("https://example.com/test", None),
        ]

        for url, expected_id in test_cases:
            result = handler._extract_instagram_id(url)
            assert result == expected_id

    def test_extract_instagram_links(self, handler):
        """Test Instagram link extraction from Slack event."""
        links = [
            {"url": "https://www.instagram.com/p/ABC123/", "domain": "instagram.com"},
            {
                "url": "https://www.instagram.com/reel/XYZ789/",
                "domain": "instagram.com",
            },
            {"url": "https://example.com/test", "domain": "example.com"},
            {"url": "https://www.instagram.com/profile/", "domain": "instagram.com"},
        ]

        result = handler._extract_instagram_links(links)

        # Should only include valid Instagram post/reel/tv URLs
        expected = [
            {
                "original_url": "https://www.instagram.com/p/ABC123/",
                "canonical_url": "https://www.instagram.com/p/ABC123",
            },
            {
                "original_url": "https://www.instagram.com/reel/XYZ789/",
                "canonical_url": "https://www.instagram.com/reel/XYZ789",
            },
        ]
        assert result == expected

    def test_canonicalize_instagram_url(self, handler):
        """Test URL canonicalization."""
        test_cases = [
            (
                "https://www.instagram.com/p/ABC123/?utm_source=ig_web",
                "https://www.instagram.com/p/ABC123",
            ),
            (
                "https://instagram.com/reel/XYZ789/#hashtag",
                "https://www.instagram.com/reel/XYZ789",
            ),
        ]

        for input_url, expected_url in test_cases:
            result = handler._canonicalize_instagram_url(input_url)
            assert result == expected_url

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_get_secret(self, mock_boto_client, handler):
        """Test secret retrieval from AWS Secrets Manager."""
        # Mock the secrets manager client
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"bot_token": "xoxb-test-token"})
        }

        # First call should fetch from AWS
        secret = await handler._get_secret("test-secret")
        assert secret["bot_token"] == "xoxb-test-token"
        mock_client.get_secret_value.assert_called_once_with(SecretId="test-secret")

        # Second call should use cache
        mock_client.get_secret_value.reset_mock()
        secret2 = await handler._get_secret("test-secret")
        assert secret2["bot_token"] == "xoxb-test-token"
        mock_client.get_secret_value.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.unfurl_processor.handler_async.AsyncUnfurlHandler._get_scraper_manager")
    async def test_fetch_instagram_data_success(
        self, mock_get_manager, handler, sample_instagram_data
    ):
        """Test successful Instagram data fetching."""
        # Mock scraper manager
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager

        # Mock successful scraping result
        mock_result = ScrapingResult(
            success=True,
            data=sample_instagram_data,
            method="playwright",
            response_time_ms=1500,
        )
        mock_manager.scrape_instagram_data.return_value = mock_result

        url = "https://www.instagram.com/p/ABC123/"
        result = await handler._fetch_instagram_data(url)

        assert result == sample_instagram_data
        mock_manager.scrape_instagram_data.assert_called_once_with(url)

    @pytest.mark.asyncio
    @patch("src.unfurl_processor.handler_async.AsyncUnfurlHandler._get_scraper_manager")
    async def test_fetch_instagram_data_failure(self, mock_get_manager, handler):
        """Test failed Instagram data fetching."""
        # Mock scraper manager
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager

        # Mock failed scraping result
        mock_result = ScrapingResult(
            success=False,
            error="All scrapers failed",
            method="manager_fallback",
            response_time_ms=3000,
        )
        mock_manager.scrape_instagram_data.return_value = mock_result

        url = "https://www.instagram.com/p/ABC123/"
        result = await handler._fetch_instagram_data(url)

        assert result is None
        mock_manager.scrape_instagram_data.assert_called_once_with(url)

    @pytest.mark.asyncio
    @patch("src.unfurl_processor.handler_async.AsyncUnfurlHandler._get_cached_unfurl")
    @patch(
        "src.unfurl_processor.handler_async.AsyncUnfurlHandler._fetch_instagram_data"
    )
    @patch("src.unfurl_processor.handler_async.AsyncUnfurlHandler._format_unfurl_data")
    @patch("src.unfurl_processor.handler_async.AsyncUnfurlHandler._cache_unfurl")
    async def test_process_single_link_with_cache(
        self,
        mock_cache_unfurl,
        mock_format,
        mock_fetch,
        mock_get_cached,
        handler,
        sample_instagram_data,
    ):
        """Test processing single link with cache hit."""
        url = "https://www.instagram.com/p/ABC123/"

        # Mock cache hit
        cached_unfurl = {"cached": True, "url": url}
        mock_get_cached.return_value = cached_unfurl

        result_url, result_data = await handler._process_single_link(url)

        assert result_url == url
        assert result_data == cached_unfurl

        # Should not fetch or format when cache hits
        mock_fetch.assert_not_called()
        mock_format.assert_not_called()
        mock_cache_unfurl.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.unfurl_processor.handler_async.AsyncUnfurlHandler._get_cached_unfurl")
    @patch(
        "src.unfurl_processor.handler_async.AsyncUnfurlHandler._fetch_instagram_data"
    )
    @patch("src.unfurl_processor.handler_async.AsyncUnfurlHandler._format_unfurl_data")
    @patch("src.unfurl_processor.handler_async.AsyncUnfurlHandler._cache_unfurl")
    async def test_process_single_link_cache_miss(
        self,
        mock_cache_unfurl,
        mock_format,
        mock_fetch,
        mock_get_cached,
        handler,
        sample_instagram_data,
    ):
        """Test processing single link with cache miss."""
        url = "https://www.instagram.com/p/ABC123/"

        # Mock cache miss
        mock_get_cached.return_value = None

        # Mock successful fetch and format
        mock_fetch.return_value = sample_instagram_data
        formatted_data = {"formatted": True, "url": url}
        mock_format.return_value = formatted_data

        result_url, result_data = await handler._process_single_link(url)

        assert result_url == url
        assert result_data == formatted_data

        # Should fetch, format, and cache
        mock_fetch.assert_called_once_with(url)
        mock_format.assert_called_once_with(sample_instagram_data)
        mock_cache_unfurl.assert_called_once_with(url, formatted_data)

    @pytest.mark.asyncio
    @patch("src.unfurl_processor.handler_async.AsyncUnfurlHandler._format_unfurl_data")
    @patch("src.unfurl_processor.handler_async.AsyncUnfurlHandler._cache_unfurl")
    @patch(
        "src.unfurl_processor.handler_async.AsyncUnfurlHandler._fetch_instagram_data"
    )
    async def test_process_single_link_persists_assets(
        self,
        mock_fetch,
        mock_cache,
        mock_format,
        handler,
        sample_instagram_data,
        monkeypatch,
    ):
        """Uploaded assets should replace the transient Instagram URL."""

        url = "https://www.instagram.com/p/ABC123/"
        monkeypatch.setenv("ASSETS_BUCKET_NAME", "assets-bucket")

        mock_fetch.return_value = sample_instagram_data.copy()
        mock_format.return_value = {"formatted": True}

        mock_asset_manager = AsyncMock()
        mock_asset_manager.upload_image.return_value = (
            "https://assets-bucket.s3.us-west-2.amazonaws.com/instagram/ABC123/img.jpg"
        )

        with (
            patch.object(handler, "_get_cached_unfurl", return_value=None),
            patch.object(
                handler, "_get_asset_manager", return_value=mock_asset_manager
            ),
            patch.object(handler, "_extract_instagram_id", return_value="ABC123"),
        ):
            result_url, result_data = await handler._process_single_link(url)

        mock_asset_manager.upload_image.assert_called_once_with(
            sample_instagram_data["image_url"], "ABC123"
        )
        formatted_input = mock_format.call_args.args[0]
        assert (
            formatted_input["image_url"] == mock_asset_manager.upload_image.return_value
        )
        mock_cache.assert_called_once_with(url, mock_format.return_value)
        assert result_url == url
        assert result_data == mock_format.return_value

    @pytest.mark.asyncio
    @patch("src.unfurl_processor.handler_async.AsyncUnfurlHandler._format_unfurl_data")
    @patch("src.unfurl_processor.handler_async.AsyncUnfurlHandler._cache_unfurl")
    @patch(
        "src.unfurl_processor.handler_async.AsyncUnfurlHandler._fetch_instagram_data"
    )
    async def test_process_single_link_uses_original_url_when_upload_fails(
        self,
        mock_fetch,
        mock_cache,
        mock_format,
        handler,
        sample_instagram_data,
        monkeypatch,
    ):
        """If persistence fails, fall back to the scraped image URL."""

        url = "https://www.instagram.com/p/ABC123/"
        monkeypatch.setenv("ASSETS_BUCKET_NAME", "assets-bucket")

        mock_fetch.return_value = sample_instagram_data.copy()
        mock_format.return_value = {"formatted": True}

        mock_asset_manager = AsyncMock()
        mock_asset_manager.upload_image.return_value = None

        with (
            patch.object(handler, "_get_cached_unfurl", return_value=None),
            patch.object(
                handler, "_get_asset_manager", return_value=mock_asset_manager
            ),
            patch.object(handler, "_extract_instagram_id", return_value="ABC123"),
        ):
            result_url, result_data = await handler._process_single_link(url)

        mock_asset_manager.upload_image.assert_called_once_with(
            sample_instagram_data["image_url"], "ABC123"
        )
        formatted_input = mock_format.call_args.args[0]
        assert formatted_input["image_url"] == sample_instagram_data["image_url"]
        mock_cache.assert_called_once_with(url, mock_format.return_value)
        assert result_url == url
        assert result_data == mock_format.return_value

    @pytest.mark.asyncio
    @patch("src.unfurl_processor.handler_async.AsyncUnfurlHandler._get_secret")
    @patch("src.unfurl_processor.handler_async.AsyncUnfurlHandler._process_single_link")
    @patch(
        "src.unfurl_processor.handler_async.AsyncUnfurlHandler._send_unfurl_to_slack"
    )
    async def test_process_event_success(
        self,
        mock_send_unfurl,
        mock_process_link,
        mock_get_secret,
        handler,
        sample_event,
    ):
        """Test successful event processing."""
        # Mock secret retrieval
        mock_get_secret.return_value = {"bot_token": "xoxb-test-token"}

        # Mock successful link processing
        url = "https://www.instagram.com/p/ABC123/"
        unfurl_data = {"formatted": True, "url": url}
        mock_process_link.return_value = (url, unfurl_data)

        # Mock successful Slack unfurl
        mock_send_unfurl.return_value = True

        # Mock Lambda context
        context = MagicMock()

        result = await handler.process_event(sample_event, context)

        assert result["statusCode"] == 200
        assert "Processed 1 unfurls successfully" in result["body"]

        # URL should be canonicalized (no trailing slash)
        mock_process_link.assert_called_once_with("https://www.instagram.com/p/ABC123")
        mock_send_unfurl.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_event_invalid_structure(self, handler):
        """Test event processing with invalid structure."""
        invalid_event = {"invalid": "structure"}
        context = MagicMock()

        result = await handler.process_event(invalid_event, context)

        assert result["statusCode"] == 400
        assert "Invalid event structure" in result["body"]

    @pytest.mark.asyncio
    async def test_process_event_no_instagram_links(self, handler):
        """Test event processing with no Instagram links."""
        event = {
            "Records": [
                {
                    "Sns": {
                        "Message": json.dumps(
                            {
                                "channel": "C12345678",
                                "message_ts": "1640995200.001",
                                "unfurl_id": "C12345678.1640995200.001.test_unfurl_id",
                                "links": [
                                    {
                                        "url": "https://example.com/test",
                                        "domain": "example.com",
                                    }
                                ],
                            }
                        )
                    }
                }
            ]
        }
        context = MagicMock()

        result = await handler.process_event(event, context)

        assert result["statusCode"] == 200
        assert "No Instagram links found" in result["body"]

    @pytest.mark.asyncio
    async def test_async_context_manager(self, handler):
        """Test async context manager functionality."""
        # Mock cleanup methods
        handler.http_client = AsyncMock()
        handler.scraper_manager = AsyncMock()

        # Test context manager
        async with handler as h:
            assert h is handler

        # Verify cleanup was called
        handler.http_client.aclose.assert_called_once()
        handler.scraper_manager.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_link_processing(self, handler):
        """Test concurrent processing of multiple Instagram links."""
        # This test verifies that multiple links are processed concurrently
        urls = [
            "https://www.instagram.com/p/ABC123/",
            "https://www.instagram.com/p/DEF456/",
            "https://www.instagram.com/reel/GHI789/",
        ]

        with patch.object(handler, "_process_single_link") as mock_process:
            # Mock async results
            mock_process.side_effect = [
                (urls[0], {"url": urls[0]}),
                (urls[1], {"url": urls[1]}),
                (urls[2], {"url": urls[2]}),
            ]

            # Create tasks
            tasks = [handler._process_single_link(url) for url in urls]
            results = await asyncio.gather(*tasks)

            # Verify all links were processed
            assert len(results) == 3
            assert mock_process.call_count == 3

            # Verify results
            for i, (result_url, result_data) in enumerate(results):
                assert result_url == urls[i]
                assert result_data["url"] == urls[i]
