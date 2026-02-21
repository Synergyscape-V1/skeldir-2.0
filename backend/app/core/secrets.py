from __future__ import annotations

"""Single secret retrieval choke point and runtime secret contract validation."""

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from threading import Lock
from typing import Any, Literal
import os

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
    secret: str | None
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


_JWT_KEY_RING_CACHE = _CryptoKeyRingCache(
    secret_key="AUTH_JWT_SECRET",
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


def get_secret(key: str) -> str | None:
    """Return a secret value from Settings through one sanctioned access path."""
    contract = _contract_for(key)
    if contract.classification != "secret":
        raise ValueError(f"{key} is not classified as secret")
    return _read_setting(key)


def require_secret(key: str) -> str:
    value = get_secret(key)
    if value is None:
        raise RuntimeError(f"required secret missing: {key}")
    return value


def get_database_url() -> str:
    return require_secret("DATABASE_URL")


def get_platform_token_encryption_key() -> str:
    ring = get_platform_encryption_key_ring(require_fresh_for_write=True)
    return ring.keys[ring.current_key_id]


def get_jwt_validation_config() -> JwtValidationConfig:
    return JwtValidationConfig(
        secret=get_secret("AUTH_JWT_SECRET"),
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


def _refresh_jwt_ring() -> JwtKeyRing:
    value = _read_secret_source_of_truth_value("AUTH_JWT_SECRET")
    if value is None:
        raise RuntimeError("required secret missing: AUTH_JWT_SECRET")
    source = "control_plane" if should_enable_control_plane() else "settings"
    ring = _parse_jwt_key_ring_payload(value, source)
    _JWT_KEY_RING_CACHE.set(ring, fingerprint=_fingerprint(value))
    return ring


def _refresh_platform_ring() -> PlatformEncryptionKeyRing:
    value = _read_secret_source_of_truth_value("PLATFORM_TOKEN_ENCRYPTION_KEY")
    if value is None:
        raise RuntimeError("required secret missing: PLATFORM_TOKEN_ENCRYPTION_KEY")
    source = "control_plane" if should_enable_control_plane() else "settings"
    ring = _parse_platform_key_ring_payload(value, source)
    _PLATFORM_KEY_RING_CACHE.set(ring, fingerprint=_fingerprint(value))
    return ring


def get_jwt_key_ring(*, require_fresh_for_mint: bool) -> JwtKeyRing:
    cached = _JWT_KEY_RING_CACHE.current()
    is_stale = _JWT_KEY_RING_CACHE.stale()
    if cached is None or is_stale:
        try:
            return _refresh_jwt_ring()
        except Exception:
            if require_fresh_for_mint or cached is None:
                raise
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
    ring = get_jwt_key_ring(require_fresh_for_mint=True)
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
    ring = get_jwt_key_ring(require_fresh_for_mint=False)
    if kid:
        selected = ring.keys.get(kid)
        if selected:
            return selected, [], ring.requires_kid
        if _should_attempt_unknown_kid_refresh():
            try:
                refreshed = _refresh_jwt_ring()
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
    _JWT_KEY_RING_CACHE.clear()
    _PLATFORM_KEY_RING_CACHE.clear()
    with _JWT_UNKNOWN_KID_REFRESH_LOCK:
        _JWT_UNKNOWN_KID_LAST_REFRESH_AT = None


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

    auth_required = (
        role in {"api", "readiness"}
        and (
            os.getenv("SKELDIR_REQUIRE_AUTH_SECRETS", "0").strip() in {"1", "true", "yes", "on"}
            or _read_setting("ENVIRONMENT") in {"prod", "stage"}
        )
    )
    if auth_required:
        jwt_cfg = get_jwt_validation_config()
        jwt_secret = jwt_cfg.secret
        if should_enable_control_plane():
            try:
                jwt_secret = _read_secret_source_of_truth_value("AUTH_JWT_SECRET")
            except Exception:
                jwt_secret = None
        if jwt_secret is None and jwt_cfg.jwks_url is None:
            missing.extend(["AUTH_JWT_SECRET|AUTH_JWT_JWKS_URL"])
        if (jwt_secret is not None or jwt_cfg.jwks_url is not None) and jwt_cfg.algorithm is None:
            missing.append("AUTH_JWT_ALGORITHM")
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
    if env_name in {"prod", "stage"}:
        if not should_enable_control_plane():
            missing.append("SKELDIR_CONTROL_PLANE_ENABLED")
        else:
            for key in ("AUTH_JWT_SECRET", "PLATFORM_TOKEN_ENCRYPTION_KEY"):
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
