"""Consolidated Instagram URL utilities for consistent handling across modules."""

from typing import Optional
from urllib.parse import urlparse

CANONICAL_INSTAGRAM_HOST = "www.instagram.com"
INSTAGRAM_MEDIA_TYPES = {"p", "reel", "tv"}


def _get_parsed_instagram_url(url: str):
    if not isinstance(url, str) or not url:
        return None

    try:
        parsed = urlparse(url)
    except Exception:
        return None

    hostname = (parsed.hostname or parsed.netloc or "").lower()
    if not hostname:
        return None

    return parsed, hostname


def _is_instagram_hostname(hostname: str) -> bool:
    return hostname == "instagram.com" or hostname.endswith(".instagram.com")


def _get_instagram_media_parts(url: str) -> Optional[tuple[str, str]]:
    parsed_url = _get_parsed_instagram_url(url)
    if parsed_url is None:
        return None

    parsed, hostname = parsed_url
    if not _is_instagram_hostname(hostname):
        return None

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) != 2:
        return None

    media_type, media_id = path_parts[0].lower(), path_parts[1]
    if media_type not in INSTAGRAM_MEDIA_TYPES or not media_id:
        return None

    return media_type, media_id


def extract_instagram_id(url: str) -> Optional[str]:
    """
    Extract Instagram post ID from URL.

    Handles URLs like:
    - https://www.instagram.com/p/ABC123/
    - https://instagram.com/reel/XYZ456/
    - https://www.instagram.com/tv/DEF789/

    Args:
        url: Instagram URL

    Returns:
        Post ID if found, None otherwise
    """
    media_parts = _get_instagram_media_parts(url)
    if media_parts is None:
        return None

    _, media_id = media_parts
    return media_id


def canonicalize_instagram_url(url: str) -> str:
    """
    Return the canonical Instagram URL (normalized for caching).

    Removes:
    - Query parameters
    - Fragments
    - Trailing slashes (for consistency)

    Args:
        url: Instagram URL to canonicalize

    Returns:
        Canonical URL for consistent cache keys
    """
    parsed_url = _get_parsed_instagram_url(url)
    if parsed_url is None:
        return url

    parsed, hostname = parsed_url

    # If it doesn't have a scheme, return original (likely invalid)
    if not parsed.scheme:
        return url

    media_parts = _get_instagram_media_parts(url)
    if media_parts is None:
        return url

    media_type, media_id = media_parts
    netloc = CANONICAL_INSTAGRAM_HOST

    return f"{parsed.scheme}://{netloc}/{media_type}/{media_id}"


def validate_instagram_url(url: str) -> bool:
    """
    Validate that URL is a valid Instagram post URL.

    Args:
        url: URL to validate

    Returns:
        True if valid Instagram post URL, False otherwise
    """
    parsed_url = _get_parsed_instagram_url(url)
    if parsed_url is None:
        return False

    parsed, _ = parsed_url
    if parsed.scheme != "https":
        return False

    return _get_instagram_media_parts(url) is not None


def is_instagram_login_url(url: str) -> bool:
    """
    Check if URL is Instagram's login/challenge wall.

    Instagram redirects anonymous or bot-flagged requests to
    /accounts/login/?next=... — reaching this page means scraping failed,
    even though the HTTP response is 200 OK.

    Args:
        url: Final URL after redirects

    Returns:
        True if URL is a login or challenge page
    """
    parsed_url = _get_parsed_instagram_url(url)
    if parsed_url is None:
        return False

    parsed, hostname = parsed_url
    if not _is_instagram_hostname(hostname):
        return False

    path = parsed.path.lower()
    return path.startswith("/accounts/login") or path.startswith("/challenge")


def is_instagram_static_asset_url(url: str) -> bool:
    """
    Check if URL points to a static Instagram site asset (logos, icons, UI
    sprites) rather than real post media.

    The login page advertises the Instagram logo
    (e.g. static.cdninstagram.com/rsrc.php/...) which must never be used as
    a post image. Real post media lives on scontent-*.cdninstagram.com or
    *.fbcdn.net and never under /rsrc.php or /static/.

    Args:
        url: Image or video URL to check

    Returns:
        True if URL is a static site asset, not post media
    """
    if not isinstance(url, str) or not url:
        return False

    try:
        parsed = urlparse(url)
    except Exception:
        return False

    hostname = (parsed.hostname or "").lower()
    path = parsed.path.lower()

    if hostname == "static.cdninstagram.com":
        return True
    if "/rsrc.php/" in path or path.startswith("/rsrc.php"):
        return True
    if _is_instagram_hostname(hostname) and path.startswith("/static/"):
        return True

    return False


def is_instagram_video_url(url: str) -> bool:
    """
    Check if URL is likely an Instagram video URL.

    Args:
        url: URL to check

    Returns:
        True if URL contains video indicators
    """
    if not url:
        return False

    # Check for video-specific paths
    return "/reel/" in url or "/tv/" in url


def get_cache_key(url: str) -> str:
    """
    Generate a consistent cache key for an Instagram URL.

    Uses canonical URL to ensure cache hits regardless of:
    - Query parameters
    - Trailing slashes
    - www prefix variations

    Args:
        url: Instagram URL

    Returns:
        Consistent cache key
    """
    return canonicalize_instagram_url(url)


def get_cache_ttl(content_type: str = "default") -> int:
    """
    Get cache TTL in seconds based on content type.

    Args:
        content_type: Type of content (video, photo, default)

    Returns:
        TTL in seconds
    """
    ttl_map = {
        "video": 86400,  # 24 hours for videos
        "photo": 86400,  # 24 hours for photos
        "default": 86400,  # 24 hours default
    }
    return ttl_map.get(content_type, 86400)
