import hashlib
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from botocore.exceptions import ClientError

from src.unfurl_processor.asset_manager import AssetManager


@pytest.fixture
def s3_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    client = MagicMock()
    monkeypatch.setenv("ASSETS_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setattr(
        "src.unfurl_processor.asset_manager.boto3.client",
        MagicMock(return_value=client),
    )
    return client


@pytest.fixture
def http_client() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def to_thread_mock(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock(side_effect=lambda func, *args, **kwargs: func(*args, **kwargs))
    monkeypatch.setattr("src.unfurl_processor.asset_manager.asyncio.to_thread", mock)
    return mock


@pytest.fixture
def asset_manager(
    s3_client: MagicMock, http_client: AsyncMock, to_thread_mock: AsyncMock
) -> AssetManager:
    return AssetManager(http_client=http_client)


def test_key_generation(asset_manager: AssetManager) -> None:
    key = asset_manager._generate_key(
        "abc123", "https://instagram.com/image", "image/png"
    )

    expected_hash = hashlib.sha256("https://instagram.com/image".encode()).hexdigest()[
        :12
    ]
    assert key == f"instagram/abc123/{expected_hash}.png"


@pytest.mark.asyncio
async def test_upload_success(
    asset_manager: AssetManager,
    s3_client: MagicMock,
    http_client: AsyncMock,
    to_thread_mock: AsyncMock,
) -> None:
    request = httpx.Request("GET", "https://example.com/image.png")
    response = httpx.Response(
        200,
        headers={"Content-Type": "image/png"},
        content=b"image-bytes",
        request=request,
    )
    http_client.get.return_value = response

    result = await asset_manager.upload_image(str(request.url), "post123")

    expected_hash = hashlib.sha256(str(request.url).encode()).hexdigest()[:12]
    expected_key = f"instagram/post123/{expected_hash}.png"

    assert result == f"https://test-bucket.s3.us-west-2.amazonaws.com/{expected_key}"
    s3_client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key=expected_key,
        Body=b"image-bytes",
        ContentType="image/png",
        CacheControl="max-age=31536000",
    )
    to_thread_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_download_failure(
    asset_manager: AssetManager, s3_client: MagicMock, http_client: AsyncMock
) -> None:
    request = httpx.Request("GET", "https://example.com/missing.jpg")
    http_client.get.side_effect = httpx.HTTPStatusError(
        "not found", request=request, response=httpx.Response(404, request=request)
    )

    result = await asset_manager.upload_image(str(request.url), "post123")

    assert result is None
    s3_client.put_object.assert_not_called()


@pytest.mark.asyncio
async def test_s3_upload_failure(
    asset_manager: AssetManager,
    s3_client: MagicMock,
    http_client: AsyncMock,
    to_thread_mock: AsyncMock,
) -> None:
    request = httpx.Request("GET", "https://example.com/image.jpg")
    http_client.get.return_value = httpx.Response(
        200,
        headers={"Content-Type": "image/jpeg"},
        content=b"img-bytes",
        request=request,
    )
    s3_client.put_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Denied"}}, "PutObject"
    )

    result = await asset_manager.upload_image(str(request.url), "post123")

    assert result is None
    s3_client.put_object.assert_called_once()
    to_thread_mock.assert_awaited_once()
