"""Enhanced Slack formatting for Instagram unfurls with video support."""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SlackFormatter:
    """Enhanced Slack unfurl formatter with rich blocks and video support."""

    def __init__(self):
        self.logger = logger

    def format_unfurl_data(
        self, data: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Format Instagram data for rich Slack unfurl with enhanced visual layout.

        Args:
            data: Instagram post data or None

        Returns:
            Formatted unfurl data for Slack or None
        """
        if not data:
            return None

        try:
            # Determine if this is video content
            is_video = bool(data.get("video_url")) or data.get("content_type") in [
                "video",
                "reel",
            ]
            is_fallback = data.get("is_fallback", False)

            # Create enhanced unfurl based on content type
            if is_video:
                return self._format_video_unfurl(data, is_fallback)
            else:
                return self._format_image_unfurl(data, is_fallback)

        except Exception as e:
            self.logger.warning(f"Failed to format unfurl data: {e}")
            return self._format_basic_unfurl(data)

    def _format_video_unfurl(
        self, data: Dict[str, Any], is_fallback: bool
    ) -> Dict[str, Any]:
        """
        Format video/reel content with rich, Instagram-like layout using Block Kit.

        This method creates a rich, Instagram-like layout for video and reel content
        using Slack's Block Kit. It extracts metadata from the provided data and
        constructs a Block Kit layout with an image, caption, and engagement stats.
        """
        # Extract metadata
        username = data.get("username", "Instagram User")
        caption = data.get("caption", "")
        likes = data.get("likes")
        comments = data.get("comments")
        video_url = data.get("video_url")
        image_url = data.get("image_url")  # Thumbnail
        url = data.get("url", "")
        content_type = data.get("content_type", "video")
        is_verified = data.get("is_verified", False)

        # Use rich Block Kit layout for videos (similar to images but optimized
        # for video)
        if not is_fallback and (video_url or image_url):
            # For videos, we'll use the same rich block layout as images
            # but with video-specific indicators and engagement
            return self._create_rich_block_unfurl(
                username,
                caption,
                likes,
                comments,
                image_url,
                url,
                is_verified,
                content_type,
            )
        else:
            # Fallback to basic unfurl
            return self._create_basic_unfurl(username, caption, url, content_type)

    def _format_image_unfurl(
        self, data: Dict[str, Any], is_fallback: bool
    ) -> Dict[str, Any]:
        """Format image/photo content with rich, Instagram-like layout using
        Block Kit."""
        # Extract metadata
        username = data.get("username", "Instagram User")
        caption = data.get("caption", "")
        likes = data.get("likes")
        comments = data.get("comments")
        image_url = data.get("image_url")
        url = data.get("url", "")
        is_verified = data.get("is_verified", False)

        # Use Block Kit for rich, Instagram-like layout
        if not is_fallback and image_url:
            return self._create_rich_block_unfurl(
                username, caption, likes, comments, image_url, url, is_verified, "photo"
            )
        else:
            # Fallback to basic unfurl
            return self._create_basic_unfurl(username, caption, url, "photo")

    def _create_rich_block_unfurl(
        self,
        username: str,
        caption: str,
        likes: Optional[int],
        comments: Optional[int],
        image_url: str,
        url: str,
        is_verified: bool,
        content_type: str,
    ) -> Dict[str, Any]:
        """Create rich Instagram-style unfurl using Slack Block Kit."""

        blocks = []

        # Header with Instagram branding and username
        username_text = f"*{username}*"
        if is_verified:
            username_text += " "

        header_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f" Instagram*\n{username_text}",
            },
            "accessory": {
                "type": "image",
                "image_url": (
                    "https://www.instagram.com/static/images/ico/"
                    "favicon-192.png/68d99ba29cc8.png"
                ),
                "alt_text": "Instagram",
            },
        }
        blocks.append(header_block)

        # Caption (if available)
        if caption:
            display_caption = caption[:200] + "..." if len(caption) > 200 else caption
            formatted_caption = self._format_caption_with_hashtags(display_caption)

            caption_block = {
                "type": "section",
                "text": {"type": "mrkdwn", "text": formatted_caption},
            }
            blocks.append(caption_block)

        # Main image/video block
        if image_url:
            image_block = {
                "type": "image",
                "image_url": image_url,
                "alt_text": f"Instagram {content_type} by {username}",
            }

            # Add video indicator for video content
            if content_type in ["video", "reel"]:
                image_block["title"] = {
                    "type": "plain_text",
                    "text": f" {content_type.title()}",
                }

            blocks.append(image_block)

        # Footer with engagement stats and view link
        footer_elements = []

        # Add engagement stats
        if likes is not None or comments is not None:
            stats_parts = []
            if likes is not None:
                stats_parts.append(f"{self._format_number(likes)} likes")
            if comments is not None:
                stats_parts.append(f"{self._format_number(comments)} comments")

            if stats_parts:
                stats_text = " • ".join(stats_parts)
                footer_elements.append({"type": "mrkdwn", "text": stats_text})

        # Add view link
        footer_elements.append({"type": "mrkdwn", "text": f"<{url}|View on Instagram>"})

        if footer_elements:
            footer_block = {"type": "context", "elements": footer_elements}
            blocks.append(footer_block)

        return {"color": "#E4405F", "blocks": blocks}

    def _create_basic_unfurl(
        self, username: str, caption: str, url: str, content_type: str
    ) -> Dict[str, Any]:
        """Create basic unfurl for fallback scenarios."""
        title = f" {username}" if content_type == "photo" else f" {username}"

        description_parts = []
        if caption:
            display_caption = caption[:150] + "..." if len(caption) > 150 else caption
            description_parts.append(f'"{display_caption}"')

        description = (
            "\n".join(description_parts)
            if description_parts
            else f"Instagram {content_type}"
        )
        description += f"\n\n {url}|View on Instagram>"

        return {
            "color": "#E4405F",
            "title": title,
            "title_link": url,
            "text": description,
            "footer": "Instagram",
            "footer_icon": (
                "https://www.instagram.com/static/images/ico/"
                "favicon-192.png/68d99ba29cc8.png"
            ),
        }

    def _format_caption_with_hashtags(self, caption: str) -> str:
        """Format caption text with proper hashtag styling."""
        import re

        # Convert #hashtags to styled format (but keep them readable)
        hashtag_pattern = r"#([A-Za-z0-9_]+)"
        caption = re.sub(hashtag_pattern, r"`#\1`", caption)

        # Convert @mentions to styled format
        mention_pattern = r"@([A-Za-z0-9._]+)"
        caption = re.sub(mention_pattern, r"`@\1`", caption)

        return caption

    def _format_basic_unfurl(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format basic unfurl as fallback."""
        url = data.get("url", "")
        title = data.get("title", "Instagram Content")
        description = data.get("description", "Content available on Instagram")

        return {
            "color": "#E4405F",
            "title": title,
            "title_link": url,
            "text": description,
            "footer": "Instagram",
            "footer_icon": (
                "https://www.instagram.com/static/images/ico/"
                "favicon-192.png/68d99ba29cc8.png"
            ),
        }

    def _is_slack_playable_video(self, video_url: str) -> bool:
        """Check if video URL is directly playable in Slack."""
        if not video_url:
            return False

        try:
            parsed = urlparse(video_url)

            # Slack supports direct playback of MP4 videos from certain domains
            supported_domains = [
                "scontent.cdninstagram.com",
                "video.cdninstagram.com",
                "instagram.fhel3-1.fna.fbcdn.net",
                "scontent-iad3-1.cdninstagram.com",
            ]

            # Check if it's a direct MP4 link from supported domain
            return any(
                domain in parsed.netloc for domain in supported_domains
            ) and video_url.lower().endswith(".mp4")

        except Exception:
            return False

    def _format_number(self, num: int) -> str:
        """Format numbers with K/M suffixes for better readability."""
        if num is None:
            return "0"

        try:
            num = int(num)
            if num >= 1_000_000:
                return f"{num / 1_000_000:.1f}M"
            elif num >= 1_000:
                return f"{num / 1_000:.1f}K"
            else:
                return str(num)
        except (ValueError, TypeError):
            return str(num)

    def _get_video_proxy_url(self, video_url: str, url: str) -> Optional[str]:
        """Get video proxy URL for playable Instagram videos."""
        try:
            import os
            import urllib.parse

            # Get the video proxy base URL from environment
            proxy_base_url = os.environ.get("VIDEO_PROXY_BASE_URL")
            if not proxy_base_url:
                logger.warning("VIDEO_PROXY_BASE_URL not configured")
                return None

            # Only proxy Instagram video URLs for security
            if not self._is_instagram_video(video_url):
                logger.debug(f"Not an Instagram video URL: {video_url}")
                return None

            # URL encode the video URL for safe transmission
            encoded_video_url = urllib.parse.quote(video_url, safe="")

            # Construct the proxy URL
            proxy_url = f"{proxy_base_url}/video/{encoded_video_url}"

            logger.info(f"Generated video proxy URL for {video_url[:50]}...")
            return proxy_url

        except Exception as e:
            logger.error(f"Failed to generate video proxy URL: {e}")
            return None

    def _is_instagram_video(self, video_url: str) -> bool:
        """Check if URL is a valid Instagram video URL."""
        if not video_url:
            return False

        try:
            from urllib.parse import urlparse

            parsed = urlparse(video_url)

            # Instagram CDN domains
            instagram_domains = [
                "scontent.cdninstagram.com",
                "video.cdninstagram.com",
                "instagram.fhel3-1.fna.fbcdn.net",
                "scontent-iad3-1.cdninstagram.com",
                "scontent.xx.fbcdn.net",
                "video.xx.fbcdn.net",
            ]

            return any(domain in parsed.netloc for domain in instagram_domains)

        except Exception:
            return False

    def create_slack_blocks(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Create rich Slack blocks for enhanced unfurl display.

        This provides an alternative block-based layout for better visual impact.
        """
        try:
            username = data.get("username", "Instagram User")
            caption = data.get("caption", "")
            likes = data.get("likes")
            comments = data.get("comments")
            url = data.get("url", "")
            image_url = data.get("image_url")
            content_type = data.get("content_type", "photo")
            is_fallback = data.get("is_fallback", False)

            blocks = []

            # Header block
            header_text = (
                f" *{username}'s Instagram Reel*"
                if content_type == "reel"
                else f" *{username}'s Instagram Post*"
            )
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": header_text},
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View on Instagram"},
                        "url": url,
                    },
                }
            )

            # Image/video block
            if image_url and not is_fallback:
                blocks.append(
                    {
                        "type": "image",
                        "image_url": image_url,
                        "alt_text": f"{username}'s Instagram post",
                    }
                )

            # Caption block
            if caption and not is_fallback:
                display_caption = (
                    caption[:500] + "..." if len(caption) > 500 else caption
                )
                blocks.append(
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f'"{display_caption}"'},
                    }
                )

            # Stats block
            if (likes is not None or comments is not None) and not is_fallback:
                stats_text = ""
                if likes is not None:
                    stats_text += f" {self._format_number(likes)}"
                if comments is not None:
                    if stats_text:
                        stats_text += "  •  "
                    stats_text += f" {self._format_number(comments)}"

                blocks.append(
                    {
                        "type": "context",
                        "elements": [{"type": "mrkdwn", "text": stats_text}],
                    }
                )

            # Fallback message
            if is_fallback:
                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Content available on Instagram",
                        },
                    }
                )

            return blocks

        except Exception as e:
            self.logger.warning(f"Failed to create Slack blocks: {e}")
            return []
