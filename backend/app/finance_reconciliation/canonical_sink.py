"""B2.6-P1 executable canonical-consumer framework (Corrective VI).

Defect classes closed here
--------------------------

1. **Caller-selected tenant.** The executor took a ``tenant_id`` UUID from
   ordinary application code and opened the matching governed session, so an
   authenticated A could observe B's canonical truth (or a canonical-looking
   zero for a tenant that does not exist). Class-closure theorem: the only
   tenant the executor can observe is the one inside a server-verified RS256
   JWT (``app.security.auth.decode_and_verify_jwt`` over the sovereign
   public-key ring). No ``tenant_id`` parameter exists, so there is no
   second tenant input to diverge; the database transaction tenant is then
   asserted equal to the verified tenant before any aggregation, and a
   durable tenant row is required before any financial scope may resolve
   (absence refuses, never zero).

2. **Transferable canonical authority.** Canonicality was a process-global
   nonce map plus a boolean predicate: any code importing two private names
   could mint canonical truth for synthetic legs, and the authority died on
   restart with no re-derivation. Class-closure theorem: there is no
   transferable canonical token in P1. The issuance map, the mint helper,
   the nonce, and the boolean predicate are deleted (not renamed). A
   detached object -- however shaped, however digest-correct -- is never
   canonical; the only canonical consequence is a fresh execution of the
   governed executor under verified server authentication. The deterministic
   ``content_digest`` that remains is an integrity tag, explicitly
   non-authoritative.

3. **Self-authorizing sink registry.** Runtime decoration could add or
   overwrite sinks, and an implementation swap kept authorization while
   hijacking consequences. Class-closure theorem: duplicate sink
   registration is refused (first binding wins; only byte-identical
   re-registration is a no-op for import idempotency), and every execution
   re-hashes the live implementation source and refuses on divergence from
   the reviewed binding. A directly mutated registry entry therefore fails
   at the hash check or at the proof-binding check below.

4. **Representation-as-proof.** Required proofs were non-empty strings, so
   ``("FAKE",)`` authorized. Class-closure theorem: every registration's
   proof set must equal the governed required set in
   :mod:`app.finance_reconciliation.proof_manifest` for the live contract
   version, and every execution re-verifies that binding alongside the
   executable hash. CI adjudication of the exact candidate SHA/tree is the
   outer binding; the runtime checks are the inner binding.

5. **Declarative successor persistence.** A mode string plus proof strings
   authorized future durable state with no schema, implementation, or
   evidence. Class-closure theorem: P1 authorizes no durable canonical
   persistence at all -- :func:`authorize_successor_persistence` always
   refuses -- because no migration-backed durable binding exists in P1.
   :func:`register_successor_persistence` validates declarations
   (governed mode, well-formed bound proofs, sovereign source, sovereign
   backing relation) so malformed declarations fail fast, but validation
   alone authorizes nothing durable. Durable authorization requires a P2
   migration-backed binding plus candidate-bound PASS evidence.

6. **Arbitrary callbacks on the canonical path.** An ``adjunct_provider``
   parameter executed any caller-supplied callable -- including
   network/LLM-capable closures -- inside canonical execution.
   Class-closure theorem: the canonical path takes no callable parameter.
   The only projection code that runs is the statically registered,
   deterministic, network-free implementation bound to the sink at build
   time (in P1, the lawful empty adjunct). There is no LLM call
   reachability from the canonical path because there is no callable input
   through which a model client could arrive.

Execution model
---------------

``execute_governed_sink`` is the only canonical entry point. It takes a
registered sink id plus a server-verified authentication token -- never a
tenant id, session, engine, URL, DTO, financial value, or callable -- opens
its own governed capability for the verified tenant, refuses unknown
tenants before aggregation, asserts transaction-bound tenant unity before
and after derivation, cross-checks integer mathematics through the
independent oracle, runs the registered projection implementation for
adjuncts only, refuses authoritative/tenant-bearing adjunct keys, and
materializes :class:`FinalCanonicalOutput` itself.

Ordinary analytics remain lawful: any module may compute any ratio. Such
output is simply not canonical -- there is no predicate that could make it
so -- and it can never enter a canonical interface because the only
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
from uuid import UUID

from app.finance_reconciliation.coverage_authority import (
    B23_SOVEREIGN_COVERAGE_PRODUCER,
    independent_coverage_percent,
    resolve_canonical_coverage,
)
from app.finance_reconciliation.proof_manifest import (
    require_proofs_bound,
    require_successor_proofs_bound,
)
from app.finance_reconciliation.semantic_contract import (
    B26_P1_CONTRACT_VERSION,
)
from app.finance_reconciliation.tenant_authority import (
    DATABASE_CAPABILITY_MODE,
    TENANT_AUTHORITY_MODE,
    open_governed_b23_session,
    require_tenant_row_exists,
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
# A projection implementation returning any of these (or any tenant-bearing
# key) is attempting to substitute truth and is refused.
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
        "content_digest",
        "adjunct_json",
        "tenant_id",
    }
)

# Governed provenance modes for future canonical persistence. P1 registers
# no persistence and authorizes none; the law below makes omission and
# string-only authorization falsifiable from now on.
SUCCESSOR_PROVENANCE_MODES = frozenset({"RE_DERIVE_ON_READ", "DURABLE_SOURCE_BINDING"})

# Sovereign B2.3 source relations a DURABLE_SOURCE_BINDING declaration may
# name. Only relations owned by the sovereign verification-coverage
# producer may anchor durable provenance; any other relation is refused at
# declaration time.
SOVEREIGN_SOURCE_RELATIONS = frozenset(
    {
        "public.b23_match_verdicts",
        "public.webhook_ingress_identities",
        "public.attribution_events",
    }
)


class CanonicalSinkError(ValueError):
    """A canonical-sink invocation violates executable consumer authority."""


class UnregisteredSinkError(CanonicalSinkError):
    """A sink id has no machine-governed executable registration."""


class DuplicateSinkError(CanonicalSinkError):
    """A sink id is already bound to a different executable registration."""


class FinalFieldSubstitutionError(CanonicalSinkError):
    """Projection code attempted to determine an authoritative field."""


class SuccessorProvenanceError(CanonicalSinkError):
    """A successor persistence declaration or authorization is not governed."""


@dataclass(frozen=True)
class SinkRegistration:
    """Machine-readable binding of a canonical sink to its executable."""

    sink_id: str
    implementation: str
    implementation_hash: str
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
    """Read-only sovereign readout offered to projection implementations."""

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
    """The framework-materialized B2.6 financial-truth consequence.

    A value of this type is a consequence of a fresh governed execution,
    never a bearer of authority: there is no predicate, map, nonce, seal,
    or helper that can certify a detached instance as canonical.
    :func:`verify_output_integrity` reports digest integrity only.
    Downstream canonical consumers must execute
    :func:`execute_governed_sink` themselves; accepting a transferred
    object as authority is a class violation regardless of its shape.
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
    content_digest: str
    adjunct_json: str


