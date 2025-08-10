"""Lightweight Instagram video proxy utilities.

Implements a simple HTML player proxy and minimal caching using DynamoDB.
Designed to satisfy tests in tests/test_video_proxy.py.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
from typing import Any, Dict, Optional

import boto3
import requests


class VideoProxy:
    """Proxy helper to embed Instagram-hosted videos via an HTML5 player."""

    def __init__(self) -> None:
        self.cache_table_name = os.environ.get("CACHE_TABLE_NAME", "")
        self._dynamodb = None

    def lambda_handler(
        self, event: Dict[str, Any] | None, _context: Any
    ) -> Dict[str, Any]:
        try:
            if not event:
                raise ValueError("Invalid event")

            path_params = (event or {}).get("pathParameters", {}) or {}
            if "video_url" not in path_params:
                return self._create_error_response(400, "Missing video URL parameter")

            encoded_url = path_params.get("video_url", "")
            try:
                video_url = urllib.parse.unquote(encoded_url)
            except Exception:
                return self._create_error_response(
                    404, "Video not found or unavailable"
                )

            # Try cache first if configured
            cached = self._get_cached_video_data(video_url)
            if cached and cached.get("status") == "available":
                return self._create_video_response(cached)

            # Fetch fresh metadata
            metadata = self._fetch_video_data(video_url)
            if not metadata:
                return self._create_error_response(
                    404, "Video not found or unavailable"
                )

            # Cache successful lookup (best-effort)
            try:
                self._cache_video_data(video_url, metadata)
            except Exception:
                pass

            return self._create_video_response(metadata)
        except Exception:
            return self._create_error_response(500, "Internal server error")

    def _fetch_video_data(self, video_url: str) -> Optional[Dict[str, Any]]:
        try:
            resp = requests.head(video_url, timeout=10, allow_redirects=True)
            if resp.status_code != 200:
                return None
            content_type = resp.headers.get("content-type", "application/octet-stream")
            content_length_str = resp.headers.get("content-length")
            content_length = (
                int(content_length_str)
                if content_length_str and content_length_str.isdigit()
                else None
            )
            return {
                "video_url": video_url,
                "content_type": content_type,
                "content_length": content_length,
                "status": "available",
            }
        except Exception:
            return None

    def _create_video_response(self, video_data: Dict[str, Any]) -> Dict[str, Any]:
        video_url = video_data.get("video_url", "")
        body = (
            "<html><head><meta charset='utf-8'></head><body>"
            f"<video controls autoplay muted playsinline>"
            f'<source src="{video_url}" type="video/mp4" />'
            "</video>"
            "</body></html>"
        )
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "text/html",
                "X-Frame-Options": "ALLOWALL",
            },
            "body": body,
        }

    def _create_error_response(self, status: int, message: str) -> Dict[str, Any]:
        return {
            "statusCode": status,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": message}),
        }

    def _get_cached_video_data(self, video_url: str) -> Optional[Dict[str, Any]]:
        if not self.cache_table_name:
            return None
        try:
            table = self._get_dynamodb_table()
            key = {"url": f"video_proxy:{video_url}"}
            resp = table.get_item(Key=key)
            item = resp.get("Item")
            if item and isinstance(item, dict):
                return item.get("data")
            return None
        except Exception:
            return None

    def _cache_video_data(self, video_url: str, data: Dict[str, Any]) -> None:
        if not self.cache_table_name:
            return
        table = self._get_dynamodb_table()
        ttl_seconds = int(time.time()) + 6 * 3600  # 6 hours
        item = {
            "url": f"video_proxy:{video_url}",
            "data": data,
            "ttl": ttl_seconds,
        }
        table.put_item(Item=item)

    def _get_dynamodb_table(self):
        if self._dynamodb is None:
            self._dynamodb = boto3.resource("dynamodb")
        return self._dynamodb.Table(self.cache_table_name)
