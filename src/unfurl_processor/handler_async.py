"""
Async Instagram Unfurl Handler with Enhanced Performance and Slack Formatting.

Optimized for Docker-based Lambda with:
- Playwright-first scraping strategy
- Rich video unfurls with playability
- Concurrent processing
- Enhanced error handling
- Performance monitoring
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import boto3
import httpx
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

from .scrapers.manager import ScraperManager
from .slack_formatter import SlackFormatter

# Initialize observability tools
logger = Logger()
tracer = Tracer()

# Initialize metrics conditionally
try:
    metrics = Metrics(
        namespace=os.environ.get("POWERTOOLS_METRICS_NAMESPACE", "UnfurlService")
    )
    metrics_available = True
except Exception:
    metrics = None
    metrics_available = False


class AsyncUnfurlHandler:
    """High-performance async handler for Instagram unfurls."""

    def __init__(self):
        self.logger = logger
        self.scraper_manager = None
        self.slack_formatter = None
        self.secrets_cache = {}
        self.secrets_client = None
        self.dynamodb = None
        self.http_client = None

        # Initialize on first use for better cold start performance

    async def _get_scraper_manager(self) -> ScraperManager:
        """Get or create scraper manager instance."""
        if self.scraper_manager is None:
            self.scraper_manager = ScraperManager()
            # ScraperManager initializes scrapers in constructor
            self.logger.info("✅ ScraperManager initialized")
        return self.scraper_manager

    def _get_slack_formatter(self) -> SlackFormatter:
        """Get or create Slack formatter instance."""
        if self.slack_formatter is None:
            self.slack_formatter = SlackFormatter()
        return self.slack_formatter

    def _get_secrets_client(self):
        """Get Secrets Manager client."""
        if self.secrets_client is None:
            self.secrets_client = boto3.client("secretsmanager")
        return self.secrets_client

    def _get_dynamodb_resource(self):
        """Get DynamoDB resource."""
        if self.dynamodb is None:
            self.dynamodb = boto3.resource("dynamodb")
        return self.dynamodb

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get HTTP client for async operations."""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                http2=True,
            )
        return self.http_client

    async def _get_secret(self, secret_name: str) -> Dict[str, Any]:
        """Get secrets from Secrets Manager with caching."""
        if secret_name in self.secrets_cache:
            return self.secrets_cache[secret_name]

        try:
            secrets_client = self._get_secrets_client()
            response = secrets_client.get_secret_value(SecretId=secret_name)
            secret_data = json.loads(response["SecretString"])
            self.secrets_cache[secret_name] = secret_data
            return secret_data
        except Exception as e:
            self.logger.error(f"Failed to get secret {secret_name}: {e}")
            raise

    def _extract_instagram_id(self, url: str) -> Optional[str]:
        """Extract Instagram post ID from URL."""
        try:
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split("/") if p]

            if len(path_parts) >= 2 and path_parts[0] in ["p", "reel", "tv"]:
                return path_parts[1]
            return None
        except Exception:
            return None

    async def _get_cached_unfurl(self, url: str) -> Optional[Dict[str, Any]]:
        """Get cached unfurl data from DynamoDB."""
        try:
            dynamodb = self._get_dynamodb_resource()
            table = dynamodb.Table(
                os.environ.get("CACHE_TABLE_NAME", "instagram-unfurl-cache")
            )

            response = table.get_item(Key={"url": url})

            if "Item" in response:
                item = response["Item"]
                # Check if cache is still valid (24 hours)
                cache_time = datetime.fromisoformat(item["timestamp"])
                if (datetime.now(timezone.utc) - cache_time).total_seconds() < 86400:
                    return item["unfurl_data"]
                else:
                    self.logger.info(f"Cache expired for URL: {url}")

            return None
        except Exception as e:
            self.logger.warning(f"Cache lookup failed: {e}")
            return None

    async def _cache_unfurl(self, url: str, unfurl_data: Dict[str, Any]) -> None:
        """Cache unfurl data in DynamoDB."""
        try:
            dynamodb = self._get_dynamodb_resource()
            table = dynamodb.Table(
                os.environ.get("CACHE_TABLE_NAME", "instagram-unfurl-cache")
            )

            instagram_id = self._extract_instagram_id(url)
            if not instagram_id:
                return

            table.put_item(
                Item={
                    "url": url,
                    "post_id": instagram_id,
                    "unfurl_data": unfurl_data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "ttl": int(time.time()) + 86400,  # 24 hours TTL
                }
            )
            self.logger.info(f"Cached unfurl data for URL: {url}")
        except Exception as e:
            self.logger.warning(f"Failed to cache unfurl data: {e}")

    async def _fetch_instagram_data(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Fetch Instagram data using enhanced async scraper system.

        Prioritizes Playwright for best results, with intelligent fallbacks.
        """
        start_time = time.time()

        try:
            scraper_manager = await self._get_scraper_manager()
            result = await scraper_manager.scrape_instagram_data(url)

            fetch_time = time.time() - start_time

            if metrics_available and metrics:
                metrics.add_metric(
                    name="InstagramFetchTime", unit=MetricUnit.Seconds, value=fetch_time
                )
                metrics.add_metric(
                    name="InstagramFetchSuccess",
                    unit=MetricUnit.Count,
                    value=1 if result.success else 0,
                )
                metrics.add_metric(
                    name=f"ScrapingMethod_{result.method}",
                    unit=MetricUnit.Count,
                    value=1,
                )

            self.logger.info(
                "Instagram data fetch completed",
                extra={
                    "url": url,
                    "success": result.success,
                    "method": result.method,
                    "fetch_time": fetch_time,
                    "has_video": bool(result.data and result.data.get("video_url")),
                    "is_fallback": result.data
                    and result.data.get("is_fallback", False),
                },
            )

            return result.data if result.success else None

        except Exception as e:
            self.logger.error(
                f"Failed to fetch Instagram data for {url}: {str(e)}", exc_info=True
            )
            if metrics_available and metrics:
                metrics.add_metric(
                    name="InstagramFetchErrors", unit=MetricUnit.Count, value=1
                )
            return None

    def _format_unfurl_data(
        self, data: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Format Instagram data for enhanced Slack unfurl."""
        try:
            formatter = self._get_slack_formatter()
            return formatter.format_unfurl_data(data)
        except Exception as e:
            self.logger.error(f"Failed to format unfurl data: {str(e)}")
            return None

    async def _send_unfurl_to_slack(
        self,
        slack_client: AsyncWebClient,
        channel: str,
        ts: str,
        unfurl_id: str,
        unfurls: Dict[str, Dict[str, Any]],
    ) -> bool:
        """Send enhanced unfurl data to Slack."""
        try:
            response = await slack_client.chat_unfurl(
                channel=channel, ts=ts, unfurl_id=unfurl_id, unfurls=unfurls
            )

            if response["ok"]:
                self.logger.info(f"Successfully sent unfurl to Slack channel {channel}")
                if metrics_available and metrics:
                    metrics.add_metric(
                        name="SlackUnfurlSuccess", unit=MetricUnit.Count, value=1
                    )
                return True
            else:
                self.logger.error(
                    f"Slack unfurl failed: {response.get('error', 'Unknown error')}"
                )
                if metrics_available and metrics:
                    metrics.add_metric(
                        name="SlackUnfurlErrors", unit=MetricUnit.Count, value=1
                    )
                return False

        except SlackApiError as e:
            self.logger.error(f"Slack API error: {e.response['error']}")
            if metrics_available and metrics:
                metrics.add_metric(
                    name="SlackApiErrors", unit=MetricUnit.Count, value=1
                )
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending unfurl: {str(e)}")
            if metrics_available and metrics:
                metrics.add_metric(
                    name="SlackUnfurlErrors", unit=MetricUnit.Count, value=1
                )
            return False

    def _canonicalize_instagram_url(self, url: str) -> str:
        """Return the canonical Instagram URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    def _extract_instagram_links(self, links: List[Dict[str, str]]) -> List[str]:
        """Extract and validate Instagram links from Slack event."""
        instagram_links = []
        for link in links:
            url = link.get("url", "")
            domain = link.get("domain", "")

            if domain == "instagram.com" and any(
                pattern in url for pattern in ["/p/", "/reel/", "/tv/"]
            ):
                canonical_url = self._canonicalize_instagram_url(url)
                instagram_links.append(canonical_url)

        return instagram_links

    @tracer.capture_method
    async def process_event(
        self, event: Dict[str, Any], context: LambdaContext
    ) -> Dict[str, Any]:
        """
        Process incoming Lambda event with enhanced async processing.

        Args:
            event: Lambda event data
            context: Lambda context

        Returns:
            Response dictionary
        """
        start_time = time.time()

        try:
            # Parse SNS message or direct event
            if "Records" in event and event["Records"]:
                sns_message = json.loads(event["Records"][0]["Sns"]["Message"])
            else:
                sns_message = event

            # Validate event structure
            if not all(
                key in sns_message for key in ["channel", "message_ts", "unfurl_id", "links"]
            ):
                self.logger.error(
                    "Invalid event structure", extra={"event": sns_message}
                )
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Invalid event structure"}),
                }

            channel = sns_message["channel"]
            message_ts = sns_message["message_ts"]
            unfurl_id = sns_message["unfurl_id"]
            links = sns_message["links"]

            # Extract Instagram links
            instagram_links = self._extract_instagram_links(links)

            if not instagram_links:
                self.logger.info("No Instagram links found in event")
                return {
                    "statusCode": 200,
                    "body": json.dumps({"message": "No Instagram links found"}),
                }

            self.logger.info(
                f"Processing {len(instagram_links)} Instagram links for "
                f"channel {channel}"
            )

            # Get Slack credentials
            slack_secrets = await self._get_secret(
                os.environ.get("SLACK_SECRET_NAME", "slack/unfurl-bot")
            )
            slack_token = slack_secrets["bot_token"]

            # Initialize async Slack client
            slack_client = AsyncWebClient(token=slack_token)

            # Process links concurrently for better performance
            tasks = []
            for url in instagram_links:
                task = self._process_single_link(url)
                tasks.append(task)

            # Execute all tasks concurrently
            unfurl_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Collect successful unfurls
            unfurls = {}
            for i, result in enumerate(unfurl_results):
                if isinstance(result, Exception):
                    self.logger.error(
                        f"Error processing link {instagram_links[i]}: {str(result)}"
                    )
                    continue

                url, unfurl_data = result
                if unfurl_data:
                    unfurls[url] = unfurl_data

            # Send unfurls to Slack if any succeeded
            if unfurls:
                await self._send_unfurl_to_slack(
                    slack_client, channel, message_ts, unfurl_id, unfurls
                )

                processing_time = time.time() - start_time

                if metrics_available and metrics:
                    metrics.add_metric(
                        name="TotalProcessingTime",
                        unit=MetricUnit.Seconds,
                        value=processing_time,
                    )
                    metrics.add_metric(
                        name="LinksProcessed",
                        unit=MetricUnit.Count,
                        value=len(instagram_links),
                    )
                    metrics.add_metric(
                        name="UnfurlsGenerated",
                        unit=MetricUnit.Count,
                        value=len(unfurls),
                    )

                return {
                    "statusCode": 200,
                    "body": json.dumps(
                        {
                            "message": f"Processed {len(unfurls)} unfurls successfully",
                            "processing_time": processing_time,
                        }
                    ),
                }
            else:
                self.logger.warning("No unfurls generated from Instagram links")
                return {
                    "statusCode": 200,
                    "body": json.dumps({"message": "No unfurls generated"}),
                }

        except Exception as e:
            self.logger.error(
                f"Unexpected error in process_event: {str(e)}", exc_info=True
            )
            if metrics_available and metrics:
                metrics.add_metric(
                    name="ProcessingErrors", unit=MetricUnit.Count, value=1
                )

            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Internal server error"}),
            }

    async def _process_single_link(
        self, url: str
    ) -> tuple[str, Optional[Dict[str, Any]]]:
        """Process a single Instagram link with caching."""
        try:
            # Check cache first
            cached_data = await self._get_cached_unfurl(url)
            if cached_data:
                return url, cached_data

            # Fetch fresh data
            instagram_data = await self._fetch_instagram_data(url)

            # Format for Slack
            unfurl_data = self._format_unfurl_data(instagram_data)

            # Cache the result
            if unfurl_data:
                await self._cache_unfurl(url, unfurl_data)

            return url, unfurl_data

        except Exception as e:
            self.logger.error(f"Error processing link {url}: {str(e)}")
            return url, None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup resources."""
        if self.http_client:
            await self.http_client.aclose()

        if self.scraper_manager:
            await self.scraper_manager.cleanup()
