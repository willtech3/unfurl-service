"""Tests for HttpScraper async behavior."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from bs4 import BeautifulSoup


class TestHttpScraperBehavior:
    def test_scrape_rejects_invalid_instagram_url(self):
        """Scraping a non-Instagram URL should return failure."""
        from unfurl_processor.scrapers.http_scraper import HttpScraper

        scraper = HttpScraper()
        result = asyncio.run(scraper.scrape("https://example.com/not-instagram"))

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

        asyncio.run(run_test())
        assert len(completed_flag) == 1, "Background task should have completed"

    def test_scrape_uses_async_http_not_requests(self):
        """HttpScraper should not import the synchronous requests library."""
        import unfurl_processor.scrapers.http_scraper as mod

        assert not hasattr(mod, "requests"), "Should not use synchronous requests"

    def test_scrape_fails_on_login_redirect(self):
        """A redirect to the Instagram login wall must fail the scrape.

        Instagram 302s bot-flagged requests to /accounts/login/?next=...
        which returns 200 OK but contains no post data. Treating it as
        success produced placeholder unfurls with the Instagram logo.
        """
        from unfurl_processor.scrapers.http_scraper import HttpScraper

        scraper = HttpScraper()
        post_url = "https://www.instagram.com/reel/ABC123/"
        login_url = (
            "https://www.instagram.com/accounts/login/"
            "?next=https%3A%2F%2Fwww.instagram.com%2Freel%2FABC123&is_from_rle"
        )

        login_response = MagicMock(spec=httpx.Response)
        login_response.url = httpx.URL(login_url)
        login_response.status_code = 200
        login_response.raise_for_status = MagicMock()

        client = AsyncMock()
        client.get = AsyncMock(return_value=login_response)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "unfurl_processor.scrapers.http_scraper.httpx.AsyncClient",
            return_value=client,
        ):
            result = asyncio.run(scraper.scrape(post_url))

        assert result.success is False
        assert "login" in result.error.lower()


class TestHttpScraperExtraction:
    def test_static_asset_image_is_rejected(self):
        """The Instagram logo from login/error pages must not become the
        post image."""
        from unfurl_processor.scrapers.http_scraper import HttpScraper

        html = """
        <html><head>
        <meta property="og:image"
              content="https://static.cdninstagram.com/rsrc.php/v4/yD/r/logo.png" />
        </head><body></body></html>
        """
        scraper = HttpScraper()
        soup = BeautifulSoup(html, "html.parser")
        data = scraper._extract_instagram_data(
            soup, "https://www.instagram.com/reel/ABC123/"
        )

        # No real media, username, or caption -> no data at all
        assert data is None

    def test_real_post_media_is_kept(self):
        """Real scontent CDN media should still be extracted."""
        from unfurl_processor.scrapers.http_scraper import HttpScraper

        html = """
        <html><head>
        <meta property="og:image"
              content="https://scontent-iad3-1.cdninstagram.com/v/t51/photo.jpg" />
        <meta property="og:description"
              content="123 Likes, 45 Comments - someuser on Instagram" />
        </head><body></body></html>
        """
        scraper = HttpScraper()
        soup = BeautifulSoup(html, "html.parser")
        data = scraper._extract_instagram_data(
            soup, "https://www.instagram.com/p/ABC123/"
        )

        assert data is not None
        assert (
            data["image_url"]
            == "https://scontent-iad3-1.cdninstagram.com/v/t51/photo.jpg"
        )
