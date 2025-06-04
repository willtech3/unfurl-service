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
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
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
            oembed_url = (
                f"{self.graph_api_endpoint}?url={quote(url)}"
                f"&access_token=instagram_basic_display"
            )

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
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
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

            # Determine content type from URL first
            content_type = "photo"  # default
            if "/reel/" in url:
                content_type = "reel"
            elif "/tv/" in url:
                content_type = "video"

            # Try to extract video URL from HTML
            video_url = None
            if html:
                # Try to extract video URL from HTML
                import re

                # Multiple video URL patterns
                video_patterns = [
                    r'src="([^"]*\.mp4[^"]*)"',
                    r'data-video-url="([^"]*)"',
                    r'"videoUrl":"([^"]*)"',
                    r'"video_url":"([^"]*)"',
                    r'https://[^"]*instagram\.com[^"]*\.mp4[^"]*',
                ]

                for pattern in video_patterns:
                    video_match = re.search(pattern, html)
                    if video_match:
                        video_url = video_match.group(1)
                        break

                # Enhanced data extraction from HTML
                self._extract_additional_html_data(html, data={})

            # Update content type if we found video
            if video_url and content_type == "photo":
                content_type = "video"

            is_video_content = bool(video_url) or content_type in ["video", "reel"]

            data = {
                "post_id": self.extract_post_id(url),
                "url": url,
                "image_url": thumbnail_url if thumbnail_url else None,
                "video_url": video_url,
                "title": title if title else None,
                "description": (
                    title if title else None
                ),  # oEmbed often puts description in title
                "content_type": content_type,
                "is_video": is_video_content,
                "has_video": is_video_content,  # Alternative field
                "username": author_name if author_name else None,
                "author": author_name if author_name else None,
                "caption": self._extract_caption_from_title(title),
                "likes": None,
                "comments": None,
                "timestamp": None,
                "html": html,  # Include HTML for rich rendering
                "scraper_name": self.name,
            }

            # Extract engagement data from title/description
            self._extract_engagement_from_text(title, data)

            # Only return if we have meaningful data
            if data.get("image_url") or data.get("video_url") or data.get("html"):
                return data

            return None

        except Exception as e:
            self.logger.warning(f"Failed to parse oEmbed data: {e}")
            return None

    def _extract_additional_html_data(self, html: str, data: Dict[str, Any]) -> None:
        """Extract additional data from oEmbed HTML content."""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")

            # Look for video elements
            video_elements = soup.find_all("video")
            for video in video_elements:
                if video.get("src") and not data.get("video_url"):
                    data["video_url"] = video.get("src")
                    data["is_video"] = True
                    data["has_video"] = True
                    # Only override content_type if not already set from URL
                    if data.get("content_type") == "photo":
                        data["content_type"] = "video"
                    break

            # Look for additional data attributes
            data_attrs = [
                ("data-instgrm-permalink", "permalink"),
                ("data-instgrm-caption", "caption"),
                ("data-likes", "likes"),
                ("data-comments", "comments"),
            ]

            for element in soup.find_all(
                attrs=lambda x: x and any(attr in x for attr, _ in data_attrs)
            ):
                for attr_name, data_key in data_attrs:
                    if element.get(attr_name) and not data.get(data_key):
                        value = element.get(attr_name)
                        if data_key in ["likes", "comments"]:
                            try:
                                data[data_key] = int(value)
                            except (ValueError, TypeError):
                                pass
                        else:
                            data[data_key] = value

        except Exception as e:
            self.logger.debug(f"Additional HTML data extraction failed: {e}")

    def _extract_engagement_from_text(self, text: str, data: Dict[str, Any]) -> None:
        """Extract engagement data from text content."""
        if not text:
            return

        try:
            import re

            # Pattern: "123 Likes, 45 Comments"
            engagement_pattern = r"([\d,]+)\s+Likes?,\s*([\d,]+)\s+Comments?"
            match = re.search(engagement_pattern, text, re.IGNORECASE)
            if match:
                try:
                    data["likes"] = int(match.group(1).replace(",", ""))
                    data["comments"] = int(match.group(2).replace(",", ""))
                except (ValueError, TypeError):
                    pass

            # Separate patterns for individual metrics
            if not data.get("likes"):
                likes_pattern = r"([\d,]+)\s+likes?"
                match = re.search(likes_pattern, text, re.IGNORECASE)
                if match:
                    try:
                        data["likes"] = int(match.group(1).replace(",", ""))
                    except (ValueError, TypeError):
                        pass

            if not data.get("comments"):
                comments_pattern = r"([\d,]+)\s+comments?"
                match = re.search(comments_pattern, text, re.IGNORECASE)
                if match:
                    try:
                        data["comments"] = int(match.group(1).replace(",", ""))
                    except (ValueError, TypeError):
                        pass

        except Exception as e:
            self.logger.debug(f"Engagement extraction failed: {e}")

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
