"""
ORM Models Package.

Exposes all SQLAlchemy ORM models for B0.4 ingestion pipeline.

Models:
    - Base: Declarative base for all models
    - TenantMixin: Common mixin for tenant-scoped tables
    - UserIdentity: Opaque user identity registry (no raw email/IP)
    - TenantMembership: User-to-tenant membership bindings
    - Role: Role catalog (admin/manager/viewer)
    - TenantMembershipRole: Tenant-scoped role assignments
    - AttributionEvent: Revenue-generating attribution events (RLS enabled)
    - DeadEvent: Dead-letter queue for failed ingestion (RLS enabled)
    - ChannelTaxonomy: Marketing channel reference data (no RLS)
    - LLMApiCall: LLM API audit rows (RLS enabled)
    - LLMMonthlyCost: LLM monthly cost aggregates (RLS enabled)
    - Investigation: LLM investigation jobs (RLS enabled)
    - BudgetOptimizationJob: LLM budget optimization jobs (RLS enabled)

Usage:
    from app.models import AttributionEvent, DeadEvent, ChannelTaxonomy
    from app.db.session import get_session

    async with get_session(tenant_id=some_uuid) as session:
        event = AttributionEvent(...)
        session.add(event)
        await session.commit()
"""

from app.models.attribution_event import AttributionEvent
from app.models.auth_substrate import (
    AuthAccessTokenDenylist,
    AuthRefreshToken,
    AuthUserTokenCutoff,
    Role,
    Tenant,
    TenantMembership,
    TenantMembershipRole,
    UserIdentity,
)
from app.models.attribution_commerce_identity import AttributionCommerceIdentity
from app.models.base import Base, TenantMixin
from app.models.channel_taxonomy import ChannelTaxonomy
from app.models.compliance_audit_ledger import ComplianceAuditLedger
from app.models.dead_event import DeadEvent
from app.models.ephemeral_resolution import (
    EphemeralClickResolution,
    EphemeralOrderResolution,
)
from app.models.llm import (
    BudgetJob,
    BudgetOptimizationJob,
    Investigation,
    LLMApiCall,
    LLMBudgetReservation,
    LLMBreakerState,
    LLMHourlyShutoffState,
    LLMMonthlyBudgetState,
    LLMMonthlyCost,
    LLMValidationFailure,
    LLMSemanticCache,
)
from app.models.oauth_handshake_session import OAuthHandshakeSession
from app.models.platform_connection import PlatformConnection
from app.models.platform_credential import PlatformCredential
from app.models.raw_event_payload import RawEventPayload
from app.models.revenue_cache import RevenueCacheEntry
from app.models.session_authority import SessionAuthority
from app.models.webhook_ingress_identity import WebhookIngressIdentity

_BAYESIAN_EXPORTS = {
    "BayesianModelFit",
    "BayesianArtifact",
    "BayesianArtifactStorageQuota",
    "B24DirtyEvent",
    "B24ActiveExecutionLease",
    "B24FitDispatchOutbox",
    "B24FitRecoveryOutbox",
}


def __getattr__(name: str) -> object:
    if name in _BAYESIAN_EXPORTS:
        from app.bayesian import models as bayesian_models

        return getattr(bayesian_models, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Base",
    "TenantMixin",
    "Tenant",
    "UserIdentity",
    "TenantMembership",
    "Role",
    "TenantMembershipRole",
    "AuthRefreshToken",
    "AuthAccessTokenDenylist",
    "AuthUserTokenCutoff",
    "AttributionEvent",
    "AttributionCommerceIdentity",
    "DeadEvent",
    "ComplianceAuditLedger",
    "ChannelTaxonomy",
    "LLMApiCall",
    "LLMMonthlyCost",
    "LLMValidationFailure",
    "LLMMonthlyBudgetState",
    "LLMBudgetReservation",
    "LLMSemanticCache",
    "LLMBreakerState",
    "LLMHourlyShutoffState",
    "BudgetJob",
    "Investigation",
    "BudgetOptimizationJob",
    "OAuthHandshakeSession",
    "PlatformConnection",
    "PlatformCredential",
    "RawEventPayload",
    "RevenueCacheEntry",
    "SessionAuthority",
    "EphemeralOrderResolution",
    "EphemeralClickResolution",
    "WebhookIngressIdentity",
    "BayesianModelFit",
    "BayesianArtifact",
    "BayesianArtifactStorageQuota",
    "B24DirtyEvent",
    "B24ActiveExecutionLease",
    "B24FitDispatchOutbox",
    "B24FitRecoveryOutbox",
]
