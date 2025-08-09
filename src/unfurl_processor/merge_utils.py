"""Utility to merge multiple scraper result dictionaries.

Provides `merge_instagram_results` which selects the first non-empty value for
important fields across an ordered list of result dictionaries.
"""

from typing import Any, Dict, List

__all__ = ["merge_instagram_results"]

_FIELDS_PRIORITY: List[str] = [
    "username",
    "caption",
    "likes",
    "comments",
    "video_url",
    "image_url",
    "content_type",
    "is_video",
    "has_video",
    "title",
    "description",
    "is_verified",
    "timestamp",
    "post_id",
]


def _present(value: Any) -> bool:  # noqa: D401
    """Return True if value is usable (non-empty)."""
    return value not in (None, "", [], {}, ())


def merge_instagram_results(result_dicts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge ordered list of result dicts into the richest dict."""
    merged: Dict[str, Any] = {}
    field_sources: Dict[str, str] = {}

    for field in _FIELDS_PRIORITY:
        for entry in result_dicts:
            if _present(entry.get(field)):
                merged[field] = entry[field]
                src = entry.get("__scraper_method") or entry.get("scraper_method")
                if src:
                    field_sources[field] = src
                break

    # Ensure url and post_id retained
    for key in ("url", "post_id"):
        if key not in merged:
            for entry in result_dicts:
                if _present(entry.get(key)):
                    merged[key] = entry[key]
                    break

    if field_sources:
        merged["field_sources"] = field_sources

    return merged
