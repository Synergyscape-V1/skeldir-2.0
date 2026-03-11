"""
Provider-neutral OAuth lifecycle dispatch wrapper (B1.3-P5).

This module gives route/service call sites a single adapter-backed seam.
"""

from __future__ import annotations

from app.services.provider_oauth_lifecycle import (
    DEFAULT_OAUTH_LIFECYCLE_REGISTRY,
    OAuthAccountMetadataRequest,
    OAuthAccountMetadataResult,
    OAuthAuthorizeURLRequest,
    OAuthAuthorizeURLResult,
    OAuthCallbackStateValidationRequest,
    OAuthCallbackStateValidationResult,
    OAuthCodeExchangeRequest,
    OAuthDisconnectRequest,
    OAuthDisconnectResult,
    OAuthLifecycleRegistry,
    OAuthTokenRefreshRequest,
    OAuthTokenSet,
)


class ProviderOAuthLifecycleDispatcher:
    def __init__(self, registry: OAuthLifecycleRegistry | None = None) -> None:
        self._registry = registry or DEFAULT_OAUTH_LIFECYCLE_REGISTRY

    async def build_authorize_url(
        self,
        *,
        platform: str,
        request: OAuthAuthorizeURLRequest,
    ) -> OAuthAuthorizeURLResult:
        adapter = self._registry.get_adapter(platform)
        return await adapter.build_authorize_url(request)

    async def validate_callback_state(
        self,
        *,
        platform: str,
        request: OAuthCallbackStateValidationRequest,
    ) -> OAuthCallbackStateValidationResult:
        adapter = self._registry.get_adapter(platform)
        return await adapter.validate_callback_state(request)

    async def exchange_auth_code(
        self,
        *,
        platform: str,
        request: OAuthCodeExchangeRequest,
    ) -> OAuthTokenSet:
        adapter = self._registry.get_adapter(platform)
        return await adapter.exchange_auth_code(request)

    async def refresh_token(
        self,
        *,
        platform: str,
        request: OAuthTokenRefreshRequest,
    ) -> OAuthTokenSet:
        adapter = self._registry.get_adapter(platform)
        return await adapter.refresh_token(request)

    async def revoke_disconnect(
        self,
        *,
        platform: str,
        request: OAuthDisconnectRequest,
    ) -> OAuthDisconnectResult:
        adapter = self._registry.get_adapter(platform)
        return await adapter.revoke_disconnect(request)

    async def fetch_account_metadata(
        self,
        *,
        platform: str,
        request: OAuthAccountMetadataRequest,
    ) -> OAuthAccountMetadataResult:
        adapter = self._registry.get_adapter(platform)
        return await adapter.fetch_account_metadata(request)
