from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.attribution.semantics import (
    ATTRIBUTION_SEMANTICS_VERSION,
    AttributionEventKind,
    DeterministicReplayIdentity,
    classify_event_type,
    compute_effective_replay_window,
    normalize_lookback_days,
    session_scope_identity,
)


def test_b21_p1_event_taxonomy_classification_is_authoritative() -> None:
    assert classify_event_type("click") is AttributionEventKind.TOUCHPOINT
    assert classify_event_type("purchase") is AttributionEventKind.CONVERSION
    assert classify_event_type("unknown_custom_event") is AttributionEventKind.NON_ATTRIBUTION


def test_b21_p1_default_lookback_is_30_days() -> None:
    assert normalize_lookback_days(None) == 30
    with pytest.raises(ValueError):
        normalize_lookback_days(0)
    with pytest.raises(ValueError):
        normalize_lookback_days(366)


def test_b21_p1_effective_replay_window_clamps_to_lookback() -> None:
    window_start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    window_end = datetime(2025, 3, 1, tzinfo=timezone.utc)
    replay_start, replay_end = compute_effective_replay_window(
        window_start=window_start,
        window_end=window_end,
        lookback_days=30,
    )
    assert replay_start == datetime(2025, 1, 30, tzinfo=timezone.utc)
    assert replay_end == window_end


def test_b21_p1_job_model_version_encodes_replay_identity_dimensions() -> None:
    tenant_id = uuid4()
    replay = DeterministicReplayIdentity(
        tenant_id=tenant_id,
        model_version="1.0.0",
        taxonomy_version=ATTRIBUTION_SEMANTICS_VERSION,
        lookback_days=30,
        window_start=datetime(2025, 1, 1, tzinfo=timezone.utc),
        window_end=datetime(2025, 1, 2, tzinfo=timezone.utc),
        replay_window_start=datetime(2025, 1, 1, tzinfo=timezone.utc),
        replay_window_end=datetime(2025, 1, 2, tzinfo=timezone.utc),
        replay_anchor_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
        replay_event_created_ceiling=datetime(2025, 1, 2, tzinfo=timezone.utc),
        session_scope_identity=session_scope_identity(None),
    )
    token = replay.job_model_version()
    assert token.startswith("1.0.0::")
    assert "taxonomy=b2.1-p1-v1" in token
    assert "lookback_days=30" in token
    assert "session_scope=__all__" in token
    assert "window_start=2025-01-01T00:00:00+00:00" in token
    assert "window_end=2025-01-02T00:00:00+00:00" in token
