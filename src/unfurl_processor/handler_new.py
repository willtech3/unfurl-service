"""
Enhanced Instagram unfurl service Lambda handler with Docker and modular architecture.

This handler provides high-performance Instagram link unfurling with:
- Docker-based Lambda for Playwright support
- Modular scraper architecture with intelligent fallbacks
- Enhanced Slack formatting with video playback
- Performance optimizations for fast cold starts
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .scrapers.manager import ScraperManager
from .slack_formatter import SlackFormatter

# Initialize observability tools
logger = Logger()
tracer = Tracer()

# Initialize metrics conditionally for testing
try:
    metrics = Metrics(
        namespace=os.environ.get("POWERTOOLS_METRICS_NAMESPACE", "UnfurlService")
    )
except Exception:
    metrics = None

# Global instances for performance
scraper_manager = None
slack_formatter = None
secrets_cache = {}


def get_scraper_manager() -> ScraperManager:
    """Get or create scraper manager instance."""
    global scraper_manager
    if scraper_manager is None:
        scraper_manager = ScraperManager()
    return scraper_manager


def get_slack_formatter() -> SlackFormatter:
    """Get or create Slack formatter instance."""
    global slack_formatter
    if slack_formatter is None:
        slack_formatter = SlackFormatter()
    return slack_formatter


def get_secrets_client():
    """Get Secrets Manager client."""
    return boto3.client(
        "secretsmanager", region_name=os.environ.get("AWS_REGION", "us-east-2")
    )


def get_dynamodb_resource():
    """Get DynamoDB resource."""
    return boto3.resource(
        "dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-2")
    )


@tracer.capture_method
def get_secret(secret_name: str) -> Dict[str, Any]:
    """Get secrets from Secrets Manager with caching."""
    if secret_name in secrets_cache:
        return secrets_cache[secret_name]

    try:
        secrets_client = get_secrets_client()
        response = secrets_client.get_secret_value(SecretId=secret_name)
        secret_data = json.loads(response["SecretString"])
        secrets_cache[secret_name] = secret_data
        return secret_data
    except Exception as e:
        logger.error(f"Failed to get secret {secret_name}: {e}")
        raise


@tracer.capture_method
def extract_instagram_id(url: str) -> Optional[str]:
    """Extract Instagram post ID from URL."""
    try:
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split("/") if p]

        for i, part in enumerate(path_parts):
            if part in ("p", "reel", "tv") and i + 1 < len(path_parts):
                return path_parts[i + 1]

        return None
    except Exception:
        return None


@tracer.capture_method
def get_cached_unfurl(url: str) -> Optional[Dict[str, Any]]:
    """Get cached unfurl data from DynamoDB."""
    try:
        table_name = os.environ.get("CACHE_TABLE_NAME")
        if not table_name:
            return None

        dynamodb = get_dynamodb_resource()
        table = dynamodb.Table(table_name)

        response = table.get_item(Key={"url": url})

        if "Item" in response:
            item = response["Item"]
            # Check if cache is still valid (24 hours)
            cached_time = datetime.fromisoformat(item["cached_at"])
            now = datetime.now(timezone.utc)

            if (now - cached_time).total_seconds() < 86400:  # 24 hours
                logger.info(f"Cache hit for {url}")
                return item.get("unfurl_data")

        return None
    except Exception as e:
        logger.warning(f"Failed to get cached unfurl: {e}")
        return None


@tracer.capture_method
def cache_unfurl(url: str, unfurl_data: Dict[str, Any]) -> None:
    """Cache unfurl data in DynamoDB."""
    try:
        table_name = os.environ.get("CACHE_TABLE_NAME")
        if not table_name:
            return

        dynamodb = get_dynamodb_resource()
        table = dynamodb.Table(table_name)

        # Calculate TTL (30 days from now)
        ttl = int(time.time()) + (30 * 24 * 60 * 60)

        table.put_item(
            Item={
                "url": url,
                "unfurl_data": unfurl_data,
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "ttl": ttl,
            }
        )

        logger.info(f"Cached unfurl for {url}")
    except Exception as e:
        logger.warning(f"Failed to cache unfurl: {e}")


@tracer.capture_method
async def fetch_instagram_data(url: str) -> Optional[Dict[str, Any]]:
    """
    Fetch Instagram data using the enhanced modular scraper system.

    Uses intelligent fallback strategy:
    1. Playwright browser automation (best bot evasion)
    2. HTTP scraping with enhanced headers
    3. oEmbed fallback endpoints
    4. Minimal fallback unfurl
    """
    start_time = time.time()

    try:
        # Check cache first
        cached_data = get_cached_unfurl(url)
        if cached_data:
            logger.info(f"Using cached data for {url}")
            return cached_data

        # Use scraper manager for intelligent fallback
        manager = get_scraper_manager()
        result = await manager.scrape_instagram_data(url)

        if result.success and result.data:
            logger.info(
                f"✅ Successfully scraped {url} using {result.method} "
                f"in {result.response_time_ms}ms"
            )

            # Add scraping metadata
            result.data["scraped_at"] = datetime.now(timezone.utc).isoformat()
            result.data["scrape_method"] = result.method
            result.data["response_time_ms"] = result.response_time_ms

            # Cache successful result
            cache_unfurl(url, result.data)

            # Record metrics
            if metrics:
                metrics.add_metric(name="ScrapeSuccess", unit=MetricUnit.Count, value=1)
                metrics.add_metric(
                    name="ScrapeLatency",
                    unit=MetricUnit.Milliseconds,
                    value=result.response_time_ms,
                )
                metrics.add_metadata(key="scrape_method", value=result.method)

            return result.data
        else:
            logger.warning(f"❌ All scraping methods failed for {url}: {result.error}")

            # Create fallback unfurl
            fallback_data = await manager.create_fallback_unfurl(url)

            if metrics:
                metrics.add_metric(
                    name="ScrapeFallback", unit=MetricUnit.Count, value=1
                )
                metrics.add_metadata(
                    key="failure_reason", value=result.error or "unknown"
                )

            return fallback_data

    except Exception as e:
        error_msg = f"Fatal error fetching Instagram data: {str(e)}"
        logger.error(error_msg)

        if metrics:
            metrics.add_metric(name="ScrapeError", unit=MetricUnit.Count, value=1)

        # Return minimal fallback
        manager = get_scraper_manager()
        return await manager.create_fallback_unfurl(url)
    finally:
        total_time = int((time.time() - start_time) * 1000)
        logger.info(f"Total fetch time for {url}: {total_time}ms")


@tracer.capture_method
def format_unfurl_data(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Format Instagram data for enhanced Slack unfurl."""
    if not data:
        return None

    try:
        formatter = get_slack_formatter()
        return formatter.format_unfurl_data(data)
    except Exception as e:
        logger.warning(f"Failed to format unfurl data: {e}")
        return None


