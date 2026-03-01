from __future__ import annotations

import json
import multiprocessing
import os
import time
from uuid import uuid4

import jwt
import pytest
from jwt import InvalidTokenError

from app.core.config import settings
from app.core.secrets import (
    get_database_url,
    get_jwt_verification_pg_cache_state_for_testing,
    reset_crypto_secret_caches_for_testing,
    reset_jwt_verification_pg_cache_for_testing,
    seed_jwt_verification_pg_cache_for_testing,
)
from app.security.auth import _decode_token
from app.testing.jwt_rs256 import TEST_PRIVATE_KEY_PEM, TEST_PUBLIC_KEY_PEM, _generate_test_keypair

_ALT_PRIVATE_KEY_PEM, _ALT_PUBLIC_KEY_PEM = _generate_test_keypair()


def _ring_payload(*, current_kid: str, key_material: str, all_kids: list[str] | None = None) -> str:
    kids = all_kids or [current_kid]
    return json.dumps(
        {
            "current_kid": current_kid,
            "keys": {kid: key_material for kid in kids},
        }
    )


def _payload() -> dict[str, object]:
    now = int(time.time())
    return {
        "tenant_id": str(uuid4()),
        "sub": str(uuid4()),
        "user_id": str(uuid4()),
        "iss": settings.AUTH_JWT_ISSUER,
        "aud": settings.AUTH_JWT_AUDIENCE,
        "iat": now,
        "exp": now + 120,
    }


def _spawn_worker_unknown_kid(
    barrier,
    token: str,
    old_public_ring: str,
    rotated_public_ring: str,
    db_url: str,
    disable_singleflight: bool,
    result_queue,
) -> None:
    os.environ["SKELDIR_JWT_UNKNOWN_KID_REFRESH_DEBOUNCE_SECONDS"] = "0"
    os.environ["SKELDIR_JWT_REFRESH_MIN_FLOOR_SECONDS"] = "30"
    os.environ["SKELDIR_JWT_REFRESH_JITTER_SECONDS"] = "0"
    if disable_singleflight:
        os.environ["SKELDIR_B12_P3_DISABLE_PG_SINGLEFLIGHT"] = "1"
    else:
        os.environ.pop("SKELDIR_B12_P3_DISABLE_PG_SINGLEFLIGHT", None)

    from app.core.config import settings as local_settings
    from app.core import secrets as secrets_module
    from app.core.secrets import reset_crypto_secret_caches_for_testing
    from app.security.auth import _decode_token as local_decode

    local_settings.AUTH_JWT_ALGORITHM = "RS256"
    local_settings.AUTH_JWT_ISSUER = "https://issuer.skeldir.test"
    local_settings.AUTH_JWT_AUDIENCE = "skeldir-api"
    local_settings.DATABASE_URL = db_url
    local_settings.AUTH_JWT_PUBLIC_KEY_RING = old_public_ring

    def _refreshing_fetch(key: str) -> str | None:
        if key == "AUTH_JWT_PUBLIC_KEY_RING":
            time.sleep(0.2)
            return rotated_public_ring
        return getattr(local_settings, key, None)

    secrets_module._read_secret_source_of_truth_value = _refreshing_fetch
    reset_crypto_secret_caches_for_testing()

    try:
        barrier.wait(timeout=20)
        local_decode(token)
        result_queue.put("ok")
    except InvalidTokenError:
        result_queue.put("invalid")
    except Exception as exc:  # pragma: no cover - explicit process failure reporting
        result_queue.put(f"err:{type(exc).__name__}:{exc}")


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    monkeypatch.setenv("SKELDIR_JWT_UNKNOWN_KID_REFRESH_DEBOUNCE_SECONDS", "0")
    monkeypatch.setenv("SKELDIR_JWT_KEY_RING_MAX_STALENESS_SECONDS", "60")
    monkeypatch.setenv("SKELDIR_JWT_REFRESH_MIN_FLOOR_SECONDS", "5")
    monkeypatch.setenv("SKELDIR_JWT_REFRESH_JITTER_SECONDS", "1")
    monkeypatch.setenv("SKELDIR_JWT_REFRESH_BACKOFF_BASE_SECONDS", "2")
    monkeypatch.setenv("SKELDIR_JWT_REFRESH_BACKOFF_MAX_SECONDS", "30")
    monkeypatch.delenv("SKELDIR_B12_P3_DISABLE_PG_SINGLEFLIGHT", raising=False)
    monkeypatch.setattr(settings, "AUTH_JWT_ALGORITHM", "RS256")
    monkeypatch.setattr(settings, "AUTH_JWT_ISSUER", "https://issuer.skeldir.test")
    monkeypatch.setattr(settings, "AUTH_JWT_AUDIENCE", "skeldir-api")
    monkeypatch.setattr(
        settings,
        "AUTH_JWT_SECRET",
        _ring_payload(current_kid="kid-old", key_material=TEST_PRIVATE_KEY_PEM),
    )
    monkeypatch.setattr(
        settings,
        "AUTH_JWT_PUBLIC_KEY_RING",
        _ring_payload(current_kid="kid-old", key_material=TEST_PUBLIC_KEY_PEM),
    )
    reset_crypto_secret_caches_for_testing()
    reset_jwt_verification_pg_cache_for_testing()
    try:
        seed_jwt_verification_pg_cache_for_testing(
            raw_ring=_ring_payload(current_kid="kid-old", key_material=TEST_PUBLIC_KEY_PEM)
        )
        reset_jwt_verification_pg_cache_for_testing()
    except Exception as exc:
        pytest.skip(f"Postgres jwt_verification_cache table not available in this environment: {exc}")
    yield
    reset_crypto_secret_caches_for_testing()
    reset_jwt_verification_pg_cache_for_testing()


