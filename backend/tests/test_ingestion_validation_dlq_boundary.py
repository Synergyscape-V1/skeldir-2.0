"""Regression tests for durable validation-failure routing."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.ingestion.event_service import EventIngestionService, ValidationError


@pytest.mark.asyncio
async def test_missing_event_timestamp_routes_to_dlq_before_error_escapes() -> None:
    """Early timestamp validation must not bypass the durable DLQ boundary."""

    service = EventIngestionService()
    service._route_to_dlq = AsyncMock()  # type: ignore[method-assign]
    tenant_id = uuid4()
    event_data = {
        "event_type": "page_view",
        "revenue_amount": "0.00",
        "currency": "USD",
        "session_id": str(uuid4()),
        "vendor": "r2_suite_unknown_vendor",
    }

    with pytest.raises(ValidationError, match="event_timestamp"):
        await service.ingest_event_with_decision(
            session=AsyncMock(),
            tenant_id=tenant_id,
            event_data=event_data,
            idempotency_key=f"r2_s3_{uuid4()}",
            source="r2_suite",
        )

    service._route_to_dlq.assert_awaited_once()
    routed = service._route_to_dlq.await_args.kwargs
    assert routed["tenant_id"] == tenant_id
    assert routed["event_data"] == event_data
    assert routed["error_type"] == "validation_error"
    assert "event_timestamp" in routed["error_message"]
