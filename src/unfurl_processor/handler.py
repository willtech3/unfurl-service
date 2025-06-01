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

# Brotli compression support
try:
    import brotlipy

    BROTLI_AVAILABLE = True
except ImportError:
    BROTLI_AVAILABLE = False
    brotlipy = None

# Optional zstandard import - fallback if C backend not available in Lambda
try:
    import zstandard as zstd

    ZSTD_AVAILABLE = True
except ImportError:
    ZSTD_AVAILABLE = False
    zstd = None

# User agents for bot evasion
USER_AGENTS = [
    # Desktop Chrome variants
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
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    # Edge
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
    ),
    # Safari
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.2 Safari/605.1.15"
    ),
    # Mobile variants - often bypass bot detection better
    (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    ("Mozilla/5.0 (Android 14; Mobile; rv:120.0) " "Gecko/120.0 Firefox/120.0"),
    (
        "Mozilla/5.0 (Linux; Android 14; SM-G991B) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    (
        "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    ),
]

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

# Proxy configuration - can be set via environment variables
PROXY_LIST = []
if os.environ.get("PROXY_URLS"):
    PROXY_LIST = os.environ.get("PROXY_URLS", "").split(",")

# Cache for secrets
_secrets_cache: Dict[str, Dict[str, Any]] = {}

# Configure Lambda environment optimization
if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    # Lambda-specific optimizations can be added here
    pass


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
    Fetch Instagram data using advanced scraping with enhanced bot evasion.

    Uses sophisticated techniques including:
    - Session management with persistent cookies
    - Realistic browser headers and behavior
    - Proper response decompression handling
    - Multi-step navigation simulation
    - Enhanced error handling for compressed responses
    """
    try:
        # Use canonical URL for cache look-ups and network requests
        canonical_url = canonicalize_instagram_url(url)

        # Check cache first
        cached_data = get_cached_unfurl(canonical_url)
        if cached_data:
            return cached_data

        data = None

        # Step 1: Try Playwright browser automation FIRST (most effective)
        if False:
            logger.info(
                "Attempting browser automation (Playwright) as primary method",
                extra={"url": canonical_url},
            )
            try:
                data = fetch_instagram_data_with_browser(canonical_url)
                if data:
                    logger.info("✅ Playwright browser automation succeeded")
            except Exception as e:
                logger.warning(f"Playwright automation failed: {e}")

        # Step 2: Fallback to HTTP scraping if Playwright failed
        if not data:
            logger.info(
                "Browser automation failed/unavailable, attempting HTTP scraping",
                extra={"url": canonical_url},
            )

            # Create session for cookie persistence and better bot evasion
            session = requests.Session()

            # Enhanced headers for bot evasion with more realistic browser simulation
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,image/apng,*/*;q=0.8,"
                    "application/signed-exchange;v=b3;q=0.7"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",  # Explicitly exclude brotli
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
                "sec-ch-ua": (
                    '"Google Chrome";v="119", "Chromium";v="119", '
                    '"Not?A_Brand";v="24"'
                ),
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
                # Add more realistic headers to avoid detection
                "Referer": "https://www.google.com/",
                "X-Requested-With": "",
                "X-Forwarded-For": "1.1.1.1",  # Common public DNS
                "Pragma": "no-cache",
                "X-Instagram-AJAX": "1010925751",  # Instagram-specific header
            }

            # Add referer for more realistic browsing pattern
            if "instagram.com" in canonical_url:
                headers["Referer"] = "https://www.instagram.com/"

            # Set up session headers
            session.headers.update(headers)

            # Configure proxies if available
            proxies = {}
            if PROXY_LIST:
                proxies = {
                    "http": random.choice(PROXY_LIST),  # nosec B311
                    "https": random.choice(PROXY_LIST),  # nosec B311
                }

            # Step 1: Visit Instagram homepage first to get initial cookies
            # (simulate real browsing)
            logger.debug("Visiting Instagram homepage to establish session")
            time.sleep(random.uniform(0.3, 0.8))  # nosec B311

            try:
                homepage_response = session.get(
                    "https://www.instagram.com/",
                    proxies=proxies,
                    timeout=10,
                    allow_redirects=True,
                )
                logger.debug(f"Homepage visit status: {homepage_response.status_code}")
            except Exception as e:
                logger.debug(f"Homepage visit failed (continuing anyway): {e}")

            # Step 2: Add random delay to appear more human-like
            time.sleep(random.uniform(1.0, 2.5))  # nosec B311

            # Step 3: Update headers for the actual post request
            session.headers.update(
                {
                    "Referer": "https://www.instagram.com/",
                    "Sec-Fetch-Site": "same-origin",
                }
            )

            logger.debug("Making request to Instagram", extra={"url": canonical_url})

            # Enhanced retry logic for bot detection bypass
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Rotate user agent on retries
                    if attempt > 0:
                        session.headers["User-Agent"] = random.choice(
                            USER_AGENTS
                        )  # nosec B311
                        logger.debug(f"Retry {attempt} with new user agent")
                        time.sleep(random.uniform(2.0, 4.0))  # nosec B311

                    # Make the main request with enhanced error handling
                    response = session.get(
                        canonical_url,
                        proxies=proxies,
                        timeout=15,
                        allow_redirects=True,
                        stream=False,  # Ensure full response is loaded
                    )

                    # Check if we got blocked (common Instagram bot responses)
                    if response.status_code == 429:  # Rate limited
                        logger.warning(f"Rate limited on attempt {attempt + 1}")
                        if attempt < max_retries - 1:
                            time.sleep(random.uniform(5.0, 10.0))  # nosec B311
                            continue
                    elif response.status_code in [403, 406]:  # Forbidden/Not Acceptable
                        logger.warning(
                            f"Bot detection suspected (status {response.status_code}) "
                            f"on attempt {attempt + 1}"
                        )
                        if attempt < max_retries - 1:
                            time.sleep(random.uniform(3.0, 6.0))  # nosec B311
                            continue

                    # Log response details
                    logger.info(
                        "Fetched Instagram page",
                        extra={
                            "status_code": response.status_code,
                            "content_type": response.headers.get("content-type"),
                            "content_length": response.headers.get("content-length"),
                            "content_encoding": response.headers.get(
                                "content-encoding"
                            ),
                            "url": canonical_url,
                            "attempt": attempt + 1,
                        },
                    )

                    # If we made it here, break the retry loop
                    break

                except requests.exceptions.RequestException as e:
                    logger.warning(f"Request failed on attempt {attempt + 1}: {e}")
                    if attempt == max_retries - 1:
                        raise  # Re-raise on final attempt
                    time.sleep(random.uniform(2.0, 4.0))  # nosec B311
                    continue

            # Check content encoding for decompression handling
            content_encoding = response.headers.get("content-encoding", "").lower()
            logger.info(
                "🔍 DEBUGGING: Processing response content",
                extra={
                    "content_encoding": content_encoding,
                    "response_size": len(response.content),
                    "content_type": response.headers.get("content-type", ""),
                    "requests_text_preview": (
                        response.text[:200]
                        if hasattr(response, "text")
                        else "No text available"
                    ),
                },
            )

            if content_encoding == "br":
                # This should not happen since we excluded br from Accept-Encoding
                logger.warning(
                    "🚨 Received brotli compression despite excluding it from headers"
                )
                # Fall back to trying standard requests.text which may auto-decompress
                response.encoding = response.apparent_encoding or "utf-8"
                content_text = response.text
            elif content_encoding in ["gzip", "deflate"]:
                # These should be handled automatically by requests
                response.encoding = response.apparent_encoding or "utf-8"
                content_text = response.text
            else:
                # No special encoding or unknown encoding
                response.encoding = response.apparent_encoding or "utf-8"
                content_text = response.text

            # Enhanced content validation - be more lenient with compressed content
            if not content_text or len(content_text.strip()) == 0:
                logger.warning("Received empty response content")
                return None

            # More sophisticated binary content detection
            # Don't flag as binary if it's just compression artifacts
            if content_text.startswith("\x00"):
                logger.warning("Received null-prefixed content, likely binary")
                return None

            # Check for excessive unicode replacement characters
            # (indicates corruption)
            replacement_char_ratio = (
                content_text.count("\ufffd") / len(content_text) if content_text else 1
            )
            if replacement_char_ratio > 0.6:  # More than 60% replacement chars
                logger.warning(
                    f"High replacement character ratio "
                    f"({replacement_char_ratio:.2%}), "
                    "likely corrupted"
                )
                return None

            # Check if content looks like HTML (even if compressed artifacts exist)
            html_indicators = [
                "<html",
                "<head",
                "<meta",
                "<title",
                "<!doctype",
                "<script",
                "<div",
            ]
            instagram_indicators = [
                'property="og:',
                'content="Instagram',
                "application/ld+json",
                "window._sharedData",
                '"@type":"VideoObject"',
                '"@type":"ImageObject"',
                "instagram.com",
            ]

            has_html_structure = any(
                indicator in content_text.lower() for indicator in html_indicators
            )
            has_instagram_content = any(
                indicator in content_text for indicator in instagram_indicators
            )

            # Be more lenient - accept if either HTML structure OR
            # Instagram content detected
            if (
                not has_html_structure
                and not has_instagram_content
                and len(content_text) > 100
            ):
                logger.warning(
                    "Content doesn't appear to be HTML or Instagram content",
                    extra={
                        "content_preview": content_text[:200],
                        "content_length": len(content_text),
                    },
                )
                return None

            response.raise_for_status()

            # Enhanced content debugging
            logger.debug(
                "Instagram page content analysis",
                extra={
                    "url": canonical_url,
                    "content_snippet": (
                        content_text[:300] if content_text else "No content"
                    ),
                    "has_html_structure": has_html_structure,
                    "has_instagram_content": has_instagram_content,
                    "content_length": len(content_text),
                    "replacement_char_ratio": replacement_char_ratio,
                    "contains_meta_tags": '<meta property="og:' in content_text,
                    "contains_json_ld": "application/ld+json" in content_text,
                    "contains_html": "<html" in content_text.lower(),
                    "title_tag": (
                        content_text[
                            content_text.find("<title") : content_text.find("</title>")
                            + 8
                        ]
                        if "<title" in content_text
                        else "No title found"
                    ),
                },
            )

            # Parse the HTML
            soup = BeautifulSoup(content_text, "html.parser")

            # Extract data from meta tags and scripts
            data = extract_instagram_data(soup, url)

            # Enhanced debugging for extraction failures
            if not data:
                # Get all meta tags for debugging
                all_meta_tags = [
                    {
                        "property": tag.get("property", ""),
                        "name": tag.get("name", ""),
                        "content": tag.get("content", "")[:100],  # Truncate for logging
                    }
                    for tag in soup.find_all("meta")
                    if tag.get("property") or tag.get("name")
                ]

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
                        "all_meta_tags": all_meta_tags[:10],  # Limit for logging
                        "page_title": (soup.title.string if soup.title else "No title"),
                    },
                )

                # Fallback to oEmbed
                logger.warning(
                    "HTML scrape yielded no data, attempting oEmbed fallback",
                    extra={"url": url},
                )
                data = fetch_instagram_oembed(canonical_url)

        # Step 3: Final fallback to oEmbed if HTTP scraping failed completely
        if not data:
            logger.info(
                "HTTP scraping failed, attempting oEmbed fallback",
                extra={"url": canonical_url},
            )
            try:
                data = fetch_instagram_oembed(canonical_url)
                if data:
                    logger.info("✅ oEmbed fallback succeeded")
            except Exception as e:
                logger.warning(f"oEmbed fallback failed: {e}")

        # Cache and return successful result
        if data:
            # Cache the result using canonical URL so future variants hit cache
            cache_unfurl(canonical_url, data)

            if metrics:
                metrics.add_metric(
                    name="InstagramDataFetched", unit=MetricUnit.Count, value=1
                )

        return data

    except requests.exceptions.RequestException as e:
        logger.error(
            "Request failed for Instagram URL",
            extra={"error": str(e), "url": url},
        )
        if metrics:
            metrics.add_metric(
                name="InstagramFetchError", unit=MetricUnit.Count, value=1
            )
        return None
    except Exception as e:
        logger.error(
            "Unexpected error fetching Instagram data",
            extra={"error": str(e), "url": url},
        )
        if metrics:
            metrics.add_metric(
                name="InstagramFetchError", unit=MetricUnit.Count, value=1
            )
        return None


def fetch_instagram_oembed(url: str) -> Optional[Dict[str, Any]]:
    """Fetch Instagram data using oEmbed endpoints with enhanced bot evasion."""
    graph_endpoint = "https://graph.facebook.com/v18.0/instagram_oembed"
    legacy_endpoint = "https://www.instagram.com/oembed/"

    app_id = os.getenv("FACEBOOK_APP_ID")
    app_secret = os.getenv("FACEBOOK_APP_SECRET")

    def _convert_oembed(oembed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert oEmbed payload into internal unfurl data format."""
        return {
            "id": extract_post_id(url),
            "permalink": url,
            "timestamp": datetime.utcnow().isoformat(),
            "likes": None,
            "comments": None,
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
            "post_id": extract_post_id(url),
            "provider": "oembed",
        }

    try:
        # Create session for better bot evasion
        session = requests.Session()

        # Enhanced headers for oEmbed requests
        enhanced_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": ("application/json, text/plain, */*"),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",  # Explicitly exclude brotli
            "Connection": "keep-alive",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "Referer": "https://www.instagram.com/",
            "Origin": "https://www.instagram.com",
        }

        session.headers.update(enhanced_headers)

        # 1️⃣ Attempt Graph endpoint which requires app credentials
        if app_id and app_secret:
            params = {
                "url": url,
                "access_token": f"{app_id}|{app_secret}",
                "omitscript": "true",
            }

            # Add delay for more human-like behavior
            time.sleep(random.uniform(0.2, 0.6))  # nosec B311

            resp = session.get(graph_endpoint, params=params, timeout=15)

            logger.debug(
                "Graph oEmbed response",
                extra={
                    "status_code": resp.status_code,
                    "url": url,
                    "response_snippet": resp.text[:200] if resp.text else "No content",
                    "content_type": resp.headers.get("content-type", "unknown"),
                },
            )

            if resp.status_code == 200:
                try:
                    # Check for binary content before JSON parsing
                    if (
                        resp.text
                        and not resp.text.startswith("\x00")
                        and "\ufffd" not in resp.text[:50]
                    ):
                        return _convert_oembed(resp.json())
                    else:
                        logger.warning(
                            "Graph oEmbed returned binary data, likely bot detection"
                        )
                except ValueError as json_err:  # JSONDecodeError inherits ValueError
                    logger.error(
                        "Failed to parse Graph oEmbed JSON",
                        extra={
                            "url": url,
                            "error": str(json_err),
                            "response_snippet": (
                                resp.text[:200] if resp.text else "No content"
                            ),
                        },
                    )
            else:
                logger.warning(
                    "Graph oEmbed request failed, falling back to legacy endpoint",
                    extra={"status_code": resp.status_code, "url": url},
                )

        # 2️⃣ Legacy endpoint does not need credentials and works for public posts
        params = {"url": url, "omitscript": "true"}

        # Add another delay
        time.sleep(random.uniform(0.3, 0.8))  # nosec B311

        resp = session.get(legacy_endpoint, params=params, timeout=15)

        logger.debug(
            "Legacy oEmbed response",
            extra={
                "status_code": resp.status_code,
                "url": url,
                "response_snippet": resp.text[:200] if resp.text else "No content",
                "content_type": resp.headers.get("content-type", "unknown"),
                "content_encoding": resp.headers.get("content-encoding", "none"),
            },
        )

        if resp.status_code == 200:
            try:
                # Enhanced binary content detection
                if (
                    not resp.text
                    or resp.text.startswith("\x00")
                    or "\ufffd" in resp.text[:50]
                ):
                    logger.warning(
                        "Legacy oEmbed returned binary data, likely bot detection"
                    )
                    return None

                # Verify JSON structure before parsing
                content = resp.text.strip()
                if not (content.startswith("{") and content.endswith("}")):
                    logger.warning("Legacy oEmbed response is not valid JSON format")
                    return None

                return _convert_oembed(resp.json())
            except ValueError as json_err:
                logger.error(
                    "Failed to parse legacy oEmbed JSON",
                    extra={
                        "url": url,
                        "error": str(json_err),
                        "response_snippet": (
                            resp.text[:200] if resp.text else "No content"
                        ),
                    },
                )

        logger.warning(
            "Both oEmbed attempts failed",
            extra={
                "status_code": resp.status_code,
                "url": url,
                "response_snippet": resp.text[:200] if resp.text else "No content",
            },
        )

    except Exception as e:
        logger.error(
            "Error fetching oEmbed data",
            extra={"error": str(e), "url": url},
        )

    return None


def fetch_instagram_data_with_browser(url: str) -> Optional[Dict[str, Any]]:
    """
    Attempt to fetch Instagram data using browser automation.

    Note: Playwright browser binaries are not available in Lambda due to size
    constraints. This function will gracefully return None to trigger HTTP
    scraping fallback.
    """
    logger.warning("🤖 Browser automation not available in Lambda environment")
    logger.info("📱 Falling back to enhanced HTTP scraping with improved bot evasion")
    return None


def create_fallback_unfurl(url: str) -> Dict[str, Any]:
    """
    Create a basic fallback unfurl for Instagram posts when scraping fails.

    This provides a minimal but useful unfurl that still gives context to users
    about the Instagram post they're viewing.
    """
    post_id = extract_post_id(url)

    # Create a basic unfurl with Instagram branding
    fallback_data = {
        "id": post_id,
        "permalink": url,
        "timestamp": datetime.utcnow().isoformat(),
        "likes": None,
        "comments": None,
        "media_url": None,
        "username": "Instagram User",
        "caption": "Content available on Instagram",
        "post_id": post_id,
        "is_fallback": True,  # Flag to indicate this is fallback data
    }

    # Try to extract some basic info from URL
    if "/p/" in url:
        fallback_data["title"] = "Instagram Photo"
        fallback_data["description"] = "View this photo on Instagram"
    elif "/reel/" in url:
        fallback_data["title"] = "Instagram Reel"
        fallback_data["description"] = "Watch this reel on Instagram"
    elif "/tv/" in url:
        fallback_data["title"] = "Instagram Video"
        fallback_data["description"] = "Watch this video on Instagram"

    logger.info(
        "Created fallback unfurl data",
        extra={"url": url, "post_id": post_id, "fallback": True},
    )

    return fallback_data


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
                            # Create a fallback unfurl if data is missing
                            fallback_unfurl = create_fallback_unfurl(url)
                            unfurls[url] = format_unfurl_data(fallback_unfurl)
                    else:
                        # Create a fallback unfurl if data is missing
                        fallback_unfurl = create_fallback_unfurl(url)
                        unfurls[url] = format_unfurl_data(fallback_unfurl)
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


def extract_post_id(url: str) -> str:
    """Extract post ID from Instagram URL."""
    # Match patterns like /p/ABC123/ or /reel/ABC123/
    match = re.search(r"/(p|reel|tv)/([A-Za-z0-9_-]+)", url)
    return match.group(2) if match else ""


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
                r"^(?P<likes>[\d,.]+)\s+likes?,\s+"
                r"(?P<comments>[\d,.]+)\s+comments?\s+-\s+"
                r'(?P<username>[\w.]+)\s+on[^:]*:\s+"'
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
                    r'-\s+(?P<username>[\w.]+)\s+on[^:]*:\s+"' r'(?P<caption>.+)"'
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