def test_unknown_kid_refresh_is_fleet_singleflight_with_spawn_processes(monkeypatch):
    old_public_ring = _ring_payload(current_kid="kid-old", key_material=TEST_PUBLIC_KEY_PEM)
    rotated_public_ring = _ring_payload(
        current_kid="kid-new",
        key_material=TEST_PUBLIC_KEY_PEM,
        all_kids=["kid-old", "kid-new"],
    )
    monkeypatch.setattr(settings, "AUTH_JWT_PUBLIC_KEY_RING", old_public_ring)
    seed_jwt_verification_pg_cache_for_testing(raw_ring=old_public_ring)

    token = jwt.encode(_payload(), TEST_PRIVATE_KEY_PEM, algorithm="RS256", headers={"kid": "kid-new"})
    ctx = multiprocessing.get_context("spawn")
    workers = 8
    barrier = ctx.Barrier(workers)
    queue = ctx.Queue()
    db_url = get_database_url()
    processes = [
        ctx.Process(
            target=_spawn_worker_unknown_kid,
            args=(barrier, token, old_public_ring, rotated_public_ring, db_url, False, queue),
        )
        for _ in range(workers)
    ]
    for proc in processes:
        proc.start()
    for proc in processes:
        proc.join(timeout=40)
        assert proc.exitcode == 0

    outcomes = [queue.get(timeout=5) for _ in range(workers)]
    assert not [item for item in outcomes if str(item).startswith("err:")]

    state = get_jwt_verification_pg_cache_state_for_testing()
    assert state.refresh_event_count <= 1


def test_refresh_floor_blocks_repeated_unknown_kid_refresh(monkeypatch):
    from app.core import secrets as secrets_module

    monkeypatch.setenv("SKELDIR_JWT_REFRESH_MIN_FLOOR_SECONDS", "30")
    old_public_ring = _ring_payload(current_kid="kid-old", key_material=_ALT_PUBLIC_KEY_PEM)
    monkeypatch.setattr(settings, "AUTH_JWT_PUBLIC_KEY_RING", old_public_ring)
    seed_jwt_verification_pg_cache_for_testing(raw_ring=old_public_ring)

    def _same_ring_fetch(key: str) -> str | None:
        if key == "AUTH_JWT_PUBLIC_KEY_RING":
            return old_public_ring
        return getattr(settings, key, None)

    monkeypatch.setattr(secrets_module, "_read_secret_source_of_truth_value", _same_ring_fetch)
    token = jwt.encode(_payload(), TEST_PRIVATE_KEY_PEM, algorithm="RS256", headers={"kid": "kid-missing"})

    with pytest.raises(InvalidTokenError):
        _decode_token(token)
    state_after_first = get_jwt_verification_pg_cache_state_for_testing()
    assert state_after_first.refresh_event_count == 1

    with pytest.raises(InvalidTokenError):
        _decode_token(token)
    state_after_second = get_jwt_verification_pg_cache_state_for_testing()
    assert state_after_second.refresh_event_count == 1


