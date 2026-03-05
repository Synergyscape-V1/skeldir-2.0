"""
Authentication API Routes

Implements authentication operations defined in api-contracts/dist/openapi/v1/auth.bundled.yaml

Contract Operations:
- POST /api/auth/login: Authenticate user and obtain JWT tokens
- POST /api/auth/refresh: Refresh access token using refresh token
- POST /api/auth/logout: Invalidate tokens and end session

All routes use generated Pydantic models from backend/app/schemas/auth.py
"""

import os
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Security

# Import generated Pydantic models
from app.schemas.auth import (
    AdminTokenCutoffRequest,
    AdminTokenCutoffResponse,
    AdminUpdateMembershipRoleRequest,
    AdminUpdateMembershipRoleResponse,
    AdminWhoAmIResponse,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    User,
)
from app.core.secrets import get_secret
from app.db.session import AsyncSessionLocal
from app.security.auth import AuthContext, AuthError, get_auth_context, get_refresh_bearer_token
from app.services.auth_revocation import denylist_access_token, upsert_tokens_invalid_before
from app.services.auth_tokens import (
    TokenPair,
    assign_membership_primary_role,
    issue_login_token_pair,
    lookup_identity_by_login,
    resolve_tenant_membership,
    rotate_refresh_token,
    verify_password,
)

router = APIRouter()
admin_router = APIRouter(
    prefix="/admin",
    dependencies=[Security(get_auth_context, scopes=["admin"])],
)
_LOGIN_IDENTIFIER_PEPPER_CACHE: str | None = None


def _login_identifier_pepper() -> str | None:
    global _LOGIN_IDENTIFIER_PEPPER_CACHE
    if _LOGIN_IDENTIFIER_PEPPER_CACHE is None:
        _LOGIN_IDENTIFIER_PEPPER_CACHE = get_secret("AUTH_LOGIN_IDENTIFIER_PEPPER")
    return _LOGIN_IDENTIFIER_PEPPER_CACHE


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=200,
    operation_id="login",
    summary="Authenticate user and obtain JWT tokens",
    description="Authenticate with email and password to receive access and refresh tokens"
)
async def login(
    request: LoginRequest,
    _x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")]
):
    """
    Authenticate user with email and password.

    Contract: POST /api/auth/login
    Spec: api-contracts/dist/openapi/v1/auth.bundled.yaml
    """
    if request.tenant_id is None:
        raise AuthError(
            status_code=400,
            title="Validation Failed",
            detail="tenant_required",
            type_url="https://api.skeldir.com/problems/validation-error",
        )

    contract_testing = os.getenv("CONTRACT_TESTING") == "1"

    # Contract-conformance mode intentionally bypasses DB dependencies.
    if contract_testing:
        selected_tenant = request.tenant_id
        synthetic_user = uuid4()
        synthetic_email = "contract.user@example.com"
        token_pair = TokenPair(
            access_token="contract-test-access-token",
            refresh_token=f"{selected_tenant}.{uuid4()}.contract-testing-refresh",
            user_id=synthetic_user,
            tenant_id=selected_tenant,
            expires_in_seconds=900,
        )
    else:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                identity = await lookup_identity_by_login(
                    session,
                    login_identifier=str(request.email),
                    login_pepper=_login_identifier_pepper(),
                )
                password = request.password.get_secret_value()
                if (
                    identity is None
                    or not identity.is_active
                    or identity.auth_provider != "password"
                ):
                    raise AuthError(
                        status_code=401,
                        title="Authentication Failed",
                        detail="Invalid credentials.",
                        type_url="https://api.skeldir.com/problems/authentication-failed",
                    )
                if not verify_password(password, identity.password_hash):
                    raise AuthError(
                        status_code=401,
                        title="Authentication Failed",
                        detail="Invalid credentials.",
                        type_url="https://api.skeldir.com/problems/authentication-failed",
                    )
                resolved_tenant = await resolve_tenant_membership(
                    session,
                    user_id=identity.user_id,
                    requested_tenant_id=request.tenant_id,
                )
                if resolved_tenant is None:
                    raise AuthError(
                        status_code=401,
                        title="Authentication Failed",
                        detail="Invalid credentials.",
                        type_url="https://api.skeldir.com/problems/authentication-failed",
                    )
                try:
                    token_pair = await issue_login_token_pair(
                        session,
                        user_id=identity.user_id,
                        tenant_id=resolved_tenant,
                    )
                except ValueError as exc:
                    raise AuthError(
                        status_code=403,
                        title="Forbidden",
                        detail="Active membership role is required.",
                        type_url="https://api.skeldir.com/problems/forbidden",
                    ) from exc

    user = User(
        id=token_pair.user_id,
        email=synthetic_email if contract_testing else request.email,
        username=(
            synthetic_email.split("@")[0]
            if contract_testing
            else (request.email.split("@")[0] if "@" in request.email else "user")
        ),
    )
    return LoginResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.expires_in_seconds,
        user=user,
        token_type="Bearer",
    )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    status_code=200,
    operation_id="refreshToken",
    summary="Refresh access token",
    description="Exchange refresh token for new access and refresh tokens"
)
async def refresh_token(
    request: RefreshRequest,
    _x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    refresh_bearer_token: Annotated[str | None, Security(get_refresh_bearer_token)],
):
    """
    Refresh access token using refresh token.

    Contract: POST /api/auth/refresh
    Spec: api-contracts/dist/openapi/v1/auth.bundled.yaml
    """
    if os.getenv("CONTRACT_TESTING") == "1":
        return RefreshResponse(
            access_token="contract-test-access-token-refreshed",
            refresh_token=f"{request.tenant_id or uuid4()}.{uuid4()}.contract-testing-refresh-next",
            expires_in=900,
            token_type="Bearer",
        )

    token_pair = None
    async with AsyncSessionLocal() as session:
        async with session.begin():
            token_pair = await rotate_refresh_token(
                session,
                refresh_token=refresh_bearer_token or request.refresh_token,
                requested_tenant_id=request.tenant_id,
            )
    if token_pair is None:
        raise AuthError(
            status_code=401,
            title="Authentication Failed",
            detail="Invalid refresh token.",
            type_url="https://api.skeldir.com/problems/authentication-failed",
        )

    return RefreshResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.expires_in_seconds,
        token_type="Bearer",
    )


