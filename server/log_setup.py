"""structlog configuration. Application code logs through structlog, not print."""

import logging

import structlog

from server.config import Settings
from server.pii import PiiRedactor


def configure_logging(settings: Settings, redactor: PiiRedactor) -> None:
    """Install structlog and the PII processor. Safe to call again from tests."""
    level = getattr(logging, settings.log_level)
    logging.basicConfig(format="%(message)s", level=level, force=True)
    renderer: structlog.types.Processor
    if settings.log_json:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redactor.processor,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )
    redactor.warn_if_ephemeral()