@dataclass(frozen=True)
class SuccessorPersistenceRegistration:
    """Governed declaration for future canonical durable state.

    A declaration is validated input, never authorization: P1 authorizes no
    durable canonical persistence (see :func:`authorize_successor_persistence`).
    """

    registration_id: str
    provenance_mode: str
    required_runtime_proof_ids: tuple[str, ...]
    contract_version: str
    sovereign_source: str
    backing_relation: str


SINK_REGISTRY: dict[str, SinkRegistration] = {}
_SINK_IMPLEMENTATIONS: dict[str, Callable[..., Any]] = {}
SUCCESSOR_PERSISTENCE_REGISTRY: dict[str, SuccessorPersistenceRegistration] = {}


def _canonical_json(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise CanonicalSinkError(f"canonical_adjunct_not_serializable:{exc}") from exc


def _content_digest_for(
    *,
    sink_id: str,
    contract_version: str,
    tenant_id_hash: str,
    currency_code: str,
    window_start: datetime,
    window_end: datetime,
    supported_platforms: tuple[str, ...],
    matched_minor: int,
    connected_minor: int,
    coverage_percent: Decimal,
    zero_denominator: bool,
    provenance_mode: str,
    sovereign_producer: str,
) -> str:
    payload = "|".join(
        [
            sink_id,
            contract_version,
            tenant_id_hash,
            currency_code,
            window_start.isoformat(),
            window_end.isoformat(),
            ",".join(supported_platforms),
            str(matched_minor),
            str(connected_minor),
            str(coverage_percent),
            str(bool(zero_denominator)),
            provenance_mode,
            sovereign_producer,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _content_digest(output: FinalCanonicalOutput) -> str:
    return _content_digest_for(
        sink_id=output.sink_id,
        contract_version=output.contract_version,
        tenant_id_hash=output.tenant_id_hash,
        currency_code=output.currency_code,
        window_start=output.window_start,
        window_end=output.window_end,
        supported_platforms=tuple(output.supported_platforms),
        matched_minor=int(output.matched_minor),
        connected_minor=int(output.connected_minor),
        coverage_percent=output.coverage_percent,
        zero_denominator=bool(output.zero_denominator),
        provenance_mode=output.provenance_mode,
        sovereign_producer=output.sovereign_producer,
    )


def _implementation_hash(func: Callable[..., Any]) -> str:
    """Observe the SHA-256 identity of the executable that will run.

    The hash binds the reviewed source bytes. It is recomputed on every
    canonical execution, so a swapped implementation -- however named --
    is refused even when every string in the registry still matches.
    """
    try:
        source = inspect.getsource(func)
    except (OSError, TypeError) as exc:
        raise CanonicalSinkError(
            f"canonical_sink_implementation_source_unavailable:{exc}"
        ) from exc
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def verify_output_integrity(candidate: Any) -> bool:
    """Report whether a value is digest-intact framework output.

    Integrity is explicitly NOT authority: ``True`` means the value has the
    shape of framework output whose content digest matches its authoritative
    fields and whose sink/contract/executable bindings are current. A
    digest-correct synthetic value still reports ``True`` here and must
    never be treated as canonical -- canonical consumers execute the
    governed sink instead of accepting transferred objects.
    """
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
    try:
        if candidate.content_digest != _content_digest(candidate):
            return False
        registration = SINK_REGISTRY[str(candidate.sink_id)]
        implementation = _SINK_IMPLEMENTATIONS.get(str(candidate.sink_id))
        if implementation is None:
            return False
        if _implementation_hash(implementation) != registration.implementation_hash:
            return False
    except CanonicalSinkError:
        return False
    return True


def resolve_authenticated_tenant(auth_token: str) -> UUID:
    """Resolve the server-authenticated tenant from a verified JWT.

    The token is verified against the sovereign RS256 public-key ring by
    ``app.security.auth`` (B2.5/B1.2 authentication substrate, reused here
    so B2.6 introduces no second identity ontology). Only a token minted
    with the signing private material verifies; ordinary application code
    holding no signing key cannot select, forge, or substitute a tenant.
    Every verification failure refuses -- it can never become a tenant.
    """
    if not isinstance(auth_token, str) or not auth_token.strip():
        raise CanonicalSinkError("governed_sink_requires_verified_server_auth")
    from app.security.auth import (  # noqa: PLC0415
        decode_and_verify_jwt,
        unauthorized_auth_error,
    )

    claims = decode_and_verify_jwt(auth_token.strip())
    raw_tenant = claims.get("tenant_id")
    if not raw_tenant:
        raise unauthorized_auth_error()
    try:
        return UUID(str(raw_tenant))
    except ValueError as exc:
        raise unauthorized_auth_error() from exc


def canonical_sink(
    *,
    sink_id: str,
    version: str,
    required_runtime_proof_ids: tuple[str, ...] | list[str],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register an executable canonical-sink implementation.

    The decorator binds the sink id to the decorated function's module and
    qualified name, the SHA-256 of its reviewed source, the current contract
    version, the sovereign source, the tenant/capability/provenance modes,
    and the projection-only law. Proof identifiers must equal the governed
    required set in the proof manifest: forgeries fail here, at declaration
    time. A bare string claim without this registration is not a canonical
    sink, and a second registration of the same id with a different binding
    is refused -- the first binding wins.
    """
    proofs = tuple(required_runtime_proof_ids)
    if not sink_id or not str(sink_id).strip():
        raise CanonicalSinkError("canonical_sink_id_required")
    if not version or not str(version).strip():
        raise CanonicalSinkError("canonical_sink_version_required")
    bound = require_proofs_bound(
        sink_id=str(sink_id),
        required_runtime_proof_ids=proofs,
        contract_version=B26_P1_CONTRACT_VERSION,
    )

    def decorate(func: Callable[..., Any]) -> Callable[..., Any]:
        implementation = f"{func.__module__}.{func.__qualname__}"
        registration = SinkRegistration(
            sink_id=str(sink_id),
            implementation=implementation,
            implementation_hash=_implementation_hash(func),
            contract_version=B26_P1_CONTRACT_VERSION,
            output_contract="final_canonical_output_v1",
            sovereign_source=B23_SOVEREIGN_COVERAGE_PRODUCER,
            tenant_authority_mode=TENANT_AUTHORITY_MODE,
            database_capability_mode=DATABASE_CAPABILITY_MODE,
            provenance_mode=SINK_PROVENANCE_MODE,
            projection_policy=PROJECTION_POLICY,
            version=str(version),
            required_runtime_proof_ids=bound,
        )
        existing = SINK_REGISTRY.get(str(sink_id))
        if existing is not None:
            if existing == registration:
                return func
            raise DuplicateSinkError(
                f"canonical_sink_duplicate_refused:{sink_id}"
            )
        SINK_REGISTRY[str(sink_id)] = registration
        _SINK_IMPLEMENTATIONS[str(sink_id)] = func
        return func

    return decorate


def require_registered_sink(sink_id: str) -> SinkRegistration:
    """Require a machine-governed executable sink registration.

    Re-verifies the live executable hash and the proof binding on every
    call: a mutated registry entry or a swapped implementation is refused
    here even when the registry strings still name the sink.
    """
    registration = SINK_REGISTRY.get(str(sink_id))
    if registration is None:
        raise UnregisteredSinkError(f"canonical_sink_not_registered:{sink_id}")
    implementation = _SINK_IMPLEMENTATIONS.get(str(sink_id))
    if implementation is None:
        raise UnregisteredSinkError(f"canonical_sink_implementation_missing:{sink_id}")
    if _implementation_hash(implementation) != registration.implementation_hash:
        raise CanonicalSinkError(
            f"canonical_sink_implementation_diverged:{sink_id}"
        )
    require_proofs_bound(
        sink_id=str(sink_id),
        required_runtime_proof_ids=registration.required_runtime_proof_ids,
        contract_version=registration.contract_version,
    )
    if registration.contract_version != B26_P1_CONTRACT_VERSION:
        raise CanonicalSinkError(f"canonical_sink_contract_stale:{sink_id}")
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
    """Serialize framework output for approved consumers.

    This is a projection renderer, not an authority predicate: it requires
    digest-intact framework output and emits only the sovereign one-way
    tenant hash (raw tenant identity never leaves this boundary). A
    digest-correct synthetic value renders here exactly as framework output
    would -- and confers nothing, because no canonical consumer accepts
    transferred objects.
    """
    if not verify_output_integrity(output):
        raise CanonicalSinkError(
            f"value_is_not_framework_output:{type(output).__name__}"
        )
    rendered = _project_external_fields(output)
    if "tenant_id" in rendered:
        raise CanonicalSinkError("canonical_external_emits_raw_tenant_id")
    return rendered


async def execute_governed_sink(
    sink_id: str,
    *,
    auth_token: str,
    window_start: datetime,
    window_end: datetime,
    supported_platforms: Any = None,
    currency_code: str = "USD",
) -> FinalCanonicalOutput:
    """Execute a registered canonical sink for the server-authenticated tenant.

    Accepts a registered sink id plus a server-verified authentication token
    -- no tenant id, session, engine, database value, DTO, mapping,
    financial number, or callable. The framework verifies the token against
    the sovereign key ring, refuses unknown tenants before aggregation,
    opens its own governed capability for the verified tenant, re-derives
    sovereign B2.3 truth, verifies integer mathematics through the
    independent oracle, runs the registered projection implementation for
    adjuncts only, and materializes the authoritative fields itself.
    """
    registration = require_registered_sink(sink_id)
    tenant_id = resolve_authenticated_tenant(auth_token)
    implementation = _SINK_IMPLEMENTATIONS[str(sink_id)]
    async with open_governed_b23_session(tenant_id) as session:
        await require_tenant_row_exists(session, tenant_id)
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
        return FinalCanonicalOutput(
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
            content_digest=_content_digest_for(
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
                zero_denominator=bool(context.zero_denominator),
                provenance_mode=SINK_PROVENANCE_MODE,
                sovereign_producer=B23_SOVEREIGN_COVERAGE_PRODUCER,
            ),
            adjunct_json=_canonical_json(cleaned),
        )


def executor_signature_has_no_session_capability() -> bool:
    """Introspect that the canonical executor takes no session capability."""
    parameters = inspect.signature(execute_governed_sink).parameters
    forbidden = {"session", "engine", "factory", "connection", "database_url", "dsn"}
    return not (set(parameters) & forbidden)


def executor_binds_tenant_from_verified_auth_only() -> bool:
    """Introspect that no caller-supplied tenant or callable can enter."""
    parameters = inspect.signature(execute_governed_sink).parameters
    forbidden = {
        "tenant_id",
        "tenant",
        "scope_tenant",
        "adjunct_provider",
        "callback",
        "provider",
        "projection",
        "session",
        "engine",
        "factory",
        "connection",
        "database_url",
        "dsn",
    }
    names = set(parameters)
    return "auth_token" in names and not (names & forbidden)


def register_successor_persistence(
    *,
    registration_id: str,
    provenance_mode: str,
    required_runtime_proof_ids: tuple[str, ...] | list[str],
    sovereign_source: str = B23_SOVEREIGN_COVERAGE_PRODUCER,
    backing_relation: str = "public.b23_match_verdicts",
) -> SuccessorPersistenceRegistration:
    """Validate a future canonical durable-state declaration.

    A declaration is validated input, never authorization. Refuses unknown
    modes, malformed or denylisted proofs, non-sovereign sources, and
    non-sovereign backing relations at declaration time. P1 registers no
    persistence; every declaration awaits P2 durable binding.
    """
    proofs = require_successor_proofs_bound(
        registration_id=str(registration_id),
        required_runtime_proof_ids=tuple(required_runtime_proof_ids),
    )
    if not registration_id or not str(registration_id).strip():
        raise SuccessorProvenanceError("successor_registration_id_required")
    if str(provenance_mode) not in SUCCESSOR_PROVENANCE_MODES:
        raise SuccessorProvenanceError(
            f"successor_provenance_mode_not_governed:{provenance_mode}"
        )
    if str(sovereign_source) != B23_SOVEREIGN_COVERAGE_PRODUCER:
        raise SuccessorProvenanceError(
            f"successor_sovereign_source_not_governed:{sovereign_source}"
        )
    if str(backing_relation) not in SOVEREIGN_SOURCE_RELATIONS:
        raise SuccessorProvenanceError(
            f"successor_backing_relation_not_sovereign:{backing_relation}"
        )
    registration = SuccessorPersistenceRegistration(
        registration_id=str(registration_id),
        provenance_mode=str(provenance_mode),
        required_runtime_proof_ids=proofs,
        contract_version=B26_P1_CONTRACT_VERSION,
        sovereign_source=str(sovereign_source),
        backing_relation=str(backing_relation),
    )
    SUCCESSOR_PERSISTENCE_REGISTRY[str(registration_id)] = registration
    return registration


def deregister_successor_persistence(registration_id: str) -> None:
    """Remove a successor declaration (tests and superseded phases only)."""
    SUCCESSOR_PERSISTENCE_REGISTRY.pop(str(registration_id), None)


def authorize_successor_persistence(registration_id: str) -> bool:
    """Authorize durable canonical persistence.

    P1 law: always refuses. No migration-backed durable binding exists in
    P1, so no declaration -- however well-formed -- can authorize durable
    canonical state. Durable authorization requires a P2 migration-backed
    binding (DB-enforced source relation, least-privilege writer, history
    discipline) plus candidate-bound PASS evidence. This function exists so
    that requirement is machine-enforced rather than conventional.
    """
    registration = SUCCESSOR_PERSISTENCE_REGISTRY.get(str(registration_id))
    if registration is None:
        raise SuccessorProvenanceError(
            f"successor_persistence_not_registered:{registration_id}"
        )
    raise SuccessorProvenanceError(
        "successor_persistence_requires_p2_durable_binding:"
        f"{registration_id}"
    )


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
