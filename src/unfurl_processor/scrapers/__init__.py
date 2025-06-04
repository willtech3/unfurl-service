"""Instagram scrapers package with modular fallback architecture."""

from .base import BaseScraper, ScrapingResult
from .http_scraper import HttpScraper
from .manager import ScraperManager
from .oembed_scraper import OEmbedScraper
from .playwright_scraper import PlaywrightScraper

__all__ = [
    "BaseScraper",
    "ScrapingResult",
    "HttpScraper",
    "OEmbedScraper",
    "PlaywrightScraper",
    "ScraperManager",
]
