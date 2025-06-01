"""Instagram scrapers package with modular fallback architecture."""

from .base import BaseScraper, ScrapingResult
from .http_scraper import HttpScraper
from .oembed_scraper import OEmbedScraper
from .playwright_scraper import PlaywrightScraper
from .manager import ScraperManager

__all__ = [
    "BaseScraper",
    "ScrapingResult",
    "HttpScraper",
    "OEmbedScraper",
    "PlaywrightScraper",
    "ScraperManager",
]
