"""B2.6-P1 authoritative field registry and immutable snapshot boundary (Corrective IX).

Corrective-IX law (defect class IX-A: mutable authority alias reintroduction)
-----------------------------------------------------------------------------
AUTHORITATIVE STATE AND NON-AUTHORITATIVE PROJECTION STATE MUST NEVER SHARE
MUTABLE STORAGE THAT CAN CHANGE A LATER CANONICAL CONSEQUENCE::

    MUTABLE_REACHABLE_GRAPH(P) ∩ AUTHORITATIVE_MATERIALIZATION_GRAPH(S) = ∅

for all mutable objects. Immutable shared values are lawful; mutable shared
storage is not.

This module is the single machine-readable source of truth for which
``FinalCanonicalOutput`` fields are authoritative versus adjunct /
non-authoritative, with per-field isolation obligations. The static validator
(``scripts/ci/validate_b26_p1_authority.py``) enforces that the registry
exactly covers the ``FinalCanonicalOutput`` dataclass: a new authoritative
field without a registry declaration turns CI RED. The behavioral battery
(``test_b26_p1_corrective_ix_consequence.py``) enforces that every
authoritative field is snapshot-isolated: shared-storage in-place mutation
leaves canonical truth sovereign or execution refuses.

No second semantic ontology is created: the field *list* is derived from the
canonical ``FinalCanonicalOutput`` type itself (ground truth), and this
registry supplies only the isolation *obligations* for that list. Sovereign
sources (B2.3 callable, tenant authority, JWT substrate, semantic contract)
are composed, never reimplemented.

Runtime boundary
----------------
    :func:`freeze_platform_scope` normalizes the platform scope to a deeply
    immutable ``tuple[str, ...]``. On pristine inputs (already a tuple of str)
    it returns an equal tuple with identical semantics -- behavior preserving.
    On future mutable inputs (list/set/frozenset of str) it converts to an
    independent immutable tuple instead of aliasing mutable storage; unordered
    set/frozenset inputs are sorted so the frozen form is deterministic across
    processes (set iteration order varies with hash randomization, and
    deterministic finance authority must never depend on it). Mapping,
    object, bytearray, or non-str members are refused fail-closed: a future
    extension needing a new shape must declare it here first.

:func:`assert_snapshot_types_immutable` is the runtime invariant assertion:
every authoritative snapshot local must belong to its allowed immutable
family before projection code runs. A future refactor that makes a snapshot
field mutable (e.g. tuple -> list) refuses loudly instead of drifting
silently.

The pre/post-projection digest comparison in ``execute_governed_sink``
(which calls :func:`snapshot_digest_inputs`) converts any residual alias
violation into refusal: if projection-reachable mutation alters snapshot
storage, the digests diverge and execution raises instead of emitting
corrupted canonical truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping

from app.finance_reconciliation.external_semantics import EXTERNAL_SEMANTICS


@dataclass(frozen=True)
class AuthoritativeFieldSpec:
    """Machine-observed isolation obligation for one output field."""

    field_name: str
    authoritative: bool
    sovereign_source: str
    snapshot_point: str
    allowed_type_family: str
    projection_representation: str
    alias_policy: str
    externalization_policy: str


AUTHORITATIVE_FIELD_REGISTRY: dict[str, AuthoritativeFieldSpec] = {
    "authority": AuthoritativeFieldSpec(
        field_name="authority",
        authoritative=True,
        sovereign_source="framework constant CANONICAL_OUTPUT_AUTHORITY",
        snapshot_point="construction (module import, trusted computing base)",
        allowed_type_family="str (immutable constant)",
        projection_representation="omitted from projection view (not projection-visible)",
        alias_policy="constant immutable value; no shared mutable storage",
        externalization_policy="emitted as render key (sovereign label)",
    ),
    "sink_id": AuthoritativeFieldSpec(
        field_name="sink_id",
        authoritative=True,
        sovereign_source="caller scope sink_id bound at final atomic capture",
        snapshot_point="post-oracle final atomic _capture_verified_implementation",
        allowed_type_family="str (immutable)",
        projection_representation="scalar copy in AdjunctContext.sink_id",
        alias_policy="immutable value sharing lawful; mutable sharing forbidden",
        externalization_policy="emitted as render key",
    ),
    "contract_version": AuthoritativeFieldSpec(
        field_name="contract_version",
        authoritative=True,
        sovereign_source="registration contract_version == B26_P1_CONTRACT_VERSION",
        snapshot_point="post-oracle final atomic capture",
        allowed_type_family="str (immutable)",
        projection_representation="omitted from projection view (framework-owned)",
        alias_policy="immutable value sharing lawful; mutable sharing forbidden",
        externalization_policy="emitted as render key",
    ),
    "tenant_id_hash": AuthoritativeFieldSpec(
        field_name="tenant_id_hash",
        authoritative=True,
        sovereign_source="aggregate.tenant_id via app.trust.refusal.tenant_hash",
        snapshot_point="post-oracle final atomic capture",
        allowed_type_family="str (immutable one-way hash)",
        projection_representation="scalar copy in AdjunctContext.tenant_id_hash",
        alias_policy="immutable value sharing lawful; mutable sharing forbidden",
        externalization_policy="emitted hash-only (raw UUID never externalized)",
    ),
    "currency_code": AuthoritativeFieldSpec(
        field_name="currency_code",
        authoritative=True,
        sovereign_source="aggregate.currency_code (B2.3 sovereign derivation)",
        snapshot_point="post-oracle final atomic capture",
        allowed_type_family="str (immutable)",
        projection_representation="scalar copy in AdjunctContext.currency_code",
        alias_policy="immutable value sharing lawful; mutable sharing forbidden",
        externalization_policy="emitted as render key",
    ),
    "window_start": AuthoritativeFieldSpec(
        field_name="window_start",
        authoritative=True,
        sovereign_source="aggregate.window_start (B2.3 sovereign derivation)",
        snapshot_point="post-oracle final atomic capture",
        allowed_type_family="datetime (immutable)",
        projection_representation="copy in AdjunctContext.window_start",
        alias_policy="immutable value sharing lawful; mutable sharing forbidden",
        externalization_policy="emitted as ISO-8601 render key",
    ),
    "window_end": AuthoritativeFieldSpec(
        field_name="window_end",
        authoritative=True,
        sovereign_source="aggregate.window_end (B2.3 sovereign derivation)",
        snapshot_point="post-oracle final atomic capture",
        allowed_type_family="datetime (immutable)",
        projection_representation="copy in AdjunctContext.window_end",
        alias_policy="immutable value sharing lawful; mutable sharing forbidden",
        externalization_policy="emitted as ISO-8601 render key",
    ),
    "supported_platforms": AuthoritativeFieldSpec(
        field_name="supported_platforms",
        authoritative=True,
        sovereign_source="coverage.supported_platforms (B2.3 scope, normalized tuple)",
        snapshot_point="post-oracle final atomic capture via freeze_platform_scope",
        allowed_type_family="tuple[str, ...] deeply immutable (str members only)",
        projection_representation="immutable tuple copy in AdjunctContext.supported_platforms",
        alias_policy="MUST be storage-disjoint from projection for mutable storage; "
        "immutable tuple sharing lawful only when deeply immutable",
        externalization_policy="emitted as list render key (materialized from snapshot only)",
    ),
    "matched_minor": AuthoritativeFieldSpec(
        field_name="matched_minor",
        authoritative=True,
        sovereign_source="aggregate.matched_webhook_revenue_minor (integer minor units)",
        snapshot_point="post-oracle final atomic capture",
        allowed_type_family="int (immutable)",
        projection_representation="scalar copy in AdjunctContext.matched_minor",
        alias_policy="immutable value sharing lawful; mutable sharing forbidden",
        externalization_policy="emitted as render key",
    ),
    "connected_minor": AuthoritativeFieldSpec(
        field_name="connected_minor",
        authoritative=True,
        sovereign_source="aggregate.connected_platform_revenue_minor (integer minor units)",
        snapshot_point="post-oracle final atomic capture",
        allowed_type_family="int (immutable)",
        projection_representation="scalar copy in AdjunctContext.connected_minor",
        alias_policy="immutable value sharing lawful; mutable sharing forbidden",
        externalization_policy="emitted as render key",
    ),
    "coverage_percent": AuthoritativeFieldSpec(
        field_name="coverage_percent",
        authoritative=True,
        sovereign_source="result.coverage_percent cross-checked via independent oracle",
        snapshot_point="post-oracle final atomic capture",
        allowed_type_family="Decimal (immutable)",
        projection_representation="copy in AdjunctContext.coverage_percent",
        alias_policy="immutable value sharing lawful; mutable sharing forbidden",
        externalization_policy="emitted as string render key",
    ),
    "zero_denominator": AuthoritativeFieldSpec(
        field_name="zero_denominator",
        authoritative=True,
        sovereign_source="result.zero_denominator cross-checked via independent oracle",
        snapshot_point="post-oracle final atomic capture",
        allowed_type_family="bool (immutable)",
        projection_representation="copy in AdjunctContext.zero_denominator",
        alias_policy="immutable value sharing lawful; mutable sharing forbidden",
        externalization_policy="emitted as render key",
    ),
    "provenance_mode": AuthoritativeFieldSpec(
        field_name="provenance_mode",
        authoritative=True,
        sovereign_source="framework constant SINK_PROVENANCE_MODE",
        snapshot_point="post-oracle final atomic capture",
        allowed_type_family="str (immutable constant)",
        projection_representation="omitted from projection view (framework-owned)",
        alias_policy="constant immutable value; no shared mutable storage",
        externalization_policy="emitted as render key",
    ),
    "sovereign_producer": AuthoritativeFieldSpec(
        field_name="sovereign_producer",
        authoritative=True,
        sovereign_source="framework constant B23_SOVEREIGN_COVERAGE_PRODUCER",
        snapshot_point="post-oracle final atomic capture",
        allowed_type_family="str (immutable constant)",
        projection_representation="omitted from projection view (framework-owned)",
        alias_policy="constant immutable value; no shared mutable storage",
        externalization_policy="emitted as render key",
    ),
    "content_digest": AuthoritativeFieldSpec(
        field_name="content_digest",
        authoritative=False,
        sovereign_source="derived integrity tag over snapshot S via _content_digest_for",
        snapshot_point="materialization from S only (never from projection state)",
        allowed_type_family="str hex digest (immutable, non-authoritative)",
        projection_representation="not projection-visible; computed from S post-projection",
        alias_policy="must derive from S only; never from projection-visible storage",
        externalization_policy="NOT emitted externally (integrity only, never authority)",
    ),
    "adjunct_json": AuthoritativeFieldSpec(
        field_name="adjunct_json",
        authoritative=False,
        sovereign_source="governed projection adjunct return via reject_authoritative_adjunct",
        snapshot_point="post-projection governed cleaning (adjuncts only)",
        allowed_type_family="str JSON mapping (immutable serialization)",
        projection_representation="the projection return itself (guarded, adjunct-only)",
        alias_policy="adjuncts must never determine authoritative fields (guard refuses)",
        externalization_policy="NOT emitted externally (adjuncts never externalize)",
    ),
}


# ---------------------------------------------------------------------------
# Corrective-X law (defect classes X-A/X-B: external canonical census escape
# and detached authority reacquisition).
#
# ONE semantic contract governs canonical external representation. The
# internal registry above remains the single source of truth for field
# obligations; everything below is a MECHANICALLY DERIVED projection of it,
# never a second independently editable schema:
#
#   GOVERNED_EXTERNAL_KEYS == {registry names whose externalization_policy
#                              is an emission ("emitted ...")}
#
# A renderer, serializer, helper, compatibility function, export path,
# response model, or future adapter may not add a financial semantic outside
# this set: the approved renderer refuses extra/missing/prohibited keys at
# runtime (construction-primitive independent -- dict.update, |= merge,
# comprehension, helper mapping, conditional/loop insertion all funnel
# through the validated final mapping), and the static validator pins the
# exact census merge-blocking. A new external semantic requires amending
# the registry obligation row itself, which is a governed contract change,
# not a renderer edit.
# ---------------------------------------------------------------------------


def governed_external_keys() -> frozenset[str]:
    """Derive the governed external key universe from registry obligations."""
    return frozenset(
        name
        for name, spec in AUTHORITATIVE_FIELD_REGISTRY.items()
        if spec.externalization_policy.startswith("emitted")
    )


GOVERNED_EXTERNAL_KEYS: frozenset[str] = governed_external_keys()

REQUIRED_EXTERNAL_KEYS: frozenset[str] = GOVERNED_EXTERNAL_KEYS

PROHIBITED_EXTERNAL_KEYS: frozenset[str] = frozenset(
    {"tenant_id", "content_digest", "adjunct_json"}
)

# Machine-readable value-lineage map (Theorem X-B, Corrective-XI hardening):
# every governed external key derives ONLY from its declared canonical
# source through its declared transform. Since Corrective XI this map is a
# MECHANICAL PROJECTION of the frozen executable transform contract
# (``external_semantics.EXTERNAL_SEMANTICS``): ``render_attr`` is the
# contract's ``source_attr`` and ``transform`` is the contract's stable
# ``transform_id``. The prose ``canonical_source`` rows remain human-facing
# documentation of sovereign origin. The map can no longer self-authorize
# a wrong lineage: a source substitution must change the transform
# contract module, which the semantic contract pins by AST hash and the
# CI validator pins by value-blind key->source data.
_EXTERNAL_CANONICAL_SOURCE_PROSE: dict[str, str] = {
    "authority": "framework constant CANONICAL_OUTPUT_AUTHORITY",
    "sink_id": "caller scope sink_id bound at final atomic capture (_s_sink_id)",
    "contract_version": "registration contract_version == B26_P1_CONTRACT_VERSION (_s_contract_version)",
    "tenant_id_hash": "aggregate.tenant_id via app.trust.refusal.tenant_hash (_s_tenant_id_hash)",
    "currency_code": "aggregate.currency_code, B2.3 sovereign derivation (_s_currency_code)",
    "window_start": "aggregate.window_start, B2.3 sovereign derivation (_s_window_start)",
    "window_end": "aggregate.window_end, B2.3 sovereign derivation (_s_window_end)",
    "supported_platforms": "coverage.supported_platforms via freeze_platform_scope (_s_supported_platforms)",
    "matched_minor": "aggregate.matched_webhook_revenue_minor, integer minor units (_s_matched_minor)",
    "connected_minor": "aggregate.connected_platform_revenue_minor, integer minor units (_s_connected_minor)",
    "coverage_percent": "result.coverage_percent cross-checked via independent oracle (_s_coverage_percent)",
    "zero_denominator": "result.zero_denominator cross-checked via independent oracle (_s_zero_denominator)",
    "provenance_mode": "framework constant SINK_PROVENANCE_MODE (_s_provenance_mode)",
    "sovereign_producer": "framework constant B23_SOVEREIGN_COVERAGE_PRODUCER (_s_sovereign_producer)",
}

EXTERNAL_FIELD_SOURCES: dict[str, dict[str, str]] = {
    spec.external_key: {
        "canonical_source": _EXTERNAL_CANONICAL_SOURCE_PROSE.get(
            spec.external_key, "undeclared external semantic"
        ),
        "transform": spec.transform_id,
        "authority_class": "authoritative",
        "render_attr": spec.source_attr,
    }
    for spec in EXTERNAL_SEMANTICS.values()
}

# External key to the FinalCanonicalOutput attribute it must derive from.
# 1:1 by law: same key name, wrong source (adjunct/caller/detached/B2.4/
# B2.13/LLM/helper) is a lineage violation even when the key set is lawful.
EXTERNAL_FIELD_RENDER_ATTRS: dict[str, str] = {
    key: spec["render_attr"] for key, spec in EXTERNAL_FIELD_SOURCES.items()
}


def assert_external_keys_derive_from_registry() -> None:
    """Require the external universe to be a mechanical registry projection.

    The governed external set, the required set, the source map, and the
    render-attr map must all agree with the registry emission obligations:
    no independently maintained external truth may exist. Since Corrective
    XI the lineage map must ALSO be a mechanical projection of the frozen
    executable transform contract -- prose cannot self-authorize lineage.
    """
    derived = governed_external_keys()
    if set(GOVERNED_EXTERNAL_KEYS) != set(derived):
        raise ValueError(
            "canonical_external_registry_drift:governed_set_not_derived"
        )
    if set(REQUIRED_EXTERNAL_KEYS) != set(derived):
        raise ValueError(
            "canonical_external_registry_drift:required_set_not_derived"
        )
    if set(EXTERNAL_FIELD_SOURCES) != set(derived):
        raise ValueError(
            "canonical_external_registry_drift:source_map_not_derived"
        )
    if set(EXTERNAL_FIELD_RENDER_ATTRS) != set(derived):
        raise ValueError(
            "canonical_external_registry_drift:render_attr_map_not_derived"
        )
    if set(EXTERNAL_SEMANTICS) != set(derived):
        raise ValueError(
            "canonical_external_registry_drift:transform_contract_not_derived"
        )
    for name, spec in EXTERNAL_FIELD_SOURCES.items():
        for required in ("canonical_source", "transform", "authority_class", "render_attr"):
            if not spec.get(required, ""):
                raise ValueError(
                    f"canonical_external_lineage_obligation_missing:{name}:{required}"
                )
        contract_spec = EXTERNAL_SEMANTICS[name]
        if spec["render_attr"] != contract_spec.source_attr:
            raise ValueError(
                "canonical_external_registry_drift:render_attr_not_contract_projection:"
                f"{name}"
            )
        if spec["transform"] != contract_spec.transform_id:
            raise ValueError(
                "canonical_external_registry_drift:transform_not_contract_projection:"
                f"{name}"
            )


def validate_external_rendering(rendered: Mapping[str, Any]) -> None:
    """Refuse any external mapping outside the governed external universe.

    Construction-primitive independent: validates the FINAL runtime mapping,
    so literal, dict(), comprehension, ** expansion, update(), |= merge,
    helper-produced, conditional, loop, Mapping-subclass, or response-model
    insertions are all governed identically. Extra key, missing required
    key, or prohibited internal-only/adjunct/raw-tenant key raises.
    """
    if not isinstance(rendered, Mapping):
        raise ValueError("canonical_external_rendering_not_mapping")
    actual = set(rendered.keys())
    governed = set(GOVERNED_EXTERNAL_KEYS)
    extra = sorted(actual - governed)
    if extra:
        raise ValueError(
            f"canonical_external_undeclared_key:{','.join(extra)}"
        )
    missing = sorted(set(REQUIRED_EXTERNAL_KEYS) - actual)
    if missing:
        raise ValueError(
            f"canonical_external_required_key_missing:{','.join(missing)}"
        )
    prohibited = sorted(actual & set(PROHIBITED_EXTERNAL_KEYS))
    if prohibited:
        raise ValueError(
            f"canonical_external_prohibited_key:{','.join(prohibited)}"
        )
    if "tenant_id" in actual:
        raise ValueError("canonical_external_emits_raw_tenant")


def authoritative_field_names() -> frozenset[str]:
    """Return the authoritative field names requiring snapshot isolation."""
    return frozenset(
        name
        for name, spec in AUTHORITATIVE_FIELD_REGISTRY.items()
        if spec.authoritative
    )


def non_authoritative_field_names() -> frozenset[str]:
    """Return the non-authoritative (integrity/adjunct) field names."""
    return frozenset(
        name
        for name, spec in AUTHORITATIVE_FIELD_REGISTRY.items()
        if not spec.authoritative
    )


def assert_registry_covers_output(output_type: Any) -> None:
    """Require the registry to exactly cover a dataclass output type.

    The field *list* is derived from the canonical type (ground truth);
    this registry supplies the isolation *obligations*. Any drift in either
    direction -- a dataclass field without a registry declaration, or a
    registry entry without a dataclass field -- raises, which the static
    validator turns into a merge-blocking RED.
    """
    import dataclasses as _dataclasses

    declared = {field.name for field in _dataclasses.fields(output_type)}
    registered = set(AUTHORITATIVE_FIELD_REGISTRY)
    missing = sorted(declared - registered)
    extra = sorted(registered - declared)
    if missing:
        raise ValueError(
            f"canonical_authoritative_census_incomplete:{','.join(missing)}"
        )
    if extra:
        raise ValueError(f"canonical_authoritative_census_stale:{','.join(extra)}")
    for name, spec in AUTHORITATIVE_FIELD_REGISTRY.items():
        for required in (
            "sovereign_source",
            "snapshot_point",
            "allowed_type_family",
            "projection_representation",
            "alias_policy",
            "externalization_policy",
        ):
            if not getattr(spec, required, ""):
                raise ValueError(
                    f"canonical_authoritative_census_obligation_missing:{name}:{required}"
                )


def freeze_platform_scope(value: Any) -> tuple[str, ...]:
    """Normalize platform scope to a deeply immutable tuple of str.

    Behavior-preserving on pristine inputs: a tuple of str returns an equal
    tuple with identical order and semantics. Future mutable inputs
    (list/set/frozenset of str) are converted to an independent immutable
    tuple instead of aliasing mutable storage. Unordered set/frozenset inputs
    are sorted: set iteration order is process-dependent (hash randomization),
    and deterministic finance authority must never depend on it. Anything
    else -- mappings, objects, bytearray, non-str members, bare strings --
    is refused fail-closed so a new shape must be declared here first.
    """
    if isinstance(value, str):
        raise ValueError(
            "canonical_platform_scope_not_sequence:bare string is not a scope"
        )
    unordered = isinstance(value, (frozenset, set))
    if isinstance(value, tuple):
        members = list(value)
    elif isinstance(value, (list, frozenset, set)):
        members = list(value)
    else:
        raise ValueError(
            f"canonical_platform_scope_not_governed:{type(value).__name__}"
        )
    for member in members:
        if not isinstance(member, str):
            raise ValueError(
                f"canonical_platform_scope_member_not_immutable:{type(member).__name__}"
            )
    if unordered:
        members.sort()
    return tuple(members)


def assert_snapshot_types_immutable(
    *,
    sink_id: Any,
    contract_version: Any,
    tenant_id_hash: Any,
    currency_code: Any,
    window_start: Any,
    window_end: Any,
    supported_platforms: Any,
    matched_minor: Any,
    connected_minor: Any,
    coverage_percent: Any,
    zero_denominator: Any,
    provenance_mode: Any,
    sovereign_producer: Any,
) -> None:
    """Runtime invariant: every snapshot local is in its allowed family.

    A future refactor that makes any snapshot field mutable (tuple -> list,
    str -> bytearray, int -> object) raises here before projection code runs,
    converting silent alias drift into loud refusal. Immutable sharing
    remains lawful; only the *type family* is enforced, never object
    identity (``tuple(t) is t`` sharing of deeply immutable tuples is
    explicitly permitted).
    """
    if not isinstance(sink_id, str):
        raise ValueError("canonical_snapshot_type_violation:sink_id")
    if not isinstance(contract_version, str):
        raise ValueError("canonical_snapshot_type_violation:contract_version")
    if not isinstance(tenant_id_hash, str):
        raise ValueError("canonical_snapshot_type_violation:tenant_id_hash")
    if not isinstance(currency_code, str):
        raise ValueError("canonical_snapshot_type_violation:currency_code")
    if not isinstance(window_start, datetime):
        raise ValueError("canonical_snapshot_type_violation:window_start")
    if not isinstance(window_end, datetime):
        raise ValueError("canonical_snapshot_type_violation:window_end")
    if type(supported_platforms) is not tuple:
        raise ValueError(
            "canonical_snapshot_type_violation:supported_platforms_not_tuple"
        )
    for member in supported_platforms:
        if type(member) is not str:
            raise ValueError(
                "canonical_snapshot_type_violation:supported_platforms_member_not_str"
            )
    if type(matched_minor) is not int or isinstance(matched_minor, bool):
        raise ValueError("canonical_snapshot_type_violation:matched_minor")
    if type(connected_minor) is not int or isinstance(connected_minor, bool):
        raise ValueError("canonical_snapshot_type_violation:connected_minor")
    if not isinstance(coverage_percent, Decimal):
        raise ValueError("canonical_snapshot_type_violation:coverage_percent")
    if type(zero_denominator) is not bool:
        raise ValueError("canonical_snapshot_type_violation:zero_denominator")
    if not isinstance(provenance_mode, str):
        raise ValueError("canonical_snapshot_type_violation:provenance_mode")
    if not isinstance(sovereign_producer, str):
        raise ValueError("canonical_snapshot_type_violation:sovereign_producer")


def snapshot_digest_inputs(
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
) -> Mapping[str, Any]:
    """Return the mapping whose digest detects snapshot mutation.

    The executor captures this digest before projection code runs and
    recomputes it after projection returns (including across the awaitable
    projection await). Divergence proves projection-reachable storage
    mutated authoritative state, and execution refuses instead of emitting
    corrupted canonical truth.
    """
    return {
        "sink_id": sink_id,
        "contract_version": contract_version,
        "tenant_id_hash": tenant_id_hash,
        "currency_code": currency_code,
        "window_start": window_start,
        "window_end": window_end,
        "supported_platforms": supported_platforms,
        "matched_minor": matched_minor,
        "connected_minor": connected_minor,
        "coverage_percent": coverage_percent,
        "zero_denominator": zero_denominator,
        "provenance_mode": provenance_mode,
        "sovereign_producer": sovereign_producer,
    }
