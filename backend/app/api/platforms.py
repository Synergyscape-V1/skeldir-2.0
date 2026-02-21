"""
Platform connections and credential endpoints (Phase 2).

Implements tenant-scoped platform connection substrate without outbound calls.
"""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.problem_details import problem_details_response
from app.core.config import settings
from app.core.secrets import get_platform_encryption_material_for_write
from app.security.auth import AuthContext, get_auth_context
from app.db.deps import get_db_session
from app.schemas.attribution import (
    PlatformConnectionResponse,
    PlatformConnectionUpsertRequest,
    PlatformCredentialStatusResponse,
    PlatformCredentialStatus,
    PlatformCredentialUpsertRequest,
)
from app.services.platform_connections import (
    PlatformConnectionService,
    PlatformConnectionNotFoundError,
    UnsupportedPlatformError,
)
from app.services.platform_credentials import PlatformCredentialStore

router = APIRouter()


def _supported_platforms() -> set[str]:
    return {
        item.strip()
        for item in settings.PLATFORM_SUPPORTED_PLATFORMS.split(",")
        if item.strip()
    }


def _validate_platform(platform: str) -> None:
    if platform not in _supported_platforms():
        raise UnsupportedPlatformError(f"Unsupported platform: {platform}")


@router.post(
    "/platform-connections",
    response_model=PlatformConnectionResponse,
    status_code=200,
    operation_id="upsertPlatformConnection",
    summary="Create or update a platform connection",
)
async def upsert_platform_connection(
    request: Request,
    payload: PlatformConnectionUpsertRequest,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    auth_context: Annotated[AuthContext, Depends(get_auth_context)],
):
    try:
        _validate_platform(payload.platform.value)
    except UnsupportedPlatformError as exc:
        return problem_details_response(
            request,
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Validation Error",
            detail=str(exc),
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/validation-error",
        )

    result = await PlatformConnectionService.upsert_connection(
        db_session,
        tenant_id=auth_context.tenant_id,
        platform=payload.platform.value,
        platform_account_id=payload.platform_account_id,
        status=payload.status.value if payload.status else "active",
        metadata=payload.metadata,
    )
    return result


@router.get(
    "/platform-connections/{platform}",
    response_model=PlatformConnectionResponse,
    status_code=200,
    operation_id="getPlatformConnection",
    summary="Get platform connection status",
)
async def get_platform_connection(
    request: Request,
    platform: str,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    auth_context: Annotated[AuthContext, Depends(get_auth_context)],
    platform_account_id: Optional[str] = None,
):
    try:
        _validate_platform(platform)
    except UnsupportedPlatformError as exc:
        return problem_details_response(
            request,
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Validation Error",
            detail=str(exc),
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/validation-error",
        )

    try:
        connection = await PlatformConnectionService.get_connection(
            db_session,
            tenant_id=auth_context.tenant_id,
            platform=platform,
            platform_account_id=platform_account_id,
        )
    except PlatformConnectionNotFoundError:
        return problem_details_response(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            title="Not Found",
            detail="Platform connection not found.",
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/not-found",
        )

    return connection


@router.post(
    "/platform-credentials",
    response_model=PlatformCredentialStatusResponse,
    status_code=200,
    operation_id="upsertPlatformCredentials",
    summary="Store or update platform credentials",
)
async def upsert_platform_credentials(
    request: Request,
    payload: PlatformCredentialUpsertRequest,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    auth_context: Annotated[AuthContext, Depends(get_auth_context)],
):
    try:
        _validate_platform(payload.platform.value)
    except UnsupportedPlatformError as exc:
        return problem_details_response(
            request,
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Validation Error",
            detail=str(exc),
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/validation-error",
        )

    try:
        key_id, encryption_key = get_platform_encryption_material_for_write()
    except RuntimeError:
        return problem_details_response(
            request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="Platform token encryption key is not configured.",
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/internal-server-error",
        )

    try:
        stored = await PlatformCredentialStore.upsert_tokens(
            db_session,
            tenant_id=auth_context.tenant_id,
            platform=payload.platform.value,
            platform_account_id=payload.platform_account_id,
            access_token=payload.access_token,
            refresh_token=payload.refresh_token,
            expires_at=payload.expires_at,
            scope=payload.scope,
            token_type=payload.token_type,
            key_id=key_id,
            encryption_key=encryption_key,
        )
    except PlatformConnectionNotFoundError:
        return problem_details_response(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            title="Not Found",
            detail="Platform connection not found.",
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/not-found",
        )

    return PlatformCredentialStatusResponse(
        tenant_id=str(auth_context.tenant_id),
        platform=payload.platform,
        platform_account_id=payload.platform_account_id,
        status=PlatformCredentialStatus.stored,
        expires_at=stored.get("expires_at"),
        updated_at=stored["updated_at"],
    )
