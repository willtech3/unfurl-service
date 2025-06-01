import json
import os
import random
import re
import time
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import boto3
import requests
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

# Type imports for boto3
from boto3.resources.base import ServiceResource
from botocore.client import BaseClient
from bs4 import BeautifulSoup
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Initialize Powertools logger with a service name.
# Defaults to "UnfurlService" when POWERTOOLS_SERVICE_NAME is not set.
logger = Logger(service=os.getenv("POWERTOOLS_SERVICE_NAME", "UnfurlService"))
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
                return unfurl_data

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
def fetch_instagram_data(url: str) -> Optional[Dict[str, Any]]:
    """
    Fetch Instagram post data by scraping the HTML page.

    Falls back to oEmbed API if scraping doesn't work. Uses the
    canonical URL to avoid duplicate cache entries for the same post with
    different query parameters (e.g. `?img_index`).
    """
    try:
        # Use canonical URL for cache look-ups and network requests
        canonical_url = canonicalize_instagram_url(url)

        # Check cache first
        cached_data = get_cached_unfurl(canonical_url)
        if cached_data:
            return cached_data

        # Fetch the Instagram page with enhanced headers and user agent rotation
        user_agents = [
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/119.0.0.0 Safari/537.36"
            ),
            (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.1 Safari/605.1.15"
            ),
        ]

        headers = {
            "User-Agent": random.choice(user_agents),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "DNT": "1",
            "Sec-CH-UA": (
                '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
            ),
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"Windows"',
        }

        # Add random delay to appear more human-like
        time.sleep(random.uniform(0.5, 2.0))

        logger.debug("Making request to Instagram", extra={"url": canonical_url})

        response = requests.get(canonical_url, headers=headers, timeout=15)
        logger.info(
            "Fetched Instagram page",
            extra={
                "status_code": response.status_code,
                "url": canonical_url,
                "content_length": len(response.text),
            },
        )
        response.raise_for_status()

        # Log response content snippet for debugging
        logger.debug(
            "Instagram page content snippet",
            extra={
                "url": canonical_url,
                "content_snippet": response.text[:500],
                "contains_meta_tags": '<meta property="og:' in response.text,
                "contains_json_ld": "application/ld+json" in response.text,
                "title_tag": (
                    response.text[
                        response.text.find("<title") : response.text.find("</title>")
                        + 8
                    ]
                    if "<title" in response.text
                    else "No title found"
                ),
            },
        )

        # Parse the HTML
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract data from meta tags and scripts
        data = extract_instagram_data(soup, url)

        # Enhanced debugging for extraction failures
        if not data:
            logger.warning(
                "HTML scrape yielded no data - debugging extraction",
                extra={
                    "url": url,
                    "meta_og_image": bool(soup.find("meta", property="og:image")),
                    "meta_og_description": bool(
                        soup.find("meta", property="og:description")
                    ),
                    "meta_og_title": bool(soup.find("meta", property="og:title")),
                    "json_ld_scripts": len(
                        soup.find_all("script", type="application/ld+json")
                    ),
                    "all_meta_tags": [
                        tag.get("property", tag.get("name", ""))
                        for tag in soup.find_all("meta")
                    ],
                },
            )

        # Fallback to oEmbed API if scraping did not return data
        if not data:
            logger.warning(
                "HTML scrape yielded no data, attempting oEmbed fallback",
                extra={"url": url},
            )
            data = fetch_instagram_oembed(canonical_url)

        if data:
            # Cache the result using canonical URL so future variants hit cache
            cache_unfurl(canonical_url, data)

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
        # Helper to extract meta tag content.
        # Checks both 'property' and 'name' attributes.
        def _get_meta_content(names: list) -> Optional[str]:
            for n in names:
                tag = soup.find("meta", attrs={"property": n}) or soup.find(
                    "meta",
                    attrs={"name": n},
                )
                if tag and tag.get("content"):
                    return tag["content"]
            return None

        # Retrieve commonly used meta values (supporting Twitter fallbacks)
        og_image_url = _get_meta_content(["og:image", "twitter:image", "og:video"])
        og_description_content = _get_meta_content(
            ["og:description", "twitter:description"]
        )
        og_title_content = _get_meta_content(["og:title", "twitter:title"])

        # Build the data object
        data = {
            "id": extract_post_id(url),
            "permalink": url,
            "timestamp": datetime.utcnow().isoformat(),
            "likes": None,
            "comments": None,
        }

        # Extract image / video URL
        if og_image_url:
            data["media_url"] = og_image_url
            data["media_type"] = "VIDEO" if og_image_url.endswith(".mp4") else "IMAGE"

        # Extract caption and username
        description = og_description_content or ""
        if description:
            description = description.strip()
            # Regex tolerant to variations (case, pluralisation, extra text)
            # Pattern: "123 likes, 4 comments - username on Instagram: \"caption\""
            desc_pattern = (
                r"^(?P<likes>[\\d,.]+)\\s+likes?,\\s+"
                r"(?P<comments>[\\d,.]+)\\s+comments?\\s+-\\s+"
                r'(?P<username>[\\w.]+)\\s+on[^:]*:\\s+"'
                r'(?P<caption>.+)"'
            )
            desc_match = re.match(desc_pattern, description, flags=re.IGNORECASE)
            if desc_match:
                data["likes"] = desc_match.group("likes").replace(",", "")
                data["comments"] = desc_match.group("comments").replace(",", "")
                data["username"] = desc_match.group("username")
                data["caption"] = desc_match.group("caption")
            else:
                # Fallback: search for pattern "- username on <something>: \"caption\""
                uc_pattern = (
                    r'-\\s+(?P<username>[\\w.]+)\\s+on[^:]*:\\s+"' r'(?P<caption>.+)"'
                )
                uc_match = re.search(uc_pattern, description, flags=re.IGNORECASE)
                if uc_match:
                    data["username"] = uc_match.group("username")
                    data["caption"] = uc_match.group("caption")
                else:
                    # Attempt simpler pattern "<username> on Instagram: \"<caption>\""
                    simple_match = re.match(
                        r"^(?P<user>.+?) on Instagram:\s+\"(?P<cap>.+)\"",
                        description,
                        flags=re.IGNORECASE,
                    )
                    if simple_match:
                        if not data.get("username"):
                            # Keep existing username if already set later from title
                            data["username"] = simple_match.group("user")
                        data["caption"] = simple_match.group("cap")
                    else:
                        # Last resort: raw description as caption (trim period)
                        data["caption"] = description.rstrip(" .")

        # Extract additional details from the title if available
        if og_title_content:
            title = og_title_content
            # First, attempt to parse @username from the title
            at_match = re.search(r"@([\w.]+)", title)
            if at_match:
                data["username"] = at_match.group(1)
            # Otherwise, take the part before " on " as a potential username/page name
            elif " on " in title and not data.get("username"):
                data["username"] = title.split(" on ")[0].strip()

            # If caption not already set, extract quoted part from the title
            if not data.get("caption"):
                quoted = re.search(r'"(.+?)"', title)
                if quoted:
                    data["caption"] = quoted.group(1)

        # Use structured data (JSON-LD) if available
        structured_data: Optional[Any] = None
        json_ld = soup.find("script", type="application/ld+json")
        if json_ld and (json_ld.string or json_ld.text):
            raw_json = json_ld.string or json_ld.text
            try:
                structured_data = json.loads(raw_json)
            except json.JSONDecodeError:
                structured_data = None

        # Normalise JSON-LD to a list of dictionaries for easier processing
        if structured_data:
            items = (
                structured_data
                if isinstance(structured_data, list)
                else [structured_data]
            )
            # Pick the first item that contains media information
            primary = next(
                (
                    item
                    for item in items
                    if isinstance(item, dict)
                    and (
                        "thumbnailUrl" in item
                        or "image" in item
                        or item.get("@type") in {"ImageObject", "VideoObject"}
                    )
                ),
                None,
            )

            if primary and isinstance(primary, dict):
                # Username
                if "author" in primary and isinstance(primary["author"], dict):
                    data["username"] = primary["author"].get(
                        "name", data.get("username", "Instagram User")
                    )

                # Caption
                if "caption" in primary:
                    data["caption"] = primary["caption"]

                # Timestamp
                if "uploadDate" in primary:
                    data["timestamp"] = primary["uploadDate"]

                # Media URL (thumbnail or image)
                thumb = primary.get("thumbnailUrl") or primary.get("image")
                if isinstance(thumb, list):
                    thumb = thumb[0]
                if thumb:
                    data["media_url"] = thumb
                    data["media_type"] = "VIDEO" if thumb.endswith(".mp4") else "IMAGE"

                # Engagement metrics if available
                interaction = primary.get("interactionStatistic")
                if isinstance(interaction, list):
                    for stat in interaction:
                        if not isinstance(stat, dict):
                            continue
                        if stat.get("name") == "LikeAction":
                            data["likes"] = stat.get("userInteractionCount")
                        elif stat.get("name") == "CommentAction":
                            data["comments"] = stat.get("userInteractionCount")

        return data if "media_url" in data else None

    except Exception as e:
        logger.error("Error extracting Instagram data", extra={"error": str(e)})
        return None


