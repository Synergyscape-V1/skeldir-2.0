"""B2.6-P1 Corrective-XII consequence proof battery.

Defect class XII-A (post-issuance authoritative state mutation through
shared mutable references): an issued canonical capability conserved only
its top-level mapping while its governed platform scope remained an
ordinary mutable list shared with every consumer, so append/extend/index
assignment/clear/reorder/duplication -- including through dict(capability)
and the storage slot -- changed canonical meaning after issuance while
admission kept accepting it.

Defect class XII-B (live semantic-registry replacement): the executable
transform registry was an ordinary mutable mapping consulted at use time
while the contract pin was verified only at import.

Governing properties:

PROPERTY 1 -- DEEP CANONICAL IMMUTABILITY: the complete authoritative
object graph reachable from an issued capability is immutable by
construction (fresh tuples, read-only mappings, exact scalars).

PROPERTY 2 -- READ-ALIAS ISOLATION: no public read or conversion exposes a
write-through alias to canonical storage.

PROPERTY 3 -- CLOSED AUTHORITATIVE TYPE UNIVERSE: every authoritative type
family has an explicit immutable storage policy; unknown families refuse.

PROPERTY 4 -- WIRE SEPARATION: mutable presentation data is a fresh
non-authoritative copy that can never write back nor be admitted.

Every expectation below is hard-coded evidence data, never derived from
the modules under proof.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from types import MappingProxyType
from typing import Any
from uuid import UUID

import pytest

from app.finance_reconciliation.authoritative_fields import (
    validate_external_rendering,
)
from app.finance_reconciliation.canonical_sink import (
    CANONICAL_OUTPUT_AUTHORITY,
    CanonicalExternalTruth,
    CanonicalSinkError,
    _EGRESS_ISSUANCE,
    _verify_live_semantics_identity,
    admit_canonical_external,
    assert_canonical_external_semantics,
    render_governed_external,
)
from app.finance_reconciliation.external_semantics import (
    EXTERNAL_SEMANTICS,
    EXTERNAL_SEMANTIC_KEYS,
    ExternalSemanticsError,
    GOVERNED_CANONICAL_EXTERNAL_TYPES,
    assert_canonical_value_frozen,
    freeze_canonical_value,
    to_wire_dict,
)
from app.finance_reconciliation.semantic_contract import (
    B26_P1_CONTRACT_VERSION,
)
from test_b26_p1_corrective_v_consequence import (
    _auth_token,
    _execute,
    _scope,
    _seed_ratio_tenant,
)

PINNED_EXTERNAL_KEYS = frozenset(
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
    }
)

PINNED_EXTERNAL_TYPES = frozenset({"str", "int", "bool", "tuple[str]", "mapping"})

LAWFUL_CANONICAL = {
    "authority": "canonical_B2.6_financial_truth",
    "sink_id": "future_finance_projection",
    "contract_version": B26_P1_CONTRACT_VERSION,
    "tenant_id_hash": "sha256:" + "ab" * 32,
    "currency_code": "USD",
    "window_start": "2026-01-01T00:00:00+00:00",
    "window_end": "2026-02-01T12:30:05+02:00",
    "supported_platforms": ("paypal", "stripe"),
    "matched_minor": 76000,
    "connected_minor": 80000,
    "coverage_percent": "95.00",
    "zero_denominator": False,
    "provenance_mode": "RE_DERIVE_ON_READ",
    "sovereign_producer": (
        "app.revenue_verification.verification_coverage."
        "fetch_verification_coverage_aggregate"
        "+app.revenue_verification.verification_coverage."
        "VERIFICATION_COVERAGE.compute"
    ),
}

LAWFUL_WIRE = dict(LAWFUL_CANONICAL)
LAWFUL_WIRE["supported_platforms"] = ["paypal", "stripe"]


def _issue(fields: dict[str, Any] | None = None) -> CanonicalExternalTruth:
    return CanonicalExternalTruth(
        dict(LAWFUL_CANONICAL if fields is None else fields), _EGRESS_ISSUANCE
    )


@pytest.fixture(autouse=True)
async def _fresh_engines_per_test():
    yield
    from app.db.session import b23_engine
    from app.db.session import engine as app_engine

    await b23_engine.dispose()
    await app_engine.dispose()


# ---------------------------------------------------------------------------
# P-XII-1 -- closed authoritative type universe (unit).
# ---------------------------------------------------------------------------


def test_pxii1_closed_type_universe_and_storage_law() -> None:
    assert set(EXTERNAL_SEMANTICS) == set(PINNED_EXTERNAL_KEYS)
    assert set(EXTERNAL_SEMANTIC_KEYS) == set(PINNED_EXTERNAL_KEYS)
    assert set(GOVERNED_CANONICAL_EXTERNAL_TYPES) == set(PINNED_EXTERNAL_TYPES)
    for key, spec in EXTERNAL_SEMANTICS.items():
        assert spec.external_type in PINNED_EXTERNAL_TYPES, key
    # Canonical storage representation per family.
    assert EXTERNAL_SEMANTICS["supported_platforms"].external_type == "tuple[str]"
    assert EXTERNAL_SEMANTICS["matched_minor"].external_type == "int"
    assert EXTERNAL_SEMANTICS["zero_denominator"].external_type == "bool"
    # The live registry is read-only process state, not an ordinary dict.
    assert type(EXTERNAL_SEMANTICS) is MappingProxyType
    with pytest.raises(TypeError):
        EXTERNAL_SEMANTICS["xii_probe"] = 1  # type: ignore[index]
    assert "xii_probe" not in EXTERNAL_SEMANTICS
    # Import-time spec identity re-verification is live.
    _verify_live_semantics_identity()


# ---------------------------------------------------------------------------
# P-XII-2 -- recursive freeze / assert / wire unit laws (unit).
# ---------------------------------------------------------------------------


def test_pxii2_freeze_assert_wire_unit_laws() -> None:
    assert freeze_canonical_value(["a", "b"], field="probe") == ("a", "b")
    assert freeze_canonical_value(("a",), field="probe") == ("a",)
    nested = freeze_canonical_value({"k": ["v"]}, field="probe")
    assert type(nested) is MappingProxyType
    assert nested["k"] == ("v",)
    assert type(nested["k"]) is tuple
    deep = freeze_canonical_value(("a", ["b", {"c": "d"}]), field="probe")
    assert type(deep[1]) is tuple
    assert type(deep[1][1]) is MappingProxyType
    for scalar in ("s", 7, True, False, 0):
        assert freeze_canonical_value(scalar, field="probe") == scalar
    for bad in (
        bytearray(b"x"),
        {"a", "b"},
        frozenset({"a"}),
        None,
        3.5,
        object(),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        Decimal("1.00"),
    ):
        with pytest.raises(ExternalSemanticsError):
            freeze_canonical_value(bad, field="probe")
    # Assertion accepts frozen forms, refuses raw mutable containers even
    # with frozen contents.
    assert_canonical_value_frozen(("a", "b"), field="probe")
    assert_canonical_value_frozen(MappingProxyType({"k": ("v",)}), field="probe")
    for bad in (["a"], {"k": "v"}, ("a", ["b"]), {"k": ["v"]}, {1, 2}):
        with pytest.raises(ExternalSemanticsError):
            assert_canonical_value_frozen(bad, field="probe")
    # Wire projection is fresh, JSON-ready, and isolated.
    capability = _issue()
    wire = to_wire_dict(capability)
    assert wire == LAWFUL_WIRE
    assert type(wire["supported_platforms"]) is list
    assert wire["supported_platforms"] == ["paypal", "stripe"]
    assert wire["supported_platforms"] is not capability["supported_platforms"]
    json.dumps(wire)
    with pytest.raises(ExternalSemanticsError):
        to_wire_dict({"authority": "canonical_B2.6_financial_truth"})
    with pytest.raises(ExternalSemanticsError):
        to_wire_dict("not-a-mapping")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# P-XII-3 -- deep-mutation battery: every ordinary mutator refuses (unit).
# ---------------------------------------------------------------------------


def test_pxii3_deep_mutation_battery_refuses() -> None:
    capability = _issue()
    assert admit_canonical_external(capability) is capability
    assert type(capability["supported_platforms"]) is tuple
    mutators = (
        ("append", lambda: capability["supported_platforms"].append("shopify")),
        ("extend", lambda: capability["supported_platforms"].extend(["x"])),
        (
            "index_assign",
            lambda: capability["supported_platforms"].__setitem__(0, "other"),
        ),
        (
            "slice_assign",
            lambda: capability["supported_platforms"].__setitem__(
                slice(None), ["shopify"]
            ),
        ),
        ("insert", lambda: capability["supported_platforms"].insert(0, "x")),
        ("remove", lambda: capability["supported_platforms"].remove("paypal")),
        ("pop", lambda: capability["supported_platforms"].pop()),
        ("clear", lambda: capability["supported_platforms"].clear()),
        ("reverse", lambda: capability["supported_platforms"].reverse()),
        ("sort", lambda: capability["supported_platforms"].sort()),
        (
            "duplicate",
            lambda: capability["supported_platforms"].__add__(("paypal",)),
        ),
    )
    for name, attempt in mutators:
        if name == "duplicate":
            # Tuple concatenation is a pure value operation: it must produce
            # a NEW tuple and leave canonical state untouched.
            grown = attempt()
            assert grown == ("paypal", "stripe", "paypal")
            assert capability["supported_platforms"] == ("paypal", "stripe"), name
            continue
        with pytest.raises((AttributeError, TypeError)):
            attempt()
    # Top-level item assignment and storage-slot writes refuse.
    with pytest.raises(TypeError):
        capability["matched_minor"] = 0  # type: ignore[index]
    with pytest.raises(TypeError):
        capability._fields["matched_minor"] = 0  # noqa: SLF001
    # The storage slot cannot be rebound or deleted through ordinary access.
    with pytest.raises(AttributeError):
        capability._fields = MappingProxyType({})  # noqa: SLF001
    with pytest.raises(AttributeError):
        del capability._fields  # noqa: SLF001
    # Canonical meaning is exactly conserved.
    assert capability["supported_platforms"] == ("paypal", "stripe")
    assert capability["matched_minor"] == 76000
    assert capability["connected_minor"] == 80000
    assert capability["coverage_percent"] == "95.00"
    assert admit_canonical_external(capability) is capability


# ---------------------------------------------------------------------------
# P-XII-4 -- read/copy alias isolation incl. object identity (unit).
# ---------------------------------------------------------------------------


def test_pxii4_read_copy_alias_isolation() -> None:
    caller_owned = ["paypal", "stripe"]
    fields = dict(LAWFUL_CANONICAL)
    fields["supported_platforms"] = caller_owned  # type: ignore[dict-item]
    capability = CanonicalExternalTruth(fields, _EGRESS_ISSUANCE)
    # The constructor freezes caller-owned mutable input: no alias survives.
    assert capability["supported_platforms"] == ("paypal", "stripe")
    assert capability["supported_platforms"] is not caller_owned
    caller_owned.append("shopify")
    assert capability["supported_platforms"] == ("paypal", "stripe")
    assert admit_canonical_external(capability) is capability
    # Consumer conversions share no mutable storage with canonical state.
    consumed = dict(capability)
    assert type(consumed["supported_platforms"]) is tuple
    with pytest.raises((AttributeError, TypeError)):
        consumed["supported_platforms"].append("shopify")
    assert capability["supported_platforms"] == ("paypal", "stripe")
    items_copy = dict(capability.items())
    with pytest.raises((AttributeError, TypeError)):
        items_copy["supported_platforms"].append("shopify")
    assert capability["supported_platforms"] == ("paypal", "stripe")
    values = list(capability.values())
    assert ("paypal", "stripe") in values
    assert [k for k in capability] == list(LAWFUL_CANONICAL)
    assert len(capability) == 14


# ---------------------------------------------------------------------------
# P-XII-5 -- temporal orderings conserve admitted state (unit).
# ---------------------------------------------------------------------------


def test_pxii5_temporal_orderings_conserve_state() -> None:
    # ISSUE -> MUTATE(attempted) -> ADMIT.
    cap_a = _issue()
    with pytest.raises((AttributeError, TypeError)):
        cap_a["supported_platforms"].append("shopify")
    assert admit_canonical_external(cap_a) is cap_a
    assert cap_a["supported_platforms"] == ("paypal", "stripe")
    # ISSUE -> ADMIT -> MUTATE(attempted) -> CONSUME.
    cap_b = _issue()
    assert admit_canonical_external(cap_b) is cap_b
    with pytest.raises((AttributeError, TypeError)):
        cap_b["supported_platforms"].clear()
    consumed = dict(cap_b)
    assert consumed["supported_platforms"] == ("paypal", "stripe")
    assert admit_canonical_external(cap_b) is cap_b
    # ISSUE -> ADMIT -> AWAIT -> CONSUME.
    async def _await_then_consume() -> None:
        cap_c = _issue()
        assert admit_canonical_external(cap_c) is cap_c
        await asyncio.sleep(0)
        assert dict(cap_c)["supported_platforms"] == ("paypal", "stripe")
        assert admit_canonical_external(cap_c) is cap_c

    asyncio.run(_await_then_consume())


def test_pxii5_concurrent_readers_observe_stable_state() -> None:
    import threading

    capability = _issue()
    assert admit_canonical_external(capability) is capability
    failures: list[str] = []

    def reader() -> None:
        try:
            for _ in range(200):
                assert capability["supported_platforms"] == ("paypal", "stripe")
                assert dict(capability)["supported_platforms"] == (
                    "paypal",
                    "stripe",
                )
        except AssertionError as exc:
            failures.append(str(exc))

    def writer() -> None:
        try:
            for _ in range(200):
                try:
                    capability["supported_platforms"].append("shopify")
                except (AttributeError, TypeError):
                    pass
                else:
                    failures.append("mutation_succeeded")
        except Exception as exc:  # noqa: BLE001
            failures.append(str(exc))

    threads = [threading.Thread(target=reader) for _ in range(4)] + [
        threading.Thread(target=writer) for _ in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert failures == []
    assert capability["supported_platforms"] == ("paypal", "stripe")
    assert admit_canonical_external(capability) is capability


# ---------------------------------------------------------------------------
# P-XII-6 -- wire data is presentation, never authority (unit).
# ---------------------------------------------------------------------------


def test_pxii6_wire_is_data_never_authority() -> None:
    capability = _issue()
    wire = to_wire_dict(capability)
    # Mutating the wire copy cannot write back into canonical storage.
    wire["supported_platforms"].append("shopify")
    wire["supported_platforms"].clear()
    wire["matched_minor"] = 0
    assert capability["supported_platforms"] == ("paypal", "stripe")
    assert capability["matched_minor"] == 76000
    assert admit_canonical_external(capability) is capability
    # Wire data -- however lawful looking -- is refused admission.
    fresh_wire = to_wire_dict(capability)
    assert fresh_wire == LAWFUL_WIRE
    with pytest.raises(CanonicalSinkError):
        admit_canonical_external(fresh_wire)
    with pytest.raises(CanonicalSinkError):
        admit_canonical_external(json.loads(json.dumps(fresh_wire)))
    # Fresh wire copies share nothing with each other either.
    assert to_wire_dict(capability)["supported_platforms"] is not fresh_wire[
        "supported_platforms"
    ]


# ---------------------------------------------------------------------------
# P-XII-7 -- future-field class closure (unit).
# ---------------------------------------------------------------------------


def test_pxii7_future_field_class_closure() -> None:
    # An undeclared key cannot become canonical.
    with pytest.raises(ValueError, match="canonical_external_undeclared_key"):
        validate_external_rendering(
            {**dict(LAWFUL_CANONICAL), "future_nested": {"a": [1]}}
        )
    with pytest.raises((ValueError, CanonicalSinkError)):
        CanonicalExternalTruth(
            {**dict(LAWFUL_CANONICAL), "future_nested": {"a": [1]}},
            _EGRESS_ISSUANCE,
        )
    # A future MAPPING value under a governed family freezes recursively.
    frozen = freeze_canonical_value({"ledger": ["a", "b"]}, field="future")
    assert type(frozen) is MappingProxyType
    assert frozen["ledger"] == ("a", "b")
    # A future SEQUENCE value freezes to an immutable tuple.
    assert freeze_canonical_value([["x"]], field="future") == (("x",),)
    # Unknown families refuse closed, including user-defined containers.
    class _CustomSequence:
        pass

    for bad in (bytearray(b"x"), {"a"}, _CustomSequence(), (x for x in range(2))):
        with pytest.raises(ExternalSemanticsError):
            freeze_canonical_value(bad, field="future")
    # A tuple containing a mutable child is frozen at depth, not admitted raw.
    assert_canonical_value_frozen(
        freeze_canonical_value(("a", ["b"]), field="future"), field="future"
    )
    with pytest.raises(ExternalSemanticsError):
        assert_canonical_value_frozen(("a", ["b"]), field="future")


# ---------------------------------------------------------------------------
# P-XII-8 -- lawful issuance still validates exactly what is frozen (unit).
# ---------------------------------------------------------------------------


def test_pxii8_validated_is_frozen_and_admitted() -> None:
    capability = _issue()
    assert admit_canonical_external(capability) is capability
    assert_canonical_external_semantics(dict(capability.items()))
    validate_external_rendering(capability)
    with pytest.raises(ValueError):
        CanonicalExternalTruth(dict(LAWFUL_CANONICAL), object())
    missing = dict(LAWFUL_CANONICAL)
    del missing["matched_minor"]
    with pytest.raises(ValueError):
        CanonicalExternalTruth(missing, _EGRESS_ISSUANCE)


# ---------------------------------------------------------------------------
# P-XII-9 -- future B2.5 handoff seam shape (unit).
# ---------------------------------------------------------------------------


def test_pxii9_trustenvelope_handoff_seam_shape() -> None:
    capability = _issue()
    admitted = admit_canonical_external(capability)
    # The lawful future composition consumes admitted values through fresh
    # wire copies only: admit -> wire -> payload dict.
    payload = dict(to_wire_dict(admitted))
    assert payload["supported_platforms"] == ["paypal", "stripe"]
    assert payload["matched_minor"] == 76000
    # The payload is ordinary data: mutating it cannot reach authority, and
    # it is refused if ever presented as canonical.
    payload["supported_platforms"].append("shopify")
    assert admitted["supported_platforms"] == ("paypal", "stripe")
    with pytest.raises(CanonicalSinkError):
        admit_canonical_external(payload)
    # No unsigned detached dict is called canonical anywhere on this path.
    assert type(admitted) is CanonicalExternalTruth


# ---------------------------------------------------------------------------
# P-XII-10 -- lawful deterministic render end to end (DB).
# ---------------------------------------------------------------------------


async def test_pxii10_lawful_render_tuple_storage_wire_list() -> None:
    tenant_id = _seed_ratio_tenant(76000, 80000, "xii10")
    rendered = await render_governed_external(
        "future_finance_projection", auth_token=_auth_token(tenant_id), **_scope()
    )
    assert type(rendered) is CanonicalExternalTruth
    assert set(rendered.keys()) == set(PINNED_EXTERNAL_KEYS)
    # Canonical storage: immutable tuple, deterministic order.
    assert rendered["supported_platforms"] == ("stripe",)
    assert type(rendered["supported_platforms"]) is tuple
    assert type(rendered["matched_minor"]) is int and rendered["matched_minor"] == 76000
    assert type(rendered["connected_minor"]) is int and rendered["connected_minor"] == 80000
    assert rendered["coverage_percent"] == "95.00"
    assert rendered["zero_denominator"] is False
    assert rendered["window_start"] == "2026-01-01T00:00:00+00:00"
    assert rendered["window_end"] == "2026-02-01T00:00:00+00:00"
    assert admit_canonical_external(rendered) is rendered
    # Wire projection: fresh mutable list, JSON-ready, isolated.
    wire = to_wire_dict(rendered)
    assert wire["supported_platforms"] == ["stripe"]
    assert type(wire["supported_platforms"]) is list
    json.dumps(wire)
    wire["supported_platforms"].append("shopify")
    assert rendered["supported_platforms"] == ("stripe",)
    assert admit_canonical_external(rendered) is rendered
    # Internal sovereign execution agrees field-for-field through the
    # frozen transforms.
    output = await _execute("future_finance_projection", tenant_id)
    assert output.supported_platforms == ("stripe",)
    assert output.matched_minor == 76000
    assert output.connected_minor == 80000
    assert rendered["matched_minor"] == output.matched_minor
    assert rendered["connected_minor"] == output.connected_minor


async def test_pxii10_multi_platform_scope_order_preserved() -> None:
    # Governed order is semantic: issuance preserves membership and order
    # through the immutable tuple for lawful multi-platform scopes.
    ordered = CanonicalExternalTruth(
        {**dict(LAWFUL_CANONICAL), "supported_platforms": ("shopify", "stripe")},
        _EGRESS_ISSUANCE,
    )
    assert ordered["supported_platforms"] == ("shopify", "stripe")
    assert to_wire_dict(ordered)["supported_platforms"] == ["shopify", "stripe"]
    assert admit_canonical_external(ordered) is ordered
    # ...while a reordered scope is a DIFFERENT canonical meaning.
    reordered = CanonicalExternalTruth(
        {**dict(LAWFUL_CANONICAL), "supported_platforms": ("stripe", "shopify")},
        _EGRESS_ISSUANCE,
    )
    assert reordered["supported_platforms"] != ordered["supported_platforms"]


# ---------------------------------------------------------------------------
# P-XII-11 -- preservation spots: successor, ghost, IX freeze, XI pin (DB).
# ---------------------------------------------------------------------------


async def test_pxii11_preservation_spots() -> None:
    from app.finance_reconciliation.authoritative_fields import (
        freeze_platform_scope,
    )
    from app.finance_reconciliation.canonical_sink import (
        SuccessorProvenanceError,
        authorize_successor_persistence,
        deregister_successor_persistence,
        register_successor_persistence,
    )
    from app.finance_reconciliation.tenant_authority import UnknownTenantError

    # IX snapshot freeze boundary intact.
    assert freeze_platform_scope(["b", "a"]) == ("b", "a")
    assert freeze_platform_scope(("stripe",)) == ("stripe",)
    # Successor persistence remains unauthorized in P1.
    register_successor_persistence(
        registration_id="pxii11_probe",
        provenance_mode="RE_DERIVE_ON_READ",
        required_runtime_proof_ids=("VI-6",),
    )
    try:
        with pytest.raises(SuccessorProvenanceError):
            authorize_successor_persistence("pxii11_probe")
    finally:
        deregister_successor_persistence("pxii11_probe")
    # Ghost tenants refuse rather than becoming canonical zero.
    ghost = UUID("12345678-1234-5678-1234-567812345678")
    with pytest.raises(UnknownTenantError):
        await render_governed_external(
            "future_finance_projection",
            auth_token=_auth_token(ghost),
            **_scope(),
        )
    # Lawful multi-platform unit scope still admits after remediation.
    tenant_id = _seed_ratio_tenant(76000, 80000, "xii11")
    rendered = await render_governed_external(
        "future_finance_projection", auth_token=_auth_token(tenant_id), **_scope()
    )
    assert rendered["coverage_percent"] == "95.00"
    assert CANONICAL_OUTPUT_AUTHORITY == "canonical_B2.6_financial_truth"
