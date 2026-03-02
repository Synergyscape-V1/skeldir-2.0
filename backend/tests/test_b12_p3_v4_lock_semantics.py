from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import timedelta

from app.core import secrets as secrets_module
from app.testing.jwt_rs256 import TEST_PUBLIC_KEY_PEM


def _ring_payload(*, current_kid: str, key_material: str, all_kids: list[str] | None = None) -> str:
    kids = all_kids or [current_kid]
    return json.dumps(
        {
            "current_kid": current_kid,
            "keys": {kid: key_material for kid in kids},
        }
    )


def test_refresh_path_uses_transaction_scoped_advisory_try_lock(monkeypatch):
    old_ring = _ring_payload(current_kid="kid-old", key_material=TEST_PUBLIC_KEY_PEM)
    refreshed_ring = _ring_payload(
        current_kid="kid-new",
        key_material=TEST_PUBLIC_KEY_PEM,
        all_kids=["kid-old", "kid-new"],
    )
    executed_sql: list[str] = []

    class _FakeCursor:
        def execute(self, sql, params=None):
            del params
            executed_sql.append(str(sql))

        def fetchone(self):
            return (False,)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            return False

    class _FakeConn:
        def __init__(self):
            self.cursor_obj = _FakeCursor()

        def cursor(self):
            return self.cursor_obj

        def rollback(self):
            return None

        def commit(self):
            return None

    @contextmanager
    def _fake_conn():
        yield _FakeConn()

    monkeypatch.setattr(secrets_module, "_open_pg_conn", _fake_conn)
    monkeypatch.setattr(secrets_module, "_select_pg_jwt_cache_row", lambda _cursor: {"jwks_json": old_ring})
    monkeypatch.setattr(
        secrets_module,
        "_pg_cache_state_from_row",
        lambda _row: secrets_module.JwtVerificationPgCacheState(
            fetched_at=secrets_module.clock_module.utcnow() - timedelta(seconds=120),
            next_allowed_refresh_at=None,
            last_refresh_error_at=None,
            refresh_error_count=0,
            refresh_event_count=0,
        ),
    )
    monkeypatch.setattr(secrets_module, "_should_refresh_from_pg_state", lambda **_kwargs: True)
    monkeypatch.setattr(secrets_module, "_jwt_singleflight_mutation_enabled", lambda: False)
    monkeypatch.setattr(
        secrets_module,
        "_poll_for_unknown_kid_cache_update",
        lambda **_kwargs: secrets_module._parse_jwt_key_ring_payload(refreshed_ring, "postgres_cache"),
    )

    ring = secrets_module._resolve_verification_ring_via_postgres(reason="unknown_kid", kid="kid-new")
    assert ring.keys.get("kid-new")
    assert any("pg_try_advisory_xact_lock" in sql for sql in executed_sql)
    assert not any("pg_try_advisory_lock" in sql for sql in executed_sql)


def test_unknown_kid_lock_miss_polling_finds_cache_update_within_budget(monkeypatch):
    old_ring = secrets_module._parse_jwt_key_ring_payload(
        _ring_payload(current_kid="kid-old", key_material=TEST_PUBLIC_KEY_PEM),
        "postgres_cache",
    )
    new_ring = secrets_module._parse_jwt_key_ring_payload(
        _ring_payload(current_kid="kid-new", key_material=TEST_PUBLIC_KEY_PEM, all_kids=["kid-old", "kid-new"]),
        "postgres_cache",
    )
    baseline = old_ring.fetched_at
    snapshots = iter(
        [
            (old_ring, baseline, _ring_payload(current_kid="kid-old", key_material=TEST_PUBLIC_KEY_PEM)),
            (
                new_ring,
                baseline + timedelta(seconds=1),
                _ring_payload(current_kid="kid-new", key_material=TEST_PUBLIC_KEY_PEM, all_kids=["kid-old", "kid-new"]),
            ),
        ]
    )
    sleeps: list[float] = []

    monkeypatch.setenv("SKELDIR_JWT_UNKNOWN_KID_LOCK_MISS_BUDGET_MS", "120")
    monkeypatch.setenv("SKELDIR_JWT_UNKNOWN_KID_POLL_INITIAL_MS", "2")
    monkeypatch.setenv("SKELDIR_JWT_UNKNOWN_KID_POLL_CAP_MS", "10")
    monkeypatch.setattr(secrets_module, "_pg_cached_ring_snapshot", lambda: next(snapshots))
    monkeypatch.setattr(secrets_module.time, "sleep", lambda seconds: sleeps.append(seconds))

    found = secrets_module._poll_for_unknown_kid_cache_update(kid="kid-new", baseline_fetched_at=baseline)
    assert found is not None
    assert "kid-new" in found.keys
    assert sleeps


def test_unknown_kid_lock_miss_polling_exhausts_budget_and_returns_none(monkeypatch):
    baseline = secrets_module.clock_module.utcnow()
    ring = secrets_module._parse_jwt_key_ring_payload(
        _ring_payload(current_kid="kid-old", key_material=TEST_PUBLIC_KEY_PEM),
        "postgres_cache",
    )
    monotonic_ticks = {"value": 0.0}

    def _fake_monotonic():
        monotonic_ticks["value"] += 0.02
        return monotonic_ticks["value"]

    monkeypatch.setenv("SKELDIR_JWT_UNKNOWN_KID_LOCK_MISS_BUDGET_MS", "50")
    monkeypatch.setenv("SKELDIR_JWT_UNKNOWN_KID_POLL_INITIAL_MS", "1")
    monkeypatch.setenv("SKELDIR_JWT_UNKNOWN_KID_POLL_CAP_MS", "2")
    monkeypatch.setattr(
        secrets_module,
        "_pg_cached_ring_snapshot",
        lambda: (ring, baseline, _ring_payload(current_kid="kid-old", key_material=TEST_PUBLIC_KEY_PEM)),
    )
    monkeypatch.setattr(secrets_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(secrets_module.time, "monotonic", _fake_monotonic)

    found = secrets_module._poll_for_unknown_kid_cache_update(kid="kid-missing", baseline_fetched_at=baseline)
    assert found is None
