from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import Header, Request
import jwt
from jwt import InvalidTokenError

from app.core.secrets import (
    get_jwt_signing_material,
    get_jwt_validation_config,
    resolve_jwt_verification_keys,
)
from app.core.identity import resolve_user_id
from app.observability.context import set_tenant_id, set_user_id

RS256_ALGORITHM = "RS256"


class AuthError(Exception):
    def __init__(self, *, status_code: int, title: str, detail: str, type_url: str) -> None:
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.type_url = type_url
        super().__init__(detail)


@dataclass(frozen=True)
class AuthContext:
    tenant_id: UUID
    user_id: UUID
    subject: Optional[str]
    issuer: Optional[str]
    audience: Optional[str | list[str]]
    claims: dict[str, Any]


def _get_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise AuthError(
            status_code=401,
            title="Authentication Failed",
            detail="Missing Authorization header.",
            type_url="https://api.skeldir.com/problems/authentication-failed",
        )
    stripped = authorization.strip()
    if not stripped.lower().startswith("bearer "):
        raise AuthError(
            status_code=401,
            title="Authentication Failed",
            detail="Authorization header must be a Bearer token.",
            type_url="https://api.skeldir.com/problems/authentication-failed",
        )
    return stripped.split(" ", 1)[1].strip()


def _ensure_auth_configured() -> None:
    jwt_cfg = get_jwt_validation_config()
    if not jwt_cfg.public_key_ring:
        raise AuthError(
            status_code=500,
            title="Internal Server Error",
            detail="JWT verification key ring is not configured.",
            type_url="https://api.skeldir.com/problems/internal-server-error",
        )
    if not jwt_cfg.algorithm:
        raise AuthError(
            status_code=500,
            title="Internal Server Error",
            detail="JWT algorithm is not configured.",
            type_url="https://api.skeldir.com/problems/internal-server-error",
        )
    if jwt_cfg.algorithm != RS256_ALGORITHM:
        raise AuthError(
            status_code=500,
            title="Internal Server Error",
            detail="JWT algorithm must be RS256.",
            type_url="https://api.skeldir.com/problems/internal-server-error",
        )


def _decode_token(token: str) -> dict[str, Any]:
    _ensure_auth_configured()
    jwt_cfg = get_jwt_validation_config()
    options = {"require": ["exp"]}
    decode_kwargs: dict[str, Any] = {"options": options}
    if jwt_cfg.issuer:
        decode_kwargs["issuer"] = jwt_cfg.issuer
    if jwt_cfg.audience:
        decode_kwargs["audience"] = jwt_cfg.audience

    kid: str | None = None
    try:
        header = jwt.get_unverified_header(token)
        token_algorithm = str(header.get("alg", "")).strip()
        if token_algorithm != RS256_ALGORITHM:
            raise InvalidTokenError("Invalid JWT algorithm.")
        kid_value = header.get("kid")
        kid = str(kid_value).strip() if kid_value is not None else None
    except InvalidTokenError:
        kid = None
    primary_key, fallback_keys, requires_kid = resolve_jwt_verification_keys(kid=kid)
    if requires_kid and not kid:
        raise InvalidTokenError("JWT is missing required 'kid' header.")
    attempted_keys = [primary_key, *fallback_keys]
    for key in attempted_keys:
        try:
            return jwt.decode(
                token,
                key,
                algorithms=[RS256_ALGORITHM],
                **decode_kwargs,
            )
        except InvalidTokenError:
            continue
    raise InvalidTokenError("Invalid or expired JWT token.")


def decode_and_verify_jwt(token: str) -> dict[str, Any]:
    """Shared JWT verification primitive for HTTP and worker planes."""
    return _decode_token(token)


def mint_internal_jwt(
    *,
    tenant_id: UUID,
    user_id: UUID,
    expires_in_seconds: int = 300,
    additional_claims: Optional[dict[str, Any]] = None,
) -> str:
    """Mint internal JWTs using rotation-safe current key material and `kid` header."""
    signing = get_jwt_signing_material()
    if signing.algorithm != RS256_ALGORITHM:
        raise RuntimeError("AUTH_JWT_ALGORITHM must be RS256")
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "tenant_id": str(tenant_id),
        "sub": str(user_id),
        "user_id": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=max(1, expires_in_seconds))).timestamp()),
    }
    if signing.issuer:
        payload["iss"] = signing.issuer
    if signing.audience:
        payload["aud"] = signing.audience
    if additional_claims:
        payload.update(additional_claims)
    return jwt.encode(
        payload,
        signing.key,
        algorithm=RS256_ALGORITHM,
        headers={"kid": signing.kid},
    )


def _require_tenant_id(claims: dict[str, Any]) -> UUID:
    tenant_id = claims.get("tenant_id")
    if not tenant_id:
        raise AuthError(
            status_code=401,
            title="Authentication Failed",
            detail="Missing tenant_id claim.",
            type_url="https://api.skeldir.com/problems/authentication-failed",
        )
    try:
        return UUID(str(tenant_id))
    except ValueError as exc:
        raise AuthError(
            status_code=401,
            title="Authentication Failed",
            detail="Invalid tenant_id claim.",
            type_url="https://api.skeldir.com/problems/authentication-failed",
        ) from exc


def _resolve_user_id(claims: dict[str, Any]) -> UUID:
    candidate = claims.get("user_id") or claims.get("sub")
    return resolve_user_id(candidate)


def get_auth_context(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> AuthContext:
    token = _get_bearer_token(authorization)
    try:
        claims = _decode_token(token)
    except InvalidTokenError as exc:
        raise AuthError(
            status_code=401,
            title="Authentication Failed",
            detail="Invalid or expired JWT token.",
            type_url="https://api.skeldir.com/problems/authentication-failed",
        ) from exc

    tenant_id = _require_tenant_id(claims)
    user_id = _resolve_user_id(claims)
    auth_context = AuthContext(
        tenant_id=tenant_id,
        user_id=user_id,
        subject=claims.get("sub"),
        issuer=claims.get("iss"),
        audience=claims.get("aud"),
        claims=claims,
    )
    request.state.auth_context = auth_context
    set_tenant_id(tenant_id)
    set_user_id(user_id)
    return auth_context
