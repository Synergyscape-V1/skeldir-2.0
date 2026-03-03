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
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header

# Import generated Pydantic models
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    User,
)
from app.core.secrets import get_secret
from app.db.session import AsyncSessionLocal
from app.security.auth import AuthContext, AuthError, get_auth_context
from app.services.auth_tokens import (
    TokenPair,
    issue_login_token_pair,
    lookup_identity_by_login,
    resolve_tenant_membership,
    rotate_refresh_token,
    verify_password,
)

router = APIRouter()
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
                token_pair = await issue_login_token_pair(
                    session,
                    user_id=identity.user_id,
                    tenant_id=resolved_tenant,
                )

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
                refresh_token=request.refresh_token,
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
    auth_context: Annotated[AuthContext, Depends(get_auth_context)],
):
    """
    Logout user and invalidate tokens.
    
    This is a sample implementation for contract enforcement testing.
    Production implementation would blacklist tokens or mark session as ended.
    
    Contract: POST /api/auth/logout
    Spec: api-contracts/dist/openapi/v1/auth.bundled.yaml
    """
    # Sample implementation - always succeeds for testing
    # Production: blacklist tokens, mark session ended in database
    
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
    auth_context: Annotated[AuthContext, Depends(get_auth_context)],
):
    return {
        "valid": True,
        "user_id": str(auth_context.user_id),
    }
