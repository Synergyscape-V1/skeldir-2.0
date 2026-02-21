from __future__ import annotations

"""Single secret retrieval choke point and runtime secret contract validation."""

from dataclasses import dataclass
from typing import Any, Literal
import os

from app.core.config import settings
from app.core.managed_settings_contract import MANAGED_SETTINGS_CONTRACT

RuntimeRole = Literal["api", "worker", "readiness"]


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
    return require_secret("PLATFORM_TOKEN_ENCRYPTION_KEY")


def get_jwt_validation_config() -> JwtValidationConfig:
    return JwtValidationConfig(
        secret=get_secret("AUTH_JWT_SECRET"),
        jwks_url=_read_setting("AUTH_JWT_JWKS_URL"),
        algorithm=_read_setting("AUTH_JWT_ALGORITHM"),
        issuer=_read_setting("AUTH_JWT_ISSUER"),
        audience=_read_setting("AUTH_JWT_AUDIENCE"),
    )


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
        if jwt_cfg.secret is None and jwt_cfg.jwks_url is None:
            missing.extend(["AUTH_JWT_SECRET|AUTH_JWT_JWKS_URL"])
        if (jwt_cfg.secret is not None or jwt_cfg.jwks_url is not None) and jwt_cfg.algorithm is None:
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
    if role in {"api", "readiness"} and platform_required and get_secret("PLATFORM_TOKEN_ENCRYPTION_KEY") is None:
        missing.append("PLATFORM_TOKEN_ENCRYPTION_KEY")

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
