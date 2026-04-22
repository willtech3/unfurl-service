"""Centralized Logfire metric instruments.

Creating instruments once here avoids duplicate "instrument already created"
warnings that occur when instruments are instantiated across multiple modules.
Import and use these instruments wherever metrics are recorded.

Observability must fail open: if Logfire is not importable or instrument
creation fails, we substitute no-op instruments so that call sites like
`processing_errors.add(1)` remain safe without guards everywhere.
"""

from __future__ import annotations


class _NoOpInstrument:
    """Stand-in for a Logfire metric instrument when creation fails."""

    def add(self, *_args, **_kwargs) -> None:
        return None

    def record(self, *_args, **_kwargs) -> None:
        return None


def _counter(name: str):
    try:
        import logfire

        return logfire.metric_counter(name)
    except Exception:
        return _NoOpInstrument()


def _histogram(name: str, *, unit: str):
    try:
        import logfire

        return logfire.metric_histogram(name, unit=unit)
    except Exception:
        return _NoOpInstrument()


# Generic service-level metrics
links_processed = _counter("links_processed")
unfurls_generated = _counter("unfurls_generated")
processing_errors = _counter("processing_errors")

total_processing_time_ms = _histogram("total_processing_time_ms", unit="ms")

# Instagram fetch/scraping metrics
instagram_fetch_time_ms = _histogram("instagram_fetch_time_ms", unit="ms")
instagram_fetch_success = _counter("instagram_fetch_success")
instagram_fetch_errors = _counter("instagram_fetch_errors")
scraping_method = _counter("scraping_method")

# Slack delivery metrics
slack_unfurl_success = _counter("slack_unfurl_success")
slack_unfurl_errors = _counter("slack_unfurl_errors")
slack_api_errors = _counter("slack_api_errors")

# ScraperManager metrics (minimal set)
scraper_success = _counter("scraper_success")
scraper_failure = _counter("scraper_failure")
scraper_exception = _counter("scraper_exception")
scraper_response_time_ms = _histogram("scraper_response_time_ms", unit="ms")
all_scrapers_failed = _counter("all_scrapers_failed")
