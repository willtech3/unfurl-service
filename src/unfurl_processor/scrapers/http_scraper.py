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
            twitter_player = soup.find("meta", attrs={"name": "twitter:player"})
            twitter_player_stream = soup.find(
                "meta", attrs={"name": "twitter:player:stream"}
            )

            # Determine if this is video content
            is_video_content = False
            video_url = None

            # Multiple video detection strategies
            if og_video and og_video.get("content"):
                video_url = og_video.get("content")
                is_video_content = True
            elif twitter_player and twitter_player.get("content"):
                video_url = twitter_player.get("content")
                is_video_content = True
            elif twitter_player_stream and twitter_player_stream.get("content"):
                video_url = twitter_player_stream.get("content")
                is_video_content = True
            elif "/reel/" in url or "/tv/" in url:
                # Instagram Reels and IGTV are always video content
                is_video_content = True
            elif og_type and "video" in og_type.get("content", "").lower():
                is_video_content = True

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
                "video_url": video_url,
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
                "content_type": "video" if is_video_content else "photo",
                "is_video": is_video_content,  # Add explicit video flag
                "username": None,
                "caption": None,
                "likes": None,
                "comments": None,
                "timestamp": None,
                "is_verified": False,  # Will be extracted from page content
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

            # Enhanced patterns for Instagram descriptions
            patterns = [
                # Pattern 1: "123 Likes, 45 Comments - username on Instagram: "caption""
                r'^([\d,]+) Likes, ([\d,]+) Comments - (.+?) on Instagram: "(.+)"$',
                # Pattern 2: "See Instagram photos and videos from username (@handle)"
                r"See Instagram photos and videos from (.+?) \(@([^)]+)\)",
                # Pattern 3: "username on Instagram: "caption""
                r'^(.+?) on Instagram: "(.+)"$',
                # Pattern 4: "@username • Instagram photos and videos"
                r"^@([^\s•]+?)\s*•\s*Instagram",
                # Pattern 5: Just engagement numbers
                r"([\d,]+)\s+likes?,\s*([\d,]+)\s+comments?",
                # Pattern 6: Username in title format
                r"^([^:•\-]+?)\s*[\-•:]\s*Instagram",
            ]

            for i, pattern in enumerate(patterns):
                match = re.search(pattern, description, re.IGNORECASE)
                if match:
                    if i == 0:  # Full pattern with engagement
                        data["likes"] = int(match.group(1).replace(",", ""))
                        data["comments"] = int(match.group(2).replace(",", ""))
                        data["username"] = match.group(3).strip()
                        data["caption"] = match.group(4).strip()
                        break
                    elif i == 1:  # Instagram profile pattern
                        data["username"] = match.group(1).strip()
                        # Try to extract handle if different
                        handle = match.group(2).strip()
                        if handle != data["username"]:
                            data["handle"] = handle
                        break
                    elif i == 2:  # Username and caption
                        data["username"] = match.group(1).strip()
                        data["caption"] = match.group(2).strip()
                        break
                    elif i == 3:  # Handle format
                        data["username"] = match.group(1).strip()
                        break
                    elif i == 4:  # Just engagement numbers
                        data["likes"] = int(match.group(1).replace(",", ""))
                        data["comments"] = int(match.group(2).replace(",", ""))
                        break
                    elif i == 5:  # Username from title
                        data["username"] = match.group(1).strip()
                        break

            # Separate extraction for engagement numbers if not found above
            if not data.get("likes"):
                likes_patterns = [
                    r"([\d,]+)\s+likes?",
                    r"♥\s*([\d,]+)",
                    r"❤\s*([\d,]+)",
                ]
                for pattern in likes_patterns:
                    match = re.search(pattern, description, re.IGNORECASE)
                    if match:
                        try:
                            data["likes"] = int(match.group(1).replace(",", ""))
                            break
                        except ValueError:
                            continue

            if not data.get("comments"):
                comment_patterns = [
                    r"([\d,]+)\s+comments?",
                    r"💬\s*([\d,]+)",
                ]
                for pattern in comment_patterns:
                    match = re.search(pattern, description, re.IGNORECASE)
                    if match:
                        try:
                            data["comments"] = int(match.group(1).replace(",", ""))
                            break
                        except ValueError:
                            continue

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
                        # Extract author information
                        if "author" in ld_data and not data.get("username"):
                            if isinstance(ld_data["author"], dict):
                                data["username"] = ld_data["author"].get("name")
                                if "url" in ld_data["author"]:
                                    data["profile_url"] = ld_data["author"]["url"]
                            elif isinstance(ld_data["author"], str):
                                data["username"] = ld_data["author"]

                        # Extract caption/headline
                        if "headline" in ld_data and not data.get("caption"):
                            data["caption"] = ld_data["headline"]
                        elif "description" in ld_data and not data.get("caption"):
                            data["caption"] = ld_data["description"]

                        # Extract engagement statistics
                        if "interactionStatistic" in ld_data:
                            for stat in ld_data["interactionStatistic"]:
                                interaction_type = stat.get("interactionType", "")
                                count = stat.get("userInteractionCount", 0)

                                if "LikeAction" in interaction_type and not data.get(
                                    "likes"
                                ):
                                    try:
                                        data["likes"] = int(count)
                                    except (ValueError, TypeError):
                                        pass
                                elif (
                                    "CommentAction" in interaction_type
                                    and not data.get("comments")
                                ):
                                    try:
                                        data["comments"] = int(count)
                                    except (ValueError, TypeError):
                                        pass
                                elif "ShareAction" in interaction_type:
                                    try:
                                        data["shares"] = int(count)
                                    except (ValueError, TypeError):
                                        pass

                        # Extract media information
                        if "video" in ld_data and not data.get("video_url"):
                            video_data = ld_data["video"]
                            if isinstance(video_data, dict):
                                if "contentUrl" in video_data:
                                    data["video_url"] = video_data["contentUrl"]
                                elif "url" in video_data:
                                    data["video_url"] = video_data["url"]
                                # Mark as video content
                                data["is_video"] = True
                                data["content_type"] = "video"

                        # Extract timestamps
                        if "datePublished" in ld_data and not data.get("timestamp"):
                            data["timestamp"] = ld_data["datePublished"]
                        elif "uploadDate" in ld_data and not data.get("timestamp"):
                            data["timestamp"] = ld_data["uploadDate"]

                except (json.JSONDecodeError, AttributeError):
                    continue

            # Additional video detection strategies
            self._detect_additional_video_sources(soup, data)

            # Check page title for additional context
            title_tag = soup.find("title")
            if title_tag and not data.get("title"):
                title_text = title_tag.get_text().strip()
                if title_text and title_text != "Instagram":
                    data["title"] = title_text

            # Extract verification status
            self._extract_verification_status(soup, data)

        except Exception as e:
            self.logger.debug(f"Enhanced data extraction failed: {e}")

    def _detect_additional_video_sources(
        self, soup: BeautifulSoup, data: Dict[str, Any]
    ) -> None:
        """Detect additional video sources from page elements."""
        try:
            # Look for video elements
            video_elements = soup.find_all("video")
            for video in video_elements:
                if video.get("src") and not data.get("video_url"):
                    data["video_url"] = video.get("src")
                    data["is_video"] = True
                    break

                # Check source elements within video
                sources = video.find_all("source")
                for source in sources:
                    if source.get("src") and not data.get("video_url"):
                        data["video_url"] = source.get("src")
                        data["is_video"] = True
                        break

            # Look for data attributes that might contain video URLs
            video_containers = soup.find_all(attrs={"data-video-url": True})
            for container in video_containers:
                video_url = container.get("data-video-url")
                if video_url and not data.get("video_url"):
                    data["video_url"] = video_url
                    data["is_video"] = True
                    break

        except Exception as e:
            self.logger.debug(f"Additional video detection failed: {e}")

    def _extract_verification_status(
        self, soup: BeautifulSoup, data: Dict[str, Any]
    ) -> None:
        """Extract verification status from page content."""
        try:
            # Look for verification indicators in the page
            verification_selectors = [
                'svg[aria-label*="Verified"]',
                'span[aria-label*="Verified"]',
                ".coreSpriteVerifiedBadge",
                ".coreSpriteVerifiedBadgeSmall",
                '[aria-label*="verified"]',
                '[title*="Verified"]',
                '[title*="verified"]',
            ]

            for selector in verification_selectors:
                if soup.select(selector):
                    data["is_verified"] = True
                    self.logger.debug("Found verification badge in page")
                    return

            # Check text content for verification mentions
            page_text = soup.get_text().lower()
            if any(
                term in page_text for term in ["verified", "checkmark", "blue tick"]
            ):
                # Additional check to ensure it's not just random text
                verification_context = [
                    "verified account",
                    "verified profile",
                    "verified user",
                    "blue checkmark",
                    "verification badge",
                ]
                if any(context in page_text for context in verification_context):
                    data["is_verified"] = True
                    self.logger.debug("Found verification mention in page text")
                    return

            self.logger.debug("No verification indicators found")

        except Exception as e:
            self.logger.debug(f"Verification extraction failed: {e}")