def fetch_instagram_oembed(url: str) -> Optional[Dict[str, Any]]:
    """Fetch Instagram data using oEmbed endpoints (Graph API with token or legacy)."""
    graph_endpoint = "https://graph.facebook.com/v18.0/instagram_oembed"
    legacy_endpoint = "https://www.instagram.com/oembed/"

    app_id = os.getenv("FACEBOOK_APP_ID")
    app_secret = os.getenv("FACEBOOK_APP_SECRET")

    def _convert_oembed(oembed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert oEmbed payload into internal unfurl data format."""
        return {
            "id": extract_post_id(url),
            "permalink": url,
            "media_url": (
                oembed_data.get("thumbnail_url")
                or oembed_data.get("thumbnail_url_with_play_button")
            ),
            "media_type": (
                "VIDEO"
                if oembed_data.get("thumbnail_url_with_play_button")
                else "IMAGE"
            ),
            "username": oembed_data.get("author_name", "Instagram User"),
            "caption": oembed_data.get("title", ""),
            "timestamp": datetime.utcnow().isoformat(),
            "provider": "oembed",
        }

    try:
        # 1️⃣ Attempt Graph endpoint which requires app credentials
        if app_id and app_secret:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "DNT": "1",
            }
            params = {
                "url": url,
                "access_token": f"{app_id}|{app_secret}",
                "omitscript": "true",
            }
            resp = requests.get(
                graph_endpoint, params=params, headers=headers, timeout=15
            )
            logger.debug(
                "Graph oEmbed response",
                extra={
                    "status_code": resp.status_code,
                    "url": url,
                    "response_snippet": resp.text[:200],
                },
            )

            if resp.status_code == 200:
                try:
                    return _convert_oembed(resp.json())
                except ValueError as json_err:  # JSONDecodeError inherits ValueError
                    logger.error(
                        "Failed to parse Graph oEmbed JSON",
                        extra={
                            "url": url,
                            "error": str(json_err),
                            "response_snippet": resp.text[:200],
                        },
                    )
            else:
                logger.warning(
                    "Graph oEmbed request failed, falling back to legacy endpoint",
                    extra={"status_code": resp.status_code, "url": url},
                )

        # 2️⃣ Legacy endpoint does not need credentials and still works for public posts
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "DNT": "1",
        }
        params = {"url": url, "omitscript": "true"}
        resp = requests.get(legacy_endpoint, params=params, headers=headers, timeout=15)

        logger.debug(
            "Legacy oEmbed response",
            extra={
                "status_code": resp.status_code,
                "url": url,
                "response_snippet": resp.text[:200],
            },
        )

        if resp.status_code == 200:
            try:
                return _convert_oembed(resp.json())
            except ValueError as json_err:
                logger.error(
                    "Failed to parse legacy oEmbed JSON",
                    extra={
                        "url": url,
                        "error": str(json_err),
                        "response_snippet": resp.text[:200],
                    },
                )

        logger.warning(
            "Both oEmbed attempts failed",
            extra={
                "status_code": resp.status_code,
                "url": url,
                "response_snippet": resp.text[:200],
            },
        )

    except Exception as e:
        logger.error(
            "Error fetching oEmbed data",
            extra={"error": str(e), "url": url},
        )

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
                    instagram_data = fetch_instagram_data(url)
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


# NEW: Helper to canonicalize Instagram URLs by removing query parameters and fragments
# This helps ensure consistent caching and improves scraping reliability when URLs
# contain parameters like `?img_index` or tracking values.


def canonicalize_instagram_url(url: str) -> str:  # noqa: D401
    """Return the canonical Instagram URL without query params or fragments.

    Examples
    --------
    >>> canonicalize_instagram_url("https://www.instagram.com/p/ABC123/?img_index=4")
    'https://www.instagram.com/p/ABC123/'
    """
    parsed = urlparse(url)
    # Ensure path always ends with a trailing slash for consistency, as Instagram
    # canonical links include the final slash (e.g. `/p/<id>/`).
    path = parsed.path if parsed.path.endswith("/") else f"{parsed.path}/"

    return f"{parsed.scheme}://{parsed.netloc}{path}"
