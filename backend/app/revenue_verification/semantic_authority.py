"""Executable B2.3-P0 semantic authority freeze contract."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator


B23_P0_SEMANTIC_AUTHORITY_VERSION = "b2.3-p0-v1"
_CONTRACT_RELATIVE_PATH = (
    "contracts-internal/governance/b23_p0_semantic_authority_freeze.main.json"
)
_REPO_ROOT = Path(__file__).resolve().parents[3]

B23_PRECEDENCE_ORDER = (
    "normalized_commerce_reference",
    "provider_native_commerce_reference",
    "strict_order_id",
)

FORBIDDEN_DELAYED_ARRIVAL_STRATEGIES = frozenset(
    {
        "extend_attribution_session_window",
        "cross_session_identity_reconstruction",
        "persist_pii_for_matching",
        "persist_reversible_user_linked_hashes",
        "privacy_ambiguous_shadow_identity_graph",
    }
)

ALLOWED_DELAYED_ARRIVAL_TOPOLOGY = (
    "durable_tenant_scoped_non_pii_commerce_identity_substrate"
)
DELAYED_ARRIVAL_POLICY = (
    "match_via_durable_commerce_identity_else_explicit_unmatched_or_unsupported"
)
ALLOWED_DELAYED_ARRIVAL_TOPOLOGY_TABLE = "attribution_commerce_identities"
ALLOWED_DELAYED_ARRIVAL_REQUIRED_COLUMNS = frozenset(
    {
        "tenant_id",
        "attribution_event_id",
        "provider",
        "canonical_commerce_reference",
        "source",
        "first_observed_at",
        "last_observed_at",
    }
)
ALLOWED_DELAYED_ARRIVAL_FORBIDDEN_COLUMNS = frozenset(
    {
        "session_id",
        "user_id",
        "email",
        "ip_address",
        "gclid",
        "fbclid",
        "external_user_id",
        "device_id",
    }
)

B23_AMOUNT_BASIS = "verified_captured_amount_minor_units"
B23_CURRENCY_STANCE = "same_currency_only_cross_currency_unsupported"
UNSUPPORTED_PAYMENT_ADJUSTMENTS = frozenset(
    {
        "refund",
        "partial_capture",
        "split_payment",
        "provider_adjustment",
    }
)

B23_FORBIDDEN_FALSE_AUTHORITIES = frozenset(
    {
        "revenue_ledger.state",
        "revenue_ledger.discrepancy_bps",
        "reconciliation_runs.state",
        "RevenueReconciliationService",
        "/api/reconciliation/status",
        "/api/reconciliation/platform/{platform_id}",
        "/api/v1/revenue/realtime",
        "/api/attribution/revenue/realtime",
        "build_realtime_revenue_v1_response",
        "build_attribution_realtime_revenue_response",
        "get_realtime_revenue_snapshot",
    }
)

_DECORATED_REFERENCE_PATTERN = re.compile(r"[^a-z0-9]+")
_NUMERIC_PREFIX_TOKENS = frozenset(
    {"shopify", "woocommerce", "woo", "wc", "order", "ord", "tx", "txn"}
)


class CanonicalizationStatus(str, Enum):
    CANONICALIZED = "canonicalized"
    CANONICALIZATION_FAILED = "canonicalization_failed_explicit"


@dataclass(frozen=True)
class CanonicalReferenceResult:
    status: CanonicalizationStatus
    canonical_reference: str | None
    reason_code: str

    @staticmethod
    def failed(reason_code: str, detail: str) -> "CanonicalReferenceResult":
        return CanonicalReferenceResult(
            status=CanonicalizationStatus.CANONICALIZATION_FAILED,
            canonical_reference=None,
            reason_code=f"{reason_code}:{detail}",
        )


@dataclass(frozen=True)
class PrecedenceResolution:
    status: CanonicalizationStatus
    canonical_reference: str | None
    source_field: str | None
    reason_code: str


class B23Verdict(str, Enum):
    MATCHED = "matched"
    FLAGGED = "flagged"
    SEVERE = "severe"
    UNMATCHED = "unmatched"
    UNSUPPORTED = "unsupported"
    CANONICALIZATION_FAILED = "canonicalization_failed"


class B23DiscrepancyClass(str, Enum):
    EXACT = "exact"
    WITHIN_TOLERANCE = "within_tolerance"
    OVER_TOLERANCE = "over_tolerance"
    SEVERE_GAP = "severe_gap"
    UNSUPPORTED = "unsupported"
    IDENTITY_FAILURE = "identity_failure"


class PaymentAdjustmentSupport(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class B23PerformanceAuthority:
    kernel_1000_orders_max_seconds: int
    report_1000_orders_max_seconds: int


B23_P0_PERFORMANCE_AUTHORITY = B23PerformanceAuthority(
    kernel_1000_orders_max_seconds=5,
    report_1000_orders_max_seconds=10,
)
_B23_P0_PERFORMANCE_THRESHOLDS = MappingProxyType(
    {
        "kernel_1000_orders_max_seconds": B23_P0_PERFORMANCE_AUTHORITY.kernel_1000_orders_max_seconds,
        "report_1000_orders_max_seconds": B23_P0_PERFORMANCE_AUTHORITY.report_1000_orders_max_seconds,
    }
)


def get_b23_p0_performance_thresholds() -> Mapping[str, int]:
    return _B23_P0_PERFORMANCE_THRESHOLDS

B23_DOWNSTREAM_VERDICT_MAP = MappingProxyType(
    {
        B23Verdict.MATCHED: "b23.verdict.matched",
        B23Verdict.FLAGGED: "b23.verdict.flagged",
        B23Verdict.SEVERE: "b23.verdict.severe",
        B23Verdict.UNMATCHED: "b23.verdict.unmatched",
        B23Verdict.UNSUPPORTED: "b23.verdict.unsupported",
        B23Verdict.CANONICALIZATION_FAILED: "b23.verdict.canonicalization_failed",
    }
)
B23_DOWNSTREAM_DISCREPANCY_MAP = MappingProxyType(
    {
        B23DiscrepancyClass.EXACT: "b23.discrepancy.exact",
        B23DiscrepancyClass.WITHIN_TOLERANCE: "b23.discrepancy.within_tolerance",
        B23DiscrepancyClass.OVER_TOLERANCE: "b23.discrepancy.over_tolerance",
        B23DiscrepancyClass.SEVERE_GAP: "b23.discrepancy.severe_gap",
        B23DiscrepancyClass.UNSUPPORTED: "b23.discrepancy.unsupported",
        B23DiscrepancyClass.IDENTITY_FAILURE: "b23.discrepancy.identity_failure",
    }
)


class BaselineAuthorityModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authoritative_branch: str
    require_main_ancestor_for_semantic_work: bool


class SharedIdentityModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    law_id: str
    precedence_order: list[str]
    canonicalization_failure_state: str
    supported_decorated_variants: list[str]


class DelayedArrivalTopologyBindingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table: str
    required_columns: list[str]
    forbidden_columns: list[str]
    requires_rls: bool


class DelayedArrivalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    forbidden_mechanisms: list[str]
    allowed_topology: str
    delayed_arrival_policy: str
    topology_schema_binding: DelayedArrivalTopologyBindingModel


class FinancialTruthModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_basis: str
    currency_stance: str
    unsupported_payment_adjustments: list[str]


class BoundaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    b23_scope: str
    b23_must_not_allocate_attribution: bool
    downstream_consumers: list[str]


class DownstreamMappingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: str
    verdict_map_target: str
    discrepancy_map_target: str
    ad_hoc_free_form_translation_forbidden: bool
    pre_dispatch_validation_required: bool


class PerformanceAuthorityModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kernel_1000_orders_max_seconds: int
    report_1000_orders_max_seconds: int


class TypedBoundaryAdjudicationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_enforcer: str
    required_ci_job: str
    expected_status: str


class B23P0SemanticAuthorityContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_id: str
    contract_version: str
    repository: str
    branch: str
    phase: str
    description: str
    baseline_authority: BaselineAuthorityModel
    shared_identity_canonicalization: SharedIdentityModel
    privacy_safe_delayed_arrival: DelayedArrivalModel
    financial_truth_semantics: FinancialTruthModel
    b23_b21_boundary: BoundaryModel
    verdict_taxonomy: list[str]
    discrepancy_taxonomy: list[str]
    false_authority_exclusions: list[str]
    downstream_mapping: DownstreamMappingModel
    performance_authority: PerformanceAuthorityModel
    typed_boundary_adjudication: TypedBoundaryAdjudicationModel
    required_runtime_proofs: list[str] = Field(default_factory=list)
    required_ci_wiring: list[str] = Field(default_factory=list)


class B23DownstreamSemanticProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: str
    discrepancy: str

    @field_validator("verdict")
    @classmethod
    def _validate_verdict(cls, value: str) -> str:
        token = str(value or "").strip()
        if token not in B23_DOWNSTREAM_VERDICT_MAP.values():
            raise ValueError("invalid downstream verdict mapping token")
        return token

    @field_validator("discrepancy")
    @classmethod
    def _validate_discrepancy(cls, value: str) -> str:
        token = str(value or "").strip()
        if token not in B23_DOWNSTREAM_DISCREPANCY_MAP.values():
            raise ValueError("invalid downstream discrepancy mapping token")
        return token


def _contract_file_path() -> Path:
    return (_REPO_ROOT / _CONTRACT_RELATIVE_PATH).resolve()


def _normalize_provider(provider: str | None) -> str:
    return str(provider or "").strip().lower()


def _normalize_raw_reference(raw_reference: str | None) -> str:
    return str(raw_reference or "").strip().lower()


def _sanitize_reference_tokens(normalized_raw: str) -> list[str]:
    stripped = _DECORATED_REFERENCE_PATTERN.sub("_", normalized_raw).strip("_")
    if not stripped:
        return []
    return [token for token in stripped.split("_") if token]


def _drop_numeric_prefix(tokens: list[str]) -> list[str]:
    if len(tokens) <= 1:
        return tokens
    if tokens[0] in _NUMERIC_PREFIX_TOKENS and all(token.isdigit() for token in tokens[1:]):
        return tokens[1:]
    return tokens


def _compose_canonical_reference(tokens: list[str]) -> str | None:
    if not tokens:
        return None
    if all(token.isdigit() for token in tokens):
        numeric = "".join(tokens).lstrip("0")
        return numeric or "0"
    return "_".join(tokens)


def canonicalize_commerce_reference(
    *,
    provider: str | None,
    raw_reference: str | None,
) -> CanonicalReferenceResult:
    normalized_provider = _normalize_provider(provider)
    normalized_raw = _normalize_raw_reference(raw_reference)
    if not normalized_raw:
        return CanonicalReferenceResult.failed(
            "canonicalization_failed_explicit",
            "blank_reference",
        )

    tokens = _sanitize_reference_tokens(normalized_raw)
    if not tokens:
        return CanonicalReferenceResult.failed(
            "canonicalization_failed_explicit",
            "no_supported_tokens",
        )

    collapsed = _drop_numeric_prefix(tokens)
    canonical = _compose_canonical_reference(collapsed)
    if not canonical:
        return CanonicalReferenceResult.failed(
            "canonicalization_failed_explicit",
            f"unsupported_reference_form_for_provider:{normalized_provider or 'unknown'}",
        )

    return CanonicalReferenceResult(
        status=CanonicalizationStatus.CANONICALIZED,
        canonical_reference=canonical,
        reason_code="canonicalized",
    )


def canonicalize_verified_commerce_reference(
    *,
    provider: str | None,
    raw_reference: str | None,
) -> CanonicalReferenceResult:
    return canonicalize_commerce_reference(
        provider=provider,
        raw_reference=raw_reference,
    )


def canonicalize_attribution_commerce_reference(
    *,
    provider: str | None,
    raw_reference: str | None,
) -> CanonicalReferenceResult:
    return canonicalize_commerce_reference(
        provider=provider,
        raw_reference=raw_reference,
    )


def resolve_canonical_match_key(
    *,
    provider: str | None,
    normalized_commerce_reference: str | None,
    provider_native_commerce_reference: str | None,
    strict_order_id: str | None,
) -> PrecedenceResolution:
    candidates = {
        "normalized_commerce_reference": normalized_commerce_reference,
        "provider_native_commerce_reference": provider_native_commerce_reference,
        "strict_order_id": strict_order_id,
    }
    for source_field in B23_PRECEDENCE_ORDER:
        candidate = candidates.get(source_field)
        result = canonicalize_commerce_reference(
            provider=provider,
            raw_reference=candidate,
        )
        if result.status is CanonicalizationStatus.CANONICALIZED:
            return PrecedenceResolution(
                status=result.status,
                canonical_reference=result.canonical_reference,
                source_field=source_field,
                reason_code=result.reason_code,
            )

    return PrecedenceResolution(
        status=CanonicalizationStatus.CANONICALIZATION_FAILED,
        canonical_reference=None,
        source_field=None,
        reason_code="canonicalization_failed_explicit:no_precedence_candidate_canonicalized",
    )


def validate_delayed_arrival_strategy(strategy: str) -> None:
    normalized = str(strategy).strip().lower()
    if normalized in FORBIDDEN_DELAYED_ARRIVAL_STRATEGIES:
        raise ValueError(
            "B2.3-P0 forbids delayed-arrival strategy: "
            f"{normalized}. Use durable tenant-scoped non-PII commerce identity."
        )


def validate_delayed_arrival_topology(topology: str) -> None:
    normalized = str(topology).strip()
    if normalized != ALLOWED_DELAYED_ARRIVAL_TOPOLOGY:
        raise ValueError(
            "B2.3-P0 delayed-arrival topology mismatch: "
            f"expected {ALLOWED_DELAYED_ARRIVAL_TOPOLOGY}, observed {normalized}"
        )


def validate_delayed_arrival_topology_binding(
    *,
    table_name: str,
    columns: set[str],
    rls_enabled: bool,
) -> None:
    normalized_table = str(table_name or "").strip()
    if normalized_table != ALLOWED_DELAYED_ARRIVAL_TOPOLOGY_TABLE:
        raise ValueError(
            "B2.3-P0 delayed-arrival topology binding mismatch: "
            f"expected table {ALLOWED_DELAYED_ARRIVAL_TOPOLOGY_TABLE}, observed {normalized_table}"
        )

    normalized_columns = {str(column).strip() for column in columns if str(column).strip()}
    missing = ALLOWED_DELAYED_ARRIVAL_REQUIRED_COLUMNS - normalized_columns
    if missing:
        raise ValueError(
            "B2.3-P0 delayed-arrival topology binding missing required columns: "
            + ", ".join(sorted(missing))
        )

    forbidden = ALLOWED_DELAYED_ARRIVAL_FORBIDDEN_COLUMNS & normalized_columns
    if forbidden:
        raise ValueError(
            "B2.3-P0 delayed-arrival topology binding contains forbidden identity columns: "
            + ", ".join(sorted(forbidden))
        )

    if not rls_enabled:
        raise ValueError("B2.3-P0 delayed-arrival topology binding requires RLS enforcement")


def classify_payment_adjustment_support(adjustment_type: str) -> PaymentAdjustmentSupport:
    normalized = str(adjustment_type or "").strip().lower()
    if normalized in UNSUPPORTED_PAYMENT_ADJUSTMENTS:
        return PaymentAdjustmentSupport.UNSUPPORTED
    return PaymentAdjustmentSupport.SUPPORTED


def assert_b23_boundary_not_allocation(*, requests_allocation: bool) -> None:
    if requests_allocation:
        raise ValueError(
            "B2.3-P0 boundary violation: B2.3 establishes verified revenue truth only; "
            "B2.1/B2.5 perform attribution allocation."
        )


def assert_b23_authority_source(source: str) -> None:
    normalized = str(source or "").strip()
    if normalized in B23_FORBIDDEN_FALSE_AUTHORITIES:
        raise ValueError(
            "B2.3-P0 false-authority violation: "
            f"{normalized} is explicitly excluded from first-authority verdict semantics."
        )


def map_b23_verdict_for_downstream(verdict: B23Verdict) -> str:
    return B23_DOWNSTREAM_VERDICT_MAP[verdict]


def map_b23_discrepancy_for_downstream(discrepancy: B23DiscrepancyClass) -> str:
    return B23_DOWNSTREAM_DISCREPANCY_MAP[discrepancy]


def build_validated_downstream_projection(
    *,
    verdict: B23Verdict,
    discrepancy: B23DiscrepancyClass,
) -> B23DownstreamSemanticProjection:
    return B23DownstreamSemanticProjection.model_validate(
        {
            "verdict": map_b23_verdict_for_downstream(verdict),
            "discrepancy": map_b23_discrepancy_for_downstream(discrepancy),
        }
    )


def validate_downstream_projection_payload(
    payload: Mapping[str, Any],
) -> B23DownstreamSemanticProjection:
    return B23DownstreamSemanticProjection.model_validate(dict(payload))


def load_b23_p0_semantic_authority_contract(
    contract_path: Path | None = None,
) -> B23P0SemanticAuthorityContract:
    resolved_contract = contract_path or _contract_file_path()
    payload = json.loads(resolved_contract.read_text(encoding="utf-8"))
    contract = B23P0SemanticAuthorityContract.model_validate(payload)
    if contract.contract_id != "b23.p0.semantic_authority_freeze.main":
        raise ValueError("B2.3-P0 contract_id mismatch")
    if contract.branch != "main":
        raise ValueError("B2.3-P0 authority branch must be main")
    if contract.phase != "B2.3-P0":
        raise ValueError("B2.3-P0 phase marker mismatch")
    if tuple(contract.shared_identity_canonicalization.precedence_order) != B23_PRECEDENCE_ORDER:
        raise ValueError("B2.3-P0 precedence order drift detected")
    if (
        contract.shared_identity_canonicalization.canonicalization_failure_state
        != CanonicalizationStatus.CANONICALIZATION_FAILED.value
    ):
        raise ValueError("B2.3-P0 canonicalization failure-state drift detected")
    if contract.privacy_safe_delayed_arrival.allowed_topology != ALLOWED_DELAYED_ARRIVAL_TOPOLOGY:
        raise ValueError("B2.3-P0 allowed delayed-arrival topology drift detected")
    if contract.privacy_safe_delayed_arrival.delayed_arrival_policy != DELAYED_ARRIVAL_POLICY:
        raise ValueError("B2.3-P0 delayed-arrival policy drift detected")
    if contract.financial_truth_semantics.amount_basis != B23_AMOUNT_BASIS:
        raise ValueError("B2.3-P0 amount basis drift detected")
    if contract.financial_truth_semantics.currency_stance != B23_CURRENCY_STANCE:
        raise ValueError("B2.3-P0 currency stance drift detected")
    topology_binding = contract.privacy_safe_delayed_arrival.topology_schema_binding
    if topology_binding.table != ALLOWED_DELAYED_ARRIVAL_TOPOLOGY_TABLE:
        raise ValueError("B2.3-P0 delayed-arrival topology table drift detected")
    if set(topology_binding.required_columns) != ALLOWED_DELAYED_ARRIVAL_REQUIRED_COLUMNS:
        raise ValueError("B2.3-P0 delayed-arrival topology required-column drift detected")
    if set(topology_binding.forbidden_columns) != ALLOWED_DELAYED_ARRIVAL_FORBIDDEN_COLUMNS:
        raise ValueError("B2.3-P0 delayed-arrival topology forbidden-column drift detected")
    if topology_binding.requires_rls is not True:
        raise ValueError("B2.3-P0 delayed-arrival topology must require RLS")
    if set(contract.false_authority_exclusions) != B23_FORBIDDEN_FALSE_AUTHORITIES:
        raise ValueError("B2.3-P0 false-authority exclusion drift detected")
    if contract.downstream_mapping.strategy != "typed_deterministic_mapping_only":
        raise ValueError("B2.3-P0 downstream mapping strategy drift detected")
    if contract.downstream_mapping.ad_hoc_free_form_translation_forbidden is not True:
        raise ValueError("B2.3-P0 downstream mapping free-form prohibition drift detected")
    if contract.downstream_mapping.pre_dispatch_validation_required is not True:
        raise ValueError("B2.3-P0 downstream pre-dispatch validation requirement drift detected")
    if contract.typed_boundary_adjudication.required_enforcer != (
        "scripts/ci/enforce_b15_p4_mock_sdk_boundary.py"
    ):
        raise ValueError("B2.3-P0 typed-boundary enforcer authority drift detected")
    if contract.typed_boundary_adjudication.required_ci_job != "b15-p4-mock-sdk-typed-boundary":
        raise ValueError("B2.3-P0 typed-boundary CI job authority drift detected")
    if contract.typed_boundary_adjudication.expected_status != "mainline_clean_no_live_conflict":
        raise ValueError("B2.3-P0 typed-boundary status expectation drift detected")
    contract_thresholds = {
        "kernel_1000_orders_max_seconds": contract.performance_authority.kernel_1000_orders_max_seconds,
        "report_1000_orders_max_seconds": contract.performance_authority.report_1000_orders_max_seconds,
    }
    if contract_thresholds != dict(_B23_P0_PERFORMANCE_THRESHOLDS):
        raise ValueError("B2.3-P0 performance threshold drift detected")
    return contract
