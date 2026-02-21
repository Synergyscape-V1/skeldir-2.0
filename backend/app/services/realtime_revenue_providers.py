"""
Realtime revenue provider interfaces, registry, and aggregation helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Protocol
from uuid import UUID

import asyncio
import json
import http.client
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock as clock_module
from app.core.config import settings
from app.db.session import set_tenant_guc_async
from app.models.platform_connection import PlatformConnection
from app.services.platform_credentials import (
    PlatformCredentialExpiredError,
    PlatformCredentialNotFoundError,
    PlatformCredentialService,
)

DEFAULT_INTERVAL = "minute"
DEFAULT_CURRENCY = "USD"
DEFAULT_UPGRADE_NOTICE = (
    "Revenue data pending reconciliation. Full statistical verification available in Phase B2.6."
)


@dataclass(frozen=True)
class ProviderConnection:
    id: UUID
    platform: str
    platform_account_id: str
    status: str
    metadata: dict | None
    updated_at: datetime | None


@dataclass(frozen=True)
class ProviderCredentials:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scope: str | None
    token_type: str | None
    key_id: str


@dataclass(frozen=True)
class ProviderContext:
    tenant_id: UUID
    platform_connection: ProviderConnection
    credentials: ProviderCredentials
    correlation_id: UUID
    now: datetime


@dataclass(frozen=True)
class ProviderRevenueResult:
    total_revenue_cents: int
    event_count: int
    data_as_of: datetime
    source: str
    rate_limit_retry_after_seconds: int | None = None


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: dict[str, str]
    json_body: dict

    def json(self) -> dict:
        return self.json_body


class AsyncHttpClient(Protocol):
    async def get(
        self, path: str, *, headers: dict[str, str], params: dict[str, str]
    ) -> HttpResponse:
        raise NotImplementedError


class DefaultHttpClient:
    def __init__(self, base_url: str, *, timeout_seconds: float = 5.0) -> None:
        self._base_url = base_url
        self._timeout_seconds = max(0.1, float(timeout_seconds))

    async def get(
        self, path: str, *, headers: dict[str, str], params: dict[str, str]
    ) -> HttpResponse:
        return await asyncio.to_thread(self._get_sync, path, headers, params)

    def _get_sync(
        self, path: str, headers: dict[str, str], params: dict[str, str]
    ) -> HttpResponse:
        full_url = urljoin(self._base_url, path)
        parsed = urlsplit(full_url)
        query_params = dict(parse_qsl(parsed.query))
        query_params.update(params)
        query = urlencode(query_params)
        target = urlunsplit(("", "", parsed.path, query, ""))

        connection_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        connection = connection_cls(parsed.netloc, timeout=self._timeout_seconds)
        try:
            connection.request("GET", target, headers=headers)
            response = connection.getresponse()
            raw = response.read()
            try:
                body = json.loads(raw.decode("utf-8")) if raw else {}
            except (UnicodeDecodeError, json.JSONDecodeError):
                body = {}
            headers_map = {key: value for key, value in response.getheaders()}
            return HttpResponse(
                status_code=int(response.status),
                headers=headers_map,
                json_body=body if isinstance(body, dict) else {},
            )
        finally:
            connection.close()


class ProviderFetchError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        error_type: str = "provider_error",
        retry_after_seconds: int | None = None,
        provider_key: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.retry_after_seconds = retry_after_seconds
        self.provider_key = provider_key


class RevenueProvider(Protocol):
    provider_key: str

    async def fetch_realtime(self, ctx: ProviderContext) -> ProviderRevenueResult:
        raise NotImplementedError


class ProviderRegistry:
    def __init__(self, providers: Iterable[RevenueProvider] | None = None) -> None:
        self._providers: dict[str, RevenueProvider] = {}
        if providers:
            for provider in providers:
                self.register(provider)

    def register(self, provider: RevenueProvider) -> None:
        self._providers[provider.provider_key] = provider

    def get(self, provider_key: str) -> RevenueProvider:
        provider = self._providers.get(provider_key)
        if not provider:
            raise KeyError(f"Provider '{provider_key}' not registered")
        return provider

    def has(self, provider_key: str) -> bool:
        return provider_key in self._providers

    def keys(self) -> list[str]:
        return sorted(self._providers.keys())


class StripeRevenueProvider:
    provider_key = "stripe"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        client: AsyncHttpClient | None = None,
        max_attempts: int = 2,
    ) -> None:
        self._base_url = base_url or settings.STRIPE_BASE_URL or "https://api.stripe.com"
        self._timeout_seconds = float(timeout_seconds) if timeout_seconds is not None else 5.0
        self._client = client
        self._max_attempts = max(1, int(max_attempts))

    async def fetch_realtime(self, ctx: ProviderContext) -> ProviderRevenueResult:
        headers = {
            "Authorization": f"Bearer {ctx.credentials.access_token}",
            "X-Correlation-ID": str(ctx.correlation_id),
        }
        if ctx.platform_connection.platform_account_id:
            headers["Stripe-Account"] = ctx.platform_connection.platform_account_id

        params = {"limit": "100"}
        client = self._client or DefaultHttpClient(
            self._base_url, timeout_seconds=self._timeout_seconds
        )

        for attempt in range(1, self._max_attempts + 1):
            try:
                response = await client.get(
                    "/v1/balance_transactions",
                    headers=headers,
                    params=params,
                )
            except Exception as exc:
                if attempt < self._max_attempts:
                    continue
                raise ProviderFetchError(
                    "stripe_request_failed",
                    error_type="network",
                    provider_key=self.provider_key,
                ) from exc

            if response.status_code in (401, 403):
                raise ProviderFetchError(
                    "stripe_auth_failed",
                    error_type="auth",
                    provider_key=self.provider_key,
                )

            if response.status_code == 429:
                retry_after = _parse_retry_after(response.headers)
                raise ProviderFetchError(
                    "stripe_rate_limited",
                    error_type="rate_limit",
                    retry_after_seconds=retry_after,
                    provider_key=self.provider_key,
                )

            if 500 <= response.status_code:
                if attempt < self._max_attempts:
                    continue
                raise ProviderFetchError(
                    f"stripe_upstream_{response.status_code}",
                    error_type="upstream",
                    provider_key=self.provider_key,
                )

            if response.status_code >= 400:
                raise ProviderFetchError(
                    f"stripe_http_{response.status_code}",
                    error_type="upstream",
                    provider_key=self.provider_key,
                )

            payload = response.json()
            data = payload.get("data") or []
            total_cents = 0
            event_count = 0
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                amount = entry.get("amount")
                if amount is None:
                    continue
                if entry.get("type") != "charge":
                    continue
                try:
                    amount_int = int(amount)
                except (TypeError, ValueError):
                    continue
                if amount_int <= 0:
                    continue
                total_cents += amount_int
                event_count += 1

            return ProviderRevenueResult(
                total_revenue_cents=total_cents,
                event_count=event_count,
                data_as_of=ctx.now,
                source=self.provider_key,
            )

        raise ProviderFetchError(
            "stripe_unreachable",
            error_type="network",
            provider_key=self.provider_key,
        )


class DummyRevenueProvider:
    provider_key = "dummy"

    def __init__(
        self,
        *,
        raw_revenue_micros: int = 12_340_000,
        event_count: int = 3,
    ) -> None:
        self._raw_revenue_micros = int(raw_revenue_micros)
        self._event_count = int(event_count)

    async def fetch_realtime(self, ctx: ProviderContext) -> ProviderRevenueResult:
        total_cents = micros_to_cents(self._raw_revenue_micros)
        return ProviderRevenueResult(
            total_revenue_cents=total_cents,
            event_count=self._event_count,
            data_as_of=ctx.now,
            source=self.provider_key,
        )


DEFAULT_PROVIDER_REGISTRY = ProviderRegistry(
    providers=[StripeRevenueProvider(), DummyRevenueProvider()]
)


def micros_to_cents(micros: int) -> int:
    if micros <= 0:
        return 0
    return (micros + 5_000) // 10_000


def _utcnow() -> datetime:
    return clock_module.utcnow()


def _parse_retry_after(headers: dict[str, str]) -> int | None:
    value = headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(1, int(value))
    except ValueError:
        return None


def _sanitize_now(value: datetime | None) -> datetime:
    if value is None:
        return _utcnow()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _select_active_connections(
    connections: Iterable[PlatformConnection],
) -> list[ProviderConnection]:
    selected: dict[str, ProviderConnection] = {}
    for connection in connections:
        platform_key = connection.platform
        if platform_key in selected:
            continue
        selected[platform_key] = ProviderConnection(
            id=connection.id,
            platform=platform_key,
            platform_account_id=connection.platform_account_id,
            status=connection.status,
            metadata=connection.connection_metadata,
            updated_at=connection.updated_at,
        )
    return [selected[key] for key in sorted(selected.keys())]


def build_realtime_revenue_fetcher(
    session: AsyncSession,
    correlation_id: UUID,
    *,
    now: datetime | None = None,
    registry: ProviderRegistry | None = None,
):
    async def _fetch(tenant_id: UUID):
        return await _fetch_realtime_revenue_snapshot(
            session,
            tenant_id,
            correlation_id,
            now=now,
            registry=registry,
        )

    return _fetch


async def _fetch_realtime_revenue_snapshot(
    session: AsyncSession,
    tenant_id: UUID,
    correlation_id: UUID,
    *,
    now: datetime | None = None,
    registry: ProviderRegistry | None = None,
):
    from app.services.realtime_revenue_cache import RealtimeRevenueSnapshot

    effective_now = _sanitize_now(now)
    registry = registry or DEFAULT_PROVIDER_REGISTRY

    await set_tenant_guc_async(session, tenant_id, local=False)

    query = (
        select(PlatformConnection)
        .where(
            PlatformConnection.tenant_id == tenant_id,
            PlatformConnection.status == "active",
        )
        .order_by(
            PlatformConnection.updated_at.desc(),
            PlatformConnection.platform.asc(),
            PlatformConnection.platform_account_id.asc(),
        )
    )
    result = await session.execute(query)
    connections = result.scalars().all()

    provider_connections = _select_active_connections(connections)
    supported_connections = [
        connection
        for connection in provider_connections
        if registry.has(connection.platform)
    ]

    if not supported_connections:
        return RealtimeRevenueSnapshot(
            tenant_id=tenant_id,
            interval=DEFAULT_INTERVAL,
            currency=DEFAULT_CURRENCY,
            revenue_total_cents=0,
            event_count=0,
            verified=False,
            data_as_of=effective_now,
            sources=[],
            confidence_score=None,
            upgrade_notice=DEFAULT_UPGRADE_NOTICE,
        )

    results: list[ProviderRevenueResult] = []
    for connection in supported_connections:
        provider = registry.get(connection.platform)
        try:
            credentials = await PlatformCredentialService.get_credentials(
                session,
                tenant_id=tenant_id,
                connection_id=connection.id,
            )
        except (PlatformCredentialNotFoundError, PlatformCredentialExpiredError) as exc:
            raise ProviderFetchError(
                "platform_credentials_missing",
                error_type="credential",
                provider_key=connection.platform,
            ) from exc
        except Exception as exc:
            raise ProviderFetchError(
                "platform_credentials_unavailable",
                error_type="credential",
                provider_key=connection.platform,
            ) from exc

        ctx = ProviderContext(
            tenant_id=tenant_id,
            platform_connection=connection,
            credentials=ProviderCredentials(
                access_token=credentials.access_token,
                refresh_token=credentials.refresh_token,
                expires_at=credentials.expires_at,
                scope=credentials.scope,
                token_type=credentials.token_type,
                key_id=credentials.key_id,
            ),
            correlation_id=correlation_id,
            now=effective_now,
        )

        result = await provider.fetch_realtime(ctx)
        results.append(result)

    total_revenue_cents = sum(result.total_revenue_cents for result in results)
    event_count = sum(result.event_count for result in results)
    data_as_of = max((result.data_as_of for result in results), default=effective_now)
    sources = [result.source for result in results]

    return RealtimeRevenueSnapshot(
        tenant_id=tenant_id,
        interval=DEFAULT_INTERVAL,
        currency=DEFAULT_CURRENCY,
        revenue_total_cents=max(0, int(total_revenue_cents)),
        event_count=max(0, int(event_count)),
        verified=False,
        data_as_of=_sanitize_now(data_as_of),
        sources=sources,
        confidence_score=None,
        upgrade_notice=DEFAULT_UPGRADE_NOTICE,
    )
