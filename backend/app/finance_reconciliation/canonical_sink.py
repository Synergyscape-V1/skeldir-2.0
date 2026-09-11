"""B2.6-P1 executable canonical-consumer framework (Corrective V).

Defect classes closed here
--------------------------

1. **Symbolic sink governance.** A governed sink was a string in a set with
   no executable binding: any future module could claim an approved name,
   call the resolver as a decoy (or not call it at all), and emit another
   value while checks stayed green. Class-closure theorem: canonical status
   is available only through this framework executing a registered sink
   implementation; the framework derives sovereign truth itself through its
   own governed capability and materializes the authoritative fields
   itself after the projection callback returns.

2. **Source contact confused with source dependence.** Calling the resolver
   satisfied superficial proof while the final field came from elsewhere.
   Class-closure theorem: ``FINAL_CANONICAL_FIELD == sovereign derivation
   under the same governed scope`` holds by construction -- the callback
   supplies only non-authoritative adjuncts, any authoritative key in the
   adjunct is refused, and the framework overwrites nothing: it builds the
   final object from the sovereign result after the callback completes.

3. **Representation crossing re-acquiring authority.** Serialized,
   copied, or reconstructed state could re-enter through scope coherence.
   Class-closure theorem: the canonical sink accepts scope only (never a
   DTO, mapping, or JSON value); every execution re-derives from sovereign
   state (``RE_DERIVE_ON_READ``); caller values have no parameter to enter
   through and are ignored by construction.

4. **Declarative successor provenance.** A future durable state could omit
   provenance with no machine failure. Class-closure theorem: every future
   canonical persistence registration must declare one governed provenance
   mode with its required runtime proofs, and
   :func:`authorize_successor_persistence` refuses anything else. P1 itself
   registers no persistence.

Execution model
---------------

``execute_governed_sink`` is the only canonical entry point. It takes a
registered sink id plus a server-derived scope -- never a session, engine,
URL, DTO, or financial value -- opens its own governed capability for the
scope tenant, asserts transaction-bound tenant unity before aggregation,
derives the sovereign B2.3 result, cross-checks integer mathematics through
the independent oracle, runs the registered projection callback for
adjuncts only, refuses authoritative/tenant-bearing adjunct keys, and
materializes :class:`FinalCanonicalOutput` itself.

Ordinary analytics remain lawful: any module may compute any ratio. Such
output is simply not canonical -- :func:`is_canonical_output` is false for
it -- and it can never enter a canonical interface because the only
canonical interfaces are the registered executors in this module.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.finance_reconciliation.coverage_authority import (
    B23_SOVEREIGN_COVERAGE_PRODUCER,
    independent_coverage_percent,
    resolve_canonical_coverage,
)
from app.finance_reconciliation.semantic_contract import (
    B26_P1_CONTRACT_VERSION,
)
from app.finance_reconciliation.tenant_authority import (
    DATABASE_CAPABILITY_MODE,
    TENANT_AUTHORITY_MODE,
    open_governed_b23_session,
)


CANONICAL_SINK_EXECUTOR = (
    "app.finance_reconciliation.canonical_sink.execute_governed_sink"
)
CANONICAL_SINK_MODULE = "app.finance_reconciliation.canonical_sink"
FINAL_OUTPUT_TYPE = "app.finance_reconciliation.canonical_sink.FinalCanonicalOutput"
FINAL_FIELD_OWNER = "canonical_sink_framework_post_callback_materialization"
SINK_PROVENANCE_MODE = "RE_DERIVE_ON_READ"
PROJECTION_POLICY = "adjunct_only_authoritative_fields_framework_owned"

CANONICAL_OUTPUT_AUTHORITY = "canonical_B2.6_financial_truth"

# Fields the trusted framework materializes from the sovereign derivation.
# A projection callback returning any of these (or any tenant-bearing key)
# is attempting to substitute truth and is refused.
AUTHORITATIVE_FIELD_NAMES = frozenset(
    {
        "authority",
        "sink_id",
        "contract_version",
        "tenant_id_hash",
        "currency_code",
        "window_start",
        "window_end",
        "supported_platforms",
        "matched_minor",
        "connected_minor",
        "coverage_percent",
        "zero_denominator",
        "provenance_mode",
        "sovereign_producer",
        "provenance_nonce",
        "adjunct_json",
        "tenant_id",
    }
)

# Governed provenance modes for future canonical persistence. P1 registers
# no persistence; the law below makes omission falsifiable from now on.
SUCCESSOR_PROVENANCE_MODES = frozenset({"RE_DERIVE_ON_READ", "DURABLE_SOURCE_BINDING"})


class CanonicalSinkError(ValueError):
    """A canonical-sink invocation violates executable consumer authority."""


class UnregisteredSinkError(CanonicalSinkError):
    """A sink id has no machine-governed executable registration."""


class FinalFieldSubstitutionError(CanonicalSinkError):
    """Projection code attempted to determine an authoritative field."""


class SuccessorProvenanceError(CanonicalSinkError):
    """A successor persistence registration omits governed provenance law."""


@dataclass(frozen=True)
class SinkRegistration:
    """Machine-readable binding of a canonical sink to its executable."""

    sink_id: str
    implementation: str
    contract_version: str
    output_contract: str
    sovereign_source: str
    tenant_authority_mode: str
    database_capability_mode: str
    provenance_mode: str
    projection_policy: str
    version: str
    required_runtime_proof_ids: tuple[str, ...]


@dataclass(frozen=True)
class AdjunctContext:
    """Read-only sovereign readout offered to projection callbacks."""

    sink_id: str
    tenant_id_hash: str
    currency_code: str
    window_start: datetime
    window_end: datetime
    supported_platforms: tuple[str, ...]
    matched_minor: int
    connected_minor: int
    coverage_percent: Decimal
    zero_denominator: bool


@dataclass(frozen=True)
class FinalCanonicalOutput:
    """The only canonical B2.6 financial-truth representation.

    Instances are canonical only when returned by
    :func:`execute_governed_sink` for a registered sink: the framework
    binds a per-execution nonce to the authoritative content digest, and
    :func:`is_canonical_output` verifies that binding. Direct construction
    (or nonce/content reuse across differing content) is non-canonical and
    merge-blocking outside this module.
    """

    authority: str
    sink_id: str
    contract_version: str
    tenant_id_hash: str
    currency_code: str
    window_start: datetime
    window_end: datetime
    supported_platforms: tuple[str, ...]
    matched_minor: int
    connected_minor: int
    coverage_percent: Decimal
    zero_denominator: bool
    provenance_mode: str
    sovereign_producer: str
    provenance_nonce: str
    adjunct_json: str


@dataclass(frozen=True)
class SuccessorPersistenceRegistration:
    """Governed declaration for future canonical durable state."""

    registration_id: str
    provenance_mode: str
    required_runtime_proof_ids: tuple[str, ...]
    contract_version: str
    sovereign_source: str


SINK_REGISTRY: dict[str, SinkRegistration] = {}
_SINK_IMPLEMENTATIONS: dict[str, Callable[..., Any]] = {}
_ISSUED_PROVENANCE_DIGESTS: dict[str, str] = {}
SUCCESSOR_PERSISTENCE_REGISTRY: dict[str, SuccessorPersistenceRegistration] = {}


def _canonical_json(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise CanonicalSinkError(f"canonical_adjunct_not_serializable:{exc}") from exc


def _content_digest(output: FinalCanonicalOutput) -> str:
    payload = "|".join(
        [
            output.sink_id,
            output.contract_version,
            output.tenant_id_hash,
            output.currency_code,
            output.window_start.isoformat(),
            output.window_end.isoformat(),
            ",".join(output.supported_platforms),
            str(output.matched_minor),
            str(output.connected_minor),
            str(output.coverage_percent),
            str(bool(output.zero_denominator)),
            output.provenance_mode,
            output.sovereign_producer,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _issue_provenance(output: FinalCanonicalOutput) -> FinalCanonicalOutput:
    nonce = uuid4().hex
    issued = FinalCanonicalOutput(
        authority=output.authority,
        sink_id=output.sink_id,
        contract_version=output.contract_version,
        tenant_id_hash=output.tenant_id_hash,
        currency_code=output.currency_code,
        window_start=output.window_start,
        window_end=output.window_end,
        supported_platforms=output.supported_platforms,
        matched_minor=output.matched_minor,
        connected_minor=output.connected_minor,
        coverage_percent=output.coverage_percent,
        zero_denominator=output.zero_denominator,
        provenance_mode=output.provenance_mode,
        sovereign_producer=output.sovereign_producer,
        provenance_nonce=nonce,
        adjunct_json=output.adjunct_json,
    )
    _ISSUED_PROVENANCE_DIGESTS[nonce] = _content_digest(issued)
    return issued


def is_canonical_output(candidate: Any) -> bool:
    """Report whether a value is framework-issued canonical truth."""
    if not isinstance(candidate, FinalCanonicalOutput):
        return False
    if candidate.authority != CANONICAL_OUTPUT_AUTHORITY:
        return False
    if candidate.provenance_mode != SINK_PROVENANCE_MODE:
        return False
    if candidate.contract_version != B26_P1_CONTRACT_VERSION:
        return False
    if candidate.sink_id not in SINK_REGISTRY:
        return False
    expected = _ISSUED_PROVENANCE_DIGESTS.get(candidate.provenance_nonce)
    if expected is None:
        return False
    return expected == _content_digest(candidate)


def require_canonical_output(candidate: Any) -> FinalCanonicalOutput:
    """Require framework-issued canonical truth or refuse it."""
    if not is_canonical_output(candidate):
        raise CanonicalSinkError(
            f"value_is_not_framework_issued_canonical_truth:{type(candidate).__name__}"
        )
    return candidate


def canonical_sink(
    *,
    sink_id: str,
    version: str,
    required_runtime_proof_ids: tuple[str, ...] | list[str],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register an executable canonical-sink implementation.

    The decorator binds the sink id to the decorated function's module and
    qualified name, the current contract version, the sovereign source, the
    tenant/capability/provenance modes, and the projection-only law. A bare
    string claim without this registration is not a canonical sink.
    """
    proofs = tuple(required_runtime_proof_ids)
    if not sink_id or not str(sink_id).strip():
        raise CanonicalSinkError("canonical_sink_id_required")
    if not version or not str(version).strip():
        raise CanonicalSinkError("canonical_sink_version_required")
    if not proofs:
        raise CanonicalSinkError("canonical_sink_required_proofs_missing")

    def decorate(func: Callable[..., Any]) -> Callable[..., Any]:
        implementation = f"{func.__module__}.{func.__qualname__}"
        registration = SinkRegistration(
            sink_id=str(sink_id),
            implementation=implementation,
            contract_version=B26_P1_CONTRACT_VERSION,
            output_contract="final_canonical_output_v1",
            sovereign_source=B23_SOVEREIGN_COVERAGE_PRODUCER,
            tenant_authority_mode=TENANT_AUTHORITY_MODE,
            database_capability_mode=DATABASE_CAPABILITY_MODE,
            provenance_mode=SINK_PROVENANCE_MODE,
            projection_policy=PROJECTION_POLICY,
            version=str(version),
            required_runtime_proof_ids=proofs,
        )
        SINK_REGISTRY[str(sink_id)] = registration
        _SINK_IMPLEMENTATIONS[str(sink_id)] = func
        return func

    return decorate


