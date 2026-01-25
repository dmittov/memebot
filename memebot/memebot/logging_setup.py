"""Centralized logging configuration.

This module is the single point of configuration for logging.
All other modules should use standard `logging.getLogger(__name__)`.

To switch cloud provider, modify this module only.
"""

import logging
import os


def setup_logging() -> None:
    """Configure logging based on environment.

    Set LOG_PROVIDER environment variable to choose the logging backend:
    - "gcp" (default): Use Google Cloud Logging with structured logs
    - "standard": Use standard Python logging to stdout

    LOG_LEVEL controls the log level (default: INFO).
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)

    provider = os.getenv("LOG_PROVIDER", "gcp").lower()

    if provider == "gcp":
        _setup_gcp_logging(level)
    else:
        _setup_standard_logging(level)


def _setup_gcp_logging(level: int) -> None:
    """Configure Google Cloud Logging integration.

    This enables:
    - Structured JSON logs
    - Automatic severity mapping (INFO/WARNING/ERROR)
    - python_logger field for filtering by module name
    - Request correlation in App Engine
    """
    try:
        import google.cloud.logging

        client = google.cloud.logging.Client()
        client.setup_logging(log_level=level)
    except ImportError:
        # Fallback if google-cloud-logging is not installed
        _setup_standard_logging(level)
        logging.warning(
            "google-cloud-logging not installed, falling back to standard logging"
        )


def _setup_standard_logging(level: int) -> None:
    """Configure standard Python logging.

    Used for local development or non-GCP environments.
    """
    logging.basicConfig(
        level=level,
        format="%(levelname)s:%(name)s:%(message)s",
    )
