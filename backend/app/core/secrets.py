from __future__ import annotations

"""Single secret retrieval choke point and runtime secret contract validation."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from contextlib import contextmanager
from hashlib import sha256
import json
from threading import Lock
from typing import Any, Literal
import os

import psycopg2

from app.core import clock as clock_module
from app.core.config import settings
from app.core.control_plane import (
    resolve_aws_path_for_key,
    resolve_control_plane_env,
    should_enable_control_plane,
    _fetch_value_from_aws,  # sanctioned internal control-plane fetch path
)
from app.core.managed_settings_contract import MANAGED_SETTINGS_CONTRACT

RuntimeRole = Literal["api", "worker", "readiness"]
MAX_ACCEPTED_CRYPTO_KEYS = 3


@dataclass(frozen=True)
class RuntimeSecretValidationResult:
    ok: bool
    missing: tuple[str, ...]
    invalid: tuple[str, ...]


@dataclass(frozen=True)
class JwtValidationConfig:
    public_key_ring: str | None
    jwks_url: str | None
    algorithm: str | None
    issuer: str | None
    audience: str | None


@dataclass(frozen=True)
class JwtSigningMaterial:
    kid: str
    key: str
    algorithm: str
    issuer: str | None
    audience: str | None


@dataclass(frozen=True)
class JwtKeyRing:
    current_kid: str
    keys: dict[str, str]
    previous_kids: tuple[str, ...]
    fetched_at: datetime
    source: str
    requires_kid: bool


@dataclass(frozen=True)
class PlatformEncryptionKeyRing:
    current_key_id: str
    keys: dict[str, str]
    previous_key_ids: tuple[str, ...]
    fetched_at: datetime
    source: str


@dataclass(frozen=True)
class JwtVerificationPgCacheState:
    fetched_at: datetime | None
    next_allowed_refresh_at: datetime | None
    last_refresh_error_at: datetime | None
    refresh_error_count: int
    refresh_event_count: int


class _CryptoKeyRingCache:
    def __init__(self, *, secret_key: str, max_staleness_env: str, default_staleness_seconds: int) -> None:
        self._secret_key = secret_key
        self._max_staleness_env = max_staleness_env
        self._default_staleness_seconds = default_staleness_seconds
        self._lock = Lock()
        self._value: JwtKeyRing | PlatformEncryptionKeyRing | None = None
        self._version_fingerprint: str | None = None

    def _max_staleness_seconds(self) -> int:
        raw = os.getenv(self._max_staleness_env, str(self._default_staleness_seconds)).strip()
        try:
            parsed = int(raw)
        except ValueError:
            parsed = self._default_staleness_seconds
        return max(1, parsed)

    def _is_stale(self, fetched_at: datetime) -> bool:
        age_seconds = (clock_module.utcnow() - fetched_at).total_seconds()
        return age_seconds > self._max_staleness_seconds()

    def current(self) -> JwtKeyRing | PlatformEncryptionKeyRing | None:
        with self._lock:
            return self._value

    def set(self, value: JwtKeyRing | PlatformEncryptionKeyRing, *, fingerprint: str) -> None:
        with self._lock:
            self._value = value
            self._version_fingerprint = fingerprint

    def clear(self) -> None:
        with self._lock:
            self._value = None
            self._version_fingerprint = None

    def stale(self) -> bool:
        with self._lock:
            cached = self._value
        if cached is None:
            return True
        return self._is_stale(cached.fetched_at)


_JWT_SIGNING_KEY_RING_CACHE = _CryptoKeyRingCache(
    secret_key="AUTH_JWT_SECRET",
    max_staleness_env="SKELDIR_JWT_KEY_RING_MAX_STALENESS_SECONDS",
    default_staleness_seconds=60,
)
_JWT_VERIFICATION_KEY_RING_CACHE = _CryptoKeyRingCache(
    secret_key="AUTH_JWT_PUBLIC_KEY_RING",
    max_staleness_env="SKELDIR_JWT_KEY_RING_MAX_STALENESS_SECONDS",
    default_staleness_seconds=60,
)
_PLATFORM_KEY_RING_CACHE = _CryptoKeyRingCache(
    secret_key="PLATFORM_TOKEN_ENCRYPTION_KEY",
    max_staleness_env="SKELDIR_PLATFORM_KEY_RING_MAX_STALENESS_SECONDS",
    default_staleness_seconds=60,
)
_JWT_UNKNOWN_KID_REFRESH_LOCK = Lock()
_JWT_UNKNOWN_KID_LAST_REFRESH_AT: datetime | None = None
_JWT_REFRESH_PG_LOCK_KEY = int.from_bytes(
    sha256("skeldir_jwks_refresh_v1".encode("utf-8")).digest()[:8],
    byteorder="big",
    signed=True,
)
_JWT_PG_CACHE_TABLE = "public.jwt_verification_cache"
_DATABASE_DSN_CACHE: str | None = None
_DATABASE_DSN_CACHE_LOCK = Lock()


def _contract_for(key: str):
    contract = MANAGED_SETTINGS_CONTRACT.get(key)
    if contract is None:
        raise KeyError(f"managed settings contract missing key: {key}")
    return contract


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "unicode_string"):
        text = value.unicode_string()
    else:
        text = str(value)
    cleaned = text.strip()
    return cleaned or None


def _read_setting(key: str) -> str | None:
    return _coerce_str(getattr(settings, key, None))


def _control_plane_source_marker(key: str) -> str:
    return f"SKELDIR_CONTROL_PLANE_SOURCE_{key}"


def _mark_control_plane_source(key: str) -> None:
    os.environ[_control_plane_source_marker(key)] = "1"


def was_loaded_from_control_plane(key: str) -> bool:
    return os.getenv(_control_plane_source_marker(key), "0").strip() == "1"


def _read_secret_source_of_truth_value(key: str) -> str | None:
    if should_enable_control_plane():
        canonical_env = resolve_control_plane_env(os.getenv("ENVIRONMENT", settings.ENVIRONMENT))
        contract = _contract_for(key)
        path = resolve_aws_path_for_key(key=key, canonical_env=canonical_env)
        value = _fetch_value_from_aws(contract, path)
        cleaned = _coerce_str(value)
        if cleaned is None:
            return None
        _mark_control_plane_source(key)
        return cleaned
    return _read_setting(key)


def _jwt_max_staleness_seconds() -> int:
    raw = os.getenv("SKELDIR_JWT_KEY_RING_MAX_STALENESS_SECONDS", "60").strip()
    try:
        parsed = int(raw)
    except ValueError:
        parsed = 60
    return max(1, parsed)


def _jwt_refresh_floor_seconds() -> int:
    raw = os.getenv("SKELDIR_JWT_REFRESH_MIN_FLOOR_SECONDS", "5").strip()
    try:
        parsed = int(raw)
    except ValueError:
        parsed = 5
    return max(0, parsed)


def _jwt_refresh_jitter_seconds() -> int:
    raw = os.getenv("SKELDIR_JWT_REFRESH_JITTER_SECONDS", "3").strip()
    try:
        parsed = int(raw)
    except ValueError:
        parsed = 3
    return max(0, parsed)


def _jwt_refresh_backoff_base_seconds() -> int:
    raw = os.getenv("SKELDIR_JWT_REFRESH_BACKOFF_BASE_SECONDS", "2").strip()
    try:
        parsed = int(raw)
    except ValueError:
        parsed = 2
    return max(1, parsed)


def _jwt_refresh_backoff_max_seconds() -> int:
    raw = os.getenv("SKELDIR_JWT_REFRESH_BACKOFF_MAX_SECONDS", "60").strip()
    try:
        parsed = int(raw)
    except ValueError:
        parsed = 60
    return max(1, parsed)


def _jwt_singleflight_mutation_enabled() -> bool:
    return os.getenv("SKELDIR_B12_P3_DISABLE_PG_SINGLEFLIGHT", "0").strip().lower() in {"1", "true", "yes", "on"}


def _database_url_for_sync_pg() -> str:
    global _DATABASE_DSN_CACHE
    with _DATABASE_DSN_CACHE_LOCK:
        if _DATABASE_DSN_CACHE:
            return _DATABASE_DSN_CACHE

        candidate = _read_setting("DATABASE_URL")
        if not candidate:
            try:
                from app.db import session as db_session  # local import avoids import-cycle during module init

                candidate = getattr(db_session, "_ASYNC_DATABASE_URL", None)
                if candidate:
                    candidate = str(candidate).replace("postgresql+asyncpg://", "postgresql://", 1)
            except Exception:
                candidate = None
        if not candidate:
            candidate = require_secret("DATABASE_URL")

        _DATABASE_DSN_CACHE = candidate
        return _DATABASE_DSN_CACHE


@contextmanager
def _open_pg_conn():
    conn = psycopg2.connect(_database_url_for_sync_pg())
    conn.autocommit = False
    try:
        yield conn
    finally:
        conn.close()


def _pg_fetchone_dict(cursor) -> dict[str, Any] | None:
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [col.name for col in cursor.description]
    return dict(zip(columns, row))


def _pg_cache_state_from_row(row: dict[str, Any] | None) -> JwtVerificationPgCacheState:
    if row is None:
        return JwtVerificationPgCacheState(
            fetched_at=None,
            next_allowed_refresh_at=None,
            last_refresh_error_at=None,
            refresh_error_count=0,
            refresh_event_count=0,
        )
    return JwtVerificationPgCacheState(
        fetched_at=row.get("fetched_at"),
        next_allowed_refresh_at=row.get("next_allowed_refresh_at"),
        last_refresh_error_at=row.get("last_refresh_error_at"),
        refresh_error_count=int(row.get("refresh_error_count") or 0),
        refresh_event_count=int(row.get("refresh_event_count") or 0),
    )


def _should_refresh_from_pg_state(
    *,
    state: JwtVerificationPgCacheState,
    now: datetime,
    reason: str,
) -> bool:
    if state.fetched_at is None:
        return True
    if reason == "unknown_kid":
        return True
    jitter = _deterministic_refresh_jitter_seconds(
        now=now,
        reason=reason,
        discriminator=state.fetched_at.isoformat(),
    )
    return now >= state.fetched_at + timedelta(seconds=_jwt_max_staleness_seconds() + jitter)


def _next_allowed_refresh_on_success(now: datetime) -> datetime:
    jitter = _deterministic_refresh_jitter_seconds(
        now=now,
        reason="success",
    )
    return now + timedelta(seconds=_jwt_refresh_floor_seconds() + jitter)


def _next_allowed_refresh_on_failure(now: datetime, failure_count: int) -> datetime:
    exp_delay = _jwt_refresh_backoff_base_seconds() * (2 ** max(0, failure_count - 1))
    bounded = min(_jwt_refresh_backoff_max_seconds(), exp_delay)
    jitter = _deterministic_refresh_jitter_seconds(
        now=now,
        reason="failure",
        discriminator=str(failure_count),
    )
    return now + timedelta(seconds=bounded + jitter)


def _deterministic_refresh_jitter_seconds(
    *,
    now: datetime,
    reason: str,
    discriminator: str = "",
) -> int:
    max_jitter = _jwt_refresh_jitter_seconds()
    if max_jitter <= 0:
        return 0
    bucket = int(now.timestamp()) // 5
    seed = "|".join(
        (
            reason,
            discriminator,
            str(bucket),
            str(os.getpid()),
            os.getenv("HOSTNAME", ""),
        )
    )
    digest = sha256(seed.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], byteorder="big", signed=False) % (max_jitter + 1)


def _select_pg_jwt_cache_row(cursor) -> dict[str, Any] | None:
    cursor.execute(
        f"""
        SELECT singleton_id, jwks_json, fetched_at, next_allowed_refresh_at,
               last_refresh_error_at, refresh_error_count, refresh_event_count
          FROM {_JWT_PG_CACHE_TABLE}
         WHERE singleton_id = 1
        """
    )
    return _pg_fetchone_dict(cursor)


def _ensure_pg_jwt_cache_table(cursor) -> None:
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_JWT_PG_CACHE_TABLE} (
            singleton_id SMALLINT PRIMARY KEY CHECK (singleton_id = 1),
            jwks_json TEXT NULL,
            fetched_at TIMESTAMPTZ NULL,
            next_allowed_refresh_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_refresh_error_at TIMESTAMPTZ NULL,
            refresh_error_count INTEGER NOT NULL DEFAULT 0,
            refresh_event_count BIGINT NOT NULL DEFAULT 0,
            last_refresh_reason TEXT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def _upsert_pg_jwt_cache_row_success(
    cursor,
    *,
    jwks_json: str,
    now: datetime,
    next_allowed_refresh_at: datetime,
    reason: str,
) -> None:
    cursor.execute(
        f"""
        INSERT INTO {_JWT_PG_CACHE_TABLE} (
            singleton_id, jwks_json, fetched_at, next_allowed_refresh_at,
            last_refresh_error_at, refresh_error_count, refresh_event_count, last_refresh_reason, updated_at
        ) VALUES (
            1, %(jwks_json)s, %(fetched_at)s, %(next_allowed_refresh_at)s,
            NULL, 0, 1, %(reason)s, %(updated_at)s
        )
        ON CONFLICT (singleton_id)
        DO UPDATE SET
            jwks_json = EXCLUDED.jwks_json,
            fetched_at = EXCLUDED.fetched_at,
            next_allowed_refresh_at = EXCLUDED.next_allowed_refresh_at,
            last_refresh_error_at = NULL,
            refresh_error_count = 0,
            refresh_event_count = {_JWT_PG_CACHE_TABLE}.refresh_event_count + 1,
            last_refresh_reason = EXCLUDED.last_refresh_reason,
            updated_at = EXCLUDED.updated_at
        """,
        {
            "jwks_json": jwks_json,
            "fetched_at": now,
            "next_allowed_refresh_at": next_allowed_refresh_at,
            "reason": reason,
            "updated_at": now,
        },
    )


def _upsert_pg_jwt_cache_row_failure(
    cursor,
    *,
    now: datetime,
    reason: str,
) -> JwtVerificationPgCacheState:
    current = _pg_cache_state_from_row(_select_pg_jwt_cache_row(cursor))
    next_error_count = current.refresh_error_count + 1
    next_allowed = _next_allowed_refresh_on_failure(now, next_error_count)
    cursor.execute(
        f"""
        INSERT INTO {_JWT_PG_CACHE_TABLE} (
            singleton_id, jwks_json, fetched_at, next_allowed_refresh_at,
            last_refresh_error_at, refresh_error_count, refresh_event_count, last_refresh_reason, updated_at
        ) VALUES (
            1, NULL, NULL, %(next_allowed_refresh_at)s,
            %(last_refresh_error_at)s, %(refresh_error_count)s, 1, %(reason)s, %(updated_at)s
        )
        ON CONFLICT (singleton_id)
        DO UPDATE SET
            next_allowed_refresh_at = EXCLUDED.next_allowed_refresh_at,
            last_refresh_error_at = EXCLUDED.last_refresh_error_at,
            refresh_error_count = {_JWT_PG_CACHE_TABLE}.refresh_error_count + 1,
            refresh_event_count = {_JWT_PG_CACHE_TABLE}.refresh_event_count + 1,
            last_refresh_reason = EXCLUDED.last_refresh_reason,
            updated_at = EXCLUDED.updated_at
        """,
        {
            "next_allowed_refresh_at": next_allowed,
            "last_refresh_error_at": now,
            "refresh_error_count": next_error_count,
            "reason": reason,
            "updated_at": now,
        },
    )
    return JwtVerificationPgCacheState(
        fetched_at=current.fetched_at,
        next_allowed_refresh_at=next_allowed,
        last_refresh_error_at=now,
        refresh_error_count=next_error_count,
        refresh_event_count=current.refresh_event_count + 1,
    )


def _parse_pg_jwt_ring(raw: str | None) -> JwtKeyRing | None:
    if not raw:
        return None
    return _parse_jwt_key_ring_payload(raw, "postgres_cache")


def _refresh_verification_ring_from_source_of_truth() -> tuple[JwtKeyRing, str]:
    value = _read_secret_source_of_truth_value("AUTH_JWT_PUBLIC_KEY_RING")
    if value is None:
        env_name = (_read_setting("ENVIRONMENT") or "").lower()
        if env_name in {"local", "dev", "ci", "test"}:
            value = _read_secret_source_of_truth_value("AUTH_JWT_SECRET")
    if value is None:
        raise RuntimeError("required secret missing: AUTH_JWT_PUBLIC_KEY_RING")
    source = "control_plane" if should_enable_control_plane() else "settings"
    ring = _parse_jwt_key_ring_payload(value, source)
    return ring, value


def _update_local_verification_ring_cache(ring: JwtKeyRing, raw_value: str) -> None:
    _JWT_VERIFICATION_KEY_RING_CACHE.set(ring, fingerprint=_fingerprint(raw_value))


def _resolve_verification_ring_via_postgres(*, reason: str, kid: str | None) -> JwtKeyRing:
    now = clock_module.utcnow()
    with _open_pg_conn() as conn:
        with conn.cursor() as cursor:
            row = _select_pg_jwt_cache_row(cursor)
            state = _pg_cache_state_from_row(row)
            cached_ring = _parse_pg_jwt_ring(row.get("jwks_json") if row else None)

            if cached_ring is not None and not _should_refresh_from_pg_state(state=state, now=now, reason=reason):
                conn.rollback()
                _update_local_verification_ring_cache(cached_ring, row["jwks_json"])
                return cached_ring

            floor_blocked = (
                not _jwt_singleflight_mutation_enabled()
                and state.next_allowed_refresh_at is not None
                and now < state.next_allowed_refresh_at
            )
            if floor_blocked and cached_ring is not None:
                conn.rollback()
                _update_local_verification_ring_cache(cached_ring, row["jwks_json"])
                return cached_ring

            lock_acquired = True
            if not _jwt_singleflight_mutation_enabled():
                cursor.execute("SELECT pg_try_advisory_lock(%s)", (_JWT_REFRESH_PG_LOCK_KEY,))
                lock_acquired = bool(cursor.fetchone()[0])
            if not lock_acquired:
                conn.rollback()
                if cached_ring is not None:
                    _update_local_verification_ring_cache(cached_ring, row["jwks_json"])
                    return cached_ring
                fallback = _JWT_VERIFICATION_KEY_RING_CACHE.current()
                if fallback is not None:
                    return fallback
                return _refresh_jwt_verification_ring()

            try:
                # Re-read under refresh lease to absorb concurrent winner updates.
                row = _select_pg_jwt_cache_row(cursor)
                state = _pg_cache_state_from_row(row)
                cached_ring = _parse_pg_jwt_ring(row.get("jwks_json") if row else None)
                if cached_ring is not None and kid and kid in cached_ring.keys:
                    conn.rollback()
                    _update_local_verification_ring_cache(cached_ring, row["jwks_json"])
                    return cached_ring

                now = clock_module.utcnow()
                floor_blocked = (
                    not _jwt_singleflight_mutation_enabled()
                    and state.next_allowed_refresh_at is not None
                    and now < state.next_allowed_refresh_at
                )
                if floor_blocked and cached_ring is not None:
                    conn.rollback()
                    _update_local_verification_ring_cache(cached_ring, row["jwks_json"])
                    return cached_ring

                ring, raw_value = _refresh_verification_ring_from_source_of_truth()
                _upsert_pg_jwt_cache_row_success(
                    cursor,
                    jwks_json=raw_value,
                    now=now,
                    next_allowed_refresh_at=_next_allowed_refresh_on_success(now),
                    reason=reason,
                )
                conn.commit()
                _update_local_verification_ring_cache(ring, raw_value)
                return ring
            except Exception:
                _upsert_pg_jwt_cache_row_failure(cursor, now=clock_module.utcnow(), reason=reason)
                conn.commit()
                if cached_ring is not None:
                    _update_local_verification_ring_cache(cached_ring, row["jwks_json"])
                    return cached_ring
                fallback = _JWT_VERIFICATION_KEY_RING_CACHE.current()
                if fallback is not None:
                    return fallback
                raise
            finally:
                if not _jwt_singleflight_mutation_enabled():
                    cursor.execute("SELECT pg_advisory_unlock(%s)", (_JWT_REFRESH_PG_LOCK_KEY,))
                    conn.commit()


def get_secret(key: str) -> str | None:
    """Return a secret value from Settings through one sanctioned access path."""
    contract = _contract_for(key)
    if contract.classification != "secret":
        raise ValueError(f"{key} is not classified as secret")
    return _read_secret_source_of_truth_value(key)


def require_secret(key: str) -> str:
    value = get_secret(key)
    if value is None:
        raise RuntimeError(f"required secret missing: {key}")
    return value


def get_database_url() -> str:
    return require_secret("DATABASE_URL")


def get_migration_database_url() -> str:
    value = get_secret("MIGRATION_DATABASE_URL")
    if value is not None:
        return value
    env_name = _read_setting("ENVIRONMENT")
    if env_name in {"local", "dev", "ci"}:
        return require_secret("DATABASE_URL")
    raise RuntimeError("required secret missing: MIGRATION_DATABASE_URL")


def get_platform_token_encryption_key() -> str:
    ring = get_platform_encryption_key_ring(require_fresh_for_write=True)
    return ring.keys[ring.current_key_id]


def get_jwt_validation_config() -> JwtValidationConfig:
    public_ring = _read_setting("AUTH_JWT_PUBLIC_KEY_RING")
    if public_ring is None:
        env_name = (_read_setting("ENVIRONMENT") or "").lower()
        if env_name in {"local", "dev", "ci", "test"}:
            public_ring = _read_setting("AUTH_JWT_SECRET")
    return JwtValidationConfig(
        public_key_ring=public_ring,
        jwks_url=_read_setting("AUTH_JWT_JWKS_URL"),
        algorithm=_read_setting("AUTH_JWT_ALGORITHM"),
        issuer=_read_setting("AUTH_JWT_ISSUER"),
        audience=_read_setting("AUTH_JWT_AUDIENCE"),
    )


def _normalize_bounded_key_list(*, keys: dict[str, str], explicit_previous: list[str] | None, current: str) -> tuple[str, ...]:
    if len(keys) > MAX_ACCEPTED_CRYPTO_KEYS:
        raise RuntimeError(
            f"key ring exceeds max accepted keys ({len(keys)} > {MAX_ACCEPTED_CRYPTO_KEYS})"
        )
    if explicit_previous is not None:
        normalized = tuple(k for k in explicit_previous if k in keys and k != current)
    else:
        normalized = tuple(k for k in keys.keys() if k != current)
    if len(normalized) > MAX_ACCEPTED_CRYPTO_KEYS - 1:
        normalized = normalized[: MAX_ACCEPTED_CRYPTO_KEYS - 1]
    return normalized


def _parse_jwt_key_ring_payload(raw_value: str, source: str) -> JwtKeyRing:
    parsed: dict[str, Any] | None = None
    try:
        maybe = json.loads(raw_value)
        if isinstance(maybe, dict):
            parsed = maybe
    except json.JSONDecodeError:
        parsed = None

    if parsed is None:
        legacy_kid = "legacy-default"
        return JwtKeyRing(
            current_kid=legacy_kid,
            keys={legacy_kid: raw_value},
            previous_kids=tuple(),
            fetched_at=clock_module.utcnow(),
            source=source,
            requires_kid=False,
        )

    keys_obj = parsed.get("keys")
    current_kid = _coerce_str(parsed.get("current_kid"))
    if not isinstance(keys_obj, dict) or not current_kid:
        raise RuntimeError("AUTH_JWT_SECRET key-ring payload is invalid: missing current_kid/keys")
    keys: dict[str, str] = {}
    for kid, material in keys_obj.items():
        kid_clean = _coerce_str(kid)
        material_clean = _coerce_str(material)
        if not kid_clean or not material_clean:
            continue
        keys[kid_clean] = material_clean
    if current_kid not in keys:
        raise RuntimeError("AUTH_JWT_SECRET key-ring payload invalid: current_kid missing from keys")
    explicit_previous = parsed.get("previous_kids")
    previous_kids = _normalize_bounded_key_list(
        keys=keys,
        explicit_previous=explicit_previous if isinstance(explicit_previous, list) else None,
        current=current_kid,
    )
    return JwtKeyRing(
        current_kid=current_kid,
        keys=keys,
        previous_kids=previous_kids,
        fetched_at=clock_module.utcnow(),
        source=source,
        requires_kid=True,
    )


def _parse_platform_key_ring_payload(raw_value: str, source: str) -> PlatformEncryptionKeyRing:
    parsed: dict[str, Any] | None = None
    try:
        maybe = json.loads(raw_value)
        if isinstance(maybe, dict):
            parsed = maybe
    except json.JSONDecodeError:
        parsed = None

    if parsed is None:
        default_key_id = _read_setting("PLATFORM_TOKEN_KEY_ID") or "legacy-default"
        return PlatformEncryptionKeyRing(
            current_key_id=default_key_id,
            keys={default_key_id: raw_value},
            previous_key_ids=tuple(),
            fetched_at=clock_module.utcnow(),
            source=source,
        )

    keys_obj = parsed.get("keys")
    current_key_id = _coerce_str(parsed.get("current_key_id"))
    if not isinstance(keys_obj, dict) or not current_key_id:
        raise RuntimeError(
            "PLATFORM_TOKEN_ENCRYPTION_KEY key-ring payload is invalid: missing current_key_id/keys"
        )
    keys: dict[str, str] = {}
    for key_id, material in keys_obj.items():
        key_id_clean = _coerce_str(key_id)
        material_clean = _coerce_str(material)
        if not key_id_clean or not material_clean:
            continue
        keys[key_id_clean] = material_clean
    if current_key_id not in keys:
        raise RuntimeError(
            "PLATFORM_TOKEN_ENCRYPTION_KEY key-ring payload invalid: current_key_id missing from keys"
        )
    explicit_previous = parsed.get("previous_key_ids")
    previous_key_ids = _normalize_bounded_key_list(
        keys=keys,
        explicit_previous=explicit_previous if isinstance(explicit_previous, list) else None,
        current=current_key_id,
    )
    return PlatformEncryptionKeyRing(
        current_key_id=current_key_id,
        keys=keys,
        previous_key_ids=previous_key_ids,
        fetched_at=clock_module.utcnow(),
        source=source,
    )


def _fingerprint(raw_value: str) -> str:
    return sha256(raw_value.encode("utf-8")).hexdigest()


def _refresh_jwt_signing_ring() -> JwtKeyRing:
    value = _read_secret_source_of_truth_value("AUTH_JWT_SECRET")
    if value is None:
        raise RuntimeError("required secret missing: AUTH_JWT_SECRET")
    source = "control_plane" if should_enable_control_plane() else "settings"
    ring = _parse_jwt_key_ring_payload(value, source)
    _JWT_SIGNING_KEY_RING_CACHE.set(ring, fingerprint=_fingerprint(value))
    return ring


def _refresh_jwt_verification_ring() -> JwtKeyRing:
    ring, raw_value = _refresh_verification_ring_from_source_of_truth()
    _JWT_VERIFICATION_KEY_RING_CACHE.set(ring, fingerprint=_fingerprint(raw_value))
    return ring


def _refresh_platform_ring() -> PlatformEncryptionKeyRing:
    value = _read_secret_source_of_truth_value("PLATFORM_TOKEN_ENCRYPTION_KEY")
    if value is None:
        raise RuntimeError("required secret missing: PLATFORM_TOKEN_ENCRYPTION_KEY")
    source = "control_plane" if should_enable_control_plane() else "settings"
    ring = _parse_platform_key_ring_payload(value, source)
    _PLATFORM_KEY_RING_CACHE.set(ring, fingerprint=_fingerprint(value))
    return ring


def get_jwt_signing_key_ring(*, require_fresh_for_mint: bool) -> JwtKeyRing:
    cached = _JWT_SIGNING_KEY_RING_CACHE.current()
    is_stale = _JWT_SIGNING_KEY_RING_CACHE.stale()
    if cached is None or is_stale:
        try:
            return _refresh_jwt_signing_ring()
        except Exception:
            if require_fresh_for_mint or cached is None:
                raise
            return cached
    return cached


def get_jwt_verification_key_ring() -> JwtKeyRing:
    cached = _JWT_VERIFICATION_KEY_RING_CACHE.current()
    is_stale = _JWT_VERIFICATION_KEY_RING_CACHE.stale()
    if cached is None:
        try:
            return _resolve_verification_ring_via_postgres(reason="cold_start", kid=None)
        except Exception:
            return _refresh_jwt_verification_ring()
    if is_stale:
        try:
            return _resolve_verification_ring_via_postgres(reason="ttl_stale", kid=None)
        except Exception:
            return cached
    return cached


def get_platform_encryption_key_ring(*, require_fresh_for_write: bool) -> PlatformEncryptionKeyRing:
    cached = _PLATFORM_KEY_RING_CACHE.current()
    is_stale = _PLATFORM_KEY_RING_CACHE.stale()
    if cached is None or is_stale:
        try:
            return _refresh_platform_ring()
        except Exception:
            if require_fresh_for_write or cached is None:
                raise
            return cached
    return cached


def get_jwt_signing_material() -> JwtSigningMaterial:
    cfg = get_jwt_validation_config()
    if not cfg.algorithm:
        raise RuntimeError("required config missing: AUTH_JWT_ALGORITHM")
    ring = get_jwt_signing_key_ring(require_fresh_for_mint=True)
    key = ring.keys.get(ring.current_kid)
    if key is None:
        raise RuntimeError("JWT key ring current kid is missing key material")
    return JwtSigningMaterial(
        kid=ring.current_kid,
        key=key,
        algorithm=cfg.algorithm,
        issuer=cfg.issuer,
        audience=cfg.audience,
    )


def resolve_jwt_verification_keys(*, kid: str | None) -> tuple[str, list[str], bool]:
    if os.getenv("SKELDIR_B12_P3_FORCE_PER_REQUEST_VERIFIER_REFRESH", "0").strip() in {"1", "true", "yes", "on"}:
        ring = _refresh_jwt_verification_ring()
    else:
        ring = get_jwt_verification_key_ring()
    if kid:
        selected = ring.keys.get(kid)
        if selected:
            return selected, [], ring.requires_kid
        if _should_attempt_unknown_kid_refresh():
            try:
                refreshed = _resolve_verification_ring_via_postgres(reason="unknown_kid", kid=kid)
            except Exception:
                refreshed = ring
            selected_after_refresh = refreshed.keys.get(kid)
            if selected_after_refresh:
                return selected_after_refresh, [], refreshed.requires_kid
            ring = refreshed
    fallback_order = [ring.current_kid, *ring.previous_kids]
    fallback_keys = [ring.keys[k] for k in fallback_order if k in ring.keys]
    bounded = fallback_keys[:MAX_ACCEPTED_CRYPTO_KEYS]
    if not bounded:
        raise RuntimeError("JWT verification key ring is empty")
    return bounded[0], bounded[1:], ring.requires_kid


def get_platform_encryption_material_for_write() -> tuple[str, str]:
    ring = get_platform_encryption_key_ring(require_fresh_for_write=True)
    key = ring.keys.get(ring.current_key_id)
    if key is None:
        raise RuntimeError("Platform key ring current key_id is missing key material")
    return ring.current_key_id, key


def resolve_platform_encryption_key_by_id(key_id: str) -> str:
    ring = get_platform_encryption_key_ring(require_fresh_for_write=False)
    key = ring.keys.get(key_id)
    if key:
        return key
    # Force one refresh on miss to absorb rotation within bounded staleness.
    ring = _refresh_platform_ring()
    key = ring.keys.get(key_id)
    if key:
        return key
    raise RuntimeError(f"Unknown platform encryption key_id: {key_id}")


def reset_crypto_secret_caches_for_testing() -> None:
    global _JWT_UNKNOWN_KID_LAST_REFRESH_AT
    _JWT_SIGNING_KEY_RING_CACHE.clear()
    _JWT_VERIFICATION_KEY_RING_CACHE.clear()
    _PLATFORM_KEY_RING_CACHE.clear()
    with _JWT_UNKNOWN_KID_REFRESH_LOCK:
        _JWT_UNKNOWN_KID_LAST_REFRESH_AT = None


def reset_jwt_verification_pg_cache_for_testing() -> None:
    try:
        with _open_pg_conn() as conn:
            with conn.cursor() as cursor:
                _ensure_pg_jwt_cache_table(cursor)
                cursor.execute(f"DELETE FROM {_JWT_PG_CACHE_TABLE} WHERE singleton_id = 1")
            conn.commit()
    except Exception:
        # Some unit tests run without Postgres; keep tests that don't require DB unaffected.
        return


def seed_jwt_verification_pg_cache_for_testing(
    *,
    raw_ring: str,
    fetched_at: datetime | None = None,
    next_allowed_refresh_at: datetime | None = None,
    refresh_error_count: int = 0,
    refresh_event_count: int = 0,
) -> None:
    now = clock_module.utcnow()
    fetched = fetched_at or now
    next_allowed = next_allowed_refresh_at or now
    with _open_pg_conn() as conn:
        with conn.cursor() as cursor:
            _ensure_pg_jwt_cache_table(cursor)
            cursor.execute(
                f"""
                INSERT INTO {_JWT_PG_CACHE_TABLE} (
                    singleton_id, jwks_json, fetched_at, next_allowed_refresh_at,
                    last_refresh_error_at, refresh_error_count, refresh_event_count, last_refresh_reason, updated_at
                ) VALUES (
                    1, %(jwks_json)s, %(fetched_at)s, %(next_allowed_refresh_at)s,
                    NULL, %(refresh_error_count)s, %(refresh_event_count)s, 'seed', %(updated_at)s
                )
                ON CONFLICT (singleton_id)
                DO UPDATE SET
                    jwks_json = EXCLUDED.jwks_json,
                    fetched_at = EXCLUDED.fetched_at,
                    next_allowed_refresh_at = EXCLUDED.next_allowed_refresh_at,
                    last_refresh_error_at = NULL,
                    refresh_error_count = EXCLUDED.refresh_error_count,
                    refresh_event_count = EXCLUDED.refresh_event_count,
                    last_refresh_reason = EXCLUDED.last_refresh_reason,
                    updated_at = EXCLUDED.updated_at
                """,
                {
                    "jwks_json": raw_ring,
                    "fetched_at": fetched,
                    "next_allowed_refresh_at": next_allowed,
                    "refresh_error_count": max(0, int(refresh_error_count)),
                    "refresh_event_count": max(0, int(refresh_event_count)),
                    "updated_at": now,
                },
            )
        conn.commit()


def get_jwt_verification_pg_cache_state_for_testing() -> JwtVerificationPgCacheState:
    with _open_pg_conn() as conn:
        with conn.cursor() as cursor:
            _ensure_pg_jwt_cache_table(cursor)
            row = _select_pg_jwt_cache_row(cursor)
        conn.rollback()
    return _pg_cache_state_from_row(row)


def _should_attempt_unknown_kid_refresh() -> bool:
    global _JWT_UNKNOWN_KID_LAST_REFRESH_AT
    raw = os.getenv("SKELDIR_JWT_UNKNOWN_KID_REFRESH_DEBOUNCE_SECONDS", "5").strip()
    try:
        debounce_seconds = max(0, int(raw))
    except ValueError:
        debounce_seconds = 5

    with _JWT_UNKNOWN_KID_REFRESH_LOCK:
        now = clock_module.utcnow()
        last = _JWT_UNKNOWN_KID_LAST_REFRESH_AT
        if last is not None and (now - last).total_seconds() < debounce_seconds:
            return False
        _JWT_UNKNOWN_KID_LAST_REFRESH_AT = now
        return True


def validate_runtime_secret_contract(role: RuntimeRole) -> RuntimeSecretValidationResult:
    """Validate boot/readiness secret prerequisites without exposing secret values."""
    missing: list[str] = []
    invalid: list[str] = []

    if get_secret("DATABASE_URL") is None:
        missing.append("DATABASE_URL")
    if role in {"readiness", "worker"} and get_secret("MIGRATION_DATABASE_URL") is None:
        env_name = _read_setting("ENVIRONMENT")
        if env_name not in {"local", "dev", "ci"}:
            missing.append("MIGRATION_DATABASE_URL")

    auth_required = (
        role in {"api", "readiness"}
        and (
            os.getenv("SKELDIR_REQUIRE_AUTH_SECRETS", "0").strip() in {"1", "true", "yes", "on"}
            or _read_setting("ENVIRONMENT") in {"prod", "stage"}
        )
    )
    if auth_required:
        jwt_cfg = get_jwt_validation_config()
        jwt_private_ring = get_secret("AUTH_JWT_SECRET")
        jwt_public_ring = jwt_cfg.public_key_ring
        if should_enable_control_plane():
            try:
                jwt_private_ring = _read_secret_source_of_truth_value("AUTH_JWT_SECRET")
            except Exception:
                jwt_private_ring = None
            try:
                jwt_public_ring = _read_secret_source_of_truth_value("AUTH_JWT_PUBLIC_KEY_RING")
            except Exception:
                jwt_public_ring = None
        if jwt_private_ring is None:
            missing.append("AUTH_JWT_SECRET")
        if jwt_public_ring is None:
            missing.append("AUTH_JWT_PUBLIC_KEY_RING")
        if (jwt_private_ring is not None or jwt_public_ring is not None) and jwt_cfg.algorithm is None:
            missing.append("AUTH_JWT_ALGORITHM")
        if jwt_cfg.algorithm is not None and jwt_cfg.algorithm != "RS256":
            invalid.append("AUTH_JWT_ALGORITHM!=RS256")
        if jwt_cfg.issuer is None:
            missing.append("AUTH_JWT_ISSUER")
        if jwt_cfg.audience is None:
            missing.append("AUTH_JWT_AUDIENCE")

    platform_key_id = _read_setting("PLATFORM_TOKEN_KEY_ID")
    platform_required = (
        os.getenv("SKELDIR_REQUIRE_PLATFORM_TOKEN_KEY", "0").strip() in {"1", "true", "yes", "on"}
        or platform_key_id is not None
    )
    if role in {"api", "readiness"} and platform_required:
        platform_secret = get_secret("PLATFORM_TOKEN_ENCRYPTION_KEY")
        if should_enable_control_plane():
            try:
                platform_secret = _read_secret_source_of_truth_value("PLATFORM_TOKEN_ENCRYPTION_KEY")
            except Exception:
                platform_secret = None
        if platform_secret is None:
            missing.append("PLATFORM_TOKEN_ENCRYPTION_KEY")

    env_name = _read_setting("ENVIRONMENT")
    llm_required = bool(_read_setting("LLM_PROVIDER_ENABLED")) and (
        env_name in {"stage", "prod"}
        or os.getenv("SKELDIR_REQUIRE_PROVIDER_SECRETS", "0").strip().lower() in {"1", "true", "yes", "on"}
    )
    if role in {"api", "worker", "readiness"} and llm_required:
        llm_secret = get_secret("LLM_PROVIDER_API_KEY")
        if llm_secret is None:
            missing.append("LLM_PROVIDER_API_KEY")

    if env_name in {"prod", "stage"}:
        if not should_enable_control_plane():
            missing.append("SKELDIR_CONTROL_PLANE_ENABLED")
        else:
            control_plane_keys = [
                "DATABASE_URL",
                "MIGRATION_DATABASE_URL",
                "CELERY_BROKER_URL",
                "CELERY_RESULT_BACKEND",
                "AUTH_JWT_SECRET",
                "AUTH_JWT_PUBLIC_KEY_RING",
                "PLATFORM_TOKEN_ENCRYPTION_KEY",
            ]
            if llm_required:
                control_plane_keys.append("LLM_PROVIDER_API_KEY")
            for key in control_plane_keys:
                try:
                    _read_secret_source_of_truth_value(key)
                except Exception:
                    missing.append(f"{key}@control-plane")
                if not was_loaded_from_control_plane(key):
                    missing.append(f"{key}@source-of-truth")

    return RuntimeSecretValidationResult(
        ok=not missing and not invalid,
        missing=tuple(sorted(set(missing))),
        invalid=tuple(sorted(set(invalid))),
    )


def assert_runtime_secret_contract(role: RuntimeRole) -> None:
    result = validate_runtime_secret_contract(role)
    if result.ok:
        return
    fragments: list[str] = []
    if result.missing:
        fragments.append(f"missing={','.join(result.missing)}")
    if result.invalid:
        fragments.append(f"invalid={','.join(result.invalid)}")
    raise RuntimeError(f"runtime secret contract failed for role={role}: {';'.join(fragments)}")
