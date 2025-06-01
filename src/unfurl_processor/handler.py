import os
import time
import re
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlparse
import boto3
import requests
from bs4 import BeautifulSoup
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import json
from typing import cast

# Type imports for boto3
from boto3.resources.base import ServiceResource
from botocore.client import BaseClient

# Initialize Powertools
logger = Logger()
tracer = Tracer()

# Initialize metrics conditionally
if os.environ.get("DISABLE_METRICS") == "true":
    metrics = None
else:
    metrics = Metrics(
        namespace=os.environ.get("POWERTOOLS_METRICS_NAMESPACE", "UnfurlService")
    )

# Environment variables
CACHE_TABLE_NAME = os.environ.get("CACHE_TABLE_NAME", "unfurl-cache")
SLACK_SECRET_NAME = os.environ.get("SLACK_SECRET_NAME", "unfurl-service/slack")
CACHE_TTL_HOURS = int(os.environ.get("CACHE_TTL_HOURS", "24"))

# Cache for secrets
_secrets_cache: Dict[str, Dict[str, Any]] = {}


def get_dynamodb_resource() -> ServiceResource:
    """Get DynamoDB resource."""
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-2")
    return boto3.resource("dynamodb", region_name=region)


def get_secrets_client() -> BaseClient:
    """Get Secrets Manager client."""
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-2")
    return boto3.client("secretsmanager", region_name=region)


@tracer.capture_method
def get_secret(secret_name: str) -> Dict[str, Any]:
    """Get secrets from Secrets Manager with caching."""
    if secret_name not in _secrets_cache:
        secrets_client = get_secrets_client()
        response = secrets_client.get_secret_value(SecretId=secret_name)
        _secrets_cache[secret_name] = json.loads(response["SecretString"])
    return _secrets_cache[secret_name]


@tracer.capture_method
def extract_instagram_id(url: str) -> Optional[str]:
    """Extract Instagram post ID from URL."""
    # Handle different Instagram URL formats
    # https://www.instagram.com/p/ABC123/
    # https://www.instagram.com/reel/ABC123/
    # https://instagram.com/p/ABC123/?igshid=xxx

    parsed = urlparse(url)
    path_parts = parsed.path.strip("/").split("/")

    if len(path_parts) >= 2 and path_parts[0] in ["p", "reel"]:
        return path_parts[1]

    return None


@tracer.capture_method
def get_cached_unfurl(url: str) -> Optional[Dict[str, Any]]:
    """Get cached unfurl data from DynamoDB."""
    dynamodb = get_dynamodb_resource()
    cache_table = dynamodb.Table(CACHE_TABLE_NAME)

    try:
        response = cache_table.get_item(Key={"url": url})

        if "Item" in response:
            item = response["Item"]
            # Check if cache is still valid
            if item.get("ttl", 0) > int(time.time()):
                logger.info("Cache hit for URL", extra={"url": url})
                if metrics:
                    metrics.add_metric(name="CacheHit", unit=MetricUnit.Count, value=1)
                unfurl_data = item.get("unfurl_data")
                return cast(Optional[Dict[str, Any]], unfurl_data)

        if metrics:
            metrics.add_metric(name="CacheMiss", unit=MetricUnit.Count, value=1)
        return None

    except Exception as e:
        logger.error("Error reading from cache", extra={"error": str(e)})
        return None


@tracer.capture_method
def cache_unfurl(url: str, unfurl_data: Dict[str, Any]) -> None:
    """Cache unfurl data in DynamoDB."""
    dynamodb = get_dynamodb_resource()
    cache_table = dynamodb.Table(CACHE_TABLE_NAME)

    try:
        ttl = int(time.time()) + (CACHE_TTL_HOURS * 3600)

        cache_table.put_item(
            Item={
                "url": url,
                "unfurl_data": unfurl_data,
                "ttl": ttl,
                "created_at": datetime.utcnow().isoformat(),
            }
        )

        logger.info("Cached unfurl data", extra={"url": url, "ttl": ttl})

    except Exception as e:
        logger.error("Error writing to cache", extra={"error": str(e)})


@tracer.capture_method
def fetch_instagram_data(url: str, post_id: str) -> Optional[Dict[str, Any]]:
    """Fetch Instagram post data using web scraping."""
    try:
        # Check cache first
        cached_data = get_cached_unfurl(url)
        if cached_data:
            # cached_data is already a dict, not a string
            return cached_data

        # Fetch the Instagram page
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # Parse the HTML
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract data from meta tags and scripts
        data = extract_instagram_data(soup, url)

        # Fallback to oEmbed API if scraping did not return data
        if not data:
            logger.warning(
                "HTML scrape yielded no data, attempting oEmbed fallback",
                extra={"url": url},
            )
            data = fetch_instagram_oembed(url)

        if data:
            # Cache the result
            cache_unfurl(url, data)

            if metrics:
                metrics.add_metric(
                    name="InstagramDataFetched", unit=MetricUnit.Count, value=1
                )

        return data

    except Exception as e:
        logger.error(
            "Error fetching Instagram data", extra={"error": str(e), "url": url}
        )
        if metrics:
            metrics.add_metric(
                name="InstagramFetchError", unit=MetricUnit.Count, value=1
            )

        return None


