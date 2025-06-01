"""Enhanced Slack formatting for Instagram unfurls with video support."""

from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from aws_lambda_powertools import Logger

logger = Logger()


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
            "footer_icon": "https://www.instagram.com/static/images/ico/favicon-192.png/68d99ba29cc8.png",
        }

        # Add video if available and supported
        if video_url and not is_fallback:
            # Check if video URL is directly playable in Slack
            if self._is_slack_playable_video(video_url):
                unfurl[
                    "video_html"
                ] = f"""
                <video controls width="400" height="400" poster="{image_url or ''}" preload="metadata">
                    <source src="{video_url}" type="video/mp4">
                    <p>Your browser doesn't support HTML5 video. <a href="{video_url}">Download the video</a>.</p>
                </video>
                """
                unfurl["video_html_width"] = 400
                unfurl["video_html_height"] = 400
            else:
                # Use thumbnail if video not directly playable
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
            "footer_icon": "https://www.instagram.com/static/images/ico/favicon-192.png/68d99ba29cc8.png",
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
            "footer_icon": "https://www.instagram.com/static/images/ico/favicon-192.png/68d99ba29cc8.png",
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
