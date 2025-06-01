"""Enhanced scraper manager with async support and intelligent fallback orchestration."""

import asyncio
import os
import time
from typing import Any, Dict, List, Optional

from aws_lambda_powertools import Logger

from .base import BaseScraper, ScrapingResult
from .http_scraper import HttpScraper
from .oembed_scraper import OEmbedScraper
from .playwright_scraper import PlaywrightScraper

logger = Logger()


class ScraperManager:
    """Manages multiple scrapers with intelligent fallback strategy."""

    def __init__(self):
        self.logger = logger

        # Initialize proxy configuration
        proxy_urls = []
        proxy_env = os.environ.get("PROXY_URLS", "")
        if proxy_env:
            proxy_urls = [url.strip() for url in proxy_env.split(",") if url.strip()]
            self.logger.info(f"Configured {len(proxy_urls)} proxy URLs")

        # Initialize scrapers in priority order
        self.scrapers: List[BaseScraper] = []

        # 1. Playwright (highest priority - best bot evasion)
        playwright_scraper = PlaywrightScraper()
        self.scrapers.append(playwright_scraper)
        self.logger.info("✅ PlaywrightScraper initialized")

        # 2. HTTP scraper with enhanced headers
        http_scraper = HttpScraper(proxy_urls=proxy_urls)
        self.scrapers.append(http_scraper)
        self.logger.info("✅ HttpScraper initialized with enhanced headers")

        # 3. oEmbed fallback
        oembed_scraper = OEmbedScraper()
        self.scrapers.append(oembed_scraper)
        self.logger.info("✅ OEmbedScraper initialized")

        self.logger.info(
            f"ScraperManager initialized with {len(self.scrapers)} scrapers"
        )

    async def scrape_instagram_data(self, url: str) -> ScrapingResult:
        """
        Scrape Instagram data using intelligent fallback strategy.

        Fallback order:
        1. Playwright browser automation (best bot evasion)
        2. HTTP scraping with enhanced headers
        3. oEmbed Instagram Graph API

        Args:
            url: Instagram URL to scrape

        Returns:
            ScrapingResult with data from the first successful scraper
        """
        start_time = time.time()
        errors = []

        self.logger.info(f"🔍 Starting intelligent scraping for: {url}")

        for i, scraper in enumerate(self.scrapers, 1):
            try:
                self.logger.info(
                    f"📊 Attempting scraper {i}/{len(self.scrapers)}: {scraper.name}"
                )

                # Execute scraping (async or sync based on scraper)
                if hasattr(scraper, "scrape") and asyncio.iscoroutinefunction(
                    scraper.scrape
                ):
                    result = await scraper.scrape(url)
                else:
                    # Run sync scrapers in thread pool to avoid blocking
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, scraper.scrape, url
                    )

                if result.success and result.data:
                    total_time = self.measure_time(start_time)
                    self.logger.info(
                        f"✅ Success with {scraper.name} (attempt {i}/{len(self.scrapers)}) "
                        f"in {result.response_time_ms}ms (total: {total_time}ms)"
                    )

                    # Add manager metadata
                    result.data["scraper_attempts"] = i
                    result.data["total_response_time_ms"] = total_time
                    result.data["fallback_errors"] = errors.copy()

                    return result
                else:
                    error_msg = f"{scraper.name} failed: {result.error}"
                    errors.append(error_msg)
                    self.logger.warning(f"❌ {error_msg}")

                    # Add small delay between attempts to avoid rate limiting
                    if i < len(self.scrapers):
                        await asyncio.sleep(0.5)

            except Exception as e:
                error_msg = f"{scraper.name} exception: {str(e)}"
                errors.append(error_msg)
                self.logger.error(f"💥 {error_msg}")

                # Continue to next scraper
                if i < len(self.scrapers):
                    await asyncio.sleep(0.5)

        # All scrapers failed
        total_time = self.measure_time(start_time)
        self.logger.error(f"❌ All {len(self.scrapers)} scrapers failed for {url}")

        return ScrapingResult(
            success=False,
            error=f"All scrapers failed: {'; '.join(errors)}",
            method="manager_fallback",
            response_time_ms=total_time,
            data={
                "scraper_attempts": len(self.scrapers),
                "total_response_time_ms": total_time,
                "fallback_errors": errors,
                "url": url,
            },
        )

    async def scrape_multiple_urls(
        self, urls: List[str], max_concurrent: int = 3
    ) -> List[ScrapingResult]:
        """
        Scrape multiple Instagram URLs concurrently with controlled concurrency.

        Args:
            urls: List of Instagram URLs to scrape
            max_concurrent: Maximum number of concurrent scraping operations

        Returns:
            List of ScrapingResults in same order as input URLs
        """
        if not urls:
            return []

        self.logger.info(
            f"🔗 Scraping {len(urls)} URLs with max {max_concurrent} concurrent operations"
        )

        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)

        async def scrape_with_semaphore(url: str) -> ScrapingResult:
            async with semaphore:
                return await self.scrape_instagram_data(url)

        # Execute all scraping operations concurrently
        start_time = time.time()
        results = await asyncio.gather(
            *[scrape_with_semaphore(url) for url in urls], return_exceptions=True
        )

        total_time = self.measure_time(start_time)

        # Convert exceptions to failed results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(
                    ScrapingResult(
                        success=False,
                        error=f"Concurrent scraping exception: {str(result)}",
                        method="manager_concurrent",
                        response_time_ms=total_time,
                        data={"url": urls[i]},
                    )
                )
            else:
                final_results.append(result)

        successful = sum(1 for r in final_results if r.success)
        self.logger.info(
            f"✅ Concurrent scraping completed: {successful}/{len(urls)} successful "
            f"in {total_time}ms"
        )

        return final_results

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all scrapers.

        Returns:
            Dictionary with health status of each scraper
        """
        health_status = {"manager": "healthy", "scrapers": {}, "timestamp": time.time()}

        for scraper in self.scrapers:
            try:
                # Test with a sample Instagram URL
                test_url = "https://www.instagram.com/p/sample/"

                if hasattr(scraper, "scrape") and asyncio.iscoroutinefunction(
                    scraper.scrape
                ):
                    result = await scraper.scrape(test_url)
                else:
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, scraper.scrape, test_url
                    )

                health_status["scrapers"][scraper.name] = {
                    "status": "healthy" if not result.error else "degraded",
                    "error": result.error,
                    "response_time_ms": result.response_time_ms,
                }

            except Exception as e:
                health_status["scrapers"][scraper.name] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "response_time_ms": None,
                }

        return health_status

    async def cleanup(self) -> None:
        """Clean up all scraper resources."""
        cleanup_tasks = []

        for scraper in self.scrapers:
            if hasattr(scraper, "cleanup") and asyncio.iscoroutinefunction(
                scraper.cleanup
            ):
                cleanup_tasks.append(scraper.cleanup())

        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            self.logger.info("✅ All scrapers cleaned up")

    def measure_time(self, start_time: float) -> int:
        """Measure time elapsed since start_time in milliseconds."""
        return int((time.time() - start_time) * 1000)

    def get_scraper_info(self) -> Dict[str, Any]:
        """Get information about configured scrapers."""
        return {
            "total_scrapers": len(self.scrapers),
            "scraper_names": [scraper.name for scraper in self.scrapers],
            "fallback_order": [
                f"{i+1}. {scraper.name}" for i, scraper in enumerate(self.scrapers)
            ],
            "capabilities": {
                scraper.name: {
                    "async": hasattr(scraper, "scrape")
                    and asyncio.iscoroutinefunction(scraper.scrape),
                    "proxy_support": hasattr(scraper, "proxy_urls"),
                    "stealth_mode": scraper.name == "playwright",
                }
                for scraper in self.scrapers
            },
        }

    def __del__(self):
        """Ensure cleanup on destruction."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.cleanup())
            else:
                loop.run_until_complete(self.cleanup())
        except Exception:
            pass  # Best effort cleanup
