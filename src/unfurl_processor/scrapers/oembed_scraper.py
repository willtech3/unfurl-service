"""oEmbed-based Instagram scraper for fallback data retrieval."""

import time
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests

from .base import BaseScraper, ScrapingResult


class OEmbedScraper(BaseScraper):
    """oEmbed-based scraper using Instagram's oEmbed endpoints."""

    def __init__(self):
        super().__init__("oembed")
        self.graph_api_endpoint = "https://graph.facebook.com/v18.0/instagram_oembed"
        self.legacy_endpoint = "https://api.instagram.com/oembed/"

    async def scrape(self, url: str) -> ScrapingResult:
        """Scrape Instagram data using oEmbed endpoints."""
        start_time = time.time()

        if not self.validate_instagram_url(url):
            return ScrapingResult(
                success=False,
                error="Invalid Instagram URL",
                method=self.name,
                response_time_ms=self.measure_time(start_time),
            )

        # Try Graph API endpoint first
        result = await self._try_graph_api_oembed(url, start_time)
        if result.success:
            return result

        # Fallback to legacy endpoint
        result = await self._try_legacy_oembed(url, start_time)
        return result

    async def _try_graph_api_oembed(
        self, url: str, start_time: float
    ) -> ScrapingResult:
        """Try Instagram Graph API oEmbed endpoint."""
        try:
            # Create session with enhanced headers
            session = requests.Session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "DNT": "1",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "cross-site",
            }
            session.headers.update(headers)

            # Make request to Graph API oEmbed
            oembed_url = f"{self.graph_api_endpoint}?url={quote(url)}&access_token=instagram_basic_display"

            response = session.get(oembed_url, timeout=10)

            if response.status_code == 200:
                try:
                    oembed_data = response.json()
                    data = self._parse_oembed_data(oembed_data, url)

                    if data:
                        self.logger.info(f"✅ Graph API oEmbed successful for {url}")
                        return ScrapingResult(
                            success=True,
                            data=data,
                            method=f"{self.name}_graph",
                            response_time_ms=self.measure_time(start_time),
                        )
                except ValueError:
                    pass

            return ScrapingResult(
                success=False,
                error=f"Graph API oEmbed failed with status {response.status_code}",
                method=f"{self.name}_graph",
                response_time_ms=self.measure_time(start_time),
            )

        except Exception as e:
            error_msg = f"Graph API oEmbed request failed: {str(e)}"
            self.logger.warning(error_msg)
            return ScrapingResult(
                success=False,
                error=error_msg,
                method=f"{self.name}_graph",
                response_time_ms=self.measure_time(start_time),
            )

    async def _try_legacy_oembed(self, url: str, start_time: float) -> ScrapingResult:
        """Try legacy Instagram oEmbed endpoint."""
        try:
            # Create session with enhanced headers
            session = requests.Session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "DNT": "1",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "cross-site",
            }
            session.headers.update(headers)

            # Make request to legacy oEmbed endpoint
            oembed_url = f"{self.legacy_endpoint}?url={quote(url)}"

            response = session.get(oembed_url, timeout=10)

            if response.status_code == 200:
                try:
                    oembed_data = response.json()
                    data = self._parse_oembed_data(oembed_data, url)

                    if data:
                        self.logger.info(f"✅ Legacy oEmbed successful for {url}")
                        return ScrapingResult(
                            success=True,
                            data=data,
                            method=f"{self.name}_legacy",
                            response_time_ms=self.measure_time(start_time),
                        )
                except ValueError:
                    pass

            return ScrapingResult(
                success=False,
                error=f"Legacy oEmbed failed with status {response.status_code}",
                method=f"{self.name}_legacy",
                response_time_ms=self.measure_time(start_time),
            )

        except Exception as e:
            error_msg = f"Legacy oEmbed request failed: {str(e)}"
            self.logger.warning(error_msg)
            return ScrapingResult(
                success=False,
                error=error_msg,
                method=f"{self.name}_legacy",
                response_time_ms=self.measure_time(start_time),
            )

    def _parse_oembed_data(
        self, oembed_data: Dict[str, Any], url: str
    ) -> Optional[Dict[str, Any]]:
        """Parse oEmbed response data into standardized format."""
        try:
            if not isinstance(oembed_data, dict):
                return None

            # Extract basic oEmbed fields
            title = oembed_data.get("title", "")
            author_name = oembed_data.get("author_name", "")
            thumbnail_url = oembed_data.get("thumbnail_url", "")
            html = oembed_data.get("html", "")

            # Parse HTML for additional metadata
            video_url = None
            if html and "video" in html.lower():
                # Try to extract video URL from HTML
                import re

                video_match = re.search(r'src="([^"]*\.mp4[^"]*)"', html)
                if video_match:
                    video_url = video_match.group(1)

            data = {
                "post_id": self.extract_post_id(url),
                "url": url,
                "image_url": thumbnail_url if thumbnail_url else None,
                "video_url": video_url,
                "title": title if title else None,
                "description": (
                    title if title else None
                ),  # oEmbed often puts description in title
                "content_type": "video" if video_url else "photo",
                "username": author_name if author_name else None,
                "caption": self._extract_caption_from_title(title),
                "likes": None,
                "comments": None,
                "timestamp": None,
                "html": html,  # Include HTML for rich rendering
            }

            # Only return if we have meaningful data
            if data.get("image_url") or data.get("video_url") or data.get("html"):
                return data

            return None

        except Exception as e:
            self.logger.warning(f"Failed to parse oEmbed data: {e}")
            return None

    def _extract_caption_from_title(self, title: str) -> Optional[str]:
        """Extract caption from oEmbed title."""
        if not title:
            return None

        try:
            # Common patterns in Instagram oEmbed titles
            # Pattern: "username on Instagram: "caption""
            if " on Instagram: " in title:
                parts = title.split(" on Instagram: ", 1)
                if len(parts) == 2:
                    caption = parts[1].strip().strip('"').strip("'")
                    return caption if caption else None

            # If no clear pattern, return title as caption if it's not just username
            if title and len(title) > 50:  # Longer titles likely contain captions
                return title

            return None

        except Exception:
            return None
