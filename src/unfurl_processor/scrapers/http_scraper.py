"""HTTP-based Instagram scraper with enhanced bot evasion."""

import random
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapingResult


class HttpScraper(BaseScraper):
    """HTTP-based scraper with session management and bot evasion."""

    def __init__(self, proxy_urls: Optional[List[str]] = None):
        super().__init__("http")
        self.proxy_urls = proxy_urls or []
        self.session = None
        self.user_agents = [
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 "
                "Safari/537.36"
            ),
            (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
                "Gecko/20100101 Firefox/121.0"
            ),
            (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) "
                "Gecko/20100101 Firefox/121.0"
            ),
        ]

    async def scrape(self, url: str) -> ScrapingResult:
        """Scrape Instagram data using HTTP requests with enhanced bot evasion."""
        start_time = time.time()

        if not self.validate_instagram_url(url):
            return ScrapingResult(
                success=False,
                error="Invalid Instagram URL",
                method=self.name,
                response_time_ms=self.measure_time(start_time),
            )

        try:
            # Create session with enhanced headers
            session = requests.Session()

            # Random user agent for each request
            user_agent = random.choice(self.user_agents)  # nosec B311

            # Comprehensive browser-like headers
            headers = {
                "User-Agent": user_agent,
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,image/apng,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",  # Exclude 'br' to avoid brotli
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
                "sec-ch-ua": (
                    '"Not_A Brand";v="8", "Chromium";v="120", '
                    '"Google Chrome";v="120"'
                ),
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            }

            session.headers.update(headers)

            # Set proxy if available
            proxies = {}
            if self.proxy_urls:
                proxy_url = random.choice(self.proxy_urls)  # nosec B311
                proxies = {"http": proxy_url, "https": proxy_url}
                self.logger.info(f"Using proxy: {proxy_url}")

            # Multi-step navigation simulation
            # Step 1: Visit Instagram homepage first
            try:
                session.get(
                    "https://www.instagram.com/",
                    proxies=proxies,
                    timeout=10,
                    allow_redirects=True,
                )

                # Human-like delay
                time.sleep(random.uniform(0.5, 2.0))  # nosec B311

            except Exception as e:
                self.logger.warning(f"Homepage visit failed: {e}")

            # Step 2: Navigate to target URL
            response = session.get(
                url, proxies=proxies, timeout=15, allow_redirects=True
            )

            response.raise_for_status()

            # Log response details for debugging
            self.logger.info(f"Response status: {response.status_code}")
            self.logger.info(
                f"Content encoding: {response.headers.get('content-encoding', 'none')}"
            )
            self.logger.info(f"Response size: {len(response.content)}")

            # Get text content
            content = response.text

            # Validate content
            if not self._is_valid_html_content(content):
                return ScrapingResult(
                    success=False,
                    error="Invalid or bot-detected content received",
                    method=self.name,
                    response_time_ms=self.measure_time(start_time),
                )

            # Parse with BeautifulSoup
            soup = BeautifulSoup(content, "html.parser")
            data = self._extract_instagram_data(soup, url)

            if data:
                self.logger.info(f"✅ HTTP scraping successful for {url}")
                return ScrapingResult(
                    success=True,
                    data=data,
                    method=self.name,
                    response_time_ms=self.measure_time(start_time),
                )
            else:
                return ScrapingResult(
                    success=False,
                    error="No valid Instagram data found in response",
                    method=self.name,
                    response_time_ms=self.measure_time(start_time),
                )

        except requests.RequestException as e:
            error_msg = f"HTTP request failed: {str(e)}"
            self.logger.warning(error_msg)
            return ScrapingResult(
                success=False,
                error=error_msg,
                method=self.name,
                response_time_ms=self.measure_time(start_time),
            )
        except Exception as e:
            error_msg = f"HTTP scraping failed: {str(e)}"
            self.logger.warning(error_msg)
            return ScrapingResult(
                success=False,
                error=error_msg,
                method=self.name,
                response_time_ms=self.measure_time(start_time),
            )

    def _is_valid_html_content(self, content: str) -> bool:
        """Check if content is valid HTML and not bot-detected response."""
        if not content or len(content) < 1000:
            return False

        # Check for basic HTML structure OR Instagram-specific content
        html_indicators = ["<html", "<head", "<body", "<!doctype", "<!DOCTYPE"]
        instagram_indicators = [
            'property="og:',
            "application/ld+json",
            "window._sharedData",
            "instagram.com",
            '"username"',
            '"shortcode"',
        ]

        content_lower = content.lower()

        has_html_structure = any(
            indicator in content_lower for indicator in html_indicators
        )
        has_instagram_content = any(
            indicator in content for indicator in instagram_indicators
        )

        # Check for binary/compressed content markers
        binary_markers = [
            b"\x00",  # Null bytes
            b"\x1f\x8b",  # Gzip header
            b"\x28\xb5\x2f\xfd",  # Zstandard header
        ]

        content_bytes = content.encode("utf-8", errors="ignore")
        has_binary_content = any(
            marker in content_bytes[:100] for marker in binary_markers
        )

        if has_binary_content:
            self.logger.warning("Content appears to be binary/compressed")
            return False

        is_valid = has_html_structure or has_instagram_content

        self.logger.info(
            f"Content validation - HTML structure: {has_html_structure}, "
            f"Instagram content: {has_instagram_content}"
        )

        return is_valid

    def _extract_instagram_data(
        self, soup: BeautifulSoup, url: str
    ) -> Optional[Dict[str, Any]]:
        """Extract Instagram data from BeautifulSoup object."""
        try:
            # Extract Open Graph metadata
            og_image = soup.find("meta", property="og:image")
            og_title = soup.find("meta", property="og:title")
            og_description = soup.find("meta", property="og:description")
            og_video = soup.find("meta", property="og:video")
            og_type = soup.find("meta", property="og:type")

            # Extract Twitter Card metadata as fallback
            twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
            twitter_title = soup.find("meta", attrs={"name": "twitter:title"})
            twitter_description = soup.find(
                "meta", attrs={"name": "twitter:description"}
            )

            data = {
                "post_id": self.extract_post_id(url),
                "url": url,
                "image_url": (
                    og_image.get("content")
                    if og_image
                    else twitter_image.get("content")
                    if twitter_image
                    else None
                ),
                "video_url": og_video.get("content") if og_video else None,
                "title": (
                    og_title.get("content")
                    if og_title
                    else twitter_title.get("content")
                    if twitter_title
                    else None
                ),
                "description": (
                    og_description.get("content")
                    if og_description
                    else (
                        twitter_description.get("content")
                        if twitter_description
                        else None
                    )
                ),
                "content_type": og_type.get("content") if og_type else "photo",
                "username": None,
                "caption": None,
                "likes": None,
                "comments": None,
                "timestamp": None,
            }

            # Parse description for additional metadata
            if data.get("description"):
                self._parse_description_metadata(data["description"], data)

            # Try to extract enhanced data
            self._extract_enhanced_data(soup, data)

            # Only return data if we have essential metadata
            if (
                data.get("image_url")
                or data.get("video_url")
                or data.get("description")
            ):
                return data

            return None

        except Exception as e:
            self.logger.warning(f"Failed to extract Instagram data: {e}")
            return None

    def _parse_description_metadata(
        self, description: str, data: Dict[str, Any]
    ) -> None:
        """Parse Instagram description for username, likes, comments."""
        try:
            import re

            # Pattern: "123 Likes, 45 Comments - username on Instagram: "caption""
            pattern = (
                r'^([\d,]+) Likes, ([\d,]+) Comments - (.+?) on Instagram: "(.+)"$'
            )
            match = re.match(pattern, description)

            if match:
                data["likes"] = int(match.group(1).replace(",", ""))
                data["comments"] = int(match.group(2).replace(",", ""))
                data["username"] = match.group(3)
                data["caption"] = match.group(4)
            else:
                # Fallback: split by " on Instagram: "
                if " on Instagram: " in description:
                    parts = description.split(" on Instagram: ", 1)
                    if len(parts) == 2:
                        data["username"] = parts[0].strip()
                        data["caption"] = parts[1].strip().strip('"')

        except Exception as e:
            self.logger.debug(f"Description parsing failed: {e}")

    def _extract_enhanced_data(self, soup: BeautifulSoup, data: Dict[str, Any]) -> None:
        """Extract additional data from page elements."""
        try:
            # Try to find JSON-LD structured data
            json_scripts = soup.find_all("script", type="application/ld+json")
            for script in json_scripts:
                try:
                    import json

                    ld_data = json.loads(script.string)
                    if isinstance(ld_data, dict):
                        if "author" in ld_data and not data.get("username"):
                            if isinstance(ld_data["author"], dict):
                                data["username"] = ld_data["author"].get("name")
                            elif isinstance(ld_data["author"], str):
                                data["username"] = ld_data["author"]

                        if "headline" in ld_data and not data.get("caption"):
                            data["caption"] = ld_data["headline"]

                        if "interactionStatistic" in ld_data:
                            for stat in ld_data["interactionStatistic"]:
                                if stat.get(
                                    "interactionType"
                                ) == "LikeAction" and not data.get("likes"):
                                    data["likes"] = stat.get("userInteractionCount")
                                elif stat.get(
                                    "interactionType"
                                ) == "CommentAction" and not data.get("comments"):
                                    data["comments"] = stat.get("userInteractionCount")
                except (json.JSONDecodeError, AttributeError):
                    continue

            # Check page title for additional context
            title_tag = soup.find("title")
            if title_tag and not data.get("title"):
                title_text = title_tag.get_text().strip()
                if title_text and title_text != "Instagram":
                    data["title"] = title_text

        except Exception as e:
            self.logger.debug(f"Enhanced data extraction failed: {e}")
