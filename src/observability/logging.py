from __future__ import annotations

import logging
import os
from typing import Optional

import logfire


def _parse_log_level(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    level = value.strip().upper()
    mapping = {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }
    return mapping.get(level)


def _get_powertools_service_name() -> str:
    """Determine the service name that AWS Lambda Powertools Logger will use.

    Powertools Logger uses this priority for the logger name:
    1. POWERTOOLS_SERVICE_NAME environment variable
    2. AWS_LAMBDA_FUNCTION_NAME environment variable (set automatically in Lambda)
    3. Falls back to "service_undefined"
    """
    return os.getenv(
        "POWERTOOLS_SERVICE_NAME",
        os.getenv("AWS_LAMBDA_FUNCTION_NAME", "service_undefined"),
    )


def setup_logfire(*, enable_console_output: bool = False) -> None:
    """Configure Logfire and bridge stdlib logging.

    - Configures Logfire with service name, token and distributed tracing.
    - Optionally enables console output formatting (useful for API Gateway Lambdas).
    - Bridges the stdlib root logger to Logfire via LogfireLoggingHandler.
    - Bridges the AWS Lambda Powertools logger (using actual service name).
    - Honors LOG_LEVEL if set; otherwise does not modify the root logger level.
    - Dials down noisy third-party loggers to WARNING.
    """

    console_opts = None
    if enable_console_output:
        console_opts = logfire.ConsoleOptions(
            colors="always",
            include_timestamps=True,
            verbose=True,
        )

    logfire.configure(
        service_name=os.getenv("LOGFIRE_SERVICE_NAME", "unfurl-service"),
        token=os.getenv("LOGFIRE_TOKEN"),
        distributed_tracing=True,
        console=console_opts,
    )

    # Set desired log level on root logger FIRST so propagated logs are accepted
    desired_level = _parse_log_level(os.getenv("LOG_LEVEL"))
    if desired_level is not None:
        logging.getLogger().setLevel(desired_level)

    # Bridge stdlib logging to Logfire using the official handler name
    # per current Logfire docs: LogfireLoggingHandler
    try:
        handler_cls = getattr(
            logfire, "LogfireLoggingHandler"
        )  # type: ignore[attr-defined]
    except AttributeError:
        logging.getLogger(__name__).warning(
            "LogfireLoggingHandler unavailable; stdlib logs will not be bridged"
        )
    else:
        root_logger = logging.getLogger()
        if not any(isinstance(h, handler_cls) for h in root_logger.handlers):
            root_logger.addHandler(handler_cls())

        # Bridge AWS Lambda Powertools Logger using the ACTUAL service name.
        # Powertools Logger creates loggers named after the service, NOT
        # "aws_lambda_powertools". Service name comes from POWERTOOLS_SERVICE_NAME
        # or AWS_LAMBDA_FUNCTION_NAME.
        powertools_service = _get_powertools_service_name()
        powertools_logger = logging.getLogger(powertools_service)
        if not any(isinstance(h, handler_cls) for h in powertools_logger.handlers):
            powertools_logger.addHandler(handler_cls())

        # Also ensure the Powertools logger level allows logs through
        if desired_level is not None:
            powertools_logger.setLevel(desired_level)

    # Reduce noise from common libraries unless explicitly overridden elsewhere
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
