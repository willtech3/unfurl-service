import asyncio
import hashlib
import logging
import os
from typing import Optional

import boto3
import httpx
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


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

    async def upload_image(self, url: str, post_id: str) -> Optional[str]:
        try:
            response = await self.http_client.get(url, timeout=5.0)
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "image/jpeg")
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