@tracer.capture_method
def send_unfurl_to_slack(
    slack_client: WebClient, channel: str, ts: str, unfurls: Dict[str, Dict[str, Any]]
) -> None:
    """Send enhanced unfurl data to Slack with error handling."""
    try:
        response = slack_client.chat_unfurl(channel=channel, ts=ts, unfurls=unfurls)

        if response["ok"]:
            logger.info(f"✅ Successfully sent unfurl to {channel}")
            if metrics:
                metrics.add_metric(name="UnfurlSuccess", unit=MetricUnit.Count, value=1)
        else:
            logger.error(f"❌ Slack API error: {response.get('error', 'unknown')}")
            if metrics:
                metrics.add_metric(name="UnfurlError", unit=MetricUnit.Count, value=1)

    except SlackApiError as e:
        logger.error(f"❌ Slack API error: {e.response['error']}")
        if metrics:
            metrics.add_metric(name="UnfurlError", unit=MetricUnit.Count, value=1)
    except Exception as e:
        logger.error(f"❌ Failed to send unfurl: {str(e)}")
        if metrics:
            metrics.add_metric(name="UnfurlError", unit=MetricUnit.Count, value=1)


@tracer.capture_method
def canonicalize_instagram_url(url: str) -> str:
    """Return the canonical Instagram URL without query params or fragments."""
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except Exception:
        return url


