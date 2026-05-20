"""Tests for PlaywrightScraper resource lifecycle."""

import asyncio
from unittest.mock import AsyncMock


class FakePlaywrightDriver:
    """Fake Playwright driver that tracks lifecycle calls."""

    def __init__(self):
        self.started = True
        self.stopped = False
        self.chromium = FakeChromiumType()

    async def stop(self):
        self.stopped = True


class FakeChromiumType:
    async def launch(self, **kwargs):
        browser = AsyncMock()
        context = AsyncMock()
        browser.new_context = AsyncMock(return_value=context)
        page = AsyncMock()
        context.new_page = AsyncMock(return_value=page)
        return browser


class TestPlaywrightScraperLifecycle:
    def test_cleanup_stops_driver_process(self):
        """After cleanup, the Playwright driver process should be stopped."""
        from unfurl_processor.scrapers.playwright_scraper import PlaywrightScraper

        scraper = PlaywrightScraper()
        driver = FakePlaywrightDriver()
        scraper._playwright_driver = driver
        scraper.browser = AsyncMock()
        scraper.context = AsyncMock()
        scraper.is_initialized = True

        asyncio.get_event_loop().run_until_complete(scraper.cleanup())

        assert driver.stopped is True
        assert scraper._playwright_driver is None
        assert scraper.browser is None
        assert scraper.context is None
        assert scraper.is_initialized is False

    def test_cleanup_handles_uninitialized_scraper(self):
        """Cleanup should not raise when scraper was never initialized."""
        from unfurl_processor.scrapers.playwright_scraper import PlaywrightScraper

        scraper = PlaywrightScraper()
        # Should not raise
        asyncio.get_event_loop().run_until_complete(scraper.cleanup())
        assert scraper.is_initialized is False

    def test_driver_reference_stored_on_instance(self):
        """The scraper should store the Playwright driver on self, not a local var."""
        from unfurl_processor.scrapers.playwright_scraper import PlaywrightScraper

        scraper = PlaywrightScraper()
        assert hasattr(scraper, "_playwright_driver")
        assert scraper._playwright_driver is None
