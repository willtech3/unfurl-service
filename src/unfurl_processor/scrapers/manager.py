"""Enhanced scraper manager with async support and intelligent fallback
orchestration."""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
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
        
        # Initialize CloudWatch client for metrics
        try:
            self.cloudwatch = boto3.client('cloudwatch')
            self.metrics_enabled = True
            self.logger.info("✅ CloudWatch metrics enabled")
        except Exception as e:
            self.logger.warning(f"⚠️ CloudWatch metrics disabled: {e}")
            self.cloudwatch = None
            self.metrics_enabled = False

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

    def _emit_metric(self, metric_name: str, value: float, unit: str = 'Count', 
                    dimensions: Optional[Dict[str, str]] = None):
        """Emit CloudWatch metric with error handling."""
        if not self.metrics_enabled:
            return
            
        try:
            metric_data = {
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit,
                'Timestamp': datetime.now(timezone.utc)
            }
            
            if dimensions:
                metric_data['Dimensions'] = [
                    {'Name': k, 'Value': v} for k, v in dimensions.items()
                ]
            
            self.cloudwatch.put_metric_data(
                Namespace='UnfurlService/Scrapers',
                MetricData=[metric_data]
            )
            
        except Exception as e:
            # Don't let metrics failures break scraping
            self.logger.warning(f"Failed to emit metric {metric_name}: {e}")

    async def scrape_instagram_data(self, url: str) -> ScrapingResult:
        """
        Scrape Instagram data using all scrapers and select the richest result.

        Strategy:
        1. Execute all scrapers (Playwright, HTTP, oEmbed) concurrently/sequentially
        2. Compare successful results using quality scoring algorithm
        3. Return the result with the highest quality score (richest content)

        Quality scoring considers:
        - Content richness (caption, description, title)
        - Media availability (images, videos)
        - Metadata completeness (author, timestamps, engagement)
        - Technical quality (high-res images, direct video URLs)
        - Data source reliability (official API vs scraping)

        Args:
            url: Instagram URL to scrape

        Returns:
            ScrapingResult with data from the richest scraper
        """
        start_time = time.time()
        errors = []
        results = []

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
                    results.append(result)
                    self._emit_metric('ScraperSuccess', 1, dimensions={'Scraper': scraper.name})
                else:
                    error_msg = f"{scraper.name} failed: {result.error}"
                    errors.append(error_msg)
                    self.logger.warning(f"❌ {error_msg}")
                    self._emit_metric('ScraperFailure', 1, dimensions={'Scraper': scraper.name})

                # Emit response time metric for each scraper
                self._emit_metric(
                    'ScraperResponseTime', 
                    result.response_time_ms, 
                    unit='Milliseconds',
                    dimensions={'Scraper': scraper.name}
                )

            except Exception as e:
                error_msg = f"{scraper.name} exception: {str(e)}"
                errors.append(error_msg)
                self.logger.error(f"💥 {error_msg}")
                self._emit_metric('ScraperException', 1, dimensions={'Scraper': scraper.name})

        # Select the richest result
        if results:
            richest_result = max(results, key=self.calculate_quality_score)
            total_time = self.measure_time(start_time)

            # Log quality comparison
            for result in results:
                score = self.calculate_quality_score(result)
                self.logger.info(f"📊 {result.method}: quality score {score}")
                self._emit_metric('QualityScore', score, dimensions={'Scraper': result.method})

            best_score = self.calculate_quality_score(richest_result)
            scraper_success_msg = f"✅ Best quality: {richest_result.method} (score: {best_score})"
            time_msg = f"in {richest_result.response_time_ms}ms (total: {total_time}ms)"
            self.logger.info(f"{scraper_success_msg} {time_msg}")
            self._emit_metric('BestQualityScraper', 1, dimensions={'Scraper': richest_result.method})
            self._emit_metric('ScrapingTime', total_time, unit='Milliseconds')

            # Add manager metadata
            richest_result.data["scraper_attempts"] = len(self.scrapers)
            richest_result.data["total_response_time_ms"] = total_time
            richest_result.data["quality_score"] = best_score
            richest_result.data["fallback_errors"] = errors.copy()

            return richest_result
        else:
            # All scrapers failed
            total_time = self.measure_time(start_time)
            self.logger.error(f"❌ All {len(self.scrapers)} scrapers failed for {url}")
            self._emit_metric('AllScrapersFailed', 1)

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
            f"🔗 Scraping {len(urls)} URLs with max {max_concurrent} "
            f"concurrent operations"
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
        self._emit_metric('ConcurrentScrapingSuccess', successful)
        self._emit_metric('ConcurrentScrapingTime', total_time, unit='Milliseconds')

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
                self._emit_metric('ScraperHealthCheck', 1, dimensions={'Scraper': scraper.name, 'Status': health_status["scrapers"][scraper.name]['status']})

            except Exception as e:
                health_status["scrapers"][scraper.name] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "response_time_ms": None,
                }
                self._emit_metric('ScraperHealthCheck', 1, dimensions={'Scraper': scraper.name, 'Status': health_status["scrapers"][scraper.name]['status']})

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

    def calculate_quality_score(self, result: ScrapingResult) -> int:
        """
        Calculate quality score for a scraping result based on content richness.
        
        Scoring factors:
        - Content richness (caption, description, title): 70 points max
        - Media content (videos, images): 80 points max  
        - Metadata (author, timestamps, engagement): 50 points max
        - Technical quality (high-res, video URLs): 35 points max
        - Source reliability bonus: 15 points max
        
        Total possible: 250 points
        """
        if not result.success or not result.data:
            return 0

        score = 0
        data = result.data
        
        # Track quality factors for metrics
        quality_factors = {
            'has_caption': False,
            'has_description': False,
            'has_title': False,
            'has_video': False,
            'has_multiple_images': False,
            'has_author': False,
            'has_engagement': False,
            'is_high_quality': False
        }

        # Content richness (70 points max)
        if data.get("caption"):
            score += 30
            quality_factors['has_caption'] = True
        if data.get("description"):
            score += 25
            quality_factors['has_description'] = True
        if data.get("title"):
            score += 15
            quality_factors['has_title'] = True

        # Media content (80 points max)
        videos = data.get("videos", [])
        if videos and len(videos) > 0:
            score += 40  # Videos are premium content
            quality_factors['has_video'] = True

        images = data.get("images", [])
        if images:
            if len(images) > 1:
                score += 20  # Multiple images
                quality_factors['has_multiple_images'] = True
            else:
                score += 10  # Single image

        # Metadata richness (50 points max)
        if data.get("author"):
            score += 15
            quality_factors['has_author'] = True
        if data.get("timestamp") or data.get("created_at"):
            score += 10
        if any(data.get(field) for field in ["like_count", "comment_count", "view_count"]):
            score += 15
            quality_factors['has_engagement'] = True
        if data.get("hashtags"):
            score += 10

        # Technical quality indicators (35 points max)
        if data.get("video_url"):
            score += 15  # Direct video URL
        
        # Check for high-resolution indicators
        image_url = data.get("image_url", "")
        if any(indicator in image_url.lower() for indicator in ["1080", "720", "high", "hd"]):
            score += 10
            quality_factors['is_high_quality'] = True
            
        if data.get("thumbnail_url"):
            score += 5
        if data.get("embed_url"):
            score += 5

        # Source reliability bonus (15 points max)
        source = result.method.lower() if result.method else ""
        if "oembed" in source:
            score += 15  # Official API
        elif "playwright" in source:
            score += 10  # Browser automation
        elif "http" in source:
            score += 5   # Basic HTTP

        # Emit detailed quality metrics
        content_type = 'video' if quality_factors['has_video'] else 'photo'
        self._emit_metric('ContentType', 1, dimensions={
            'Type': content_type,
            'Scraper': result.method
        })
        
        # Emit quality factor metrics
        for factor, has_factor in quality_factors.items():
            if has_factor:
                self._emit_metric('QualityFactor', 1, dimensions={
                    'Factor': factor,
                    'Scraper': result.method
                })

        return score

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