def require_registered_sink(sink_id: str) -> SinkRegistration:
    """Require a machine-governed executable sink registration."""
    registration = SINK_REGISTRY.get(str(sink_id))
    if registration is None:
        raise UnregisteredSinkError(f"canonical_sink_not_registered:{sink_id}")
    implementation = _SINK_IMPLEMENTATIONS.get(str(sink_id))
    if implementation is None:
        raise UnregisteredSinkError(f"canonical_sink_implementation_missing:{sink_id}")
    return registration


def reject_authoritative_adjunct(adjunct: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate projection adjuncts: authoritative/tenant keys are refused."""
    if adjunct is None:
        return {}
    if not isinstance(adjunct, Mapping):
        raise FinalFieldSubstitutionError(
            f"canonical_adjunct_must_be_mapping_or_none:{type(adjunct).__name__}"
        )
    cleaned: dict[str, Any] = {}
    for key, value in adjunct.items():
        name = str(key)
        if name in AUTHORITATIVE_FIELD_NAMES or "tenant" in name.lower():
            raise FinalFieldSubstitutionError(
                f"projection_may_not_determine_authoritative_field:{name}"
            )
        cleaned[name] = value
    return cleaned


def _tenant_external_id(tenant_id: UUID | str) -> str:
    from app.trust.refusal import tenant_hash  # noqa: PLC0415

    return tenant_hash(tenant_id)


def _project_external_fields(output: FinalCanonicalOutput) -> dict[str, Any]:
    """Render the approved external projection (hash identity only)."""
    return {
        "authority": output.authority,
        "sink_id": output.sink_id,
        "contract_version": output.contract_version,
        "tenant_id_hash": output.tenant_id_hash,
        "currency_code": output.currency_code,
        "window_start": output.window_start.isoformat(),
        "window_end": output.window_end.isoformat(),
        "supported_platforms": list(output.supported_platforms),
        "matched_minor": int(output.matched_minor),
        "connected_minor": int(output.connected_minor),
        "coverage_percent": str(output.coverage_percent),
        "zero_denominator": bool(output.zero_denominator),
        "provenance_mode": output.provenance_mode,
        "sovereign_producer": output.sovereign_producer,
    }


def to_canonical_external(output: FinalCanonicalOutput) -> dict[str, Any]:
    """Serialize framework-issued canonical truth for approved consumers.

    Raw tenant identity is never emitted: only the sovereign one-way hash
    bound at derivation time leaves this boundary.
    """
    require_canonical_output(output)
    rendered = _project_external_fields(output)
    if "tenant_id" in rendered:
        raise CanonicalSinkError("canonical_external_emits_raw_tenant_id")
    return rendered


async def execute_governed_sink(
    sink_id: str,
    *,
    tenant_id: UUID,
    window_start: datetime,
    window_end: datetime,
    supported_platforms: Any = None,
    currency_code: str = "USD",
    adjunct_provider: Callable[[AdjunctContext], Mapping[str, Any] | None]
    | None = None,
) -> FinalCanonicalOutput:
    """Execute a registered canonical sink for a server-derived scope.

    Accepts scope only -- no session, engine, database value, DTO, mapping,
    or financial number. The framework opens its own governed capability,
    re-derives sovereign B2.3 truth, verifies integer mathematics through
    the independent oracle, runs the projection callback for adjuncts only,
    and materializes the authoritative fields itself.
    """
    registration = require_registered_sink(sink_id)
    if tenant_id is None or not str(tenant_id).strip():
        raise CanonicalSinkError("governed_sink_requires_server_derived_tenant")
    implementation = _SINK_IMPLEMENTATIONS[str(sink_id)]
    async with open_governed_b23_session(tenant_id) as session:
        coverage = await resolve_canonical_coverage(
            session,
            tenant_id=tenant_id,
            window_start=window_start,
            window_end=window_end,
            supported_platforms=supported_platforms,
            currency_code=currency_code,
        )
        aggregate = coverage.aggregate
        result = coverage.result
        expected_percent, expected_zero = independent_coverage_percent(
            aggregate.matched_webhook_revenue_minor,
            aggregate.connected_platform_revenue_minor,
        )
        if result.coverage_percent != expected_percent:
            raise CanonicalSinkError(
                "governed_sink_sovereign_math_diverged_from_oracle"
            )
        if result.zero_denominator is not expected_zero:
            raise CanonicalSinkError(
                "governed_sink_sovereign_zero_diverged_from_oracle"
            )
        context = AdjunctContext(
            sink_id=str(sink_id),
            tenant_id_hash=_tenant_external_id(aggregate.tenant_id),
            currency_code=aggregate.currency_code,
            window_start=aggregate.window_start,
            window_end=aggregate.window_end,
            supported_platforms=tuple(coverage.supported_platforms),
            matched_minor=int(aggregate.matched_webhook_revenue_minor),
            connected_minor=int(aggregate.connected_platform_revenue_minor),
            coverage_percent=result.coverage_percent,
            zero_denominator=bool(result.zero_denominator),
        )
        raw_adjunct = implementation(context) if implementation is not None else {}
        cleaned = reject_authoritative_adjunct(raw_adjunct)
        if adjunct_provider is not None:
            extra = reject_authoritative_adjunct(adjunct_provider(context))
            for key in extra:
                if key in cleaned:
                    raise FinalFieldSubstitutionError(f"duplicate_adjunct_key:{key}")
            cleaned.update(extra)
        draft = FinalCanonicalOutput(
            authority=CANONICAL_OUTPUT_AUTHORITY,
            sink_id=str(sink_id),
            contract_version=registration.contract_version,
            tenant_id_hash=context.tenant_id_hash,
            currency_code=context.currency_code,
            window_start=context.window_start,
            window_end=context.window_end,
            supported_platforms=context.supported_platforms,
            matched_minor=context.matched_minor,
            connected_minor=context.connected_minor,
            coverage_percent=context.coverage_percent,
            zero_denominator=context.zero_denominator,
            provenance_mode=SINK_PROVENANCE_MODE,
            sovereign_producer=B23_SOVEREIGN_COVERAGE_PRODUCER,
            provenance_nonce="",
            adjunct_json=_canonical_json(cleaned),
        )
        return _issue_provenance(draft)


def executor_signature_has_no_session_capability() -> bool:
    """Introspect that the canonical executor takes no session capability."""
    parameters = inspect.signature(execute_governed_sink).parameters
    forbidden = {"session", "engine", "factory", "connection", "database_url", "dsn"}
    return not (set(parameters) & forbidden)


def register_successor_persistence(
    *,
    registration_id: str,
    provenance_mode: str,
    required_runtime_proof_ids: tuple[str, ...] | list[str],
    sovereign_source: str = B23_SOVEREIGN_COVERAGE_PRODUCER,
) -> SuccessorPersistenceRegistration:
    """Register a future canonical durable state with governed provenance."""
    proofs = tuple(required_runtime_proof_ids)
    if not registration_id or not str(registration_id).strip():
        raise SuccessorProvenanceError("successor_registration_id_required")
    if str(provenance_mode) not in SUCCESSOR_PROVENANCE_MODES:
        raise SuccessorProvenanceError(
            f"successor_provenance_mode_not_governed:{provenance_mode}"
        )
    if not proofs:
        raise SuccessorProvenanceError("successor_provenance_requires_runtime_proofs")
    registration = SuccessorPersistenceRegistration(
        registration_id=str(registration_id),
        provenance_mode=str(provenance_mode),
        required_runtime_proof_ids=proofs,
        contract_version=B26_P1_CONTRACT_VERSION,
        sovereign_source=str(sovereign_source),
    )
    SUCCESSOR_PERSISTENCE_REGISTRY[str(registration_id)] = registration
    return registration


def deregister_successor_persistence(registration_id: str) -> None:
    """Remove a successor registration (tests and superseded phases only)."""
    SUCCESSOR_PERSISTENCE_REGISTRY.pop(str(registration_id), None)


def authorize_successor_persistence(registration_id: str) -> bool:
    """Authorize only provenance-bound successor persistence registrations."""
    registration = SUCCESSOR_PERSISTENCE_REGISTRY.get(str(registration_id))
    if registration is None:
        raise SuccessorProvenanceError(
            f"successor_persistence_not_registered:{registration_id}"
        )
    if registration.provenance_mode not in SUCCESSOR_PROVENANCE_MODES:
        raise SuccessorProvenanceError(
            f"successor_provenance_mode_not_governed:{registration.provenance_mode}"
        )
    if not registration.required_runtime_proof_ids:
        raise SuccessorProvenanceError("successor_provenance_requires_runtime_proofs")
    if registration.contract_version != B26_P1_CONTRACT_VERSION:
        raise SuccessorProvenanceError("successor_provenance_contract_version_mismatch")
    return True


def _lawful_empty_adjunct(context: AdjunctContext) -> dict[str, Any]:
    """Lawful P1 placeholder projection: no adjuncts, truth untouched."""
    return {}


canonical_sink(
    sink_id="future_B2.6_deterministic_reconciliation_projection_boundary",
    version="v5.0",
    required_runtime_proof_ids=("V-2", "V-3", "V-4"),
)(_lawful_empty_adjunct)
canonical_sink(
    sink_id="future_finance_projection",
    version="v5.0",
    required_runtime_proof_ids=("V-2", "V-3", "V-4"),
)(_lawful_empty_adjunct)
canonical_sink(
    sink_id="future_B2.6_TrustEnvelope_projection",
    version="v5.0",
    required_runtime_proof_ids=("V-2", "V-3", "V-4"),
)(_lawful_empty_adjunct)
