from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.workers.llm import _PROVIDER_BOUNDARY


@pytest.mark.asyncio
async def test_b16_p1_breaker_policy_trips_for_provider_transport_failures(monkeypatch) -> None:
    calls = {"count": 0}

    async def _breaker_failure(session, tenant_id, user_id, now):
        calls["count"] += 1

    monkeypatch.setattr(_PROVIDER_BOUNDARY, "_breaker_failure", _breaker_failure, raising=True)

    await _PROVIDER_BOUNDARY._apply_breaker_failure_accounting(
        session=None,  # type: ignore[arg-type]
        tenant_id=uuid4(),
        user_id=uuid4(),
        failed_at=datetime.now(timezone.utc),
        failure_reason="provider_timeout",
    )

    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_b16_p1_breaker_policy_is_request_local_for_validation_failures(monkeypatch) -> None:
    calls = {"count": 0}

    async def _breaker_failure(session, tenant_id, user_id, now):
        calls["count"] += 1

    monkeypatch.setattr(_PROVIDER_BOUNDARY, "_breaker_failure", _breaker_failure, raising=True)

    await _PROVIDER_BOUNDARY._apply_breaker_failure_accounting(
        session=None,  # type: ignore[arg-type]
        tenant_id=uuid4(),
        user_id=uuid4(),
        failed_at=datetime.now(timezone.utc),
        failure_reason="validation_numeric_mismatch",
    )

    assert calls["count"] == 0
    assert _PROVIDER_BOUNDARY._is_breaker_eligible_failure("validation_schema_mismatch") is False
    assert _PROVIDER_BOUNDARY._is_breaker_eligible_failure("provider_error:RuntimeError") is True