@tracer.capture_method
def extract_instagram_links(links: List[Dict[str, str]]) -> List[str]:
    """Extract and validate Instagram links from Slack event."""
    instagram_links = []

    for link in links:
        url = link.get("url", "")
        domain = link.get("domain", "")

        if domain in ("instagram.com", "www.instagram.com"):
            # Validate it's a post/reel/tv URL
            if any(pattern in url for pattern in ["/p/", "/reel/", "/tv/"]):
                canonical_url = canonicalize_instagram_url(url)
                instagram_links.append(canonical_url)

    return instagram_links


@tracer.capture_lambda_handler
async def _lambda_handler(
    event: Dict[str, Any], context: LambdaContext
) -> Dict[str, Any]:
    """Enhanced Lambda handler for Instagram unfurl processing."""
    start_time = time.time()

    try:
        logger.info(f"Processing event: {json.dumps(event, default=str)}")

        # Parse SNS message
        if "Records" not in event:
            logger.error("No Records found in event")
            return {"statusCode": 400, "body": "Invalid event format"}

        for record in event["Records"]:
            if record.get("EventSource") == "aws:sns":
                try:
                    # Parse SNS message
                    sns_message = json.loads(record["Sns"]["Message"])

                    # Extract required fields
                    channel = sns_message.get("channel")
                    message_ts = sns_message.get("message_ts")
                    links = sns_message.get("links", [])

                    if not all([channel, message_ts, links]):
                        logger.warning(
                            f"Missing required fields in SNS message: {sns_message}"
                        )
                        continue

                    # Extract Instagram links
                    instagram_links = extract_instagram_links(links)

                    if not instagram_links:
                        logger.info("No Instagram links found in message")
                        continue

                    logger.info(f"Processing {len(instagram_links)} Instagram links")

                    # Get Slack credentials
                    try:
                        slack_secret = get_secret("unfurl-service/slack")
                        bot_token = slack_secret.get("bot_token")

                        if not bot_token:
                            logger.error("No Slack bot token found in secrets")
                            continue

                    except Exception as e:
                        logger.error(f"Failed to get Slack credentials: {e}")
                        continue

                    # Initialize Slack client
                    slack_client = WebClient(token=bot_token)

                    # Process each Instagram link concurrently for performance
                    tasks = []
                    for url in instagram_links:
                        tasks.append(fetch_instagram_data(url))

                    # Execute concurrently with timeout
                    try:
                        instagram_data_list = await asyncio.wait_for(
                            asyncio.gather(*tasks), timeout=30  # 30-second timeout
                        )
                    except asyncio.TimeoutError:
                        logger.warning("Timeout processing Instagram links")
                        continue

                    # Create unfurls
                    unfurls = {}
                    for url, data in zip(instagram_links, instagram_data_list):
                        if data:
                            formatted_unfurl = format_unfurl_data(data)
                            if formatted_unfurl:
                                unfurls[url] = formatted_unfurl

                    # Send unfurls to Slack
                    if unfurls:
                        send_unfurl_to_slack(slack_client, channel, message_ts, unfurls)
                        logger.info(f"✅ Processed {len(unfurls)} unfurls successfully")
                    else:
                        logger.warning("No valid unfurls created")

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse SNS message JSON: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing SNS record: {e}")
                    continue

        processing_time = int((time.time() - start_time) * 1000)
        logger.info(f"Total processing time: {processing_time}ms")

        if metrics:
            metrics.add_metric(
                name="ProcessingLatency",
                unit=MetricUnit.Milliseconds,
                value=processing_time,
            )

        return {"statusCode": 200, "body": "Successfully processed unfurl requests"}

    except Exception as e:
        logger.error(f"Fatal error in lambda handler: {str(e)}")

        if metrics:
            metrics.add_metric(name="HandlerError", unit=MetricUnit.Count, value=1)

        return {"statusCode": 500, "body": f"Internal server error: {str(e)}"}


# Create async wrapper for Lambda
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Async wrapper for Lambda handler."""
    return asyncio.run(_lambda_handler(event, context))


# Apply decorators conditionally based on metrics availability
if metrics:
    lambda_handler = tracer.capture_lambda_handler(metrics.log_metrics(lambda_handler))
