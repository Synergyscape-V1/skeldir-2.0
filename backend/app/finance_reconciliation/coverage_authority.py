"""B2.6-P1 scope-only sovereign coverage authority (Corrective IV).

P1 remains authority/proof-plane only. This module creates no reconciliation
state, table, API, worker, scheduler, export, or TrustEnvelope field. It
states positively how canonical verification-coverage authority is obtained
and refuses every caller-manufactured origin regardless of numeric
coincidence, representation, or transport.

Corrective-IV law
-----------------

``CANONICAL_COVERAGE(value)`` holds only for a value returned by
:func:`resolve_canonical_coverage` (aliased as
:func:`load_canonical_verification_coverage`) in the same execution that
performed a sovereign B2.3 read from PostgreSQL under the governed
tenant/currency/window/provider scope, with mathematics independently
re-derived from the integer legs.

There is NO transferable canonical token. In particular:

* the :class:`CanonicalVerificationCoverage` class identity confers zero
  authority -- it is a non-authoritative data carrier;
* the ``producer`` string is a non-authoritative label, never trusted;
* there is no seal, boolean, nonce, hash, or signature that a caller can
  supply to create authority (the Corrective-III ``_sealed`` mechanism is
  removed, not renamed);
* :func:`admit_canonical_verification_coverage` is a fail-closed shim that
  always refuses caller-supplied observations and directs callers to the
  scope-only resolver;
* canonical sinks accept scope identity only and invoke the sovereign
  boundary themselves (consumer-side re-derivation, Class A).

A plain number, an independently computed ratio, a legacy-service response,
an estimation/counterfactual blend, an explanation-model output, a copied
object, a serialized diagnostic rebuild, or a neutral-module emission can
never satisfy this law, even when its digits equal the sovereign result.

Mathematics
-----------

Every resolver return re-derives ``coverage_percent`` and
``zero_denominator`` from the integer legs through an independent Decimal
oracle (:func:`independent_coverage_percent`) that does not call the
sovereign ``compute`` method. Caller-supplied percentages are never trusted.

Tenant externalization
----------------------

Diagnostic output carries only the approved one-way tenant external
identifier produced by the sovereign ``app.trust.refusal.tenant_hash``. The
raw tenant UUID is never emitted.

Future durability
-----------------

P1 creates no durable provenance rows. Serialization therefore destroys
authority: diagnostic mappings are explicitly non-authoritative and no
reconstruction protocol exists. Future durable reconciliation snapshots
(P2/P4/P8) MUST bind source identity through sovereign re-derivation or a
database substrate satisfying the Corrective-IV database rules; caller
conventions alone are insufficient.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING, Any, Mapping, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:  # Import-time light: sovereign modules load only on use.
    from app.revenue_verification.verification_coverage import (
        VerificationCoverageAggregate,
        VerificationCoverageResult,
    )


def _sovereign():
    """Load the sovereign B2.3 coverage modules on use, not on import."""
    from app.revenue_verification import (  # noqa: PLC0415
        verification_coverage as sovereign,
    )

    return sovereign


def _tenant_external_id(tenant_id: UUID | str) -> str:
    """Return the sovereign one-way tenant external identifier."""
    from app.trust.refusal import tenant_hash  # noqa: PLC0415

    return tenant_hash(tenant_id)


B23_SOVEREIGN_COVERAGE_PRODUCER = (
    "app.revenue_verification.verification_coverage."
    "fetch_verification_coverage_aggregate"
    "+app.revenue_verification.verification_coverage."
    "VERIFICATION_COVERAGE.compute"
)
CANONICAL_COVERAGE_LAW = "only_sovereign_rederivation_may_be_canonical"
CANONICAL_PROVENANCE_MODEL = "scope_only_sovereign_rederivation_no_transferable_token"
CANONICAL_ADMISSION_MODULE = "app.finance_reconciliation.coverage_authority"
CANONICAL_SEALED_TYPE = (
    "app.finance_reconciliation.coverage_authority.CanonicalVerificationCoverage"
)
CANONICAL_LOADER = (
    "app.finance_reconciliation.coverage_authority.load_canonical_verification_coverage"
)
CANONICAL_RESOLVER = (
    "app.finance_reconciliation.coverage_authority.resolve_canonical_coverage"
)
CANONICAL_ADMITTER = (
    "app.finance_reconciliation.coverage_authority."
    "admit_canonical_verification_coverage"
)
CANONICAL_SCOPE_VERIFIER = (
    "app.finance_reconciliation.coverage_authority.require_canonical_scope"
)

# Positive canonical-sink governance (P1 freeze, no P2 product): only the
# governed future projection boundaries named in the contract's
# future_insertion_seam may emit canonical B2.6 financial fields, and only by
# resolving through this module. Arbitrary repository modules may calculate
# anything; their output is structurally non-canonical until a governed sink
# re-derives it from the sovereign source.
GOVERNED_CANONICAL_SINK_NAMES = frozenset(
    {
        "future_B2.6_deterministic_reconciliation_projection_boundary",
        "future_finance_projection",
        "future_B2.6_TrustEnvelope_projection",
    }
)

_INDEPENDENT_PERCENT = Decimal("100")
_INDEPENDENT_QUANTIZER = Decimal("0.01")
_INDEPENDENT_ZERO_PERCENT = Decimal("0.00")


class CanonicalCoverageAuthorityError(ValueError):
    """A value claimed as canonical coverage lacks sovereign B2.3 origin."""


@dataclass(frozen=True)
class CanonicalVerificationCoverage:
    """Non-authoritative canonical coverage data carrier.

    Class identity confers ZERO authority. A value of this type is canonical
    only when it is the return value of :func:`resolve_canonical_coverage`
    (or its :func:`load_canonical_verification_coverage` alias) in the same
    execution that performed the sovereign B2.3 read. Any other instance --
    constructed, copied, deserialized, rebuilt, or received from another
    component -- is structurally non-canonical and is refused wherever
    canonical authority is required.
    """

    aggregate: VerificationCoverageAggregate
    result: VerificationCoverageResult
    producer: str
    supported_platforms: tuple[str, ...]


@dataclass(frozen=True)
class CanonicalCoverageScope:
    """Scope identity accepted by the sovereign resolver (no finance truth)."""

    tenant_id: UUID
    currency_code: str
    window_start: datetime
    window_end: datetime
    supported_platforms: tuple[str, ...]


def is_governed_canonical_sink(name: str) -> bool:
    """Report whether a projection boundary is a governed canonical sink."""
    return str(name) in GOVERNED_CANONICAL_SINK_NAMES


def require_governed_canonical_sink(name: str) -> str:
    """Require a governed canonical-sink name or refuse it."""
    if not is_governed_canonical_sink(name):
        raise CanonicalCoverageAuthorityError(f"canonical_sink_not_governed:{name}")
    return str(name)


def independent_coverage_percent(
    numerator_matched_minor: int,
    denominator_connected_minor: int,
) -> tuple[Decimal, bool]:
    """Independently derive (percent, zero_denominator) from integer legs.

    This oracle does NOT call the sovereign ``compute`` method. It exists so
    the authority boundary can cross-check sovereign output and so tests can
    assert mathematical truth without self-confirmation. Rounding law:
    half-up to two decimal places; zero denominator yields
    ``(Decimal("0.00"), True)``.
    """
    numerator = int(numerator_matched_minor)
    denominator = int(denominator_connected_minor)
    if not isinstance(numerator_matched_minor, int) or isinstance(
        numerator_matched_minor, bool
    ):
        raise CanonicalCoverageAuthorityError(
            "canonical_coverage_legs_must_be_integer_minor_units"
        )
    if not isinstance(denominator_connected_minor, int) or isinstance(
        denominator_connected_minor, bool
    ):
        raise CanonicalCoverageAuthorityError(
            "canonical_coverage_legs_must_be_integer_minor_units"
        )
    if numerator < 0 or denominator < 0:
        raise CanonicalCoverageAuthorityError(
            "canonical_coverage_revenue_must_be_non_negative"
        )
    if numerator > denominator:
        raise CanonicalCoverageAuthorityError(
            "canonical_coverage_numerator_exceeds_denominator"
        )
    if denominator == 0:
        return (_INDEPENDENT_ZERO_PERCENT, True)
    percent = (
        (Decimal(numerator) * _INDEPENDENT_PERCENT) / Decimal(denominator)
    ).quantize(_INDEPENDENT_QUANTIZER, rounding=ROUND_HALF_UP)
    return (percent, False)


def _supported_platform_universe() -> frozenset[str]:
    return frozenset(_sovereign().SUPPORTED_VERIFICATION_COVERAGE_PLATFORMS)


def _supported_currency_universe() -> frozenset[str]:
    return frozenset(_sovereign().SUPPORTED_VERIFICATION_COVERAGE_CURRENCIES)


def _normalize_platforms(
    supported_platforms: Sequence[str] | None,
) -> tuple[str, ...]:
    if supported_platforms is None:
        return tuple(sorted(_supported_platform_universe()))
    normalized = tuple(
        sorted(
            {
                str(item).strip().lower()
                for item in supported_platforms
                if str(item).strip()
            }
        )
    )
    if not normalized:
        raise CanonicalCoverageAuthorityError(
            "canonical_coverage_supported_platforms_required"
        )
    unsupported = set(normalized) - set(_supported_platform_universe())
    if unsupported:
        raise CanonicalCoverageAuthorityError(
            f"canonical_coverage_unsupported_platform:{sorted(unsupported)}"
        )
    return normalized


def _verify_math_against_legs(value: CanonicalVerificationCoverage) -> None:
    """Re-derive percentage/zero-denominator from integer legs or refuse.

    Caller-supplied ``coverage_percent`` and ``zero_denominator`` are never
    trusted: they are recomputed through the independent oracle and compared.
    """
    sovereign = _sovereign()
    aggregate = value.aggregate
    result = value.result
    if not isinstance(aggregate, sovereign.VerificationCoverageAggregate):
        raise CanonicalCoverageAuthorityError(
            "canonical_coverage_aggregate_not_sovereign_type"
        )
    if not isinstance(result, sovereign.VerificationCoverageResult):
        raise CanonicalCoverageAuthorityError(
            "canonical_coverage_result_not_sovereign_type"
        )
    if (
        aggregate.tenant_id != result.tenant_id
        or aggregate.currency_code != result.currency_code
        or aggregate.window_start != result.window_start
        or aggregate.window_end != result.window_end
        or aggregate.matched_webhook_revenue_minor
        != result.numerator_matched_webhook_revenue_minor
        or aggregate.connected_platform_revenue_minor
        != result.denominator_connected_platform_revenue_minor
    ):
        raise CanonicalCoverageAuthorityError(
            "canonical_coverage_aggregate_result_scope_mismatch"
        )
    expected_percent, expected_zero = independent_coverage_percent(
        aggregate.matched_webhook_revenue_minor,
        aggregate.connected_platform_revenue_minor,
    )
    if result.coverage_percent != expected_percent:
        raise CanonicalCoverageAuthorityError(
            "canonical_coverage_percent_not_derived_from_integer_legs"
        )
    if result.zero_denominator is not expected_zero:
        raise CanonicalCoverageAuthorityError(
            "canonical_coverage_zero_denominator_not_derived_from_integer_legs"
        )


async def resolve_canonical_coverage(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    window_start: datetime,
    window_end: datetime,
    supported_platforms: Sequence[str] | None = None,
    currency_code: str = "USD",
) -> CanonicalVerificationCoverage:
    """Resolve canonical coverage by sovereign re-derivation (scope in only).

    This is the ONLY lawful way to obtain a canonical value. It accepts scope
    identity only -- never a caller-supplied coverage object -- invokes the
    sovereign B2.3 producer against PostgreSQL, cross-checks the sovereign
    computation through the independent oracle, and returns the execution
    result. The return value is canonical in this execution; serializing,
    copying, or transferring it to another execution strips authority.
    """
    sovereign = _sovereign()
    platforms = _normalize_platforms(supported_platforms)
    aggregate = await sovereign.fetch_verification_coverage_aggregate(
        session,
        tenant_id=tenant_id,
        window_start=window_start,
        window_end=window_end,
        supported_platforms=platforms,
        currency_code=currency_code,
    )
    result = sovereign.VERIFICATION_COVERAGE.compute(aggregate)
    candidate = CanonicalVerificationCoverage(
        aggregate=aggregate,
        result=result,
        producer=B23_SOVEREIGN_COVERAGE_PRODUCER,
        supported_platforms=tuple(platforms),
    )
    # Independent cross-check: sovereign output must equal the oracle, or the
    # boundary fails closed rather than projecting a divergent computation.
    _verify_math_against_legs(candidate)
    return candidate


async def load_canonical_verification_coverage(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    window_start: datetime,
    window_end: datetime,
    supported_platforms: Sequence[str] | None = None,
    currency_code: str = "USD",
) -> CanonicalVerificationCoverage:
    """Alias of :func:`resolve_canonical_coverage` (contract-bound name)."""
    return await resolve_canonical_coverage(
        session,
        tenant_id=tenant_id,
        window_start=window_start,
        window_end=window_end,
        supported_platforms=supported_platforms,
        currency_code=currency_code,
    )


def admit_canonical_verification_coverage(
    candidate: Any,
) -> CanonicalVerificationCoverage:
    """Fail-closed shim: caller-supplied observations are never canonical.

    Corrective IV removed transferable canonical tokens. No caller-provided
    value -- however shaped, however numerically correct, however labeled --
    can be admitted as canonical. Canonical values are obtained only by
    resolving scope through :func:`resolve_canonical_coverage`. This function
    is retained under its contract-bound name so existing references fail
    loudly instead of silently conferring authority.
    """
    raise CanonicalCoverageAuthorityError(
        "canonical_admission_requires_sovereign_rederivation:"
        "caller_observations_are_never_canonical:"
        f"{type(candidate).__name__}"
    )


def require_canonical_scope(
    coverage: CanonicalVerificationCoverage,
    *,
    tenant_id: UUID,
    currency_code: str,
    window_start: datetime,
    window_end: datetime,
    supported_platforms: Sequence[str] | None = None,
) -> CanonicalVerificationCoverage:
    """Require governed scope coherence AND independently derived mathematics.

    Scope verification is necessary but NOT sufficient for provenance: a
    return from this function is canonical only when its input was obtained
    via :func:`resolve_canonical_coverage` in the same execution. Forged
    values with coherent scope are still non-canonical because no admission
    path will accept them; this function merely reports scope/math coherence.
    """
    if not isinstance(coverage, CanonicalVerificationCoverage):
        raise CanonicalCoverageAuthorityError(
            f"canonical_coverage_origin_not_sovereign:{type(coverage).__name__}"
        )
    platforms = _normalize_platforms(supported_platforms)
    aggregate = coverage.aggregate
    if (
        aggregate.tenant_id != tenant_id
        or aggregate.currency_code != str(currency_code).strip().upper()
        or aggregate.window_start != window_start
        or aggregate.window_end != window_end
        or tuple(coverage.supported_platforms) != platforms
    ):
        raise CanonicalCoverageAuthorityError(
            "canonical_coverage_scope_identity_mismatch"
        )
    if aggregate.currency_code not in _supported_currency_universe():
        raise CanonicalCoverageAuthorityError(
            "canonical_coverage_currency_not_governed"
        )
    _verify_math_against_legs(coverage)
    return coverage


def to_diagnostic_dict(coverage: CanonicalVerificationCoverage) -> Mapping[str, Any]:
    """Render an explicitly non-authoritative diagnostic copy.

    The copy carries no provenance and can never be reconstructed into
    canonical authority: :func:`admit_canonical_verification_coverage` always
    refuses, and canonical sinks resolve scope rather than consuming
    observations. Tenant identity is projected ONLY as the sovereign one-way
    hash; the raw UUID is never emitted.
    """
    if not isinstance(coverage, CanonicalVerificationCoverage):
        raise CanonicalCoverageAuthorityError(
            f"canonical_coverage_origin_not_sovereign:{type(coverage).__name__}"
        )
    aggregate = coverage.aggregate
    result = coverage.result
    return {
        "authority": "non_authoritative_diagnostic_copy",
        "producer": coverage.producer,
        "tenant_id_hash": _tenant_external_id(aggregate.tenant_id),
        "currency_code": aggregate.currency_code,
        "window_start": aggregate.window_start.isoformat(),
        "window_end": aggregate.window_end.isoformat(),
        "supported_platforms": list(coverage.supported_platforms),
        "matched_webhook_revenue_minor": aggregate.matched_webhook_revenue_minor,
        "connected_platform_revenue_minor": aggregate.connected_platform_revenue_minor,
        "coverage_percent": str(result.coverage_percent),
        "zero_denominator": bool(result.zero_denominator),
    }