@router.post(
    "/logout",
    status_code=200,
    operation_id="logout",
    summary="Logout user and invalidate tokens",
    description="Invalidate access and refresh tokens, ending the user session"
)
async def logout(
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
):
    """
    Logout user and invalidate tokens.
    
    This is a sample implementation for contract enforcement testing.
    Production implementation would blacklist tokens or mark session as ended.
    
    Contract: POST /api/auth/logout
    Spec: api-contracts/dist/openapi/v1/auth.bundled.yaml
    """
    if os.getenv("CONTRACT_TESTING") != "1":
        exp = auth_context.claims.get("exp")
        try:
            expires_at = datetime.fromtimestamp(int(exp), tz=timezone.utc)
        except (TypeError, ValueError):
            raise AuthError(
                status_code=401,
                title="Authentication Failed",
                detail="Invalid exp claim.",
                type_url="https://api.skeldir.com/problems/authentication-failed",
            )
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await denylist_access_token(
                    session,
                    tenant_id=auth_context.tenant_id,
                    user_id=auth_context.user_id,
                    jti=auth_context.jti,
                    expires_at=expires_at,
                    reason="logout",
                )

    return {
        "success": True,
        "correlation_id": str(x_correlation_id),
        "message": f"Session terminated for {auth_context.user_id}",
    }


@router.get(
    "/verify",
    status_code=200,
    operation_id="verifyToken",
    summary="Verify token validity",
    description="Check if the current access token is valid",
)
async def verify_token(
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
):
    return {
        "valid": True,
        "user_id": str(auth_context.user_id),
    }


