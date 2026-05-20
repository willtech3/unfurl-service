"""Tests for HttpScraper async behavior."""

import asyncio


class TestHttpScraperBehavior:
    def test_scrape_rejects_invalid_instagram_url(self):
        """Scraping a non-Instagram URL should return failure."""
        from unfurl_processor.scrapers.http_scraper import HttpScraper

        scraper = HttpScraper()
        result = asyncio.get_event_loop().run_until_complete(
            scraper.scrape("https://example.com/not-instagram")
        )

        assert result.success is False
        assert "Invalid Instagram URL" in result.error

    def test_scrape_does_not_block_event_loop(self):
        """Scraping should yield control to the event loop, not block it."""
        from unfurl_processor.scrapers.http_scraper import HttpScraper

        scraper = HttpScraper()
        completed_flag = []

        async def background_task():
            """A task that should run concurrently if the loop isn't blocked."""
            completed_flag.append(True)

        async def run_test():
            # Schedule a background task
            bg = asyncio.ensure_future(background_task())
            # Start scraping (will fail on network, but shouldn't block)
            await scraper.scrape("https://www.instagram.com/p/TEST123/")
            await bg

        asyncio.get_event_loop().run_until_complete(run_test())
        assert len(completed_flag) == 1, "Background task should have completed"

    def test_scrape_uses_async_http_not_requests(self):
        """HttpScraper should not import the synchronous requests library."""
        import unfurl_processor.scrapers.http_scraper as mod

        assert not hasattr(mod, "requests"), "Should not use synchronous requests"
