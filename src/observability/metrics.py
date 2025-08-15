"""Centralized Logfire metric instruments.

Creating instruments once here avoids duplicate "instrument already created"
warnings that occur when instruments are instantiated across multiple modules.
Import and use these instruments wherever metrics are recorded.
"""

from __future__ import annotations

import logfire

# Generic service-level metrics
links_processed = logfire.metric_counter("links_processed")
unfurls_generated = logfire.metric_counter("unfurls_generated")
processing_errors = logfire.metric_counter("processing_errors")

total_processing_time_ms = logfire.metric_histogram(
    "total_processing_time_ms", unit="ms"
)

# Instagram fetch/scraping metrics
instagram_fetch_time_ms = logfire.metric_histogram("instagram_fetch_time_ms", unit="ms")
instagram_fetch_success = logfire.metric_counter("instagram_fetch_success")
instagram_fetch_errors = logfire.metric_counter("instagram_fetch_errors")
scraping_method = logfire.metric_counter("scraping_method")

# Slack delivery metrics
slack_unfurl_success = logfire.metric_counter("slack_unfurl_success")
slack_unfurl_errors = logfire.metric_counter("slack_unfurl_errors")
slack_api_errors = logfire.metric_counter("slack_api_errors")

# ScraperManager metrics (minimal set)
scraper_success = logfire.metric_counter("scraper_success")
scraper_failure = logfire.metric_counter("scraper_failure")
scraper_exception = logfire.metric_counter("scraper_exception")
scraper_response_time_ms = logfire.metric_histogram(
    "scraper_response_time_ms", unit="ms"
)
all_scrapers_failed = logfire.metric_counter("all_scrapers_failed")
