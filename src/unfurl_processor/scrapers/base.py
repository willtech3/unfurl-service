"""Base scraper interface and common functionality."""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from aws_lambda_powertools import Logger
import logfire

logger = Logger()


@dataclass
class ScrapingResult:
    """Result of a scraping operation."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    method: str = "unknown"
    response_time_ms: int = 0


class BaseScraper(ABC):
    """Base class for Instagram scrapers."""

    def __init__(self, name: str):
        self.name = name
        self.logger = logger

    @abstractmethod
    async def scrape(self, url: str) -> ScrapingResult:
        """Scrape Instagram data from the given URL."""
        pass

    def extract_post_id(self, url: str) -> Optional[str]:
        """Extract post ID from Instagram URL."""
        try:
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split("/") if p]

            # Look for post ID patterns: /p/ID, /reel/ID, /tv/ID
            for i, part in enumerate(path_parts):
                if part in ("p", "reel", "tv") and i + 1 < len(path_parts):
                    return path_parts[i + 1]

            return None
        except Exception as e:
            self.logger.warning(f"Failed to extract post ID from {url}: {e}")
            return None

    def validate_instagram_url(self, url: str) -> bool:
        """Validate that URL is a valid Instagram URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc in ("instagram.com", "www.instagram.com") and any(
                x in parsed.path for x in ("/p/", "/reel/", "/tv/")
            )
        except Exception:
            return False

    def measure_time(self, start_time: float) -> int:
        """Calculate elapsed time in milliseconds."""
        return int((time.time() - start_time) * 1000)
