"""Consolidated Instagram URL utilities for consistent handling across modules."""

from typing import Optional
from urllib.parse import urlparse


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
    try:
        parsed = urlparse(url)
        # Validate it's an Instagram domain first
        if parsed.netloc not in ("instagram.com", "www.instagram.com", ""):
            return None
            
        path_parts = [p for p in parsed.path.split("/") if p]

        if len(path_parts) >= 2 and path_parts[0] in ["p", "reel", "tv"]:
            return path_parts[1]
        return None
    except Exception:
        return None


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
    try:
        parsed = urlparse(url)
        
        # If it doesn't have a scheme, return original (likely invalid)
        if not parsed.scheme:
            return url
            
        # Ensure consistent netloc
        netloc = parsed.netloc if parsed.netloc else "www.instagram.com"
        if not netloc.startswith("www."):
            netloc = "www." + netloc

        # Build path without trailing slash for consistency
        path = parsed.path.rstrip("/")
        if not path:
            path = "/"

        return f"{parsed.scheme}://{netloc}{path}"
    except Exception:
        # Return original if parsing fails
        return url


def validate_instagram_url(url: str) -> bool:
    """
    Validate that URL is a valid Instagram post URL.

    Args:
        url: URL to validate

    Returns:
        True if valid Instagram post URL, False otherwise
    """
    try:
        parsed = urlparse(url)
        # Check domain
        if parsed.netloc not in ("instagram.com", "www.instagram.com"):
            return False

        # Check for valid post paths
        return any(pattern in parsed.path for pattern in ("/p/", "/reel/", "/tv/"))
    except Exception:
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
