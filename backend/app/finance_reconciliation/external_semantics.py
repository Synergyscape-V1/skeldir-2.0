"""B2.6-P1 executable external semantic contract (Corrective XI).

Corrective-XI law (defect class XI-A: transform semantic drift)
----------------------------------------------------------------
EVERY externally authoritative value must equal the EXECUTION of its one
governed transform over its one sovereign source attribute::

    External[k] == EXTERNAL_SEMANTICS[k].transform(
        getattr(FinalCanonicalOutput, EXTERNAL_SEMANTICS[k].source_attr)
    )

Reference is not meaning. A renderer expression that names the correct
``output.<attr>`` while changing the value's meaning (date-only truncation,
sign inversion, zeroing, scaling, slicing, rounding drift, timezone loss,
precision loss, representation-type drift) violates this contract even
though every Corrective-X proof stays GREEN -- which is exactly the class
this module closes. The approved renderer contains NO per-field transform
expressions at all: it derives the complete external mapping mechanically
through :func:`project_external_fields`, so a transform can only change by
changing THIS contract module, and this module is frozen into the semantic
contract (``contracts/reconciliation/b2.6/semantic-authority.v1.yaml`` pins
its AST sha256 -- the same freeze precedent as the B2.3 coverage
implementation pin), re-verified at canonical-sink import and by the CI
validator on every run.

Every transform is fail-closed: a value outside its governed type family
(naive datetime, boolean money, negative money, unquantized Decimal,
non-tuple platform scope, mutable or non-str members) refuses instead of
coercing. :func:`check_external_semantics` is the machine-executable shape
law for the final external mapping; the constant-label law (authority,
provenance, producer, contract version) is enforced by the egress module
which owns those constants (``canonical_sink.assert_canonical_external_semantics``).

This module is deliberately pure: standard library only, no application
imports, no I/O, no environment reads. Adjacent-domain state (LLM output,
B2.4 estimates, B2.13 counterfactuals, caller input) has no syntactic
entry point here.

Corrective-XII law (defect class XII-A: post-issuance authoritative state
mutation through shared mutable references)
-------------------------------------------------------------------------
CANONICAL STORAGE IS DEEPLY IMMUTABLE; WIRE FORMAT IS A FRESH COPY. The
governed platform scope is stored as an immutable ``tuple[str, ...]`` --
never as the JSON-facing ``list`` -- and every canonical value passes
through :func:`freeze_canonical_value`, which converts ordered sequences
to fresh tuples, mappings to fresh deeply-frozen read-only mappings, and
refuses every type family without an explicit freeze policy (sets,
bytearrays, custom objects, datetimes, Decimals, ``None``). The closed
universe of authoritative ``external_type`` labels is
:data:`GOVERNED_CANONICAL_EXTERNAL_TYPES`; a spec carrying any other label
refuses fail-closed in :func:`check_external_semantics` instead of passing
silently. :func:`to_wire_dict` projects a fresh JSON-ready mapping (tuples
to fresh lists) at the non-authoritative serialization boundary: mutating
wire data can never write back into canonical storage, and wire data is
never admissible as canonical. The live contract registry itself is
exposed as a read-only mapping over a private store so post-import item
replacement through ordinary access refuses; issuance and admission
additionally re-verify live spec identity (see
``canonical_sink._verify_live_semantics_identity``).
"""

from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping


GOVERNED_AUTHORITY_LABEL = "canonical_B2.6_financial_truth"

# Full ISO-8601 instant with mandatory timezone offset: the external window
# semantics preserve the complete governed instant. Date-only, time-zone-less,
# and offset-less strings are representation drift and refuse.
_INSTANT_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$"
)
_TENANT_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
_PERCENT_PATTERN = re.compile(r"^\d+\.\d{2}$")


class ExternalSemanticsError(ValueError):
    """An external value or transform violates the frozen semantic contract."""


def _identity_str(value: Any) -> str:
    """Exact governed string identity: non-empty str in, same str out."""
    if type(value) is not str or not value:
        raise ExternalSemanticsError("external_transform_refused:str_identity")
    return value


