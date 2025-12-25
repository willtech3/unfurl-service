"""
S3 Asset Manager for persisting Instagram images.

This module handles downloading images from Instagram CDN and uploading
them to S3 for long-term persistence, fixing the "disappearing images"
issue caused by ephemeral Instagram CDN URLs.
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
    """Manages uploading Instagram images to S3 for persistence."""

    # Content-Type to file extension mapping
    CONTENT_TYPE_EXTENSIONS = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }
    DEFAULT_EXTENSION = "jpg"

    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        """
        Initialize the AssetManager.

        Args:
            http_client: Optional httpx AsyncClient for downloading images.
                        If not provided, a new client will be created.
        """
        self.s3_client = boto3.client("s3")
        self.bucket_name = os.environ.get("ASSETS_BUCKET_NAME", "")
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        self.http_client = http_client

    def _generate_key(self, post_id: str, url: str, content_type: str) -> str:
        """
        Generate a unique S3 key for the image.

        Args:
            post_id: The Instagram post ID
            url: The source URL of the image
            content_type: The Content-Type of the image

        Returns:
            S3 key in format: instagram/{post_id}/{url_hash}.{ext}
        """
        # Hash the source URL for uniqueness
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]

        # Map Content-Type to extension
        ext = self.CONTENT_TYPE_EXTENSIONS.get(content_type, self.DEFAULT_EXTENSION)

        return f"instagram/{post_id}/{url_hash}.{ext}"

    async def upload_image(self, url: str, post_id: str) -> Optional[str]:
        """
        Download an image and upload it to S3.

        Args:
            url: The source URL of the image to download
            post_id: The Instagram post ID for key generation

        Returns:
            The public S3 URL if successful, None otherwise
        """
        # Create http client if not provided
        http_client = self.http_client
        close_client = False
        if http_client is None:
            http_client = httpx.AsyncClient(timeout=5.0)
            close_client = True

        try:
            # Download the image
            response = await http_client.get(url, timeout=5.0)
            response.raise_for_status()

            # Detect content type
            content_type = response.headers.get("Content-Type", "image/jpeg")
            # Strip any charset or other parameters from content type
            if ";" in content_type:
                content_type = content_type.split(";")[0].strip()

            # Generate S3 key
            key = self._generate_key(post_id, url, content_type)

            # Upload to S3 (run sync operation in thread to avoid blocking)
            await asyncio.to_thread(
                self.s3_client.put_object,
                Bucket=self.bucket_name,
                Key=key,
                Body=response.content,
                ContentType=content_type,
                CacheControl="max-age=31536000",  # 1 year
                # Note: Do NOT set ACL - bucket policy handles public access
            )

            # Return the public S3 URL
            s3_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{key}"
            logger.info(f"Successfully uploaded image to S3: {s3_url}")
            return s3_url

        except httpx.HTTPStatusError as e:
            logger.warning(
                f"HTTP error downloading image from {url}: "
                f"status={e.response.status_code}"
            )
            return None

        except httpx.TimeoutException as e:
            logger.warning(f"Timeout downloading image from {url}: {e}")
            return None

        except httpx.HTTPError as e:
            logger.warning(f"HTTP error downloading image from {url}: {e}")
            return None

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.warning(
                f"S3 upload failed for {url}: " f"error_code={error_code}, message={e}"
            )
            return None

        except Exception as e:
            logger.error(f"Unexpected error uploading image from {url}: {e}")
            return None

        finally:
            if close_client and http_client is not None:
                await http_client.aclose()
