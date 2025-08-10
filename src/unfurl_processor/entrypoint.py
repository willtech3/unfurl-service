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

import logfire
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from opentelemetry import context as otel_context
from opentelemetry.propagate import extract

from .handler_async import AsyncUnfurlHandler

# Initialize observability tools
logger = Logger()

# Configure Logfire as the consolidated backend
logfire.configure(
    service_name=os.getenv("LOGFIRE_SERVICE_NAME", "unfurl-service"),
    environment=os.getenv("LOGFIRE_ENV", os.getenv("ENV", "dev")),
    token=os.getenv("LOGFIRE_TOKEN"),
)

# Powertools metrics/tracer removed; using Logfire metrics and spans
metrics_available = False

# Global handler instance for warm starts
handler_instance = None


def get_handler() -> AsyncUnfurlHandler:
    """Get or create the async handler instance."""
    global handler_instance
    if handler_instance is None:
        handler_instance = AsyncUnfurlHandler()
    return handler_instance


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

    # Extract W3C trace context from SNS message attributes if present
    def _extract_sns_carrier(evt: Dict[str, Any]) -> Dict[str, str]:
        try:
            attrs = evt["Records"][0]["Sns"].get("MessageAttributes", {})
            return {k: v.get("Value") or v.get("StringValue") for k, v in attrs.items()}
        except Exception:
            return {}

    carrier = _extract_sns_carrier(event)
    token = None
    if carrier:
        ctx = extract(carrier)
        token = otel_context.attach(ctx)

    try:
        handler = get_handler()
        return await handler.process_event(event, context)
    finally:
        if token is not None:
            otel_context.detach(token)


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
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


# Wrap handler with Logfire's AWS Lambda instrumentation (in-place)
logfire.instrument_aws_lambda(lambda_handler)


# No metrics decorator; metrics are handled by Logfire directly