def _instant_iso8601(value: Any) -> str:
    """Full governed instant to ISO-8601, timezone preserved.

    Naive datetimes refuse: a window boundary without timezone semantics is
    a different meaning, not a formatting choice. Truncation to date-only is
    unrepresentable here (``date`` inputs are not datetimes and refuse).
    """
    if not isinstance(value, datetime):
        raise ExternalSemanticsError("external_transform_refused:instant_not_datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ExternalSemanticsError("external_transform_refused:instant_requires_timezone")
    encoded = value.isoformat()
    if not _INSTANT_PATTERN.match(encoded):
        raise ExternalSemanticsError(
            f"external_transform_refused:instant_encoding:{encoded}"
        )
    return encoded


def _platform_scope_tuple(value: Any) -> tuple[str, ...]:
    """Immutable snapshot tuple to canonical immutable tuple, order preserved.

    The snapshot boundary already normalized and froze the governed scope;
    this transform is exact materialization into canonical storage -- no
    subsetting, supersets, deduplication, or reordering (governed order is
    semantic). The result is a fresh immutable tuple on every call: no
    caller, reader, or serializer ever receives mutable canonical storage.
    The JSON-facing list form is produced only at the non-authoritative
    wire boundary by :func:`to_wire_dict`, never stored.
    """
    if type(value) is not tuple:
        raise ExternalSemanticsError(
            f"external_transform_refused:platform_scope_not_tuple:{type(value).__name__}"
        )
    members = list(value)
    for member in members:
        if type(member) is not str or not member:
            raise ExternalSemanticsError(
                "external_transform_refused:platform_scope_member_not_str"
            )
    return tuple(members)


def _money_minor_identity(value: Any) -> int:
    """Integer minor-unit identity: no scale, sign, float, or bool drift."""
    if type(value) is not int:
        raise ExternalSemanticsError(
            f"external_transform_refused:money_not_int:{type(value).__name__}"
        )
    if value < 0:
        raise ExternalSemanticsError("external_transform_refused:money_negative")
    return value


def _percent_2dp_str(value: Any) -> str:
    """Governed Decimal coverage to exact 2-decimal-place string form.

    The sovereign derivation already quantizes (ROUND_HALF_UP at the oracle);
    this transform preserves that precision and refuses any unquantized or
    negative drift rather than re-rounding (re-rounding here would make this
    layer a second arithmetic authority).
    """
    if not isinstance(value, Decimal):
        raise ExternalSemanticsError(
            f"external_transform_refused:coverage_not_decimal:{type(value).__name__}"
        )
    if value < 0:
        raise ExternalSemanticsError("external_transform_refused:coverage_negative")
    if value != value.quantize(Decimal("0.01")):
        raise ExternalSemanticsError("external_transform_refused:coverage_not_2dp")
    encoded = str(value)
    if not _PERCENT_PATTERN.match(encoded):
        raise ExternalSemanticsError(
            f"external_transform_refused:coverage_encoding:{encoded}"
        )
    return encoded


def _bool_identity(value: Any) -> bool:
    """Actual boolean identity: 0/1/string equivalents refuse."""
    if type(value) is not bool:
        raise ExternalSemanticsError(
            f"external_transform_refused:boolean_not_bool:{type(value).__name__}"
        )
    return value


@dataclass(frozen=True)
class ExternalFieldSemantics:
    """One governed external field: source, meaning, and executable transform."""

    external_key: str
    source_attr: str
    external_type: str
    transform_id: str
    transform: Callable[[Any], Any]
    normalization: str
    omission_law: str


# The executable contract lives in a private mutable store at import time
# only; the governed public surface is a read-only mapping over it
# (Corrective-XII, class XII-B: post-import live-registry replacement
# through ordinary item assignment refuses instead of redefining canonical
# meaning). Issuance and admission additionally re-verify that the live
# specs are still the import-time pinned spec objects.
_EXTERNAL_SEMANTICS_STORE: dict[str, ExternalFieldSemantics] = {
    "authority": ExternalFieldSemantics(
        external_key="authority",
        source_attr="authority",
        external_type="str",
        transform_id="governed_label_identity",
        transform=_identity_str,
        normalization="exact governed authority constant",
        omission_law="never_omitted",
    ),
    "sink_id": ExternalFieldSemantics(
        external_key="sink_id",
        source_attr="sink_id",
        external_type="str",
        transform_id="str_identity",
        transform=_identity_str,
        normalization="exact registered sink identifier",
        omission_law="never_omitted",
    ),
    "contract_version": ExternalFieldSemantics(
        external_key="contract_version",
        source_attr="contract_version",
        external_type="str",
        transform_id="str_identity",
        transform=_identity_str,
        normalization="exact live semantic-contract version",
        omission_law="never_omitted",
    ),
    "tenant_id_hash": ExternalFieldSemantics(
        external_key="tenant_id_hash",
        source_attr="tenant_id_hash",
        external_type="str",
        transform_id="one_way_hash_identity",
        transform=_identity_str,
        normalization="approved irreversible tenant hash only; raw tenant UUID never externalizes",
        omission_law="never_omitted",
    ),
    "currency_code": ExternalFieldSemantics(
        external_key="currency_code",
        source_attr="currency_code",
        external_type="str",
        transform_id="str_identity",
        transform=_identity_str,
        normalization="governed ISO-4217 uppercase code",
        omission_law="never_omitted",
    ),
    "window_start": ExternalFieldSemantics(
        external_key="window_start",
        source_attr="window_start",
        external_type="str",
        transform_id="instant_iso8601",
        transform=_instant_iso8601,
        normalization="full governed instant, timezone preserved; date-only truncation forbidden",
        omission_law="never_omitted",
    ),
    "window_end": ExternalFieldSemantics(
        external_key="window_end",
        source_attr="window_end",
        external_type="str",
        transform_id="instant_iso8601",
        transform=_instant_iso8601,
        normalization="full governed instant, timezone preserved; date-only truncation forbidden",
        omission_law="never_omitted",
    ),
    "supported_platforms": ExternalFieldSemantics(
        external_key="supported_platforms",
        source_attr="supported_platforms",
        external_type="tuple[str]",
        transform_id="frozen_tuple_exact_materialization",
        transform=_platform_scope_tuple,
        normalization="exact frozen scope membership and order; no subset/superset/duplicate/reorder",
        omission_law="never_omitted",
    ),
    "matched_minor": ExternalFieldSemantics(
        external_key="matched_minor",
        source_attr="matched_minor",
        external_type="int",
        transform_id="integer_minor_identity",
        transform=_money_minor_identity,
        normalization="exact integer minor units; no scale, sign, float, or bool drift",
        omission_law="never_omitted",
    ),
    "connected_minor": ExternalFieldSemantics(
        external_key="connected_minor",
        source_attr="connected_minor",
        external_type="int",
        transform_id="integer_minor_identity",
        transform=_money_minor_identity,
        normalization="exact integer minor units; no scale, sign, float, or bool drift",
        omission_law="never_omitted",
    ),
    "coverage_percent": ExternalFieldSemantics(
        external_key="coverage_percent",
        source_attr="coverage_percent",
        external_type="str",
        transform_id="decimal_2dp_exact_string",
        transform=_percent_2dp_str,
        normalization="governed 2-decimal string form; no re-rounding, no precision drift",
        omission_law="never_omitted",
    ),
    "zero_denominator": ExternalFieldSemantics(
        external_key="zero_denominator",
        source_attr="zero_denominator",
        external_type="bool",
        transform_id="bool_identity",
        transform=_bool_identity,
        normalization="actual boolean; integer/string equivalents refuse",
        omission_law="never_omitted",
    ),
    "provenance_mode": ExternalFieldSemantics(
        external_key="provenance_mode",
        source_attr="provenance_mode",
        external_type="str",
        transform_id="governed_label_identity",
        transform=_identity_str,
        normalization="exact governed provenance-mode constant",
        omission_law="never_omitted",
    ),
    "sovereign_producer": ExternalFieldSemantics(
        external_key="sovereign_producer",
        source_attr="sovereign_producer",
        external_type="str",
        transform_id="governed_label_identity",
        transform=_identity_str,
        normalization="exact governed sovereign-producer constant",
        omission_law="never_omitted",
    ),
}

EXTERNAL_SEMANTICS: Mapping[str, ExternalFieldSemantics] = MappingProxyType(
    _EXTERNAL_SEMANTICS_STORE
)

EXTERNAL_SEMANTIC_KEYS: frozenset[str] = frozenset(EXTERNAL_SEMANTICS)

# Closed authoritative type-family universe (Corrective-XII §24 law). Every
# spec's ``external_type`` must be a member; any other label refuses
# fail-closed in :func:`check_external_semantics` and turns the CI
# validator RED. A future governed field family is added here explicitly,
# together with its freeze policy in :func:`freeze_canonical_value` -- never
# by silent acceptance.
GOVERNED_CANONICAL_EXTERNAL_TYPES: frozenset[str] = frozenset(
    {
        "str",
        "int",
        "bool",
        "tuple[str]",
        "mapping",
    }
)


def freeze_canonical_value(value: Any, *, field: str) -> Any:
    """Recursively freeze one canonical value into deeply immutable storage.

    Ordered sequences (tuple or list) become fresh tuples with recursively
    frozen members; mappings become fresh read-only mappings with
    recursively frozen values; exact ``str``/``int``/``bool`` pass through
    (immutable already; ``bool`` is exact-checked so it can never enter an
    integer-minor-unit field). Every other family -- sets, bytearrays,
    datetimes, Decimals, ``None``, custom containers -- refuses fail-closed:
    a future field needing a new shape must declare its freeze policy here
    first. The result shares no mutable storage with the input.
    """
    if type(value) is str or type(value) is bool or type(value) is int:
        return value
    if isinstance(value, (tuple, list)):
        return tuple(freeze_canonical_value(member, field=field) for member in value)
    if isinstance(value, MappingProxyType):
        frozen = {
            key: freeze_canonical_value(member, field=field)
            for key, member in value.items()
        }
        for key in frozen:
            if type(key) is not str:
                raise ExternalSemanticsError(
                    f"external_canonical_key_not_str:{field}"
                )
        return MappingProxyType(frozen)
    if isinstance(value, dict):
        frozen = {
            key: freeze_canonical_value(member, field=field)
            for key, member in value.items()
        }
        for key in frozen:
            if type(key) is not str:
                raise ExternalSemanticsError(
                    f"external_canonical_key_not_str:{field}"
                )
        return MappingProxyType(frozen)
    raise ExternalSemanticsError(
        f"external_canonical_type_not_governed:{field}:{type(value).__name__}"
    )


def assert_canonical_value_frozen(value: Any, *, field: str) -> None:
    """Verify one stored canonical value is deeply immutable.

    Exact ``str``/``bool``/``int``, tuples of frozen values, and read-only
    mappings with ``str`` keys and frozen values pass. Raw ``list``/``dict``
    -- however deeply frozen their contents -- refuse: mutable containers
    must never be canonical backing storage, even transiently. This is the
    verification half of the freeze-then-verify issuance law; the capability
    constructor runs it over every frozen field before storage is sealed.
    """
    if type(value) is str or type(value) is bool or type(value) is int:
        return
    if type(value) is tuple:
        for member in value:
            assert_canonical_value_frozen(member, field=field)
        return
    if type(value) is MappingProxyType:
        for key, member in value.items():
            if type(key) is not str:
                raise ExternalSemanticsError(
                    f"external_canonical_key_not_str:{field}"
                )
            assert_canonical_value_frozen(member, field=field)
        return
    raise ExternalSemanticsError(
        f"external_canonical_storage_mutable:{field}:{type(value).__name__}"
    )


def _to_wire_value(value: Any) -> Any:
    """Project one frozen canonical value to fresh JSON-ready presentation."""
    if type(value) is str or type(value) is bool or type(value) is int:
        return value
    if type(value) is tuple:
        return [_to_wire_value(member) for member in value]
    if type(value) is MappingProxyType:
        return {key: _to_wire_value(member) for key, member in value.items()}
    raise ExternalSemanticsError(
        f"external_wire_unrepresentable:{type(value).__name__}"
    )


def to_wire_dict(fields: Mapping[str, Any]) -> dict[str, Any]:
    """Project frozen canonical state to a fresh mutable wire mapping.

    The result is JSON-ready presentation data (immutable tuples become
    fresh lists, read-only mappings become fresh dicts) in contract key
    order. It is explicitly NON-AUTHORITATIVE: mutating it cannot write
    back into canonical storage (no object is shared), and it is refused
    by canonical admission. This is the only lawful path from canonical
    authority to mutable serialization -- including the future B2.5
    TrustEnvelope adapter, which must build its payload from this copy,
    never from capability storage.
    """
    if not isinstance(fields, Mapping):
        raise ExternalSemanticsError(
            f"external_wire_source_not_mapping:{type(fields).__name__}"
        )
    if set(fields) != set(EXTERNAL_SEMANTICS):
        raise ExternalSemanticsError("external_wire_key_census_drift")
    return {key: _to_wire_value(fields[key]) for key in EXTERNAL_SEMANTICS}


def project_external_fields(output: Any) -> dict[str, Any]:
    """Derive the complete external mapping by executing the contract.

    This is the ONLY lawful serializer for canonical B2.6 external truth:
    every field is the execution of its governed transform over its declared
    sovereign source attribute. There is no per-call expression surface in
    which a meaning could drift while a proof observes the right reference.
    """
    fields: dict[str, Any] = {}
    for spec in EXTERNAL_SEMANTICS.values():
        try:
            source_value = getattr(output, spec.source_attr)
        except AttributeError as exc:
            raise ExternalSemanticsError(
                f"external_source_attr_missing:{spec.external_key}:{spec.source_attr}"
            ) from exc
        fields[spec.external_key] = spec.transform(source_value)
    return fields


def check_external_semantics(fields: Mapping[str, Any]) -> None:
    """Machine-executable shape law for a final external mapping.

    Pure value law only (types, encodings, membership); the governed
    constant-label law lives in the egress module beside the constants.
    Any violation raises :class:`ExternalSemanticsError`.
    """
    for spec in EXTERNAL_SEMANTICS.values():
        if spec.external_key not in fields:
            raise ExternalSemanticsError(
                f"external_semantics_key_missing:{spec.external_key}"
            )
    for key in fields:
        if key not in EXTERNAL_SEMANTICS:
            raise ExternalSemanticsError(f"external_semantics_key_undeclared:{key}")
    for spec in EXTERNAL_SEMANTICS.values():
        value = fields[spec.external_key]
        if spec.external_type == "str":
            if type(value) is not str or not value:
                raise ExternalSemanticsError(
                    f"external_semantics_type_violation:{spec.external_key}"
                )
        elif spec.external_type == "int":
            if type(value) is not int:
                raise ExternalSemanticsError(
                    f"external_semantics_type_violation:{spec.external_key}"
                )
        elif spec.external_type == "bool":
            if type(value) is not bool:
                raise ExternalSemanticsError(
                    f"external_semantics_type_violation:{spec.external_key}"
                )
        elif spec.external_type == "tuple[str]":
            if type(value) is not tuple or any(
                type(member) is not str or not member for member in value
            ):
                raise ExternalSemanticsError(
                    f"external_semantics_type_violation:{spec.external_key}"
                )
        elif spec.external_type == "mapping":
            if type(value) is not MappingProxyType:
                raise ExternalSemanticsError(
                    f"external_semantics_type_violation:{spec.external_key}"
                )
            assert_canonical_value_frozen(value, field=spec.external_key)
        else:
            # Closed universe (Corrective-XII §24): an authoritative field
            # type without an explicit canonical freeze policy refuses
            # closed -- it must never silently pass.
            raise ExternalSemanticsError(
                f"external_semantics_type_family_not_governed:"
                f"{spec.external_key}:{spec.external_type}"
            )
    if fields["authority"] != GOVERNED_AUTHORITY_LABEL:
        raise ExternalSemanticsError("external_semantics_label_not_governed:authority")
    if fields["matched_minor"] < 0 or fields["connected_minor"] < 0:
        raise ExternalSemanticsError("external_semantics_money_negative")
    if not _TENANT_HASH_PATTERN.match(fields["tenant_id_hash"]):
        raise ExternalSemanticsError(
            "external_semantics_tenant_hash_not_64hex"
        )
    if not _CURRENCY_PATTERN.match(fields["currency_code"]):
        raise ExternalSemanticsError(
            "external_semantics_currency_not_iso4217"
        )
    if not _INSTANT_PATTERN.match(fields["window_start"]):
        raise ExternalSemanticsError("external_semantics_window_not_full_instant:window_start")
    if not _INSTANT_PATTERN.match(fields["window_end"]):
        raise ExternalSemanticsError("external_semantics_window_not_full_instant:window_end")
    if not _PERCENT_PATTERN.match(fields["coverage_percent"]):
        raise ExternalSemanticsError("external_semantics_coverage_not_2dp_string")


def external_semantics_ast_sha256() -> str:
    """AST-canonical identity of this contract module (freeze pin input).

    Mirrors the coverage implementation-pin precedent: hash of
    ``ast.dump(tree, include_attributes=False)`` so cosmetic formatting
    changes do not churn the pin while any semantic change does.
    """
    source = Path(__file__).resolve().read_text(encoding="utf-8")
    return hashlib.sha256(
        ast.dump(ast.parse(source), include_attributes=False).encode("utf-8")
    ).hexdigest()


__all__ = [
    "EXTERNAL_SEMANTIC_KEYS",
    "EXTERNAL_SEMANTICS",
    "ExternalFieldSemantics",
    "ExternalSemanticsError",
    "GOVERNED_AUTHORITY_LABEL",
    "GOVERNED_CANONICAL_EXTERNAL_TYPES",
    "assert_canonical_value_frozen",
    "check_external_semantics",
    "external_semantics_ast_sha256",
    "freeze_canonical_value",
    "project_external_fields",
    "to_wire_dict",
]
