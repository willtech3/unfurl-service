"""Unit tests for AssetManager S3 persistence."""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from botocore.exceptions import ClientError


class TestAssetManagerKeyGeneration:
    """Test suite for AssetManager._generate_key method."""

    @pytest.fixture
    def asset_manager(self):
        """Create an AssetManager instance with mocked dependencies."""
        with patch.dict(
            "os.environ",
            {
                "ASSETS_BUCKET_NAME": "test-bucket",
                "AWS_REGION": "us-west-2",
            },
        ):
            from src.unfurl_processor.asset_manager import AssetManager

            manager = AssetManager()
            return manager

    def test_key_generation_jpeg(self, asset_manager):
        """Test key generation for JPEG images."""
        post_id = "ABC123"
        url = "https://scontent.cdninstagram.com/v/image.jpg?stp=test"
        content_type = "image/jpeg"

        key = asset_manager._generate_key(post_id, url, content_type)

        # Verify key structure: instagram/{post_id}/{url_hash}.{ext}
        assert key.startswith(f"instagram/{post_id}/")
        assert key.endswith(".jpg")

        # Verify hash is 12 characters
        url_hash = key.split("/")[2].replace(".jpg", "")
        assert len(url_hash) == 12

        # Verify hash is consistent
        expected_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
        assert url_hash == expected_hash

    def test_key_generation_png(self, asset_manager):
        """Test key generation for PNG images."""
        post_id = "DEF456"
        url = "https://example.com/image.png"
        content_type = "image/png"

        key = asset_manager._generate_key(post_id, url, content_type)

        assert key.startswith(f"instagram/{post_id}/")
        assert key.endswith(".png")

    def test_key_generation_webp(self, asset_manager):
        """Test key generation for WebP images."""
        post_id = "GHI789"
        url = "https://example.com/image.webp"
        content_type = "image/webp"

        key = asset_manager._generate_key(post_id, url, content_type)

        assert key.startswith(f"instagram/{post_id}/")
        assert key.endswith(".webp")

    def test_key_generation_default_extension(self, asset_manager):
        """Test key generation defaults to jpg for unknown content types."""
        post_id = "JKL012"
        url = "https://example.com/image"
        content_type = "application/octet-stream"

        key = asset_manager._generate_key(post_id, url, content_type)

        assert key.endswith(".jpg")

    def test_key_generation_unique_for_different_urls(self, asset_manager):
        """Test that different URLs generate different keys."""
        post_id = "ABC123"
        url1 = "https://example.com/image1.jpg"
        url2 = "https://example.com/image2.jpg"
        content_type = "image/jpeg"

        key1 = asset_manager._generate_key(post_id, url1, content_type)
        key2 = asset_manager._generate_key(post_id, url2, content_type)

        assert key1 != key2


