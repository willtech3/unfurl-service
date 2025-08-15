"""Tests for consolidated Instagram URL utilities."""

from src.unfurl_processor.url_utils import (
    canonicalize_instagram_url,
    extract_instagram_id,
    get_cache_key,
    get_cache_ttl,
    is_instagram_video_url,
    validate_instagram_url,
)


class TestExtractInstagramId:
    """Tests for extract_instagram_id function."""

    def test_extract_post_id(self):
        """Test extracting ID from regular post URL."""
        url = "https://www.instagram.com/p/ABC123/"
        assert extract_instagram_id(url) == "ABC123"

    def test_extract_reel_id(self):
        """Test extracting ID from reel URL."""
        url = "https://instagram.com/reel/XYZ456/"
        assert extract_instagram_id(url) == "XYZ456"

    def test_extract_tv_id(self):
        """Test extracting ID from TV/IGTV URL."""
        url = "https://www.instagram.com/tv/DEF789/"
        assert extract_instagram_id(url) == "DEF789"

    def test_extract_id_no_trailing_slash(self):
        """Test extraction without trailing slash."""
        url = "https://www.instagram.com/p/ABC123"
        assert extract_instagram_id(url) == "ABC123"

    def test_extract_id_with_query_params(self):
        """Test extraction with query parameters."""
        url = "https://www.instagram.com/p/ABC123/?utm_source=ig_web"
        assert extract_instagram_id(url) == "ABC123"

    def test_extract_id_invalid_url(self):
        """Test extraction from invalid URL."""
        assert extract_instagram_id("not-a-url") is None
        assert extract_instagram_id("https://example.com/p/ABC123/") is None

    def test_extract_id_profile_url(self):
        """Test extraction from profile URL (should return None)."""
        url = "https://www.instagram.com/username/"
        assert extract_instagram_id(url) is None


class TestCanonicalizeInstagramUrl:
    """Tests for canonicalize_instagram_url function."""

    def test_canonicalize_basic(self):
        """Test basic URL canonicalization."""
        url = "https://www.instagram.com/p/ABC123/"
        expected = "https://www.instagram.com/p/ABC123"
        assert canonicalize_instagram_url(url) == expected

    def test_canonicalize_removes_query(self):
        """Test removal of query parameters."""
        url = "https://www.instagram.com/p/ABC123/?utm_source=ig_web&foo=bar"
        expected = "https://www.instagram.com/p/ABC123"
        assert canonicalize_instagram_url(url) == expected

    def test_canonicalize_removes_fragment(self):
        """Test removal of URL fragment."""
        url = "https://www.instagram.com/p/ABC123/#comment-123"
        expected = "https://www.instagram.com/p/ABC123"
        assert canonicalize_instagram_url(url) == expected

    def test_canonicalize_adds_www(self):
        """Test adding www prefix for consistency."""
        url = "https://instagram.com/p/ABC123/"
        expected = "https://www.instagram.com/p/ABC123"
        assert canonicalize_instagram_url(url) == expected

    def test_canonicalize_preserves_path(self):
        """Test preservation of path structure."""
        url = "https://www.instagram.com/reel/XYZ456/"
        expected = "https://www.instagram.com/reel/XYZ456"
        assert canonicalize_instagram_url(url) == expected

    def test_canonicalize_handles_http(self):
        """Test handling of HTTP URLs."""
        url = "http://www.instagram.com/p/ABC123/"
        expected = "http://www.instagram.com/p/ABC123"
        assert canonicalize_instagram_url(url) == expected

    def test_canonicalize_invalid_url(self):
        """Test canonicalization of invalid URL returns original."""
        url = "not-a-url"
        assert canonicalize_instagram_url(url) == url


class TestValidateInstagramUrl:
    """Tests for validate_instagram_url function."""

    def test_validate_post_url(self):
        """Test validation of post URL."""
        assert validate_instagram_url("https://www.instagram.com/p/ABC123/")
        assert validate_instagram_url("https://instagram.com/p/ABC123")

    def test_validate_reel_url(self):
        """Test validation of reel URL."""
        assert validate_instagram_url("https://www.instagram.com/reel/XYZ456/")

    def test_validate_tv_url(self):
        """Test validation of TV/IGTV URL."""
        assert validate_instagram_url("https://www.instagram.com/tv/DEF789/")

    def test_validate_invalid_domain(self):
        """Test rejection of non-Instagram domains."""
        assert not validate_instagram_url("https://facebook.com/p/ABC123/")
        assert not validate_instagram_url("https://example.com/p/ABC123/")

    def test_validate_profile_url(self):
        """Test rejection of profile URLs."""
        assert not validate_instagram_url("https://www.instagram.com/username/")
        assert not validate_instagram_url("https://instagram.com/explore/")

    def test_validate_invalid_url(self):
        """Test rejection of invalid URLs."""
        assert not validate_instagram_url("not-a-url")
        assert not validate_instagram_url("")
        assert not validate_instagram_url(None)


class TestIsInstagramVideoUrl:
    """Tests for is_instagram_video_url function."""

    def test_reel_is_video(self):
        """Test that reel URLs are identified as videos."""
        assert is_instagram_video_url("https://www.instagram.com/reel/ABC123/")

    def test_tv_is_video(self):
        """Test that TV/IGTV URLs are identified as videos."""
        assert is_instagram_video_url("https://www.instagram.com/tv/ABC123/")

    def test_post_not_video(self):
        """Test that regular post URLs are not identified as videos."""
        assert not is_instagram_video_url("https://www.instagram.com/p/ABC123/")

    def test_empty_url(self):
        """Test handling of empty URL."""
        assert not is_instagram_video_url("")
        assert not is_instagram_video_url(None)


class TestGetCacheKey:
    """Tests for get_cache_key function."""

    def test_cache_key_consistency(self):
        """Test that similar URLs produce same cache key."""
        urls = [
            "https://www.instagram.com/p/ABC123/",
            "https://instagram.com/p/ABC123",
            "https://www.instagram.com/p/ABC123/?utm_source=ig",
            "https://www.instagram.com/p/ABC123#comment",
        ]

        keys = [get_cache_key(url) for url in urls]
        # All should produce the same key
        assert len(set(keys)) == 1
        assert keys[0] == "https://www.instagram.com/p/ABC123"

    def test_cache_key_different_posts(self):
        """Test that different posts have different keys."""
        key1 = get_cache_key("https://www.instagram.com/p/ABC123/")
        key2 = get_cache_key("https://www.instagram.com/p/XYZ789/")
        assert key1 != key2


class TestGetCacheTtl:
    """Tests for get_cache_ttl function."""

    def test_default_ttl(self):
        """Test default TTL."""
        assert get_cache_ttl() == 86400  # 24 hours
        assert get_cache_ttl("default") == 86400

    def test_video_ttl(self):
        """Test video content TTL."""
        assert get_cache_ttl("video") == 86400

    def test_photo_ttl(self):
        """Test photo content TTL."""
        assert get_cache_ttl("photo") == 86400

    def test_unknown_type_ttl(self):
        """Test unknown content type returns default."""
        assert get_cache_ttl("unknown") == 86400
