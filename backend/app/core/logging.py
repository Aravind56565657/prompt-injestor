import logging
import os
from typing import Any

import structlog

from app.core.config import get_settings

settings = get_settings()

SECRET_FIELDS = {
    "password",
    "passwd",
    "secret",
    "token",
    "auth_token",
    "api_key",
    "apikey",
    "authorization",
    "x-api-key",
    "x-auth-token",
    "access_token",
    "refresh_token",
    "client_secret",
    "private_key",
}


def _redact_event_dict(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Redact known sensitive keys and leaked-looking values from logs."""
    redacted: dict[str, Any] = {}
    for key, value in event_dict.items():
        lowered = key.lower()
        if any(s in lowered for s in SECRET_FIELDS):
            redacted[key] = "[REDACTED]"
        elif isinstance(value, str):
            redacted[key] = redact_secret_string(value)
        else:
            redacted[key] = value
    return redacted


_DETECTION_PATTERNS = (
    ("api", "key"),
    ("bearer ", "token"),
    ("authorization", "token"),
    ("x-api-key", "token"),
)


def looks_like_secret(value: str) -> bool:
    lowered = value.lower()
    if any(marker in lowered for marker in ("api-key", "apikey", "api_key")):
        return True
    if lowered.startswith("bearer ") and len(value) > 20:
        return True
    if "sk-" in lowered and len(value) > 20:
        return True
    if "-----BEGIN" in value:
        return True
    return False


def redact_secret_string(value: str) -> str:
    if looks_like_secret(value):
        if len(value) > 16:
            return value[:6] + "..." + value[-4:] + " [REDACTED]"
        return "[REDACTED]"
    return value


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(message)s",
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact_event_dict,
            (
                structlog.processors.JSONRenderer()
                if settings.log_format == "json"
                else structlog.dev.ConsoleRenderer()
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    return structlog.get_logger(name)