def test_refresh_backoff_applies_after_failure(monkeypatch):
    from app.core import secrets as secrets_module

    monkeypatch.setenv("SKELDIR_JWT_REFRESH_MIN_FLOOR_SECONDS", "0")
    monkeypatch.setenv("SKELDIR_JWT_REFRESH_JITTER_SECONDS", "0")
    monkeypatch.setenv("SKELDIR_JWT_REFRESH_BACKOFF_BASE_SECONDS", "5")
    monkeypatch.setenv("SKELDIR_JWT_REFRESH_BACKOFF_MAX_SECONDS", "30")

    old_public_ring = _ring_payload(current_kid="kid-old", key_material=_ALT_PUBLIC_KEY_PEM)
    monkeypatch.setattr(settings, "AUTH_JWT_PUBLIC_KEY_RING", old_public_ring)
    seed_jwt_verification_pg_cache_for_testing(raw_ring=old_public_ring)

    def _boom(key: str) -> str | None:
        if key == "AUTH_JWT_PUBLIC_KEY_RING":
            raise RuntimeError("simulated refresh failure")
        return getattr(settings, key, None)

    monkeypatch.setattr(secrets_module, "_read_secret_source_of_truth_value", _boom)
    token = jwt.encode(_payload(), TEST_PRIVATE_KEY_PEM, algorithm="RS256", headers={"kid": "kid-missing"})

    with pytest.raises(InvalidTokenError):
        _decode_token(token)
    state_after_first = get_jwt_verification_pg_cache_state_for_testing()
    assert state_after_first.refresh_error_count >= 1
    assert state_after_first.next_allowed_refresh_at is not None

    with pytest.raises(InvalidTokenError):
        _decode_token(token)
    state_after_second = get_jwt_verification_pg_cache_state_for_testing()
    assert state_after_second.refresh_event_count == state_after_first.refresh_event_count


def test_refresh_jitter_changes_next_allowed_schedule(monkeypatch):
    from app.core import secrets as secrets_module

    monkeypatch.setenv("SKELDIR_B12_P3_DISABLE_PG_SINGLEFLIGHT", "1")
    monkeypatch.setenv("SKELDIR_JWT_REFRESH_MIN_FLOOR_SECONDS", "0")
    monkeypatch.setenv("SKELDIR_JWT_REFRESH_JITTER_SECONDS", "5")
    old_public_ring = _ring_payload(current_kid="kid-old", key_material=_ALT_PUBLIC_KEY_PEM)
    monkeypatch.setattr(settings, "AUTH_JWT_PUBLIC_KEY_RING", old_public_ring)
    seed_jwt_verification_pg_cache_for_testing(raw_ring=old_public_ring)

    def _same_ring_fetch(key: str) -> str | None:
        if key == "AUTH_JWT_PUBLIC_KEY_RING":
            return old_public_ring
        return getattr(settings, key, None)

    monkeypatch.setattr(secrets_module, "_read_secret_source_of_truth_value", _same_ring_fetch)
    token = jwt.encode(_payload(), TEST_PRIVATE_KEY_PEM, algorithm="RS256", headers={"kid": "kid-missing"})

    observed_offsets: set[int] = set()
    for _ in range(8):
        with pytest.raises(InvalidTokenError):
            _decode_token(token)
        state = get_jwt_verification_pg_cache_state_for_testing()
        assert state.next_allowed_refresh_at is not None
        now = time.time()
        observed_offsets.add(max(0, int(round(state.next_allowed_refresh_at.timestamp() - now))))

    assert len(observed_offsets) > 1
