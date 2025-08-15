# Instagram URL Normalization and ID Extraction

This service uses a single utility module `src/unfurl_processor/url_utils.py` to ensure consistent handling of Instagram URLs across scrapers, handlers, and caching.

## Functions

- `extract_instagram_id(url: str) -> Optional[str]`
- `canonicalize_instagram_url(url: str) -> str`
- `validate_instagram_url(url: str) -> bool`
- `get_cache_key(url: str) -> str`
- `get_cache_ttl(content_type: str = "default") -> int`

## Canonicalization rules

- Enforce `www.instagram.com` host
- Remove query parameters and fragments
- Remove trailing slashes from paths (except root)

Example equivalents produce the same cache key:

```text
https://www.instagram.com/p/ABC123/
https://instagram.com/p/ABC123
https://www.instagram.com/p/ABC123/?utm_source=ig
https://www.instagram.com/p/ABC123#comment
=> https://www.instagram.com/p/ABC123
```

## Valid post URL patterns

- `https://www.instagram.com/p/<id>`
- `https://www.instagram.com/reel/<id>`
- `https://www.instagram.com/tv/<id>`

Non-post URLs (profiles, explore, etc.) are considered invalid for unfurling.

## Tests

See `tests/test_url_utils.py` for coverage of IDs, canonicalization, validation, and cache keys.


