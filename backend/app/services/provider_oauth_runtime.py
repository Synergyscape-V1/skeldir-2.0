"""
Runtime provider OAuth lifecycle composition (B1.3-P6).

This service composes:
- P5 adapter dispatch
- P2 transient handshake consume semantics
- P3 durable platform connection/credential writes
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock as clock_module
from app.core.secrets import get_platform_encryption_material_for_write
from app.security.secret_boundary import sanitize_for_transport
from app.services.oauth_handshake_state import (
    OAuthHandshakeStateAbortedError,
    OAuthHandshakeStateBindingError,
    OAuthHandshakeStateExpiredError,
    OAuthHandshakeStateNotFoundError,
    OAuthHandshakeStateReplayError,
    OAuthHandshakeStateService,
    issue_state_reference,
)
from app.services.oauth_lifecycle_dispatcher import ProviderOAuthLifecycleDispatcher
from app.services.platform_connections import (
    PlatformConnectionNotFoundError,
    PlatformConnectionService,
)
from app.services.platform_credentials import (
    PlatformCredentialNotFoundError,
    PlatformCredentialService,
    PlatformCredentialStore,
)
from app.services.provider_oauth_lifecycle import (
    OAuthAccountMetadataRequest,
    OAuthAuthorizeURLRequest,
    OAuthCallbackStateValidationRequest,
    OAuthCodeExchangeRequest,
    OAuthDisconnectRequest,
    OAuthLifecycleAdapterError,
    OAuthLifecycleNotImplementedError,
    OAuthLifecycleRefreshError,
)

PROBLEM_TYPE_BASE = "https://api.skeldir.com/problems"
DEFAULT_AUTHORIZATION_TTL = timedelta(minutes=15)


@dataclass(frozen=True)
class ProviderOAuthAuthorizeRuntimeResult:
    tenant_id: UUID
    platform: str
    lifecycle_state: str
    authorization_url: str
    state_reference: str
    state_expires_at: datetime
    data_freshness_seconds: int
    last_updated: datetime


@dataclass(frozen=True)
class ProviderOAuthCallbackRuntimeResult:
    tenant_id: UUID
    platform: str
    platform_account_id: str
    lifecycle_state: str
    refresh_state: str
    data_freshness_seconds: int
    last_updated: datetime


@dataclass(frozen=True)
class ProviderOAuthStatusRuntimeResult:
    tenant_id: UUID
    platform: str
    platform_account_id: str
    lifecycle_state: str
    refresh_state: str
    expires_at: datetime | None
    scope: str | None
    data_freshness_seconds: int
    last_updated: datetime


@dataclass(frozen=True)
class ProviderOAuthDisconnectRuntimeResult:
    tenant_id: UUID
    platform: str
    lifecycle_state: str
    disconnected_at: datetime
    data_freshness_seconds: int
    last_updated: datetime


@dataclass(frozen=True)
class ProviderOAuthRefreshStateRuntimeResult:
    tenant_id: UUID
    platform: str
    lifecycle_state: str
    refresh_state: str
    next_refresh_due_at: datetime | None
    last_refresh_attempt_at: datetime | None
    last_refresh_success_at: datetime | None
    last_error_code: str | None
    data_freshness_seconds: int
    last_updated: datetime


@dataclass(frozen=True)
class ProviderLifecycleProblem(RuntimeError):
    status_code: int
    title: str
    detail: str
    code: str
    type_url: str
    retry_after_seconds: int | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


def _utcnow() -> datetime:
    return clock_module.utcnow()


def _normalize_provider_error(
    *,
    status_code: int,
    title: str,
    detail: str,
    code: str,
    type_suffix: str,
    retry_after_seconds: int | None = None,
) -> ProviderLifecycleProblem:
    return ProviderLifecycleProblem(
        status_code=status_code,
        title=title,
        detail=detail,
        code=code,
        type_url=f"{PROBLEM_TYPE_BASE}/{type_suffix}",
        retry_after_seconds=retry_after_seconds,
    )


def provider_not_connected(detail: str = "Provider connection is not available for this tenant.") -> ProviderLifecycleProblem:
    return _normalize_provider_error(
        status_code=404,
        title="Provider Not Connected",
        detail=detail,
        code="provider_not_connected",
        type_suffix="provider-not-connected",
    )


def provider_expired(detail: str = "Provider authorization is expired and must be renewed.") -> ProviderLifecycleProblem:
    return _normalize_provider_error(
        status_code=409,
        title="Provider Authorization Expired",
        detail=detail,
        code="provider_expired",
        type_suffix="provider-expired",
    )


def provider_revoked(detail: str = "Provider connection has been revoked and requires reconnect.") -> ProviderLifecycleProblem:
    return _normalize_provider_error(
        status_code=409,
        title="Provider Connection Revoked",
        detail=detail,
        code="provider_revoked",
        type_suffix="provider-revoked",
    )


def provider_scope_insufficient(
    detail: str = "Provider connection lacks required scopes for this lifecycle action.",
) -> ProviderLifecycleProblem:
    return _normalize_provider_error(
        status_code=403,
        title="Provider Scope Insufficient",
        detail=detail,
        code="provider_scope_insufficient",
        type_suffix="provider-scope-insufficient",
    )


def provider_transport_failure(
    detail: str = "Provider lifecycle operation is temporarily unavailable.",
) -> ProviderLifecycleProblem:
    return _normalize_provider_error(
        status_code=503,
        title="Provider Transport Failure",
        detail=detail,
        code="provider_transport_failure",
        type_suffix="provider-transport-failure",
    )


def provider_rate_limited(
    detail: str = "Provider lifecycle operation is rate-limited.",
    *,
    retry_after_seconds: int | None = None,
) -> ProviderLifecycleProblem:
    return _normalize_provider_error(
        status_code=429,
        title="Provider Rate Limited",
        detail=detail,
        code="provider_rate_limited",
        type_suffix="provider-rate-limited",
        retry_after_seconds=retry_after_seconds,
    )


_REFRESH_FAILURE_TO_EXTERNAL_CODE: dict[str, str] = {
    "provider_expired": "provider_expired",
    "provider_revoked": "provider_revoked",
    "provider_invalid_grant": "provider_revoked",
    "provider_invalid_client": "provider_revoked",
    "provider_refresh_token_missing": "provider_revoked",
    "provider_scope_insufficient": "provider_scope_insufficient",
    "provider_rate_limited": "provider_rate_limited",
    "provider_transport_failure": "provider_transport_failure",
    "provider_refresh_not_implemented": "provider_transport_failure",
}


def _first_nonempty(values: Iterable[object | None]) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _refresh_state_from_snapshot(
    *,
    lifecycle_status: str | None,
    next_refresh_due_at: datetime | None,
    last_refresh_at: datetime | None,
    last_failure_class: str | None,
    now: datetime,
) -> str:
    if lifecycle_status == "revoked":
        return "failed"
    if lifecycle_status == "degraded" or last_failure_class:
        return "failed"
    if next_refresh_due_at is not None and _as_utc(next_refresh_due_at) <= now:
        return "due"
    if last_refresh_at is not None:
        return "fresh"
    if next_refresh_due_at is not None:
        return "fresh"
    return "not_attempted"


def _refresh_result_state_from_snapshot(
    *,
    lifecycle_status: str | None,
    next_refresh_due_at: datetime | None,
    last_refresh_at: datetime | None,
    last_failure_class: str | None,
    now: datetime,
) -> str:
    if lifecycle_status == "revoked":
        return "failed"
    if last_failure_class:
        return "failed"
    if next_refresh_due_at is not None and _as_utc(next_refresh_due_at) <= now:
        return "due"
    if last_refresh_at is not None:
        return "succeeded"
    if next_refresh_due_at is not None:
        return "fresh"
    return "not_attempted"


def _lifecycle_state_from_snapshot(
    *,
    connection_status: str,
    credential_lifecycle_status: str | None,
    expires_at: datetime | None,
    now: datetime,
) -> str:
    if connection_status == "pending":
        return "authorization_pending"
    if connection_status == "disabled":
        return "revoked"
    if credential_lifecycle_status == "revoked":
        return "revoked"
    if expires_at is not None and _as_utc(expires_at) <= now:
        return "expired"
    if credential_lifecycle_status in {"active", "degraded"}:
        return "connected"
    return "reconnect_required"


def _external_error_code_for_failure_class(failure_class: str | None) -> str | None:
    if not failure_class:
        return None
    normalized = failure_class.strip().lower()
    if not normalized:
        return None
    return _REFRESH_FAILURE_TO_EXTERNAL_CODE.get(normalized, "provider_transport_failure")


def _latest_refresh_attempt_at(*, last_failure_at: datetime | None, last_refresh_at: datetime | None) -> datetime | None:
    if last_failure_at is None:
        return last_refresh_at
    if last_refresh_at is None:
        return last_failure_at
    return last_failure_at if _as_utc(last_failure_at) >= _as_utc(last_refresh_at) else last_refresh_at


def _provider_problem_from_adapter_error(exc: OAuthLifecycleAdapterError) -> ProviderLifecycleProblem:
    if isinstance(exc, OAuthLifecycleRefreshError):
        external_code = _external_error_code_for_failure_class(exc.failure_class)
        if external_code == "provider_revoked":
            return provider_revoked()
        if external_code == "provider_scope_insufficient":
            return provider_scope_insufficient()
        if external_code == "provider_rate_limited":
            return provider_rate_limited(retry_after_seconds=exc.retry_after_seconds)
        return provider_transport_failure()
    if isinstance(exc, OAuthLifecycleNotImplementedError):
        return provider_transport_failure()
    return provider_transport_failure()


def _safe_connection_metadata(
    *,
    provider_account_id: str,
    granted_scope: str | None,
    account_metadata: dict[str, str],
) -> dict[str, object]:
    return sanitize_for_transport(
        {
            "oauth": {
                "provider_account_id": provider_account_id,
                "granted_scope": granted_scope,
                "account_metadata": account_metadata,
            }
        }
    )


class ProviderOAuthLifecycleRuntimeService:
    def __init__(self, dispatcher: ProviderOAuthLifecycleDispatcher | None = None) -> None:
        self._dispatcher = dispatcher or ProviderOAuthLifecycleDispatcher()

    async def initiate_authorization(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        user_id: UUID,
        platform: str,
        correlation_id: UUID,
        platform_account_id: str,
        redirect_uri: str,
        requested_scopes: tuple[str, ...] | None = None,
    ) -> ProviderOAuthAuthorizeRuntimeResult:
        now = _utcnow()
        state_reference = issue_state_reference()
        expires_at = now + DEFAULT_AUTHORIZATION_TTL

        try:
            authorize_result = await self._dispatcher.build_authorize_url(
                platform=platform,
                request=OAuthAuthorizeURLRequest(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    correlation_id=correlation_id,
                    redirect_uri=redirect_uri,
                    state_nonce=state_reference,
                    requested_scopes=requested_scopes,
                ),
            )
        except KeyError as exc:
            raise provider_not_connected() from exc
        except OAuthLifecycleAdapterError as exc:
            raise _provider_problem_from_adapter_error(exc) from exc

        provider_metadata = dict(authorize_result.provider_session_metadata or {})
        provider_metadata["platform_account_id"] = platform_account_id
        if requested_scopes:
            provider_metadata["requested_scopes"] = list(requested_scopes)
        await OAuthHandshakeStateService.create_session(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            platform=platform,
            expires_at=expires_at,
            state_reference=state_reference,
            redirect_uri=redirect_uri,
            provider_session_metadata=sanitize_for_transport(provider_metadata),
        )

        return ProviderOAuthAuthorizeRuntimeResult(
            tenant_id=tenant_id,
            platform=platform,
            lifecycle_state="authorization_pending",
            authorization_url=authorize_result.authorization_url,
            state_reference=state_reference,
            state_expires_at=expires_at,
            data_freshness_seconds=0,
            last_updated=now,
        )

    async def complete_callback(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        user_id: UUID,
        platform: str,
        correlation_id: UUID,
        state_reference: str,
        authorization_code: str | None,
        provider_error_code: str | None,
    ) -> ProviderOAuthCallbackRuntimeResult:
        if provider_error_code:
            lowered = provider_error_code.strip().lower()
            if "rate" in lowered or "limit" in lowered:
                raise provider_rate_limited()
            if lowered in {"access_denied", "insufficient_scope"} or "scope" in lowered:
                raise provider_scope_insufficient(detail="Provider authorization was denied.")
            raise provider_revoked(detail="Provider authorization is no longer valid and requires reconnect.")
        if not authorization_code:
            raise ValueError("Provider callback code is required.")

        now = _utcnow()
        try:
            consumed = await OAuthHandshakeStateService.consume_session(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                platform=platform,
                state_reference=state_reference,
                now=now,
            )
        except OAuthHandshakeStateBindingError as exc:
            raise provider_not_connected() from exc
        except OAuthHandshakeStateNotFoundError as exc:
            raise provider_not_connected() from exc
        except OAuthHandshakeStateReplayError as exc:
            raise provider_expired(detail="Provider authorization session has already been consumed.") from exc
        except OAuthHandshakeStateExpiredError as exc:
            raise provider_expired() from exc
        except OAuthHandshakeStateAbortedError as exc:
            raise provider_revoked() from exc

        try:
            state_result = await self._dispatcher.validate_callback_state(
                platform=platform,
                request=OAuthCallbackStateValidationRequest(
                    expected_state_nonce=state_reference,
                    received_state_nonce=state_reference,
                ),
            )
            if not state_result.is_valid:
                raise provider_expired(detail="Provider authorization session state mismatch.")

            exchanged = await self._dispatcher.exchange_auth_code(
                platform=platform,
                request=OAuthCodeExchangeRequest(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    correlation_id=correlation_id,
                    authorization_code=authorization_code,
                    redirect_uri=consumed.redirect_uri or "",
                    code_verifier=consumed.pkce_verifier,
                ),
            )
            account_metadata = await self._dispatcher.fetch_account_metadata(
                platform=platform,
                request=OAuthAccountMetadataRequest(
                    tenant_id=tenant_id,
                    correlation_id=correlation_id,
                    provider_account_id=exchanged.provider_account_id,
                    access_token=exchanged.access_token,
                ),
            )
        except ProviderLifecycleProblem:
            raise
        except KeyError as exc:
            raise provider_not_connected() from exc
        except OAuthLifecycleAdapterError as exc:
            raise _provider_problem_from_adapter_error(exc) from exc

        provider_metadata = consumed.provider_session_metadata or {}
        platform_account_id = _first_nonempty(
            (
                provider_metadata.get("platform_account_id")
                if isinstance(provider_metadata, dict)
                else None,
                account_metadata.provider_account_id,
                exchanged.provider_account_id,
            )
        )
        if platform_account_id is None:
            raise provider_not_connected()

        await PlatformConnectionService.upsert_connection(
            session,
            tenant_id=tenant_id,
            platform=platform,
            platform_account_id=platform_account_id,
            status="active",
            metadata=_safe_connection_metadata(
                provider_account_id=account_metadata.provider_account_id,
                granted_scope=account_metadata.granted_scope,
                account_metadata=account_metadata.account_metadata,
            ),
        )
        key_id, encryption_key = get_platform_encryption_material_for_write()
        stored = await PlatformCredentialStore.upsert_tokens(
            session,
            tenant_id=tenant_id,
            platform=platform,
            platform_account_id=platform_account_id,
            access_token=exchanged.access_token,
            refresh_token=exchanged.refresh_token,
            expires_at=exchanged.expires_at,
            scope=account_metadata.granted_scope or exchanged.scope,
            token_type=exchanged.token_type,
            key_id=key_id,
            encryption_key=encryption_key,
        )
        refresh_state = _refresh_state_from_snapshot(
            lifecycle_status=stored.get("lifecycle_status"),
            next_refresh_due_at=stored.get("next_refresh_due_at"),
            last_refresh_at=stored.get("last_refresh_at"),
            last_failure_class=stored.get("last_failure_class"),
            now=now,
        )
        return ProviderOAuthCallbackRuntimeResult(
            tenant_id=tenant_id,
            platform=platform,
            platform_account_id=platform_account_id,
            lifecycle_state="connected",
            refresh_state=refresh_state,
            data_freshness_seconds=0,
            last_updated=now,
        )

    async def get_status(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        user_id: UUID,
        platform: str,
        platform_account_id: str | None,
    ) -> ProviderOAuthStatusRuntimeResult:
        now = _utcnow()
        try:
            connection = await PlatformConnectionService.get_connection(
                session,
                tenant_id=tenant_id,
                platform=platform,
                platform_account_id=platform_account_id,
            )
        except PlatformConnectionNotFoundError:
            pending = await OAuthHandshakeStateService.latest_pending_session(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                platform=platform,
                now=now,
            )
            if pending is None:
                raise provider_not_connected()
            pending_account_id = _first_nonempty(
                (
                    (pending.provider_session_metadata or {}).get("platform_account_id")
                    if isinstance(pending.provider_session_metadata, dict)
                    else None,
                    platform_account_id,
                )
            ) or "pending"
            return ProviderOAuthStatusRuntimeResult(
                tenant_id=tenant_id,
                platform=platform,
                platform_account_id=pending_account_id,
                lifecycle_state="authorization_pending",
                refresh_state="not_attempted",
                expires_at=None,
                scope=None,
                data_freshness_seconds=max(
                    0,
                    int((now - _as_utc(pending.updated_at)).total_seconds()),
                ),
                last_updated=pending.updated_at,
            )

        snapshot = await PlatformCredentialStore.get_latest_lifecycle_snapshot_for_connection(
            session,
            tenant_id=tenant_id,
            connection_id=UUID(str(connection["id"])),
        )
        if snapshot is None:
            lifecycle_state = "revoked" if connection.get("status") == "disabled" else "reconnect_required"
            refresh_state = "failed" if lifecycle_state == "revoked" else "not_attempted"
            last_updated = connection.get("updated_at") or now
            return ProviderOAuthStatusRuntimeResult(
                tenant_id=tenant_id,
                platform=platform,
                platform_account_id=connection["platform_account_id"],
                lifecycle_state=lifecycle_state,
                refresh_state=refresh_state,
                expires_at=None,
                scope=None,
                data_freshness_seconds=max(0, int((now - _as_utc(last_updated)).total_seconds())),
                last_updated=last_updated,
            )

        lifecycle_state = _lifecycle_state_from_snapshot(
            connection_status=str(connection.get("status") or "active"),
            credential_lifecycle_status=snapshot.lifecycle_status,
            expires_at=snapshot.expires_at,
            now=now,
        )
        refresh_state = _refresh_state_from_snapshot(
            lifecycle_status=snapshot.lifecycle_status,
            next_refresh_due_at=snapshot.next_refresh_due_at,
            last_refresh_at=snapshot.last_refresh_at,
            last_failure_class=snapshot.last_failure_class,
            now=now,
        )
        return ProviderOAuthStatusRuntimeResult(
            tenant_id=tenant_id,
            platform=platform,
            platform_account_id=connection["platform_account_id"],
            lifecycle_state=lifecycle_state,
            refresh_state=refresh_state,
            expires_at=snapshot.expires_at,
            scope=snapshot.scope,
            data_freshness_seconds=max(0, int((now - _as_utc(snapshot.updated_at)).total_seconds())),
            last_updated=snapshot.updated_at,
        )

    async def get_refresh_state(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        user_id: UUID,
        platform: str,
    ) -> ProviderOAuthRefreshStateRuntimeResult:
        now = _utcnow()
        try:
            connection = await PlatformConnectionService.get_connection(
                session,
                tenant_id=tenant_id,
                platform=platform,
                platform_account_id=None,
            )
        except PlatformConnectionNotFoundError:
            pending = await OAuthHandshakeStateService.latest_pending_session(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                platform=platform,
                now=now,
            )
            if pending is None:
                raise provider_not_connected()
            return ProviderOAuthRefreshStateRuntimeResult(
                tenant_id=tenant_id,
                platform=platform,
                lifecycle_state="authorization_pending",
                refresh_state="not_attempted",
                next_refresh_due_at=None,
                last_refresh_attempt_at=None,
                last_refresh_success_at=None,
                last_error_code=None,
                data_freshness_seconds=max(0, int((now - _as_utc(pending.updated_at)).total_seconds())),
                last_updated=pending.updated_at,
            )

        snapshot = await PlatformCredentialStore.get_latest_lifecycle_snapshot_for_connection(
            session,
            tenant_id=tenant_id,
            connection_id=UUID(str(connection["id"])),
        )
        if snapshot is None:
            if connection.get("status") == "disabled":
                raise provider_revoked()
            last_updated = connection.get("updated_at") or now
            return ProviderOAuthRefreshStateRuntimeResult(
                tenant_id=tenant_id,
                platform=platform,
                lifecycle_state="reconnect_required",
                refresh_state="not_attempted",
                next_refresh_due_at=None,
                last_refresh_attempt_at=None,
                last_refresh_success_at=None,
                last_error_code=None,
                data_freshness_seconds=max(0, int((now - _as_utc(last_updated)).total_seconds())),
                last_updated=last_updated,
            )

        lifecycle_state = _lifecycle_state_from_snapshot(
            connection_status=str(connection.get("status") or "active"),
            credential_lifecycle_status=snapshot.lifecycle_status,
            expires_at=snapshot.expires_at,
            now=now,
        )
        external_error_code = _external_error_code_for_failure_class(snapshot.last_failure_class)
        if lifecycle_state == "revoked":
            raise provider_revoked()
        if external_error_code == "provider_rate_limited":
            retry_after = None
            if snapshot.next_refresh_due_at is not None and _as_utc(snapshot.next_refresh_due_at) > now:
                retry_after = max(1, int((_as_utc(snapshot.next_refresh_due_at) - now).total_seconds()))
            raise provider_rate_limited(retry_after_seconds=retry_after)
        if external_error_code == "provider_scope_insufficient":
            raise provider_scope_insufficient()
        if external_error_code == "provider_transport_failure":
            raise provider_transport_failure()

        refresh_state = _refresh_result_state_from_snapshot(
            lifecycle_status=snapshot.lifecycle_status,
            next_refresh_due_at=snapshot.next_refresh_due_at,
            last_refresh_at=snapshot.last_refresh_at,
            last_failure_class=snapshot.last_failure_class,
            now=now,
        )
        last_refresh_attempt_at = _latest_refresh_attempt_at(
            last_failure_at=snapshot.last_failure_at,
            last_refresh_at=snapshot.last_refresh_at,
        )
        return ProviderOAuthRefreshStateRuntimeResult(
            tenant_id=tenant_id,
            platform=platform,
            lifecycle_state=lifecycle_state,
            refresh_state=refresh_state,
            next_refresh_due_at=snapshot.next_refresh_due_at,
            last_refresh_attempt_at=last_refresh_attempt_at,
            last_refresh_success_at=snapshot.last_refresh_at,
            last_error_code=external_error_code,
            data_freshness_seconds=max(0, int((now - _as_utc(snapshot.updated_at)).total_seconds())),
            last_updated=snapshot.updated_at,
        )

    async def disconnect(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        platform: str,
        correlation_id: UUID,
        reason: str,
    ) -> ProviderOAuthDisconnectRuntimeResult:
        now = _utcnow()
        try:
            connection = await PlatformConnectionService.get_connection(
                session,
                tenant_id=tenant_id,
                platform=platform,
                platform_account_id=None,
            )
        except PlatformConnectionNotFoundError as exc:
            raise provider_not_connected() from exc

        disconnected_at = now
        try:
            credentials = await PlatformCredentialService.get_credentials(
                session,
                tenant_id=tenant_id,
                connection_id=UUID(str(connection["id"])),
                allow_expired=True,
            )
            disconnected = await self._dispatcher.revoke_disconnect(
                platform=platform,
                request=OAuthDisconnectRequest(
                    tenant_id=tenant_id,
                    correlation_id=correlation_id,
                    provider_account_id=connection["platform_account_id"],
                    access_token=credentials.access_token,
                    refresh_token=credentials.refresh_token,
                    reason=reason,
                ),
            )
            disconnected_at = disconnected.revoked_at
            await PlatformCredentialStore.mark_revoked(
                session,
                tenant_id=tenant_id,
                credential_id=credentials.id,
                revoked_at=disconnected_at,
            )
        except PlatformCredentialNotFoundError:
            pass
        except KeyError as exc:
            raise provider_not_connected() from exc
        except OAuthLifecycleAdapterError as exc:
            raise _provider_problem_from_adapter_error(exc) from exc

        await PlatformConnectionService.upsert_connection(
            session,
            tenant_id=tenant_id,
            platform=platform,
            platform_account_id=connection["platform_account_id"],
            status="disabled",
            metadata=sanitize_for_transport(connection.get("metadata")),
        )
        return ProviderOAuthDisconnectRuntimeResult(
            tenant_id=tenant_id,
            platform=platform,
            lifecycle_state="revoked",
            disconnected_at=disconnected_at,
            data_freshness_seconds=0,
            last_updated=disconnected_at,
        )
