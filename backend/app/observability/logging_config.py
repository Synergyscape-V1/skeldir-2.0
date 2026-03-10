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
from app.security.secret_boundary import redact_text_fragments, sanitize_for_transport

_SENSITIVE_TEMPLATE_HINT = re.compile(
    r"(?i)(access_token|refresh_token|authorization_code|code_verifier|client_secret|bearer|api[_-]?key|_secret|_token|password|jwt|authorization)"
)


def redact_text(text: str) -> str:
    return redact_text_fragments(text)


def _sanitize_log_arg(value: Any, *, force_mask_strings: bool) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if force_mask_strings:
            return "***"
        return sanitize_for_transport(value)
    if isinstance(value, tuple):
        return tuple(_sanitize_log_arg(item, force_mask_strings=force_mask_strings) for item in value)
    if isinstance(value, list):
        return [_sanitize_log_arg(item, force_mask_strings=force_mask_strings) for item in value]
    if isinstance(value, set):
        return [_sanitize_log_arg(item, force_mask_strings=force_mask_strings) for item in value]
    if isinstance(value, dict):
        return {k: _sanitize_log_arg(v, force_mask_strings=force_mask_strings) for k, v in value.items()}
    return sanitize_for_transport(value)


def _sanitize_record_args(args: Any, *, force_mask_strings: bool) -> Any:
    if not args:
        return args
    if isinstance(args, tuple):
        return tuple(_sanitize_log_arg(item, force_mask_strings=force_mask_strings) for item in args)
    return _sanitize_log_arg(args, force_mask_strings=force_mask_strings)


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                # Preserve %-template shape for getMessage(); sanitize final text after interpolation.
                if not record.args:
                    record.msg = sanitize_for_transport(record.msg)
            else:
                record.msg = sanitize_for_transport(record.msg)
            if record.args:
                force_mask_strings = isinstance(record.msg, str) and bool(_SENSITIVE_TEMPLATE_HINT.search(record.msg))
                record.args = _sanitize_record_args(record.args, force_mask_strings=force_mask_strings)
        except Exception:
            # Redaction must never block logging.
            return True
        return True


class JsonFormatter(logging.Formatter):
    @staticmethod
    def _safe_message(record: logging.LogRecord) -> str:
        try:
            return redact_text_fragments(record.getMessage())
        except Exception:
            fallback = sanitize_for_transport({"msg": record.msg, "args": "[omitted]"})
            return redact_text_fragments(str(fallback))

    def format(self, record: logging.LogRecord) -> str:
        log: Dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": self._safe_message(record),
        }
        # Surface common Celery/task fields when provided via logger extra.
        for key in ("task_name", "task_id", "queue", "routing_key", "db_user"):
            if hasattr(record, key):
                log[key] = sanitize_for_transport(getattr(record, key))
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
            log["exc_info"] = redact_text_fragments(self.formatException(record.exc_info))
        return json.dumps(sanitize_for_transport(log), default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), handlers=[handler], force=True)
