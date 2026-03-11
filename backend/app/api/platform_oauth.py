"""
Provider OAuth lifecycle runtime handlers (B1.3-P6).

Introduces runtime authorize/callback/status/disconnect flows through the
provider-neutral dispatcher and canonical transient/durable substrates.
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.problem_details import problem_details_response
from app.core.config import settings
from app.db.deps import get_db_session
from app.schemas.attribution import (
    Platform,
    ProviderOAuthAuthorizeRequest,
    ProviderOAuthAuthorizeResponse,
    ProviderOAuthCallbackResponse,
    ProviderOAuthDisconnectRequest,
    ProviderOAuthDisconnectResponse,
    ProviderOAuthStatusResponse,
)
from app.security.auth import AuthContext
from app.security.lifecycle_authorization import (
    require_lifecycle_mutation_access,
    require_lifecycle_read_access,
)
from app.services.provider_oauth_runtime import (
    ProviderLifecycleProblem,
    ProviderOAuthLifecycleRuntimeService,
)

router = APIRouter()
logger = logging.getLogger(__name__)
runtime_service = ProviderOAuthLifecycleRuntimeService()


def _supported_platforms() -> set[str]:
    return {
        item.strip()
        for item in settings.PLATFORM_SUPPORTED_PLATFORMS.split(",")
        if item.strip()
    }


def _provider_problem_response(
    request: Request,
    *,
    correlation_id: UUID,
    problem: ProviderLifecycleProblem,
):
    response = problem_details_response(
        request,
        status_code=problem.status_code,
        title=problem.title,
        detail=problem.detail,
        correlation_id=correlation_id,
        type_url=problem.type_url,
        code=problem.code,
    )
    if problem.retry_after_seconds is not None:
        response.headers["Retry-After"] = str(problem.retry_after_seconds)
    return response


def _is_supported_platform(platform: str) -> bool:
    return platform in _supported_platforms()


@router.post(
    "/platform-oauth/{platform}/authorize",
    response_model=ProviderOAuthAuthorizeResponse,
    status_code=202,
    operation_id="initiateProviderOAuthAuthorization",
    summary="Initiate provider OAuth authorization",
)
async def initiate_provider_oauth_authorization(
    request: Request,
    platform: Platform,
    payload: ProviderOAuthAuthorizeRequest,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    auth_context: Annotated[AuthContext, Depends(require_lifecycle_mutation_access)],
):
    platform_key = platform.value
    if not _is_supported_platform(platform_key):
        return problem_details_response(
            request,
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Validation Error",
            detail=f"Unsupported platform: {platform_key}",
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/validation-error",
        )
    try:
        result = await runtime_service.initiate_authorization(
            db_session,
            tenant_id=auth_context.tenant_id,
            user_id=auth_context.user_id,
            platform=platform_key,
            correlation_id=x_correlation_id,
            platform_account_id=payload.platform_account_id,
            redirect_uri=str(payload.redirect_uri),
            requested_scopes=tuple(payload.requested_scopes or []),
        )
    except ProviderLifecycleProblem as problem:
        return _provider_problem_response(
            request,
            correlation_id=x_correlation_id,
            problem=problem,
        )

    logger.info(
        {
            "event_type": "provider_oauth_authorize",
            "tenant_id": str(auth_context.tenant_id),
            "correlation_id": str(x_correlation_id),
            "platform": platform_key,
        }
    )
    return ProviderOAuthAuthorizeResponse(
        tenant_id=str(result.tenant_id),
        platform=platform,
        lifecycle_state=result.lifecycle_state,  # type: ignore[arg-type]
        authorization_url=result.authorization_url,
        state_reference=result.state_reference,
        state_expires_at=result.state_expires_at,
        data_freshness_seconds=result.data_freshness_seconds,
        last_updated=result.last_updated,
    )


@router.get(
    "/platform-oauth/{platform}/callback",
    response_model=ProviderOAuthCallbackResponse,
    status_code=200,
    operation_id="completeProviderOAuthCallback",
    summary="Complete provider OAuth callback",
)
async def complete_provider_oauth_callback(
    request: Request,
    platform: Platform,
    state: Annotated[str, Query(description="Opaque state reference emitted during authorize initiation")],
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    auth_context: Annotated[AuthContext, Depends(require_lifecycle_mutation_access)],
    code: Annotated[str | None, Query(description="Provider authorization code")] = None,
    error: Annotated[str | None, Query(description="Provider callback error code")] = None,
    error_description: Annotated[str | None, Query(description="Provider callback error description")] = None,
):
    del error_description  # Provider detail text is intentionally ignored to preserve non-leak contract.
    platform_key = platform.value
    if not _is_supported_platform(platform_key):
        return problem_details_response(
            request,
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Validation Error",
            detail=f"Unsupported platform: {platform_key}",
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/validation-error",
        )
    try:
        result = await runtime_service.complete_callback(
            db_session,
            tenant_id=auth_context.tenant_id,
            user_id=auth_context.user_id,
            platform=platform_key,
            correlation_id=x_correlation_id,
            state_reference=state,
            authorization_code=code,
            provider_error_code=error,
        )
    except ValueError as exc:
        return problem_details_response(
            request,
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Validation Error",
            detail=str(exc),
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/validation-error",
        )
    except ProviderLifecycleProblem as problem:
        return _provider_problem_response(
            request,
            correlation_id=x_correlation_id,
            problem=problem,
        )

    logger.info(
        {
            "event_type": "provider_oauth_callback",
            "tenant_id": str(auth_context.tenant_id),
            "correlation_id": str(x_correlation_id),
            "platform": platform_key,
        }
    )
    return ProviderOAuthCallbackResponse(
        tenant_id=str(result.tenant_id),
        platform=platform,
        platform_account_id=result.platform_account_id,
        lifecycle_state=result.lifecycle_state,  # type: ignore[arg-type]
        refresh_state=result.refresh_state,  # type: ignore[arg-type]
        data_freshness_seconds=result.data_freshness_seconds,
        last_updated=result.last_updated,
    )


@router.get(
    "/platform-oauth/{platform}/status",
    response_model=ProviderOAuthStatusResponse,
    status_code=200,
    operation_id="getProviderOAuthStatus",
    summary="Read provider OAuth connection status",
)
async def get_provider_oauth_status(
    request: Request,
    platform: Platform,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    auth_context: Annotated[AuthContext, Depends(require_lifecycle_read_access)],
    platform_account_id: Annotated[str | None, Query(description="Optional provider account filter")] = None,
):
    platform_key = platform.value
    if not _is_supported_platform(platform_key):
        return problem_details_response(
            request,
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Validation Error",
            detail=f"Unsupported platform: {platform_key}",
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/validation-error",
        )
    try:
        result = await runtime_service.get_status(
            db_session,
            tenant_id=auth_context.tenant_id,
            user_id=auth_context.user_id,
            platform=platform_key,
            platform_account_id=platform_account_id,
        )
    except ProviderLifecycleProblem as problem:
        return _provider_problem_response(
            request,
            correlation_id=x_correlation_id,
            problem=problem,
        )

    logger.info(
        {
            "event_type": "provider_oauth_status",
            "tenant_id": str(auth_context.tenant_id),
            "correlation_id": str(x_correlation_id),
            "platform": platform_key,
        }
    )
    return ProviderOAuthStatusResponse(
        tenant_id=str(result.tenant_id),
        platform=platform,
        platform_account_id=result.platform_account_id,
        lifecycle_state=result.lifecycle_state,  # type: ignore[arg-type]
        refresh_state=result.refresh_state,  # type: ignore[arg-type]
        expires_at=result.expires_at,
        scope=result.scope,
        data_freshness_seconds=result.data_freshness_seconds,
        last_updated=result.last_updated,
    )


@router.post(
    "/platform-oauth/{platform}/disconnect",
    response_model=ProviderOAuthDisconnectResponse,
    status_code=200,
    operation_id="disconnectProviderOAuth",
    summary="Disconnect and revoke provider OAuth connection",
)
async def disconnect_provider_oauth(
    request: Request,
    platform: Platform,
    payload: ProviderOAuthDisconnectRequest,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    auth_context: Annotated[AuthContext, Depends(require_lifecycle_mutation_access)],
):
    platform_key = platform.value
    if not _is_supported_platform(platform_key):
        return problem_details_response(
            request,
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Validation Error",
            detail=f"Unsupported platform: {platform_key}",
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/validation-error",
        )
    try:
        result = await runtime_service.disconnect(
            db_session,
            tenant_id=auth_context.tenant_id,
            platform=platform_key,
            correlation_id=x_correlation_id,
            reason=payload.reason.value,
        )
    except ProviderLifecycleProblem as problem:
        return _provider_problem_response(
            request,
            correlation_id=x_correlation_id,
            problem=problem,
        )

    logger.info(
        {
            "event_type": "provider_oauth_disconnect",
            "tenant_id": str(auth_context.tenant_id),
            "correlation_id": str(x_correlation_id),
            "platform": platform_key,
        }
    )
    return ProviderOAuthDisconnectResponse(
        tenant_id=str(result.tenant_id),
        platform=platform,
        lifecycle_state=result.lifecycle_state,  # type: ignore[arg-type]
        disconnected_at=result.disconnected_at,
        data_freshness_seconds=result.data_freshness_seconds,
        last_updated=result.last_updated,
    )
