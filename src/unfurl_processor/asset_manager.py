import asyncio
import hashlib
import ipaddress
import os
from typing import Optional
from urllib.parse import urlparse

import boto3
import httpx
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

logger = Logger()

CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
ALLOWED_ASSET_HOST_SUFFIXES = (
    "cdninstagram.com",
    "fbcdn.net",
    "fbsbx.com",
    "instagram.fcdn.us",
)
MAX_ASSET_SIZE_BYTES = 10 * 1024 * 1024


class AssetManager:
    def __init__(self, http_client: Optional[httpx.AsyncClient] = None) -> None:
        self.s3_client = boto3.client("s3")
        self.bucket_name = os.environ.get("ASSETS_BUCKET_NAME", "")
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        self.http_client = http_client or httpx.AsyncClient()

    def _generate_key(self, post_id: str, url: str, content_type: str) -> str:
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
        ext = CONTENT_TYPE_EXTENSIONS.get(content_type.lower(), "jpg")
        return f"instagram/{post_id}/{url_hash}.{ext}"

    def _is_allowed_asset_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
        except Exception:
            return False

        if parsed.scheme != "https":
            return False

        hostname = (parsed.hostname or "").rstrip(".").lower()
        if not hostname:
            return False

        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            return False

        return any(
            hostname == suffix or hostname.endswith("." + suffix)
            for suffix in ALLOWED_ASSET_HOST_SUFFIXES
        )

    async def upload_image(self, url: str, post_id: str) -> Optional[str]:
        if not self.bucket_name:
            return None

        try:
            if not self._is_allowed_asset_url(url):
                logger.warning("Rejected asset URL outside allowlist: %s", url)
                return None

            response = await self.http_client.get(
                url, timeout=5.0, follow_redirects=False
            )
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "image/jpeg")
            content_type = content_type.split(";", 1)[0].strip().lower()
            if content_type not in CONTENT_TYPE_EXTENSIONS:
                logger.warning(
                    "Rejected asset with unsupported content type %s from %s",
                    content_type,
                    url,
                )
                return None

            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > MAX_ASSET_SIZE_BYTES:
                        logger.warning("Rejected oversized asset from %s", url)
                        return None
                except ValueError:
                    logger.warning("Invalid asset Content-Length from %s", url)

            if len(response.content) > MAX_ASSET_SIZE_BYTES:
                logger.warning("Rejected oversized asset body from %s", url)
                return None

            key = self._generate_key(post_id, url, content_type)

            await asyncio.to_thread(
                self.s3_client.put_object,
                Bucket=self.bucket_name,
                Key=key,
                Body=response.content,
                ContentType=content_type,
                CacheControl="max-age=31536000",
            )

            return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{key}"
        except httpx.HTTPError as exc:
            logger.warning("Failed to download asset from %s: %s", url, exc)
            return None
        except ClientError as exc:
            logger.warning(
                "Failed to upload asset for %s to S3: %s",
                post_id,
                exc,
            )
            return None
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.error("Unexpected error uploading asset for %s: %s", post_id, exc)
            return None
