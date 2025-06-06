"""Enhanced Slack formatting for Instagram unfurls."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SlackFormatter:
    """Enhanced Slack unfurl formatter with rich blocks."""

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
            # Determine if this is video content with playable video
            is_video = (
                bool(data.get("video_url") and data.get("video_url").strip())
                or data.get("video_playable") is True
            )

            # Check if this is video content type but without playable video
            is_video_content_type = (
                data.get("content_type") in ["video", "reel"]
                or data.get("is_video") is True
            )
            is_fallback = data.get("is_fallback", False)

            # Without playable video support, treat all video content the same
            if is_video or is_video_content_type:
                return self._format_video_content_unfurl(data, is_fallback)
            return self._format_image_unfurl(data, is_fallback)

        except Exception as e:
            self.logger.warning(f"Failed to format unfurl data: {e}")
            return self._format_basic_unfurl(data)

    def _format_video_content_unfurl(
        self, data: Dict[str, Any], is_fallback: bool
    ) -> Dict[str, Any]:
        """
        Format video content without playable video.
        Creates an enhanced image unfurl with video content indicators.
        """
        content_type = data.get("content_type", "video")

        # Create rich image unfurl with video indicators
        self.logger.info(
            f"Creating enhanced image unfurl for {content_type} content (no video URL)"
        )

        # Use the image unfurl method but with video content data
        unfurl = self._format_image_unfurl(data, is_fallback)

        # Add video content indicators
        if unfurl and "blocks" in unfurl:
            # Modify the header to indicate this is video content
            for block in unfurl["blocks"]:
                if block.get("type") == "section" and "Instagram" in block.get(
                    "text", {}
                ).get("text", ""):
                    # Add specific video emoji and type based on content
                    text = block["text"]["text"]
                    video_indicator = self._get_video_indicator(content_type)
                    content_label = self._get_content_type_label(content_type)

                    if video_indicator not in text:
                        block["text"]["text"] = text.replace(
                            " *Instagram*",
                            f" {video_indicator} *Instagram {content_label}*",
                        )
                    break

        return unfurl

    def _format_image_unfurl(
        self, data: Dict[str, Any], is_fallback: bool
    ) -> Dict[str, Any]:
        """Format image/photo content with rich, Instagram-like layout using
        Block Kit."""
        # Extract metadata
        username = data.get("username") or "Instagram User"
        caption = data.get("caption") or ""
        likes = data.get("likes")
        comments = data.get("comments")
        image_url = data.get("image_url")
        url = data.get("url", "")
        is_verified = data.get("is_verified", False)

        # Use Block Kit for rich, Instagram-like layout
        if not is_fallback and image_url:
            return self._create_rich_block_unfurl(
                username,
                caption,
                likes,
                comments,
                image_url,
                url,
                is_verified,
                data.get("content_type", "photo"),
            )
        else:
            # Fallback to basic unfurl
            return self._create_basic_unfurl(
                username, caption, url, data.get("content_type", "photo")
            )

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
            username_text += " ✓"

        # Get appropriate indicator and content type label
        content_indicator = self._get_content_indicator(content_type)
        content_label = self._get_content_type_label(content_type)

        # Instagram logo and header context
        logo_context_block = {
            "type": "context",
            "elements": [
                {
                    "type": "image",
                    "image_url": (
                        "https://www.instagram.com/static/images/ico/"
                        "favicon-192.png/68d99ba29cc8.png"
                    ),
                    "alt_text": "Instagram",
                },
                {"type": "mrkdwn", "text": f"*Instagram {content_label}*"},
            ],
        }
        blocks.append(logo_context_block)

        # Content and username section
        header_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{content_indicator} {username_text}",
            },
        }
        blocks.append(header_block)

        # Caption (if available) - parse and clean the caption
        clean_caption = self._extract_clean_caption(caption)
        if clean_caption:
            display_caption = (
                clean_caption[:200] + "..."
                if len(clean_caption) > 200
                else clean_caption
            )
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

            # Add play button overlay for video content
            if content_type in ["video", "reel", "tv"]:
                content_label = self._get_content_type_label(content_type)
                image_block["title"] = {
                    "type": "plain_text",
                    "text": f"▶️ Tap to watch {content_label.lower()}",
                }
            elif content_type == "photo":
                image_block["title"] = {
                    "type": "plain_text",
                    "text": "📷 View photo",
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
        # Normalise potential None values to safe defaults
        username = username or "Instagram User"
        caption = caption or ""

        # Get appropriate indicator and label for content type
        content_indicator = self._get_content_indicator(content_type)
        content_label = self._get_content_type_label(content_type)

        title = f"{content_indicator} *{username}"

        # Clean caption if available
        clean_caption = self._extract_clean_caption(caption)
        if clean_caption:
            description = f'"{clean_caption[:150]}..."'
        else:
            description = f"Instagram {content_label.lower()} content"

        description += f"\n\n<{url}|View on Instagram>"

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
        content_type = data.get("content_type", "photo")

        # Get appropriate indicator and label
        content_indicator = self._get_content_indicator(content_type)
        content_label = self._get_content_type_label(content_type)

        title = data.get("title") or f"{content_indicator} Instagram {content_label}"
        description = (
            data.get("description")
            or f"Instagram {content_label.lower()} content available"
        )

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

    def _get_video_indicator(self, content_type: str) -> str:
        """Get the appropriate video indicator emoji for content type."""
        indicators = {
            "reel": "▶️",
            "video": "🎬",
            "tv": "📺",
        }
        return indicators.get(content_type, "🎬")

    def _get_content_indicator(self, content_type: str) -> str:
        """Get the appropriate indicator emoji for any content type."""
        indicators = {
            "reel": "▶️",
            "video": "🎬",
            "tv": "📺",
            "photo": "📷",
        }
        return indicators.get(content_type, "📷")

    def _get_content_type_label(self, content_type: str) -> str:
        """Get the human-readable label for content type."""
        labels = {
            "reel": "Reel",
            "video": "Video",
            "tv": "IGTV",
            "photo": "Post",
        }
        return labels.get(content_type, "Content")

    def _extract_clean_caption(self, caption: str) -> str:
        """Extract clean caption from Instagram description text."""
        if not caption:
            return ""

        import re

        # Pattern 1: "X likes, Y comments - username on [date]: \"caption\""
        pattern1 = (
            r"^[\d,]+\s+likes?,\s*[\d,]+\s+comments?\s*-\s*[^:]+:\s*"
            r'["""](.+?)["""].*$'
        )
        match = re.search(pattern1, caption, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()

        # Pattern 2: "username on Instagram: \"caption\""
        pattern2 = r'^.+?\s+on\s+Instagram:\s*["""](.+?)["""].*$'
        match = re.search(pattern2, caption, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()

        # Pattern 3: Look for quoted content anywhere in the text
        pattern3 = r'["""]([^"""]+)["""]'
        match = re.search(pattern3, caption)
        if match:
            quoted_text = match.group(1).strip()
            # Only return if it's substantial (more than just a few words)
            if len(quoted_text) > 20:
                return quoted_text

        # Pattern 4: If caption doesn't look like metadata, return as-is
        # Skip if it looks like "X likes, Y comments" format
        if not re.match(r"^[\d,]+\s+likes?,", caption, re.IGNORECASE):
            return caption.strip()

        # If no clean caption found, return empty string
        return ""

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
