"""Enhanced Playwright-based Instagram scraper optimized for Docker Lambda."""

import asyncio
import glob
import logging
import os
import random
import sys
import time
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapingResult

# Enhanced Playwright import with comprehensive debugging
PLAYWRIGHT_AVAILABLE = False
async_playwright = None
stealth_async = None
Browser = None
BrowserContext = None

# Set up logging for import diagnostics
import_logger = logging.getLogger(__name__ + ".import")

try:
    import_logger.info("Attempting to import Playwright...")
    import_logger.info(f"Python version: {sys.version}")
    import_logger.info(f"Python path: {sys.path[:3]}")

    # Try importing playwright base module first
    import playwright

    version = getattr(playwright, "__version__", "unknown")
    import_logger.info(f"✅ Base playwright module imported, version: {version}")
    import_logger.info(f"Playwright location: {playwright.__file__}")

    # Try importing async API
    from playwright.async_api import Browser, BrowserContext, async_playwright

    import_logger.info("✅ Playwright async API imported successfully")

    # Try importing stealth
    try:
        from playwright_stealth import stealth_async

        import_logger.info("✅ Playwright stealth imported successfully")
    except ImportError as stealth_e:
        import_logger.warning(f"⚠️ Playwright stealth import failed: {stealth_e}")
        stealth_async = None

    PLAYWRIGHT_AVAILABLE = True
    import_logger.info("✅ All Playwright imports successful")

except ImportError as e:
    import_logger.error(f"❌ Playwright import failed: {e}")
    import_logger.error(f"Error type: {type(e)}")

    # Check if specific modules are missing
    try:
        import playwright

        import_logger.info("Base playwright module is available")
    except ImportError:
        import_logger.error("Base playwright module is not available")

    # Check PYTHONPATH and environment
    import_logger.error(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")
    task_root = os.environ.get("LAMBDA_TASK_ROOT", "Not set")
    import_logger.error(f"LAMBDA_TASK_ROOT: {task_root}")
    browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "Not set")
    import_logger.error(f"PLAYWRIGHT_BROWSERS_PATH: {browsers_path}")

    # Try to find playwright installation
    for path in sys.path:
        playwright_path = os.path.join(path, "playwright")
        if os.path.exists(playwright_path):
            import_logger.info(f"Found playwright directory at: {playwright_path}")
            try:
                contents = os.listdir(playwright_path)
                import_logger.info(f"Playwright directory contents: {contents[:10]}")
            except Exception as list_e:
                import_logger.error(f"Could not list playwright directory: {list_e}")

    import traceback

    import_logger.error(f"Full traceback: {traceback.format_exc()}")

except Exception as e:
    import_logger.error(f"❌ Unexpected error during Playwright import: {e}")
    import_logger.error(f"Error type: {type(e)}")
    import traceback

    import_logger.error(f"Full traceback: {traceback.format_exc()}")

# Log final status
if PLAYWRIGHT_AVAILABLE:
    import_logger.info("🎉 Playwright is ready for use")
else:
    import_logger.error("💥 Playwright is not available")


