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
"""

from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
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


def _platform_scope_list(value: Any) -> list[str]:
    """Immutable snapshot tuple to external list, members and order preserved.

    The snapshot boundary already normalized and froze the governed scope;
    this transform is exact materialization -- no subsetting, supersets,
    deduplication, or reordering (governed order is semantic).
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
    return members


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


EXTERNAL_SEMANTICS: Mapping[str, ExternalFieldSemantics] = {
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
        external_type="list[str]",
        transform_id="frozen_tuple_exact_materialization",
        transform=_platform_scope_list,
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

EXTERNAL_SEMANTIC_KEYS: frozenset[str] = frozenset(EXTERNAL_SEMANTICS)


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
        elif spec.external_type == "list[str]":
            if type(value) is not list or any(
                type(member) is not str or not member for member in value
            ):
                raise ExternalSemanticsError(
                    f"external_semantics_type_violation:{spec.external_key}"
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
    "check_external_semantics",
    "external_semantics_ast_sha256",
    "project_external_fields",
]
