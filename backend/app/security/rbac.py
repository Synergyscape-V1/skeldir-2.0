from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated, Any

from fastapi import Depends

from app.security.auth import AuthContext, AuthError, get_auth_context

ALLOWED_ROLES: tuple[str, ...] = ("admin", "manager", "viewer")


def normalize_role_claims(raw_roles: Iterable[Any]) -> list[str]:
    normalized = {
        str(value).strip().lower()
        for value in raw_roles
        if value is not None and str(value).strip()
    }
    known = [role for role in ALLOWED_ROLES if role in normalized]
    return known or ["viewer"]


def role_claims_from_auth_context(auth_context: AuthContext) -> list[str]:
    role_candidates: list[Any] = []
    single_role = auth_context.claims.get("role")
    if single_role is not None:
        role_candidates.append(single_role)
    roles = auth_context.claims.get("roles")
    if isinstance(roles, list):
        role_candidates.extend(roles)
    return normalize_role_claims(role_candidates)


def primary_role_from_claims(role_claims: list[str]) -> str:
    if role_claims:
        return role_claims[0]
    return "viewer"


def require_roles(*allowed_roles: str):
    allowed = set(normalize_role_claims(allowed_roles))

    async def _guard(
        auth_context: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> AuthContext:
        effective_roles = set(role_claims_from_auth_context(auth_context))
        if effective_roles.intersection(allowed):
            return auth_context
        raise AuthError(
            status_code=403,
            title="Forbidden",
            detail=f"Required role: {', '.join(sorted(allowed))}.",
            type_url="https://api.skeldir.com/problems/forbidden",
        )

    return _guard
