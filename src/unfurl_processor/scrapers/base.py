"""Base scraper interface and common functionality."""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from aws_lambda_powertools import Logger

from ..url_utils import extract_instagram_id, validate_instagram_url

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
        return extract_instagram_id(url)

    def validate_instagram_url(self, url: str) -> bool:
        """Validate that URL is a valid Instagram URL."""
        return validate_instagram_url(url)

    def measure_time(self, start_time: float) -> int:
        """Calculate elapsed time in milliseconds."""
        return int((time.time() - start_time) * 1000)
