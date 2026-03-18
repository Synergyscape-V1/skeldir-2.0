"""B1.4-P1 corrective: session pepper window stitching behavior."""

from __future__ import annotations

from datetime import datetime, timezone

from app.ingestion.privacy_boundary import derive_transient_session_id


def _session_for(identity_payload: dict[str, object], now_utc: datetime) -> str:
    return derive_transient_session_id(
        identity_payload=identity_payload,
        source="test_suite",
        idempotency_key="b14-p1-midnight-proof",
        global_idempotency_hash="abc123",
        request_headers={"user-agent": "b14-session-window-agent"},
        now=now_utc,
    )


def test_b14_p1_time_windowed_pepper_stitches_cross_midnight(monkeypatch):
    monkeypatch.setattr(
        "app.ingestion.privacy_boundary.get_secret", lambda _: "b14-p1-test-pepper"
    )
    payload = {"email": "midnight-user@test.invalid", "ip_address": "203.0.113.80"}

    before_midnight = datetime(2026, 3, 18, 23, 59, tzinfo=timezone.utc)
    just_after_midnight = datetime(2026, 3, 19, 0, 1, tzinfo=timezone.utc)
    after_grace_window = datetime(2026, 3, 19, 3, 0, tzinfo=timezone.utc)

    session_before = _session_for(payload, before_midnight)
    session_after = _session_for(payload, just_after_midnight)
    session_after_grace = _session_for(payload, after_grace_window)

    assert session_after == session_before
    assert session_after_grace != session_before