class TestAssetManagerUpload:
    """Test suite for AssetManager.upload_image method."""

    @pytest.fixture
    def mock_http_client(self):
        """Create a mocked httpx AsyncClient."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def mock_s3_client(self):
        """Create a mocked boto3 S3 client."""
        return MagicMock()

    @pytest.fixture
    def asset_manager(self, mock_http_client, mock_s3_client):
        """Create an AssetManager instance with mocked dependencies."""
        with patch.dict(
            "os.environ",
            {
                "ASSETS_BUCKET_NAME": "test-bucket",
                "AWS_REGION": "us-west-2",
            },
        ):
            with patch("boto3.client") as mock_boto_client:
                mock_boto_client.return_value = mock_s3_client

                from src.unfurl_processor.asset_manager import AssetManager

                manager = AssetManager()
                manager.http_client = mock_http_client
                return manager

    @pytest.mark.asyncio
    async def test_upload_success(
        self, asset_manager, mock_http_client, mock_s3_client
    ):
        """Test successful image upload to S3."""
        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake image data"
        mock_response.headers = {"Content-Type": "image/jpeg"}
        mock_response.raise_for_status = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock successful S3 upload
        mock_s3_client.put_object.return_value = {"ETag": '"abc123"'}

        url = "https://scontent.cdninstagram.com/v/test.jpg"
        post_id = "ABC123"

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = {"ETag": '"abc123"'}

            result = await asset_manager.upload_image(url, post_id)

        # Verify S3 URL format
        assert result is not None
        assert result.startswith("https://test-bucket.s3.us-west-2.amazonaws.com/")
        assert "/instagram/ABC123/" in result
        assert result.endswith(".jpg")

        # Verify HTTP client was called
        mock_http_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_failure_404(self, asset_manager, mock_http_client):
        """Test handling of 404 download failure."""
        # Mock HTTP 404 error
        mock_http_client.get.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=MagicMock(status_code=404),
        )

        url = "https://scontent.cdninstagram.com/v/missing.jpg"
        post_id = "ABC123"

        result = await asset_manager.upload_image(url, post_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_download_failure_500(self, asset_manager, mock_http_client):
        """Test handling of 500 server error."""
        # Mock HTTP 500 error
        mock_http_client.get.side_effect = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )

        url = "https://scontent.cdninstagram.com/v/error.jpg"
        post_id = "ABC123"

        result = await asset_manager.upload_image(url, post_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_download_failure_timeout(self, asset_manager, mock_http_client):
        """Test handling of download timeout."""
        # Mock timeout error
        mock_http_client.get.side_effect = httpx.TimeoutException(
            "Connection timed out"
        )

        url = "https://scontent.cdninstagram.com/v/slow.jpg"
        post_id = "ABC123"

        result = await asset_manager.upload_image(url, post_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_s3_upload_failure(self, asset_manager, mock_http_client):
        """Test handling of S3 upload failure."""
        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake image data"
        mock_response.headers = {"Content-Type": "image/jpeg"}
        mock_response.raise_for_status = MagicMock()
        mock_http_client.get.return_value = mock_response

        url = "https://scontent.cdninstagram.com/v/test.jpg"
        post_id = "ABC123"

        # Mock S3 upload failure
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
                "PutObject",
            )

            result = await asset_manager.upload_image(url, post_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_generic_exception_handling(self, asset_manager, mock_http_client):
        """Test handling of unexpected exceptions."""
        # Mock unexpected exception
        mock_http_client.get.side_effect = RuntimeError("Unexpected error")

        url = "https://scontent.cdninstagram.com/v/test.jpg"
        post_id = "ABC123"

        result = await asset_manager.upload_image(url, post_id)

        assert result is None


class TestAssetManagerConfiguration:
    """Test suite for AssetManager configuration."""

    def test_default_region(self):
        """Test default region when AWS_REGION is not set."""
        with patch.dict(
            "os.environ",
            {"ASSETS_BUCKET_NAME": "test-bucket"},
            clear=True,
        ):
            with patch("boto3.client"):
                from src.unfurl_processor.asset_manager import AssetManager

                manager = AssetManager()
                assert manager.region == "us-east-1"

    def test_custom_region(self):
        """Test custom region from environment."""
        with patch.dict(
            "os.environ",
            {
                "ASSETS_BUCKET_NAME": "test-bucket",
                "AWS_REGION": "eu-west-1",
            },
        ):
            with patch("boto3.client"):
                from src.unfurl_processor.asset_manager import AssetManager

                manager = AssetManager()
                assert manager.region == "eu-west-1"

    def test_bucket_name_from_env(self):
        """Test bucket name is read from environment."""
        with patch.dict(
            "os.environ",
            {
                "ASSETS_BUCKET_NAME": "my-custom-bucket",
                "AWS_REGION": "us-west-2",
            },
        ):
            with patch("boto3.client"):
                from src.unfurl_processor.asset_manager import AssetManager

                manager = AssetManager()
                assert manager.bucket_name == "my-custom-bucket"
