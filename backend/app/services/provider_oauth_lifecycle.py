"""
Provider-neutral OAuth lifecycle adapter layer (B1.3-P5).

This module defines a canonical lifecycle interface and registry-backed dispatch
surface that later runtime routes/workers consume. It intentionally does not
implement public FastAPI authorize/callback routes or refresh scheduling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Protocol
from urllib.parse import urlencode
from uuid import UUID

from app.core import clock as clock_module
from app.services.realtime_revenue_providers import ProviderRegistry

LifecycleProviderMode = Literal["runtime_backed", "internal_runtime_only"]
AdapterKind = Literal["runtime_scaffold", "deterministic_reference"]


@dataclass(frozen=True)
class OAuthAuthorizeURLRequest:
    tenant_id: UUID
    user_id: UUID
    correlation_id: UUID
    redirect_uri: str
    state_nonce: str
    code_challenge: str | None = None
    code_challenge_method: str | None = None


@dataclass(frozen=True)
class OAuthAuthorizeURLResult:
    authorization_url: str
    provider_session_metadata: dict[str, str]


@dataclass(frozen=True)
class OAuthCallbackStateValidationRequest:
    expected_state_nonce: str
    received_state_nonce: str


@dataclass(frozen=True)
class OAuthCallbackStateValidationResult:
    is_valid: bool
    failure_reason: str | None = None


@dataclass(frozen=True)
class OAuthCodeExchangeRequest:
    tenant_id: UUID
    user_id: UUID
    correlation_id: UUID
    authorization_code: str
    redirect_uri: str
    code_verifier: str | None = None


@dataclass(frozen=True)
class OAuthTokenRefreshRequest:
    tenant_id: UUID
    correlation_id: UUID
    refresh_token: str
    scope: str | None = None


@dataclass(frozen=True)
class OAuthTokenSet:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scope: str | None
    token_type: str | None
    provider_account_id: str


@dataclass(frozen=True)
class OAuthDisconnectRequest:
    tenant_id: UUID
    correlation_id: UUID
    provider_account_id: str
    access_token: str | None
    refresh_token: str | None
    reason: str | None = None


@dataclass(frozen=True)
class OAuthDisconnectResult:
    revoked: bool
    revoked_at: datetime


@dataclass(frozen=True)
class OAuthAccountMetadataRequest:
    tenant_id: UUID
    correlation_id: UUID
    provider_account_id: str | None
    access_token: str


@dataclass(frozen=True)
class OAuthAccountMetadataResult:
    provider_account_id: str
    granted_scope: str | None
    account_metadata: dict[str, str]


@dataclass(frozen=True)
class ProviderLifecycleCapability:
    provider_key: str
    mode: LifecycleProviderMode
    adapter_kind: AdapterKind
    supports_authorize_url: bool
    supports_callback_state_validation: bool
    supports_code_exchange: bool
    supports_token_refresh: bool
    supports_revoke_disconnect: bool
    supports_account_metadata: bool


class OAuthLifecycleAdapterError(RuntimeError):
    """Base adapter-layer runtime error."""


class OAuthLifecycleNotImplementedError(OAuthLifecycleAdapterError):
    """Raised when an adapter exists but runtime behavior is deferred."""


class OAuthLifecycleAdapter(Protocol):
    provider_key: str

    async def build_authorize_url(self, request: OAuthAuthorizeURLRequest) -> OAuthAuthorizeURLResult:
        raise NotImplementedError

    async def validate_callback_state(
        self,
        request: OAuthCallbackStateValidationRequest,
    ) -> OAuthCallbackStateValidationResult:
        raise NotImplementedError

    async def exchange_auth_code(self, request: OAuthCodeExchangeRequest) -> OAuthTokenSet:
        raise NotImplementedError

    async def refresh_token(self, request: OAuthTokenRefreshRequest) -> OAuthTokenSet:
        raise NotImplementedError

    async def revoke_disconnect(self, request: OAuthDisconnectRequest) -> OAuthDisconnectResult:
        raise NotImplementedError

    async def fetch_account_metadata(
        self,
        request: OAuthAccountMetadataRequest,
    ) -> OAuthAccountMetadataResult:
        raise NotImplementedError


OAUTH_LIFECYCLE_CAPABILITY_DECLARATIONS: dict[str, dict[str, str | bool]] = {
    "dummy": {
        "mode": "internal_runtime_only",
        "adapter_kind": "deterministic_reference",
        "supports_authorize_url": True,
        "supports_callback_state_validation": True,
        "supports_code_exchange": True,
        "supports_token_refresh": True,
        "supports_revoke_disconnect": True,
        "supports_account_metadata": True,
    },
    "stripe": {
        "mode": "runtime_backed",
        "adapter_kind": "runtime_scaffold",
        "supports_authorize_url": True,
        "supports_callback_state_validation": True,
        "supports_code_exchange": True,
        "supports_token_refresh": True,
        "supports_revoke_disconnect": True,
        "supports_account_metadata": True,
    },
}


def _utcnow() -> datetime:
    return clock_module.utcnow()


def _safe_suffix(value: str) -> str:
    cleaned = "".join(ch for ch in value if ch.isalnum()).lower()
    if not cleaned:
        return "stable"
    return cleaned[:24]


def _as_capabilities(
    declarations: dict[str, dict[str, str | bool]],
) -> tuple[ProviderLifecycleCapability, ...]:
    capabilities: list[ProviderLifecycleCapability] = []
    for provider_key in sorted(declarations):
        payload = declarations[provider_key]
        capabilities.append(
            ProviderLifecycleCapability(
                provider_key=provider_key,
                mode=str(payload["mode"]),  # type: ignore[arg-type]
                adapter_kind=str(payload["adapter_kind"]),  # type: ignore[arg-type]
                supports_authorize_url=bool(payload["supports_authorize_url"]),
                supports_callback_state_validation=bool(payload["supports_callback_state_validation"]),
                supports_code_exchange=bool(payload["supports_code_exchange"]),
                supports_token_refresh=bool(payload["supports_token_refresh"]),
                supports_revoke_disconnect=bool(payload["supports_revoke_disconnect"]),
                supports_account_metadata=bool(payload["supports_account_metadata"]),
            )
        )
    return tuple(capabilities)


class OAuthLifecycleRegistry:
    def __init__(
        self,
        *,
        adapters: list[OAuthLifecycleAdapter] | None = None,
        capabilities: tuple[ProviderLifecycleCapability, ...] | None = None,
    ) -> None:
        self._registry: ProviderRegistry[OAuthLifecycleAdapter] = ProviderRegistry()
        self._capabilities: dict[str, ProviderLifecycleCapability] = {}
        if capabilities:
            for capability in capabilities:
                self._capabilities[capability.provider_key] = capability
        if adapters:
            for adapter in adapters:
                self.register(adapter)

    def register(self, adapter: OAuthLifecycleAdapter) -> None:
        if adapter.provider_key not in self._capabilities:
            raise ValueError(f"missing lifecycle capability declaration for '{adapter.provider_key}'")
        self._registry.register(adapter)

    def get_adapter(self, provider_key: str) -> OAuthLifecycleAdapter:
        return self._registry.get(provider_key)

    def has_adapter(self, provider_key: str) -> bool:
        return self._registry.has(provider_key)

    def provider_keys(self) -> list[str]:
        return self._registry.keys()

    def capabilities(self) -> tuple[ProviderLifecycleCapability, ...]:
        return tuple(self._capabilities[key] for key in sorted(self._capabilities))

    def capability_for(self, provider_key: str) -> ProviderLifecycleCapability:
        capability = self._capabilities.get(provider_key)
        if capability is None:
            raise KeyError(f"lifecycle capability missing for provider '{provider_key}'")
        return capability


class DeterministicOAuthLifecycleAdapter:
    provider_key = "dummy"
    _authorize_base = "https://deterministic.provider.local/oauth/authorize"

    async def build_authorize_url(self, request: OAuthAuthorizeURLRequest) -> OAuthAuthorizeURLResult:
        query = {
            "client_id": "deterministic-client",
            "redirect_uri": request.redirect_uri,
            "response_type": "code",
            "state": request.state_nonce,
        }
        if request.code_challenge:
            query["code_challenge"] = request.code_challenge
        if request.code_challenge_method:
            query["code_challenge_method"] = request.code_challenge_method
        authorization_url = f"{self._authorize_base}?{urlencode(query)}"
        return OAuthAuthorizeURLResult(
            authorization_url=authorization_url,
            provider_session_metadata={
                "provider": self.provider_key,
                "state_nonce": request.state_nonce,
            },
        )

    async def validate_callback_state(
        self,
        request: OAuthCallbackStateValidationRequest,
    ) -> OAuthCallbackStateValidationResult:
        if request.expected_state_nonce == request.received_state_nonce:
            return OAuthCallbackStateValidationResult(is_valid=True, failure_reason=None)
        return OAuthCallbackStateValidationResult(is_valid=False, failure_reason="state_mismatch")

    async def exchange_auth_code(self, request: OAuthCodeExchangeRequest) -> OAuthTokenSet:
        suffix = _safe_suffix(request.authorization_code)
        expires_at = _utcnow() + timedelta(minutes=55)
        return OAuthTokenSet(
            access_token=f"det-access-{suffix}",
            refresh_token=f"det-refresh-{suffix}",
            expires_at=expires_at,
            scope="read_revenue write_connection",
            token_type="Bearer",
            provider_account_id=f"det-acct-{suffix[:12]}",
        )

    async def refresh_token(self, request: OAuthTokenRefreshRequest) -> OAuthTokenSet:
        suffix = _safe_suffix(request.refresh_token)
        expires_at = _utcnow() + timedelta(minutes=55)
        scope = request.scope or "read_revenue write_connection"
        return OAuthTokenSet(
            access_token=f"det-refresh-access-{suffix}",
            refresh_token=f"det-refresh-{suffix}",
            expires_at=expires_at,
            scope=scope,
            token_type="Bearer",
            provider_account_id=f"det-acct-{suffix[:12]}",
        )

    async def revoke_disconnect(self, request: OAuthDisconnectRequest) -> OAuthDisconnectResult:
        return OAuthDisconnectResult(
            revoked=True,
            revoked_at=_utcnow(),
        )

    async def fetch_account_metadata(
        self,
        request: OAuthAccountMetadataRequest,
    ) -> OAuthAccountMetadataResult:
        suffix = _safe_suffix(request.provider_account_id or request.access_token)
        return OAuthAccountMetadataResult(
            provider_account_id=f"det-acct-{suffix[:12]}",
            granted_scope="read_revenue write_connection",
            account_metadata={
                "provider": self.provider_key,
                "environment": "deterministic",
            },
        )


class StripeOAuthLifecycleAdapter:
    provider_key = "stripe"

    async def build_authorize_url(self, request: OAuthAuthorizeURLRequest) -> OAuthAuthorizeURLResult:
        raise OAuthLifecycleNotImplementedError(
            "stripe oauth authorize-url runtime behavior is deferred until B1.3-P6."
        )

    async def validate_callback_state(
        self,
        request: OAuthCallbackStateValidationRequest,
    ) -> OAuthCallbackStateValidationResult:
        raise OAuthLifecycleNotImplementedError(
            "stripe oauth callback-state validation runtime behavior is deferred until B1.3-P6."
        )

    async def exchange_auth_code(self, request: OAuthCodeExchangeRequest) -> OAuthTokenSet:
        raise OAuthLifecycleNotImplementedError(
            "stripe oauth code exchange runtime behavior is deferred until B1.3-P6."
        )

    async def refresh_token(self, request: OAuthTokenRefreshRequest) -> OAuthTokenSet:
        raise OAuthLifecycleNotImplementedError(
            "stripe oauth refresh runtime behavior is deferred until B1.3-P7."
        )

    async def revoke_disconnect(self, request: OAuthDisconnectRequest) -> OAuthDisconnectResult:
        raise OAuthLifecycleNotImplementedError(
            "stripe oauth revoke/disconnect runtime behavior is deferred until B1.3-P6."
        )

    async def fetch_account_metadata(
        self,
        request: OAuthAccountMetadataRequest,
    ) -> OAuthAccountMetadataResult:
        raise OAuthLifecycleNotImplementedError(
            "stripe oauth account metadata runtime behavior is deferred until B1.3-P6."
        )


DEFAULT_OAUTH_LIFECYCLE_CAPABILITIES = _as_capabilities(OAUTH_LIFECYCLE_CAPABILITY_DECLARATIONS)

DEFAULT_OAUTH_LIFECYCLE_REGISTRY = OAuthLifecycleRegistry(
    adapters=[
        StripeOAuthLifecycleAdapter(),
        DeterministicOAuthLifecycleAdapter(),
    ],
    capabilities=DEFAULT_OAUTH_LIFECYCLE_CAPABILITIES,
)
