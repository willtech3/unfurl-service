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
        """Format video/reel content with playable video support."""
        # Extract metadata
        username = data.get("username", "Instagram User")
        caption = data.get("caption", "")
        likes = data.get("likes")
        comments = data.get("comments")
        video_url = data.get("video_url")
        image_url = data.get("image_url")  # Thumbnail
        url = data.get("url", "")
        content_type = data.get("content_type", "video")

        # Create title
        content_label = "Reel" if content_type == "reel" else "Video"
        title = f"📹 {username}'s Instagram {content_label}"

        # Create description with engagement stats
        description_parts = []
        if caption and not is_fallback:
            # Truncate long captions
            display_caption = caption[:150] + "..." if len(caption) > 150 else caption
            description_parts.append(f'"{display_caption}"')

        if likes is not None or comments is not None:
            stats = []
            if likes is not None:
                stats.append(f"❤️ {self._format_number(likes)}")
            if comments is not None:
                stats.append(f"💬 {self._format_number(comments)}")
            if stats:
                description_parts.append(" • ".join(stats))

        description = (
            "\n".join(description_parts)
            if description_parts
            else "Instagram video content"
        )

        # Enhanced unfurl for video content
        unfurl = {
            "color": "#E4405F",  # Instagram brand color
            "title": title,
            "title_link": url,
            "text": description,
            "footer": "Instagram",
            "footer_icon": (
                "https://www.instagram.com/static/images/ico/"
                "favicon-192.png/68d99ba29cc8.png"
            ),
        }

        # Add video if available and supported
        if video_url and not is_fallback:
            # Use Slack Video Block for embedded playable videos
            video_proxy_url = self._get_video_proxy_url(video_url, url)
            if video_proxy_url:
                # Use Block Kit with Video Block for embedded playback
                unfurl["blocks"] = [
                    {
                        "type": "video",
                        "video_url": video_proxy_url,
                        "alt_text": "Instagram video",
                        "title": {
                            "type": "plain_text",
                            "text": title[:150] + "..." if len(title) > 150 else title,
                        },
                        "description": {
                            "type": "plain_text",
                            "text": (
                                description[:500] + "..."
                                if len(description) > 500
                                else description
                            ),
                        },
                        "thumbnail_url": image_url,
                        "provider_name": "Instagram",
                        "provider_icon_url": (
                            "https://www.instagram.com/static/images/ico/"
                            "favicon-192.png/68d99ba29cc8.png"
                        ),
                        "title_url": url,
                    }
                ]
                # Remove traditional unfurl fields when using blocks
                unfurl.pop("title", None)
                unfurl.pop("title_link", None)
                unfurl.pop("text", None)
            else:
                # Fallback to thumbnail with play button
                if image_url:
                    unfurl["image_url"] = image_url
                unfurl["text"] += f"\n\n🎬 <{url}|Watch on Instagram>"
        elif image_url:
            # Use thumbnail for fallback
            unfurl["image_url"] = image_url
            if is_fallback:
                unfurl["text"] += f"\n\n🎬 <{url}|Watch on Instagram>"

        return unfurl

    def _format_image_unfurl(
        self, data: Dict[str, Any], is_fallback: bool
    ) -> Dict[str, Any]:
        """Format image/photo content with rich metadata."""
        # Extract metadata
        username = data.get("username", "Instagram User")
        caption = data.get("caption", "")
        likes = data.get("likes")
        comments = data.get("comments")
        image_url = data.get("image_url")
        url = data.get("url", "")

        # Create title
        title = f"📸 {username}'s Instagram Post"

        # Create rich description
        description_parts = []
        if caption and not is_fallback:
            # Truncate long captions but show more for photos
            display_caption = caption[:200] + "..." if len(caption) > 200 else caption
            description_parts.append(f'"{display_caption}"')

        if likes is not None or comments is not None:
            stats = []
            if likes is not None:
                stats.append(f"❤️ {self._format_number(likes)}")
            if comments is not None:
                stats.append(f"💬 {self._format_number(comments)}")
            if stats:
                description_parts.append(" • ".join(stats))

        description = (
            "\n".join(description_parts) if description_parts else "Instagram photo"
        )

        # Enhanced unfurl for image content
        unfurl = {
            "color": "#E4405F",  # Instagram brand color
            "title": title,
            "title_link": url,
            "text": description,
            "footer": "Instagram",
            "footer_icon": (
                "https://www.instagram.com/static/images/ico/"
                "favicon-192.png/68d99ba29cc8.png"
            ),
        }

        # Add image if available
        if image_url and not is_fallback:
            unfurl["image_url"] = image_url
        elif is_fallback:
            unfurl["text"] += f"\n\n📱 <{url}|View on Instagram>"

        return unfurl

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
                f"📹 *{username}'s Instagram Reel*"
                if content_type == "reel"
                else f"📸 *{username}'s Instagram Post*"
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
                    stats_text += f"❤️ {self._format_number(likes)}"
                if comments is not None:
                    if stats_text:
                        stats_text += "  •  "
                    stats_text += f"💬 {self._format_number(comments)}"

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