@admin_router.post(
    "/token-cutoff",
    response_model=AdminTokenCutoffResponse,
    status_code=200,
    operation_id="adminRevokeTokensBefore",
    summary="Admin token kill-switch",
    description="Set tenant-scoped user token cutoff (`tokens_invalid_before`) for immediate revocation.",
)
async def admin_token_cutoff(
    request: AdminTokenCutoffRequest,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["admin"])],
):
    cutoff = request.tokens_invalid_before or datetime.now(timezone.utc)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)

    if os.getenv("CONTRACT_TESTING") != "1":
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await upsert_tokens_invalid_before(
                    session,
                    tenant_id=auth_context.tenant_id,
                    user_id=request.user_id,
                    invalid_before=cutoff,
                    updated_by_user_id=auth_context.user_id,
                )

    return AdminTokenCutoffResponse(
        success=True,
        correlation_id=x_correlation_id,
        tenant_id=auth_context.tenant_id,
        user_id=request.user_id,
        tokens_invalid_before=cutoff,
        message=f"Token cutoff updated for {request.user_id}",
    )


@admin_router.get(
    "/rbac-check",
    response_model=AdminWhoAmIResponse,
    status_code=200,
    operation_id="adminRbacCheck",
    summary="Admin-only RBAC proof endpoint",
    description="Representative admin-only endpoint used to prove deterministic 403 deny semantics.",
)
async def admin_rbac_check(
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["admin"])],
):
    role_value = str(auth_context.claims.get("role", "viewer")).strip().lower() or "viewer"
    if role_value not in {"admin", "manager", "viewer"}:
        role_value = "viewer"
    return AdminWhoAmIResponse(
        success=True,
        correlation_id=x_correlation_id,
        tenant_id=auth_context.tenant_id,
        user_id=auth_context.user_id,
        role=role_value,
    )


@admin_router.post(
    "/membership-role",
    response_model=AdminUpdateMembershipRoleResponse,
    status_code=200,
    operation_id="adminUpdateMembershipRole",
    summary="Admin membership role update",
    description=(
        "Set tenant-scoped membership role (Admin/Manager/Viewer). "
        "Any role change immediately bumps tokens_invalid_before for that user."
    ),
)
async def admin_update_membership_role(
    request: AdminUpdateMembershipRoleRequest,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["admin"])],
):
    now_utc = datetime.now(timezone.utc)
    changed = False

    if os.getenv("CONTRACT_TESTING") != "1":
        async with AsyncSessionLocal() as session:
            async with session.begin():
                try:
                    changed = await assign_membership_primary_role(
                        session,
                        tenant_id=auth_context.tenant_id,
                        user_id=request.user_id,
                        role_code=request.role,
                    )
                except ValueError as exc:
                    message = str(exc).lower()
                    if "membership" in message:
                        raise AuthError(
                            status_code=404,
                            title="Not Found",
                            detail="Active tenant membership not found.",
                            type_url="https://api.skeldir.com/problems/not-found",
                        ) from exc
                    raise AuthError(
                        status_code=400,
                        title="Validation Failed",
                        detail="Unsupported role code.",
                        type_url="https://api.skeldir.com/problems/validation-error",
                    ) from exc
                if changed:
                    await upsert_tokens_invalid_before(
                        session,
                        tenant_id=auth_context.tenant_id,
                        user_id=request.user_id,
                        invalid_before=now_utc,
                        updated_by_user_id=auth_context.user_id,
                    )

    return AdminUpdateMembershipRoleResponse(
        success=True,
        correlation_id=x_correlation_id,
        tenant_id=auth_context.tenant_id,
        user_id=request.user_id,
        role=request.role,
        tokens_invalid_before=now_utc,
        revoked_existing_tokens=changed,
        message=f"Membership role set to {request.role}.",
    )


router.include_router(admin_router)


if os.getenv("SKELDIR_B12_P6_ENABLE_NEGATIVE_ADMIN_UNSCOPED_ROUTE") == "1":
    @router.get(
        "/admin/_negative_unscoped",
        status_code=200,
        operation_id="adminNegativeUnscopedRoute",
        include_in_schema=True,
    )
    async def admin_negative_unscoped_route() -> dict[str, bool]:
        return {"ok": True}