def extract_instagram_data(soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
    """Extract Instagram post data from the page HTML."""
    try:
        # Try to find the data in various meta tags
        og_image = soup.find("meta", property="og:image")
        og_description = soup.find("meta", property="og:description")
        og_title = soup.find("meta", property="og:title")

        # Extract from JSON-LD structured data
        json_ld = soup.find("script", type="application/ld+json")
        structured_data = None
        if json_ld and hasattr(json_ld, "string"):
            try:
                structured_data = json.loads(json_ld.string)
            except json.JSONDecodeError:
                pass

        # Build the data object
        data = {
            "id": extract_post_id(url),
            "permalink": url,
            "timestamp": datetime.utcnow().isoformat(),
            "likes": None,
            "comments": None,
        }

        # Extract image URL
        if og_image and hasattr(og_image, "get"):
            content = og_image.get("content")
            if content:
                data["media_url"] = content
                data["media_type"] = "IMAGE"

        # Extract caption and username
        if og_description and hasattr(og_description, "get"):
            description = og_description.get("content", "")
            # Try to parse Instagram's description format
            match = re.match(
                r'^([\d,]+) Likes, ([\d,]+) Comments - (.+?) on Instagram: "(.+)"$',
                description,
            )
            if match:
                data["likes"] = match.group(1).replace(",", "")
                data["comments"] = match.group(2).replace(",", "")
                data["username"] = match.group(3)
                data["caption"] = match.group(4)
            else:
                # Fallback parsing
                parts = description.split(" on Instagram: ")
                if len(parts) == 2:
                    data["username"] = (
                        parts[0].split(" - ")[-1]
                        if " - " in parts[0]
                        else "Instagram User"
                    )
                    data["caption"] = parts[1].strip('"')
                else:
                    data["caption"] = description

        # Extract from title if needed
        if og_title and hasattr(og_title, "get"):
            title = og_title.get("content", "")
            match = re.search(r"@(\w+)", title)
            if match:
                data["username"] = match.group(1)

        # Use structured data if available
        if structured_data:
            if isinstance(structured_data, dict):
                if "author" in structured_data:
                    data["username"] = structured_data["author"].get(
                        "name", data.get("username", "Instagram User")
                    )
                if "caption" in structured_data:
                    data["caption"] = structured_data["caption"]
                if "uploadDate" in structured_data:
                    data["timestamp"] = structured_data["uploadDate"]

        return data if "media_url" in data else None

    except Exception as e:
        logger.error("Error extracting Instagram data", extra={"error": str(e)})
        return None


def fetch_instagram_oembed(url: str) -> Optional[Dict[str, Any]]:
    """Fetch Instagram data using oEmbed API as fallback."""
    try:
        oembed_url = "https://graph.facebook.com/v18.0/instagram_oembed"
        params = {
            "url": url,
            "access_token": (
                f"{os.environ.get('FACEBOOK_APP_ID', '')}"
                f"|{os.environ.get('FACEBOOK_APP_SECRET', '')}"
            ),
            "omitscript": "true",
        }

        response = requests.get(oembed_url, params=params, timeout=10)

        # If no Facebook app credentials, try without access token
        if response.status_code == 400:
            params.pop("access_token", None)
            response = requests.get(oembed_url, params=params, timeout=10)

        if response.status_code == 200:
            oembed_data = response.json()

            # Convert oEmbed data to our format
            return {
                "id": extract_post_id(url),
                "permalink": url,
                "media_url": oembed_data.get("thumbnail_url"),
                "media_type": "IMAGE",
                "username": oembed_data.get("author_name", "Instagram User"),
                "caption": oembed_data.get("title", ""),
                "timestamp": datetime.utcnow().isoformat(),
                "provider": "oembed",
            }
    except Exception as e:
        logger.error("Error fetching oEmbed data", extra={"error": str(e)})

    return None


def extract_post_id(url: str) -> str:
    """Extract post ID from Instagram URL."""
    # Match patterns like /p/ABC123/ or /reel/ABC123/
    match = re.search(r"/(p|reel|tv)/([A-Za-z0-9_-]+)", url)
    return match.group(2) if match else ""


def format_unfurl_data(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Format Instagram data for Slack unfurl."""
    if data is None:
        return None
    unfurl = {
        "title": f"@{data.get('username', 'Instagram User')}",
        "title_link": data.get("permalink"),
        "color": "#E4405F",  # Instagram brand color
        "footer": "Instagram",
        "footer_icon": (
            "https://www.instagram.com/static/images/ico/"
            "favicon-192.png/68d99ba29cc8.png"
        ),
    }

    # Add image if available
    if data.get("media_url"):
        unfurl["image_url"] = data["media_url"]

    # Add caption as text
    caption = data.get("caption", "")
    if caption:
        # Truncate long captions
        if len(caption) > 300:
            caption = caption[:297] + "..."
        unfurl["text"] = caption

    # Add fields for engagement metrics if available
    fields = []
    if data.get("likes"):
        fields.append(
            {
                "title": "Likes",
                "value": (
                    f"{int(str(data['likes']).replace(',', '')):,}"
                    if isinstance(data["likes"], (int, float))
                    or (
                        isinstance(data["likes"], str)
                        and str(data["likes"]).replace(",", "").isdigit()
                    )
                    else str(data["likes"])
                ),
                "short": True,
            }
        )
    if data.get("comments"):
        fields.append(
            {
                "title": "Comments",
                "value": (
                    f"{int(str(data['comments']).replace(',', '')):,}"
                    if isinstance(data["comments"], (int, float))
                    or (
                        isinstance(data["comments"], str)
                        and str(data["comments"]).replace(",", "").isdigit()
                    )
                    else str(data["comments"])
                ),
                "short": True,
            }
        )

    if fields:
        unfurl["fields"] = fields

    # Add timestamp if available
    if data.get("timestamp"):
        try:
            # Parse ISO timestamp and convert to Unix timestamp
            dt = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
            unfurl["ts"] = int(dt.timestamp())
        except (ValueError, AttributeError):
            pass

    # Add a note if this is from oEmbed fallback
    if data.get("provider") == "oembed":
        unfurl["footer"] = "Instagram (via oEmbed)"

    return unfurl


@tracer.capture_method
def send_unfurl_to_slack(
    slack_client: WebClient, channel: str, ts: str, unfurls: Dict[str, Dict[str, Any]]
) -> bool:
    """Send unfurl data to Slack."""
    try:
        response = slack_client.chat_unfurl(channel=channel, ts=ts, unfurls=unfurls)

        if response["ok"]:
            logger.info(
                "Successfully sent unfurl to Slack",
                extra={"channel": channel, "ts": ts, "urls": list(unfurls.keys())},
            )
            if metrics:
                metrics.add_metric(name="UnfurlSuccess", unit=MetricUnit.Count, value=1)
            return True
        else:
            logger.error("Slack API returned not ok", extra={"response": response})
            return False

    except SlackApiError as e:
        logger.error("Slack API error", extra={"error": str(e), "response": e.response})
        if metrics:
            metrics.add_metric(name="SlackAPIError", unit=MetricUnit.Count, value=1)
        return False


def _lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Process Instagram links and send unfurls to Slack."""
    try:
        # Validate event structure
        if "Records" not in event:
            logger.error("Invalid event structure - missing Records")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid event structure"}),
            }

        # Get Slack credentials
        slack_secrets = get_secret(SLACK_SECRET_NAME)
        slack_client = WebClient(token=slack_secrets["bot_token"])

        # Process SNS messages
        for record in event.get("Records", []):
            if "Sns" not in record or "Message" not in record["Sns"]:
                logger.error("Invalid record structure", extra={"record": record})
                continue

            sns_message = json.loads(record["Sns"]["Message"])

            channel = sns_message["channel"]
            message_ts = sns_message["message_ts"]
            links = sns_message["links"]

            logger.info(
                f"Processing {len(links)} Instagram links",
                extra={"channel": channel, "message_ts": message_ts},
            )

            # Build unfurls for each link
            unfurls = {}
            for link in links:
                url = link["url"]
                post_id = extract_post_id(url)

                if post_id:
                    instagram_data = fetch_instagram_data(url, post_id)
                    if instagram_data:
                        unfurl_data = format_unfurl_data(instagram_data)
                        if unfurl_data:
                            unfurls[url] = unfurl_data
                    else:
                        logger.warning(f"Could not fetch data for {url}")
                else:
                    logger.warning(f"Could not extract post ID from {url}")

            # Send unfurls to Slack if we have any
            if unfurls:
                send_unfurl_to_slack(slack_client, channel, message_ts, unfurls)
            else:
                logger.warning(
                    "No unfurls to send",
                    extra={"channel": channel, "message_ts": message_ts},
                )

        return {"statusCode": 200, "body": json.dumps({"message": "Success"})}

    except Exception as e:
        logger.error(
            "Unexpected error in handler", extra={"error": str(e)}, exc_info=True
        )
        if metrics:
            metrics.add_metric(name="HandlerError", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


# Apply decorators conditionally based on metrics availability
if metrics:
    lambda_handler = logger.inject_lambda_context(
        correlation_id_path="Records[0].Sns.MessageId"
    )(
        tracer.capture_lambda_handler(
            metrics.log_metrics(capture_cold_start_metric=True)(_lambda_handler)
        )
    )
else:
    lambda_handler = logger.inject_lambda_context(
        correlation_id_path="Records[0].Sns.MessageId"
    )(tracer.capture_lambda_handler(_lambda_handler))
