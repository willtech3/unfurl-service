#!/usr/bin/env python3
"""
High-Performance Docker Lambda Entrypoint for Instagram Unfurl Service.

Optimized for fast cold starts and maximum concurrency with:
- uvloop for async performance
- Pre-warmed Playwright instances
- Connection pooling
- Intelligent caching
"""

import asyncio
import json
import os
from typing import Any, Dict

# Performance optimization: Use uvloop if available
try:
    import uvloop

    uvloop.install()
except ImportError:
    pass

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from .handler_async import AsyncUnfurlHandler

# Initialize observability tools
logger = Logger()
tracer = Tracer()

# Initialize metrics conditionally
try:
    metrics = Metrics(
        namespace=os.environ.get("POWERTOOLS_METRICS_NAMESPACE", "UnfurlService")
    )
    metrics_available = True
except Exception:
    metrics = None
    metrics_available = False

# Global handler instance for warm starts
handler_instance = None


def get_handler() -> AsyncUnfurlHandler:
    """Get or create the async handler instance."""
    global handler_instance
    if handler_instance is None:
        handler_instance = AsyncUnfurlHandler()
    return handler_instance


@tracer.capture_lambda_handler
async def async_lambda_handler(
    event: Dict[str, Any], context: LambdaContext
) -> Dict[str, Any]:
    """
    Async Lambda handler optimized for Docker container deployment.

    Args:
        event: Lambda event data
        context: Lambda context

    Returns:
        Response dictionary
    """
    handler = get_handler()
    return await handler.process_event(event, context)


def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Sync wrapper for async Lambda handler.

    Args:
        event: Lambda event data
        context: Lambda context

    Returns:
        Response dictionary
    """
    # Ensure we have an event loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        return loop.run_until_complete(async_lambda_handler(event, context))
    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}", exc_info=True)
        if metrics_available and metrics:
            metrics.add_metric(name="HandlerErrors", unit="Count", value=1)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }
    finally:
        # Emit metrics if available
        if metrics_available and metrics:
            try:
                metrics.flush_metrics()
            except Exception:
                pass


# Apply metrics decorator conditionally
if metrics_available and metrics:
    lambda_handler = metrics.log_metrics(lambda_handler)
