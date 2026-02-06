"""
Structured logging configuration.

Uses JSON-formatted logs with correlation_id and tenant_id context.
"""
import json
import logging
import re
from typing import Any, Dict

from app.observability.context import (
    get_request_correlation_id,
    get_business_correlation_id,
    get_tenant_id,
)

_REDACTION_REPLACEMENT = "***"
_SENSITIVE_KEYS: tuple[str, ...] = (
    "DATABASE_URL",
    "DATABASE_DSN",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
    "AUTH_JWT_SECRET",
    "JWT_SECRET",
    "JWT_PRIVATE_KEY",
    "PLATFORM_TOKEN_ENCRYPTION_KEY",
    "LLM_PROVIDER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "STRIPE_API_KEY",
    "PAYPAL_CLIENT_SECRET",
    "SHOPIFY_WEBHOOK_SECRET",
    "WOOCOMMERCE_WEBHOOK_SECRET",
)
_SENSITIVE_SUFFIXES: tuple[str, ...] = (
    "_API_KEY",
    "_SECRET",
    "_TOKEN",
    "_PASSWORD",
)

_KEY_PATTERN = re.compile(
    r"(?i)(\b(?:"
    + "|".join(map(re.escape, _SENSITIVE_KEYS))
    + r"|[A-Z0-9_]+(?:"
    + "|".join(map(re.escape, _SENSITIVE_SUFFIXES))
    + r"))\b)(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|\S+)"
)
_DSN_PASSWORD_PATTERN = re.compile(
    r"(?i)\b(postgresql(?:\+\w+)?://[^:\s/]+:)([^@\s]+)(@)"
)
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+([A-Za-z0-9\-\._~\+/]+=*)")


def _redact_key_value(match: re.Match) -> str:
    key = match.group(1)
    sep = match.group(2)
    value = match.group(3)
    if value.startswith('"') and value.endswith('"'):
        return f'{key}{sep}"{_REDACTION_REPLACEMENT}"'
    if value.startswith("'") and value.endswith("'"):
        return f"{key}{sep}'{_REDACTION_REPLACEMENT}'"
    return f"{key}{sep}{_REDACTION_REPLACEMENT}"


def redact_text(text: str) -> str:
    if not text:
        return text
    redacted = _KEY_PATTERN.sub(_redact_key_value, text)
    redacted = _DSN_PASSWORD_PATTERN.sub(r"\1***\3", redacted)
    redacted = _BEARER_PATTERN.sub("Bearer ***", redacted)
    return redacted


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = redact_text(record.msg)
            else:
                record.msg = redact_text(str(record.msg))
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {
                        key: redact_text(str(value)) for key, value in record.args.items()
                    }
                elif isinstance(record.args, tuple):
                    record.args = tuple(redact_text(str(arg)) for arg in record.args)
                else:
                    record.args = redact_text(str(record.args))
        except Exception:
            # Redaction must never block logging.
            return True
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log: Dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
        }
        # Surface common Celery/task fields when provided via logger extra.
        for key in ("task_name", "task_id", "queue", "routing_key", "db_user"):
            if hasattr(record, key):
                log[key] = getattr(record, key)
        # Include correlation and tenant context if available
        cid_req = getattr(record, "correlation_id_request", None) or get_request_correlation_id()
        cid_bus = getattr(record, "correlation_id_business", None) or get_business_correlation_id()
        tid = getattr(record, "tenant_id", None) or get_tenant_id()
        if cid_req:
            log["correlation_id_request"] = cid_req
        if cid_bus:
            log["correlation_id_business"] = cid_bus
        if tid:
            log["tenant_id"] = tid
        if record.exc_info:
            log["exc_info"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(log)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), handlers=[handler], force=True)
