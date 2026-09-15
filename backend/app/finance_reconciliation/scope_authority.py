"""B2.6-P2 canonical reconciliation scope, rail, and normalization authority.

Class closed here
-----------------
More than one reachable mechanism could assign canonical provider, rail,
currency, window, and scope meaning to B2.6 truth-path evidence: B2.6-side
platform helpers, route-local alias maps, serializer transforms, worker
helpers, config mappings, and compatibility wrappers. Their divergence is
silent: the same logical evidence classifies differently depending on which
code path observes it, unsupported evidence vanishes instead of receiving
an explicit disposition, and the denominator-driving universe drifts without
a merge-blocking signal.

Closure theorem: exactly one reachable B2.6 module executes governed
scope meaning. Every reconciliation candidate deterministically resolves to
exactly one of SUPPORTED_AND_IN_SCOPE, SUPPORTED_BUT_UNRESOLVED,
EXPLICITLY_EXCLUDED, or INVALID_OR_REFUSED, carrying canonical tenant,
provider, rail, currency, window, and scope-policy version. No route,
worker, serializer, exporter, SQL path, compatibility adapter, config
mapping, or alternate primitive on the truth path determines the same
semantic independently.

Sovereign sources composed, never reimplemented
-----------------------------------------------
* B2.3 ``verification_coverage`` supported provider and currency universes,
  read on use and checked against the scope-policy contract.
* P1 semantic contract scope-disposition vocabulary for exclusion reasons.
* Server-derived tenant UUID shape law; durable tenant existence and
  row-level isolation remain owned by ``tenant_authority`` and PostgreSQL.
* The persisted commerce clock
  (``webhook_ingress_identities.event_timestamp``) as the sole window
  membership authority; wall, worker, and statement clocks never consulted.

What this module does NOT do
----------------------------
* No durable state: no table, migration, trigger, view, function, role,
  grant, or RLS change. Absence of a persisted predicate is the physical
  closure of the UNKNOWN-admission class for P2.
* No money path: no amount parameter exists, so normalization cannot alter
  monetary values by construction.
* No second coverage arithmetic: aggregate mathematics stays sovereign in
  ``verification_coverage`` plus the independent oracle.
* No P3 reason taxonomy, no P4 snapshot, no worker, route, export, signing,
  estimation, counterfactual, or explanation dependency.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import UUID

import yaml  # type: ignore[import-untyped]


_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = (
    _PACKAGE_ROOT.parent
    if (_PACKAGE_ROOT.parent / "contracts/reconciliation").is_dir()
    else _PACKAGE_ROOT
)
B26_P2_SCOPE_POLICY_PATH = (
    _REPO_ROOT / "contracts/reconciliation/b2.6/scope-policy.v1.yaml"
)
B26_P2_SCOPE_POLICY_VERSION = "b2.6-p2-scope-policy-v1"

DISPOSITION_SUPPORTED_AND_IN_SCOPE = "SUPPORTED_AND_IN_SCOPE"
DISPOSITION_SUPPORTED_BUT_UNRESOLVED = "SUPPORTED_BUT_UNRESOLVED"
DISPOSITION_EXPLICITLY_EXCLUDED = "EXPLICITLY_EXCLUDED"
DISPOSITION_INVALID_OR_REFUSED = "INVALID_OR_REFUSED"

GOVERNED_P2_DISPOSITIONS = frozenset(
    {
        DISPOSITION_SUPPORTED_AND_IN_SCOPE,
        DISPOSITION_SUPPORTED_BUT_UNRESOLVED,
        DISPOSITION_EXPLICITLY_EXCLUDED,
        DISPOSITION_INVALID_OR_REFUSED,
    }
)

REASON_SUPPORTED_IN_SCOPE = "supported_in_scope"
REASON_SOURCE_IDENTITY_UNRESOLVED = "source_identity_unresolved"
REASON_UNSUPPORTED_PROVIDER_EXCLUDED = "unsupported_provider_excluded"
REASON_UNSUPPORTED_CURRENCY_EXCLUDED = "unsupported_currency_excluded"
REASON_OUTSIDE_WINDOW_EXCLUDED = "outside_governed_window_excluded"
REASON_INVALID_TENANT = "invalid_tenant_authority"
REASON_INVALID_WINDOW = "invalid_window_authority"
REASON_INVALID_EVENT_TIME = "invalid_event_time_authority"
REASON_INVALID_PROVIDER_SHAPE = "invalid_provider_shape"
REASON_INVALID_CURRENCY_SHAPE = "invalid_currency_shape"
REASON_INVALID_POLICY_VERSION = "invalid_scope_policy_version"
REASON_AGGREGATE_INCOHERENT = "aggregate_scope_incoherent"

_CANONICAL_PROVIDERS = frozenset({"paypal", "shopify", "stripe", "woocommerce"})
_AGGREGATE_SCOPE_SOURCE_REFERENCE = "canonical_aggregate_scope"


class ScopeAuthorityError(ValueError):
    """Governed scope meaning is absent, malformed, or excluded."""


@dataclass(frozen=True)
class ScopePolicyIdentity:
    """Exact source and semantic identities of the governing scope policy."""

    phase: str
    scope_policy_version: str
    source_sha256: str
    semantic_sha256: str


@dataclass(frozen=True)
class CanonicalScopeClassification:
    """One deterministic P2 scope verdict for one candidate.

    No amount field exists: normalization cannot alter monetary values
    because no monetary value reaches this type.
    """

    tenant_id: UUID
    provider: str
    rail: str
    currency_code: str
    window_start: datetime
    window_end: datetime
    scope_policy_version: str
    disposition: str
    reason: str


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sovereign_leaf() -> Any:
    """Load the sovereign B2.3 coverage leaf without package side effects.

    The leaf module is stdlib plus sqlalchemy only, so executing it by file
    location observes the exact shipped sovereign constants without
    importing the package ``__init__`` chain (which owns engine and config
    concerns this pure classifier must never depend on).
    """
    leaf = _PACKAGE_ROOT / "app" / "revenue_verification" / "verification_coverage.py"
    loader_name = "b26_p2_sovereign_verification_coverage_leaf"
    spec = importlib.util.spec_from_file_location(loader_name, leaf)
    if spec is None or spec.loader is None:
        raise ScopeAuthorityError("b26_p2_sovereign_leaf_unloadable")
    module = importlib.util.module_from_spec(spec)
    import sys as _sys

    _sys.modules[loader_name] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def _sovereign_provider_universe_cached() -> frozenset[str]:
    return frozenset(_sovereign_leaf().SUPPORTED_VERIFICATION_COVERAGE_PLATFORMS)


@lru_cache(maxsize=1)
def _sovereign_currency_universe_cached() -> frozenset[str]:
    return frozenset(_sovereign_leaf().SUPPORTED_VERIFICATION_COVERAGE_CURRENCIES)


def _sovereign_provider_universe() -> frozenset[str]:
    return _sovereign_provider_universe_cached()


def _sovereign_currency_universe() -> frozenset[str]:
    return _sovereign_currency_universe_cached()


@lru_cache(maxsize=1)
def load_b26_p2_scope_policy() -> Mapping[str, Any]:
    """Load the exact shipped scope policy and fail closed on drift."""
    if not B26_P2_SCOPE_POLICY_PATH.is_file():
        raise ScopeAuthorityError(
            f"b26_p2_scope_policy_missing:{B26_P2_SCOPE_POLICY_PATH.as_posix()}"
        )
    document = yaml.safe_load(B26_P2_SCOPE_POLICY_PATH.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ScopeAuthorityError("b26_p2_scope_policy_not_object")
    _validate_scope_policy(document)
    return document


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ScopeAuthorityError(reason)


def _validate_scope_policy(document: Mapping[str, Any]) -> None:
    _require(document.get("phase_id") == "B2.6-P2", "b26_p2_phase_mismatch")
    _require(
        document.get("scope_policy_version") == B26_P2_SCOPE_POLICY_VERSION,
        "b26_p2_scope_policy_version_mismatch",
    )
    _require(
        document.get("authority_kind")
        == "scope_normalization_authority_not_financial_result",
        "b26_p2_authority_kind_drift",
    )
    _require(
        set(document.get("canonical_providers", [])) == set(_CANONICAL_PROVIDERS),
        "b26_p2_canonical_provider_universe_drift",
    )
    _require(
        set(document.get("canonical_rails", [])) == set(_CANONICAL_PROVIDERS),
        "b26_p2_canonical_rail_universe_drift",
    )
    _require(
        document.get("rail_identity_law")
        == "rail_identity_equals_provider_identity_for_P2",
        "b26_p2_rail_identity_law_drift",
    )
    _require(
        document.get("alias_law") == "strip_ascii_lower_exact_match_only",
        "b26_p2_alias_law_drift",
    )
    _require(
        document.get("provider_scope_reference")
        == "app.revenue_verification.verification_coverage."
        "SUPPORTED_VERIFICATION_COVERAGE_PLATFORMS",
        "b26_p2_provider_scope_reference_drift",
    )
    _require(
        document.get("currency_scope_reference")
        == "app.revenue_verification.verification_coverage."
        "SUPPORTED_VERIFICATION_COVERAGE_CURRENCIES",
        "b26_p2_currency_scope_reference_drift",
    )
    window = document.get("window_semantics", {})
    _require(
        isinstance(window, dict)
        and window.get("interval") == "half_open"
        and window.get("lower_bound") == "inclusive"
        and window.get("upper_bound") == "exclusive"
        and window.get("clock_source")
        == "persisted_webhook_ingress_identities.event_timestamp"
        and window.get("timezone") == "UTC"
        and window.get("naive_event_time") == "refused",
        "b26_p2_window_semantics_drift",
    )
    _require(
        set(document.get("dispositions", [])) == set(GOVERNED_P2_DISPOSITIONS),
        "b26_p2_disposition_vocabulary_drift",
    )
    _require(
        document.get("tenant_law")
        == "server_derived_uuid_only_missing_or_malformed_refused",
        "b26_p2_tenant_law_drift",
    )
    _require(
        document.get("money_law")
        == "normalization_never_changes_money_no_amount_path",
        "b26_p2_money_law_drift",
    )
    _require(
        document.get("replay_law")
        == "same_evidence_same_policy_version_same_identity_and_disposition",
        "b26_p2_replay_law_drift",
    )
    _require(
        document.get("evolution_law")
        == "alias_rail_currency_window_meaning_change_requires_version_bump",
        "b26_p2_evolution_law_drift",
    )
    # Sovereign correspondence: the contract-declared universes must equal
    # the live sovereign universes. A silent widening on either side refuses.
    _require(
        set(document.get("supported_currencies", []))
        == set(_sovereign_currency_universe()),
        "b26_p2_currency_universe_sovereign_drift",
    )
    _require(
        set(document.get("canonical_providers", []))
        == set(_sovereign_provider_universe()),
        "b26_p2_provider_universe_sovereign_drift",
    )


def scope_policy_identity() -> ScopePolicyIdentity:
    """Return byte and semantic hashes recoverable inside a shipped image."""
    document = load_b26_p2_scope_policy()
    source = B26_P2_SCOPE_POLICY_PATH.read_bytes()
    return ScopePolicyIdentity(
        phase="B2.6-P2",
        scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
        source_sha256=hashlib.sha256(source).hexdigest(),
        semantic_sha256=hashlib.sha256(_canonical_json(document)).hexdigest(),
    )


def _normalize_utc_instant(value: Any, *, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise ScopeAuthorityError(f"{field}:not_datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ScopeAuthorityError(f"{field}:naive_datetime_refused")
    return value.astimezone(timezone.utc)


def normalize_provider(raw: Any) -> str:
    """Normalize one raw provider token to its canonical identity.

    Governed law is strip plus ASCII lower plus exact membership. Case and
    surrounding whitespace variants of a supported provider normalize to it;
    every other token raises unsupported (the classifier maps that raise to
    EXPLICITLY_EXCLUDED). Malformed shapes raise invalid shape (mapped to
    INVALID_OR_REFUSED). No legacy alias promotion exists.
    """
    if not isinstance(raw, str):
        raise ScopeAuthorityError(
            f"{REASON_INVALID_PROVIDER_SHAPE}:{type(raw).__name__}"
        )
    token = raw.strip().lower()
    if not token:
        raise ScopeAuthorityError(f"{REASON_INVALID_PROVIDER_SHAPE}:blank")
    if token not in _CANONICAL_PROVIDERS:
        raise ScopeAuthorityError(f"{REASON_UNSUPPORTED_PROVIDER_EXCLUDED}:{token}")
    if token not in _sovereign_provider_universe():
        raise ScopeAuthorityError(f"{REASON_UNSUPPORTED_PROVIDER_EXCLUDED}:{token}")
    return token


def normalize_rail(provider: Any) -> str:
    """Map one canonical provider to its P2 rail identity (1:1)."""
    canonical = normalize_provider(provider)
    return canonical


def normalize_currency(raw: Any) -> str:
    """Normalize one raw currency token to its canonical code."""
    if not isinstance(raw, str):
        raise ScopeAuthorityError(
            f"{REASON_INVALID_CURRENCY_SHAPE}:{type(raw).__name__}"
        )
    token = raw.strip().upper()
    if not token:
        raise ScopeAuthorityError(f"{REASON_INVALID_CURRENCY_SHAPE}:blank")
    if len(token) != 3 or not token.isalpha():
        raise ScopeAuthorityError(f"{REASON_INVALID_CURRENCY_SHAPE}:{token}")
    if token not in _sovereign_currency_universe():
        raise ScopeAuthorityError(f"{REASON_UNSUPPORTED_CURRENCY_EXCLUDED}:{token}")
    return token


def normalize_provider_set(platforms: Sequence[str] | None) -> tuple[str, ...]:
    """Normalize one B2.6 provider set to its canonical sorted tuple.

    This is the single B2.6-side provider-set normalization. ``None`` admits
    the full governed universe; empty sets refuse; unsupported members
    refuse. Ordering is canonical sorted order so replay is stable.
    """
    if platforms is None:
        return tuple(sorted(_sovereign_provider_universe()))
    if isinstance(platforms, str):
        raise ScopeAuthorityError(f"{REASON_INVALID_PROVIDER_SHAPE}:bare_string")
    try:
        members = list(platforms)
    except TypeError as exc:
        raise ScopeAuthorityError(
            f"{REASON_INVALID_PROVIDER_SHAPE}:{type(platforms).__name__}"
        ) from exc
    normalized = tuple(sorted({normalize_provider(item) for item in members}))
    if not normalized:
        raise ScopeAuthorityError(f"{REASON_INVALID_PROVIDER_SHAPE}:empty_set")
    return normalized


def validate_window(
    window_start: Any, window_end: Any
) -> tuple[datetime, datetime]:
    """Validate one half-open UTC window (start inclusive, end exclusive)."""
    try:
        start = _normalize_utc_instant(window_start, field=REASON_INVALID_WINDOW)
        end = _normalize_utc_instant(window_end, field=REASON_INVALID_WINDOW)
    except ScopeAuthorityError as exc:
        raise ScopeAuthorityError(f"{REASON_INVALID_WINDOW}:{exc}") from exc
    if start >= end:
        raise ScopeAuthorityError(f"{REASON_INVALID_WINDOW}:not_half_open")
    return start, end


def _parse_tenant(tenant_id: Any) -> UUID:
    if isinstance(tenant_id, UUID):
        return tenant_id
    if not isinstance(tenant_id, str):
        raise ScopeAuthorityError(f"{REASON_INVALID_TENANT}:{type(tenant_id).__name__}")
    token = tenant_id.strip()
    if not token:
        raise ScopeAuthorityError(f"{REASON_INVALID_TENANT}:blank")
    try:
        return UUID(token)
    except (ValueError, AttributeError) as exc:
        raise ScopeAuthorityError(f"{REASON_INVALID_TENANT}:malformed") from exc


def classify_candidate(
    *,
    tenant_id: Any,
    provider_raw: Any,
    currency_raw: Any,
    event_time: Any,
    window_start: Any,
    window_end: Any,
    scope_policy_version: Any,
    source_reference: Any = None,
) -> CanonicalScopeClassification:
    """Deterministically classify one reconciliation candidate.

    Exactly one disposition is returned; no candidate vanishes. Malformed
    tenant, policy version, window, event time, or provider/currency shape
    yields INVALID_OR_REFUSED. Supported provider plus supported currency
    plus in-window event time yields SUPPORTED_AND_IN_SCOPE when a source
    reference is present and SUPPORTED_BUT_UNRESOLVED when it is absent.
    Unsupported provider, unsupported currency, or outside-window event
    time yields EXPLICITLY_EXCLUDED under deterministic priority
    (provider, then currency, then window).
    """
    load_b26_p2_scope_policy()
    if (
        not isinstance(scope_policy_version, str)
        or scope_policy_version != B26_P2_SCOPE_POLICY_VERSION
    ):
        raise ScopeAuthorityError(
            f"{REASON_INVALID_POLICY_VERSION}:{scope_policy_version}"
        )
    try:
        tenant = _parse_tenant(tenant_id)
    except ScopeAuthorityError as exc:
        raise ScopeAuthorityError(str(exc)) from exc
    try:
        start, end = validate_window(window_start, window_end)
    except ScopeAuthorityError as exc:
        raise ScopeAuthorityError(str(exc)) from exc
    if isinstance(provider_raw, str) and not provider_raw.strip():
        raise ScopeAuthorityError(f"{REASON_INVALID_PROVIDER_SHAPE}:blank")
    if isinstance(currency_raw, str) and not currency_raw.strip():
        raise ScopeAuthorityError(f"{REASON_INVALID_CURRENCY_SHAPE}:blank")
    if not isinstance(provider_raw, str):
        raise ScopeAuthorityError(
            f"{REASON_INVALID_PROVIDER_SHAPE}:{type(provider_raw).__name__}"
        )
    if not isinstance(currency_raw, str):
        raise ScopeAuthorityError(
            f"{REASON_INVALID_CURRENCY_SHAPE}:{type(currency_raw).__name__}"
        )
    try:
        occurred = _normalize_utc_instant(event_time, field=REASON_INVALID_EVENT_TIME)
    except ScopeAuthorityError as exc:
        raise ScopeAuthorityError(str(exc)) from exc

    provider_token = provider_raw.strip().lower()
    currency_token = currency_raw.strip().upper()
    provider_supported = (
        provider_token in _CANONICAL_PROVIDERS
        and provider_token in _sovereign_provider_universe()
    )
    currency_supported = currency_token in _sovereign_currency_universe()
    if not provider_supported:
        return CanonicalScopeClassification(
            tenant_id=tenant,
            provider=provider_token,
            rail=provider_token,
            currency_code=currency_token,
            window_start=start,
            window_end=end,
            scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
            disposition=DISPOSITION_EXPLICITLY_EXCLUDED,
            reason=REASON_UNSUPPORTED_PROVIDER_EXCLUDED,
        )
    if not currency_supported:
        return CanonicalScopeClassification(
            tenant_id=tenant,
            provider=provider_token,
            rail=provider_token,
            currency_code=currency_token,
            window_start=start,
            window_end=end,
            scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
            disposition=DISPOSITION_EXPLICITLY_EXCLUDED,
            reason=REASON_UNSUPPORTED_CURRENCY_EXCLUDED,
        )
    if not (start <= occurred < end):
        return CanonicalScopeClassification(
            tenant_id=tenant,
            provider=provider_token,
            rail=provider_token,
            currency_code=currency_token,
            window_start=start,
            window_end=end,
            scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
            disposition=DISPOSITION_EXPLICITLY_EXCLUDED,
            reason=REASON_OUTSIDE_WINDOW_EXCLUDED,
        )
    has_reference = isinstance(source_reference, str) and bool(
        source_reference.strip()
    )
    if not has_reference:
        return CanonicalScopeClassification(
            tenant_id=tenant,
            provider=provider_token,
            rail=provider_token,
            currency_code=currency_token,
            window_start=start,
            window_end=end,
            scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
            disposition=DISPOSITION_SUPPORTED_BUT_UNRESOLVED,
            reason=REASON_SOURCE_IDENTITY_UNRESOLVED,
        )
    return CanonicalScopeClassification(
        tenant_id=tenant,
        provider=provider_token,
        rail=provider_token,
        currency_code=currency_token,
        window_start=start,
        window_end=end,
        scope_policy_version=B26_P2_SCOPE_POLICY_VERSION,
        disposition=DISPOSITION_SUPPORTED_AND_IN_SCOPE,
        reason=REASON_SUPPORTED_IN_SCOPE,
    )


def assert_aggregate_scope_supported(
    *,
    tenant_id: Any,
    supported_platforms: Sequence[str] | None,
    currency_code: Any,
    window_start: Any,
    window_end: Any,
    scope_policy_version: Any = B26_P2_SCOPE_POLICY_VERSION,
) -> tuple[CanonicalScopeClassification, ...]:
    """Require every governed aggregate-scope member to classify in scope.

    The canonical execution calls this with its sovereign scope values and
    the window lower bound as the representative in-window instant. Any
    member that does not resolve to SUPPORTED_AND_IN_SCOPE fails closed
    instead of executing on an incoherent scope.
    """
    providers = normalize_provider_set(supported_platforms)
    currency = normalize_currency(currency_code)
    start, end = validate_window(window_start, window_end)
    tenant = _parse_tenant(tenant_id)
    results: list[CanonicalScopeClassification] = []
    for provider in providers:
        verdict = classify_candidate(
            tenant_id=tenant,
            provider_raw=provider,
            currency_raw=currency,
            event_time=start,
            window_start=start,
            window_end=end,
            scope_policy_version=scope_policy_version,
            source_reference=_AGGREGATE_SCOPE_SOURCE_REFERENCE,
        )
        if verdict.disposition != DISPOSITION_SUPPORTED_AND_IN_SCOPE:
            raise ScopeAuthorityError(
                f"{REASON_AGGREGATE_INCOHERENT}:{provider}:{verdict.disposition}"
            )
        results.append(verdict)
    return tuple(results)


__all__ = [
    "B26_P2_SCOPE_POLICY_PATH",
    "B26_P2_SCOPE_POLICY_VERSION",
    "DISPOSITION_EXPLICITLY_EXCLUDED",
    "DISPOSITION_INVALID_OR_REFUSED",
    "DISPOSITION_SUPPORTED_AND_IN_SCOPE",
    "DISPOSITION_SUPPORTED_BUT_UNRESOLVED",
    "GOVERNED_P2_DISPOSITIONS",
    "REASON_AGGREGATE_INCOHERENT",
    "REASON_INVALID_CURRENCY_SHAPE",
    "REASON_INVALID_EVENT_TIME",
    "REASON_INVALID_POLICY_VERSION",
    "REASON_INVALID_PROVIDER_SHAPE",
    "REASON_INVALID_TENANT",
    "REASON_INVALID_WINDOW",
    "REASON_OUTSIDE_WINDOW_EXCLUDED",
    "REASON_SOURCE_IDENTITY_UNRESOLVED",
    "REASON_SUPPORTED_IN_SCOPE",
    "REASON_UNSUPPORTED_CURRENCY_EXCLUDED",
    "REASON_UNSUPPORTED_PROVIDER_EXCLUDED",
    "CanonicalScopeClassification",
    "ScopeAuthorityError",
    "ScopePolicyIdentity",
    "assert_aggregate_scope_supported",
    "classify_candidate",
    "load_b26_p2_scope_policy",
    "normalize_currency",
    "normalize_provider",
    "normalize_provider_set",
    "normalize_rail",
    "scope_policy_identity",
    "validate_window",
]