class PlaywrightScraper(BaseScraper):
    """High-performance async Playwright scraper optimized for Lambda."""

    def __init__(self):
        super().__init__("playwright")
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.initialization_lock = asyncio.Lock()
        self.is_initialized = False

        # Performance-optimized configurations
        self.viewport_sizes = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1440, "height": 900},
        ]

        self.mobile_user_agents = [
            (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                "Mobile/15E148 Safari/604.1"
            ),
            (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 "
                "Mobile/15E148 Safari/604.1"
            ),
            (
                "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
            ),
            (
                "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
            ),
        ]

    async def initialize(self) -> bool:
        """Initialize Playwright browser with performance optimizations."""
        if self.is_initialized:
            return True

        async with self.initialization_lock:
            if self.is_initialized:
                return True

            if not PLAYWRIGHT_AVAILABLE:
                self.logger.warning(
                    "Playwright not available - skipping initialization"
                )
                return False

            try:
                # Detect browser executable path in Lambda environment
                browser_executable = None
                if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
                    # Lambda environment - look for Playwright browsers
                    browsers_path = os.environ.get(
                        "PLAYWRIGHT_BROWSERS_PATH", "/var/task/playwright-browsers"
                    )
                    self.logger.info(
                        f"Lambda environment detected. Browsers path: {browsers_path}"
                    )

                    # Check if browsers directory exists
                    if os.path.exists(browsers_path):
                        self.logger.info(f"Browsers path exists: {browsers_path}")
                        # List contents for debugging
                        try:
                            contents = os.listdir(browsers_path)
                            self.logger.info(f"Browsers directory contents: {contents}")
                        except Exception as e:
                            self.logger.warning(
                                f"Could not list browsers directory: {e}"
                            )
                    else:
                        self.logger.warning(
                            f"Browsers path does not exist: {browsers_path}"
                        )

                    chromium_pattern = f"{browsers_path}/chromium-*/chrome-linux/chrome"
                    possible_paths = glob.glob(chromium_pattern)
                    if possible_paths:
                        browser_executable = possible_paths[0]
                        self.logger.info(f"Found Chromium at: {browser_executable}")
                    else:
                        self.logger.warning(f"No Chromium found in {browsers_path}")

                # Launch Playwright
                playwright = await async_playwright().start()

                # Browser launch options optimized for Lambda
                launch_options = {
                    "headless": True,
                    "args": [
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-accelerated-2d-canvas",
                        "--no-first-run",
                        "--no-zygote",
                        "--single-process",
                        "--disable-gpu",
                        "--disable-background-timer-throttling",
                        "--disable-backgrounding-occluded-windows",
                        "--disable-renderer-backgrounding",
                        "--disable-features=TranslateUI",
                        "--disable-extensions",
                        "--disable-plugins",
                        "--disable-images",  # Speed optimization
                        "--disable-javascript",  # Instagram works without JS
                    ],
                }

                if browser_executable:
                    launch_options["executable_path"] = browser_executable

                self.browser = await playwright.chromium.launch(**launch_options)

                # Create persistent context with mobile emulation
                self.context = await self.browser.new_context(
                    viewport=random.choice(self.viewport_sizes),  # nosec B311
                    user_agent=random.choice(self.mobile_user_agents),  # nosec B311
                    device_scale_factor=random.choice([1, 2]),  # nosec B311
                    is_mobile=True,  # Mobile Instagram often has better metadata
                    has_touch=True,
                    locale="en-US",
                    timezone_id="America/New_York",
                    permissions=["geolocation"],
                    extra_http_headers={
                        "Accept": (
                            "text/html,application/xhtml+xml,application/xml;q=0.9,"
                            "image/webp,*/*;q=0.8"
                        ),
                        "Accept-Language": "en-US,en;q=0.5",
                        "Accept-Encoding": "gzip, deflate",
                        "DNT": "1",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Cache-Control": "max-age=0",
                    },
                )

                # Apply stealth if available
                try:
                    page = await self.context.new_page()
                    if stealth_async:
                        await stealth_async(page)
                    await page.close()
                    self.logger.info("✅ Playwright stealth mode applied")
                except Exception as e:
                    self.logger.warning(f"Stealth mode failed: {e}")

                self.is_initialized = True
                self.logger.info("✅ Playwright browser initialized successfully")
                return True

            except Exception as e:
                self.logger.error(f"Failed to initialize Playwright: {str(e)}")
                await self.cleanup()
                return False

    async def scrape(self, url: str) -> ScrapingResult:
        """Scrape Instagram data using optimized Playwright automation."""
        start_time = time.time()

        if not PLAYWRIGHT_AVAILABLE:
            return ScrapingResult(
                success=False,
                error="Playwright not available",
                method=self.name,
                response_time_ms=self.measure_time(start_time),
            )

        # Ensure browser is initialized
        if not await self.initialize():
            return ScrapingResult(
                success=False,
                error="Failed to initialize Playwright browser",
                method=self.name,
                response_time_ms=self.measure_time(start_time),
            )

        page = None
        try:
            # Create new page for this request
            page = await self.context.new_page()

            # Apply stealth mode for this page
            if stealth_async:
                await stealth_async(page)

            # Set timeout for Lambda constraints
            page.set_default_timeout(15000)  # 15 seconds max

            self.logger.info(f"🎭 Navigating to Instagram URL: {url}")

            # Navigate with realistic timing
            await page.goto(url, wait_until="domcontentloaded")

            # Wait for content to load with timeout
            try:
                await page.wait_for_selector('meta[property="og:title"]', timeout=5000)
            except asyncio.TimeoutError:
                # Continue even if specific selector not found
                pass

            # Small delay to simulate human reading
            await asyncio.sleep(random.uniform(0.5, 1.5))  # nosec B311

            # Get page content
            content = await page.content()

            # Parse with BeautifulSoup
            soup = BeautifulSoup(content, "html.parser")

            # Extract enhanced metadata
            data = self._extract_enhanced_data(soup, url)

            response_time = self.measure_time(start_time)

            if data:
                self.logger.info(f"✅ Playwright extraction successful for {url}")
                return ScrapingResult(
                    success=True,
                    data=data,
                    method=self.name,
                    response_time_ms=response_time,
                )
            else:
                self.logger.warning(f"❌ No data extracted via Playwright for {url}")
                return ScrapingResult(
                    success=False,
                    error="No data extracted from page",
                    method=self.name,
                    response_time_ms=response_time,
                )

        except asyncio.TimeoutError:
            self.logger.warning(f"⏰ Playwright timeout for {url}")
            return ScrapingResult(
                success=False,
                error="Request timeout",
                method=self.name,
                response_time_ms=self.measure_time(start_time),
            )
        except Exception as e:
            self.logger.error(f"❌ Playwright error for {url}: {str(e)}")
            return ScrapingResult(
                success=False,
                error=str(e),
                method=self.name,
                response_time_ms=self.measure_time(start_time),
            )
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    # Page cleanup is non-critical, ignore any errors
                    pass

    def _extract_enhanced_data(
        self, soup: BeautifulSoup, url: str
    ) -> Optional[Dict[str, Any]]:
        """Extract enhanced Instagram data from page content."""
        try:
            data = {
                "url": url,
                "extraction_method": "playwright",
                "timestamp": time.time(),
            }

            # Extract Open Graph metadata
            og_title = soup.find("meta", property="og:title")
            og_description = soup.find("meta", property="og:description")
            og_image = soup.find("meta", property="og:image")
            og_video = soup.find("meta", property="og:video")
            og_type = soup.find("meta", property="og:type")

            # Extract Twitter Card metadata
            twitter_title = soup.find("meta", attrs={"name": "twitter:title"})
            twitter_description = soup.find(
                "meta", attrs={"name": "twitter:description"}
            )
            twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
            twitter_player = soup.find("meta", attrs={"name": "twitter:player"})

            # Determine content type
            content_type = "photo"  # default
            if og_type and og_type.get("content"):
                if "video" in og_type.get("content", "").lower():
                    content_type = "video"
            if "/reel/" in url:
                content_type = "reel"
            elif "/tv/" in url:
                content_type = "video"

            data["content_type"] = content_type

            # Extract title and username
            title = None
            if og_title and og_title.get("content"):
                title = og_title.get("content")
            elif twitter_title and twitter_title.get("content"):
                title = twitter_title.get("content")

            if title:
                data["title"] = title
                # Parse username from title (usually "username on Instagram: ...")
                if " on Instagram" in title:
                    username = title.split(" on Instagram")[0].strip()
                    data["username"] = username

            # Extract description/caption
            description = None
            if og_description and og_description.get("content"):
                description = og_description.get("content")
            elif twitter_description and twitter_description.get("content"):
                description = twitter_description.get("content")

            if description:
                data["caption"] = description

                # Try to parse likes and comments from description
                self._parse_engagement_data(description, data)

            # Extract media URLs
            if og_image and og_image.get("content"):
                data["image_url"] = og_image.get("content")
            elif twitter_image and twitter_image.get("content"):
                data["image_url"] = twitter_image.get("content")

            # Extract video URL for reels/videos
            video_url = None
            if og_video and og_video.get("content"):
                video_url = og_video.get("content")
                data["video_url"] = video_url
            elif twitter_player and twitter_player.get("content"):
                video_url = twitter_player.get("content")
                data["video_url"] = video_url

            # Extract post ID from URL
            post_id = self._extract_post_id(url)
            if post_id:
                data["post_id"] = post_id

            # Add video-specific data for better Slack formatting
            is_video_content = bool(video_url) or content_type in ["video", "reel"]
            if is_video_content:
                data["is_video"] = True
                data["has_video"] = True
                data["video_playable"] = (
                    True  # Indicate this should be playable in Slack
                )

            # Extract additional data from page JavaScript and elements
            self._extract_enhanced_page_data(soup, data)

            # Ensure we have at least basic data
            if not any(
                key in data for key in ["title", "caption", "image_url", "video_url"]
            ):
                return None

            return data

        except Exception as e:
            self.logger.error(f"Error extracting data: {str(e)}")
            return None

    def _extract_enhanced_page_data(
        self, soup: BeautifulSoup, data: Dict[str, Any]
    ) -> None:
        """Extract additional data from page scripts and elements."""
        try:
            # Look for Instagram's shared data in page scripts
            scripts = soup.find_all("script")
            for script in scripts:
                if script.string and "window._sharedData" in script.string:
                    self._parse_shared_data(script.string, data)
                    break
                elif script.string and '"GraphSidecar"' in script.string:
                    self._parse_graph_data(script.string, data)
                elif script.string and '"shortcode_media"' in script.string:
                    self._parse_shortcode_data(script.string, data)

            # Additional video detection from page elements
            self._detect_video_elements(soup, data)

            # Extract from additional meta tags
            self._extract_additional_meta_tags(soup, data)

        except Exception as e:
            self.logger.debug(f"Enhanced page data extraction failed: {e}")

    def _parse_shared_data(self, script_content: str, data: Dict[str, Any]) -> None:
        """Parse Instagram's _sharedData for rich metadata."""
        try:
            import json
            import re

            # Extract JSON from window._sharedData
            match = re.search(r"window\._sharedData\s*=\s*({.+?});", script_content)
            if not match:
                return

            shared_data = json.loads(match.group(1))

            # Navigate through the shared data structure
            entry_data = shared_data.get("entry_data", {})
            post_page = entry_data.get("PostPage", [])

            if post_page and len(post_page) > 0:
                media = post_page[0].get("graphql", {}).get("shortcode_media", {})
                self._extract_media_data(media, data)

        except Exception as e:
            self.logger.debug(f"Shared data parsing failed: {e}")

    def _parse_graph_data(self, script_content: str, data: Dict[str, Any]) -> None:
        """Parse GraphQL data from page scripts."""
        try:
            import json
            import re

            # Look for GraphQL response data
            json_matches = re.finditer(
                r'(\{[^{}]*"GraphSidecar"[^{}]*\})', script_content
            )
            for match in json_matches:
                try:
                    graph_data = json.loads(match.group(1))
                    self._extract_media_data(graph_data, data)
                    break
                except json.JSONDecodeError:
                    continue

        except Exception as e:
            self.logger.debug(f"Graph data parsing failed: {e}")

    def _parse_shortcode_data(self, script_content: str, data: Dict[str, Any]) -> None:
        """Parse shortcode_media data from page scripts."""
        try:
            import json
            import re

            # Look for shortcode_media JSON data
            matches = re.finditer(
                r'"shortcode_media":\s*({[^}]+(?:{[^}]*}[^}]*)*})', script_content
            )
            for match in matches:
                try:
                    # Extract the JSON object
                    media_json = match.group(1)
                    media_data = json.loads(media_json)
                    self._extract_media_data(media_data, data)
                    break
                except json.JSONDecodeError:
                    continue

        except Exception as e:
            self.logger.debug(f"Shortcode data parsing failed: {e}")

    def _extract_media_data(
        self, media_data: Dict[str, Any], data: Dict[str, Any]
    ) -> None:
        """Extract data from Instagram media object."""
        try:
            # Extract owner information
            owner = media_data.get("owner", {})
            if owner and not data.get("username"):
                data["username"] = owner.get("username")
                if owner.get("is_verified"):
                    data["is_verified"] = True
                if owner.get("full_name"):
                    data["full_name"] = owner.get("full_name")

            # Extract engagement data
            if "edge_media_preview_like" in media_data and not data.get("likes"):
                data["likes"] = media_data["edge_media_preview_like"].get("count", 0)

            if "edge_media_to_comment" in media_data and not data.get("comments"):
                data["comments"] = media_data["edge_media_to_comment"].get("count", 0)

            # Extract caption
            caption_edges = media_data.get("edge_media_to_caption", {}).get("edges", [])
            if caption_edges and not data.get("caption"):
                caption_node = caption_edges[0].get("node", {})
                data["caption"] = caption_node.get("text", "")

            # Extract video URL
            if media_data.get("is_video") and not data.get("video_url"):
                data["video_url"] = media_data.get("video_url")
                data["is_video"] = True
                data["has_video"] = True
                # Only override content_type if not already set from URL
                if data.get("content_type") == "photo":
                    data["content_type"] = "video"

            # Extract timestamp
            if media_data.get("taken_at_timestamp") and not data.get("timestamp"):
                data["timestamp"] = media_data.get("taken_at_timestamp")

        except Exception as e:
            self.logger.debug(f"Media data extraction failed: {e}")

    def _detect_video_elements(self, soup: BeautifulSoup, data: Dict[str, Any]) -> None:
        """Detect video elements and URLs from page."""
        try:
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

                # Check poster attribute for video thumbnail
                if video.get("poster") and not data.get("image_url"):
                    data["image_url"] = video.get("poster")

        except Exception as e:
            self.logger.debug(f"Video element detection failed: {e}")

    def _extract_additional_meta_tags(
        self, soup: BeautifulSoup, data: Dict[str, Any]
    ) -> None:
        """Extract data from additional meta tags."""
        try:
            # Look for additional Twitter Card meta tags
            video_meta_tags = [
                ("twitter:player:stream", "video_url"),
                ("twitter:player:stream:content_type", "video_content_type"),
                ("twitter:image:alt", "image_alt"),
            ]

            for meta_name, data_key in video_meta_tags:
                meta_tag = soup.find("meta", attrs={"name": meta_name})
                if meta_tag and meta_tag.get("content") and not data.get(data_key):
                    content = meta_tag.get("content")
                    data[data_key] = content

                    # Mark as video if we found a video stream
                    if meta_name == "twitter:player:stream":
                        data["is_video"] = True
                        data["has_video"] = True
                        # Only override content_type if not already set from URL
                        if data.get("content_type") == "photo":
                            data["content_type"] = "video"

        except Exception as e:
            self.logger.debug(f"Additional meta tag extraction failed: {e}")

    def _parse_engagement_data(self, description: str, data: Dict[str, Any]) -> None:
        """Parse likes and comments from description text."""
        try:
            import re

            # Look for patterns like "1,234 Likes, 56 Comments"
            likes_match = re.search(r"([\d,]+)\s+Likes?", description, re.IGNORECASE)
            if likes_match:
                likes_str = likes_match.group(1).replace(",", "")
                try:
                    data["likes"] = int(likes_str)
                except ValueError:
                    pass

            comments_match = re.search(
                r"([\d,]+)\s+Comments?", description, re.IGNORECASE
            )
            if comments_match:
                comments_str = comments_match.group(1).replace(",", "")
                try:
                    data["comments"] = int(comments_str)
                except ValueError:
                    pass

        except Exception:
            # Non-critical parsing, continue execution
            pass

    def _extract_post_id(self, url: str) -> Optional[str]:
        """Extract Instagram post ID from URL."""
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split("/") if p]

            if len(path_parts) >= 2 and path_parts[0] in ["p", "reel", "tv"]:
                return path_parts[1]
            return None
        except Exception:
            return None

    async def cleanup(self) -> None:
        """Clean up browser resources."""
        try:
            if self.context:
                await self.context.close()
                self.context = None

            if self.browser:
                await self.browser.close()
                self.browser = None

            self.is_initialized = False
            self.logger.info("✅ Playwright browser cleaned up")

        except Exception as e:
            self.logger.warning(f"Error during Playwright cleanup: {e}")

    def __del__(self):
        """Ensure cleanup on destruction."""
        if self.is_initialized:
            try:
                # Create event loop if none exists for cleanup
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.cleanup())
                else:
                    loop.run_until_complete(self.cleanup())
            except Exception:
                pass  # Best effort cleanup
