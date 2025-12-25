"""
S3 Asset Persistence for Instagram media.

This module persists ephemeral Instagram CDN images to a public S3 bucket so
Slack unfurls remain stable over time.
"""

import asyncio
import hashlib
import os
from typing import Optional

import boto3
import httpx
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

logger = Logger()


class AssetManager:
    def __init__(self, http_client: Optional[httpx.AsyncClient] = None) -> None:
        self.s3_client = boto3.client("s3")
        self.bucket_name = os.environ.get("ASSETS_BUCKET_NAME", "")
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        self.http_client = http_client or httpx.AsyncClient()

    def _generate_key(self, post_id: str, url: str, content_type: str) -> str:
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]

        ct = (content_type or "image/jpeg").split(";", 1)[0].strip().lower()
        ext_map = {
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
        }
        ext = ext_map.get(ct, "jpg")
        return f"instagram/{post_id}/{url_hash}.{ext}"

    async def upload_image(self, url: str, post_id: str) -> Optional[str]:
        if not self.bucket_name or not url or not post_id:
            return None

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

        except httpx.HTTPError as e:
            logger.warning(f"Failed to download asset: {e}")
            return None
        except ClientError as e:
            status = (
                e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                if hasattr(e, "response")
                else None
            )
            logger.warning(f"Failed to upload asset to S3 (status={status}): {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error persisting asset: {e}", exc_info=True)
            return None
