import asyncio
import hashlib
import os
import boto3
import httpx
from botocore.exceptions import ClientError
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class AssetManager:
    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        self.bucket_name = os.environ.get("ASSETS_BUCKET_NAME")
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        self.s3_client = boto3.client("s3")
        self.http_client = http_client or httpx.AsyncClient()

    def _generate_key(self, post_id: str, url: str, content_type: str) -> str:
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]

        ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
        ext = ext_map.get(content_type, ".jpg")

        return f"instagram/{post_id}/{url_hash}{ext}"

    async def upload_image(self, url: str, post_id: str) -> Optional[str]:
        if not self.bucket_name:
            logger.warning("ASSETS_BUCKET_NAME not set, skipping upload")
            return None

        try:
            response = await self.http_client.get(url, timeout=5.0)
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "image/jpeg")
            key = self._generate_key(post_id, url, content_type)

            # Run blocking s3 call in thread
            await asyncio.to_thread(
                self.s3_client.put_object,
                Bucket=self.bucket_name,
                Key=key,
                Body=response.content,
                ContentType=content_type,
                CacheControl="max-age=31536000",
            )

            return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{key}"

        except httpx.HTTPError as e:
            logger.warning(f"Failed to download asset: {e}")
            return None
        except ClientError as e:
            logger.warning(f"S3 upload failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in asset upload: {e}")
            return None
