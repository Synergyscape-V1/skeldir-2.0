from __future__ import annotations

import io
import logging

from app.observability.logging_config import JsonFormatter, RedactionFilter, redact_text


def test_b11_p6_redact_text_masks_secret_material():
    marker = "b11_p6_secret_marker_123"
    payload = (
        f"LLM_PROVIDER_API_KEY={marker} "
        f"Authorization: Bearer {marker} "
        "postgresql://app_user:supersecret@127.0.0.1:5432/skeldir"
    )
    redacted = redact_text(payload)
    assert marker not in redacted
    assert "LLM_PROVIDER_API_KEY=***" in redacted
    assert "Bearer ***" in redacted
    assert "postgresql://app_user:***@127.0.0.1:5432/skeldir" in redacted


def test_b11_p6_redaction_filter_masks_exception_path():
    marker = "b11_p6_error_secret_marker_456"
    logger = logging.getLogger("b11_p6_redaction_integrity")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers = []
    logger.filters = []

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())
    logger.addHandler(handler)

    try:
        raise RuntimeError(f"AUTH_JWT_SECRET={marker}")
    except RuntimeError:
        logger.exception("failure Authorization: Bearer %s", marker)
    rendered = stream.getvalue()
    assert marker not in rendered
    assert "Bearer ***" in rendered

    record = logging.LogRecord(
        name="b11_p6_redaction_integrity",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=f"PLATFORM_TOKEN_ENCRYPTION_KEY={marker}",
        args=(),
        exc_info=None,
    )
    RedactionFilter().filter(record)
    assert marker not in str(record.msg)
    assert "PLATFORM_TOKEN_ENCRYPTION_KEY=***" in str(record.msg)
