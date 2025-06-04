"""Video proxy for Instagram videos to enable Slack embedded playback."""

import json
import logging
import os
import urllib.parse
from typing import Any, Dict, Optional

import boto3
import requests
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger(__name__)


class VideoProxy:
    """Proxy Instagram videos for Slack embedded playback."""

    def __init__(self):
        """Initialize the video proxy."""
        self.cache_table_name = os.environ.get("CACHE_TABLE_NAME")
        self.dynamodb = boto3.resource("dynamodb") if self.cache_table_name else None

    def lambda_handler(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """
        Lambda handler for video proxy requests.

        Expected path: /video/{encoded_video_url}
        """
        try:
            # Extract video URL from path
            path_params = event.get("pathParameters", {})
            encoded_url = path_params.get("video_url")

            if not encoded_url:
                return self._create_error_response(400, "Missing video URL parameter")

            # Decode the video URL
            try:
                video_url = urllib.parse.unquote(encoded_url)
            except Exception as e:
                logger.error(f"Failed to decode video URL: {e}")
                return self._create_error_response(400, "Invalid video URL encoding")

            # Check cache first
            cached_data = self._get_cached_video_data(video_url)
            if cached_data:
                return self._create_video_response(cached_data)

            # Fetch video metadata and create embeddable response
            video_data = self._fetch_video_data(video_url)
            if not video_data:
                return self._create_error_response(
                    404, "Video not found or unavailable"
                )

            # Cache the result
            self._cache_video_data(video_url, video_data)

            return self._create_video_response(video_data)

        except Exception as e:
            logger.error(f"Video proxy error: {e}")
            return self._create_error_response(500, "Internal server error")

    def _fetch_video_data(self, video_url: str) -> Optional[Dict[str, Any]]:
        """Fetch video data and create embeddable metadata."""
        try:
            # Make a HEAD request to verify video is accessible
            response = requests.head(
                video_url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36"
                    ),
                    "Accept": "video/*,*/*;q=0.9",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                },
                timeout=10,
                allow_redirects=True,
            )

            if response.status_code not in [200, 206]:
                logger.warning(
                    f"Video URL returned status {response.status_code}: {video_url}"
                )
                return None

            # Extract video metadata
            content_type = response.headers.get("content-type", "video/mp4")
            content_length = response.headers.get("content-length")

            return {
                "video_url": video_url,
                "content_type": content_type,
                "content_length": int(content_length) if content_length else None,
                "status": "available",
            }

        except Exception as e:
            logger.error(f"Failed to fetch video data for {video_url}: {e}")
            return None

    def _create_video_response(self, video_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an embeddable video response for Slack."""
        video_url = video_data["video_url"]

        # Create HTML5 video player that's embeddable in iframes
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ margin: 0; padding: 0; background: #000; }}
                video {{ width: 100%; height: 100%; object-fit: contain; }}
                .container {{
                    width: 100vw; height: 100vh; display: flex;
                    align-items: center; justify-content: center;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <video controls autoplay muted playsinline>
                    <source
                        src="{video_url}"
                        type="{video_data.get('content_type', 'video/mp4')}"
                    >
                    Your browser does not support the video tag.
                </video>
            </div>
        </body>
        </html>
        """

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "text/html",
                "Cache-Control": "public, max-age=3600",
                "X-Frame-Options": "ALLOWALL",  # Allow embedding in iframes
                "X-Content-Type-Options": "nosniff",
            },
            "body": html_content,
        }

    def _get_cached_video_data(self, video_url: str) -> Optional[Dict[str, Any]]:
        """Get cached video data from DynamoDB."""
        if not self.dynamodb or not self.cache_table_name:
            return None

        try:
            table = self.dynamodb.Table(self.cache_table_name)
            cache_key = f"video_proxy:{video_url}"

            response = table.get_item(Key={"url": cache_key})

            if "Item" in response:
                return response["Item"].get("data")

        except ClientError as e:
            logger.warning(f"Failed to get cached video data: {e}")

        return None

    def _cache_video_data(self, video_url: str, video_data: Dict[str, Any]) -> None:
        """Cache video data in DynamoDB."""
        if not self.dynamodb or not self.cache_table_name:
            return

        try:
            table = self.dynamodb.Table(self.cache_table_name)
            cache_key = f"video_proxy:{video_url}"

            import time

            ttl = int(time.time()) + (6 * 3600)  # 6 hours TTL

            table.put_item(Item={"url": cache_key, "data": video_data, "ttl": ttl})

        except ClientError as e:
            logger.warning(f"Failed to cache video data: {e}")

    def _create_error_response(self, status_code: int, message: str) -> Dict[str, Any]:
        """Create an error response."""
        return {
            "statusCode": status_code,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": message}),
        }


# Lambda handler function
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda entry point."""
    proxy = VideoProxy()
    return proxy.lambda_handler(event, context)
