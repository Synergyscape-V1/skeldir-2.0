"""B2.6-P1 Corrective-IX consequence proof battery (cells P-IX-1..P-IX-9).

Defect class IX-A (mutable authority alias reintroduction): authoritative
state S and projection-visible state P must never share mutable storage
that can change a later canonical consequence::

    MUTABLE_REACHABLE_GRAPH(P) ∩ AUTHORITATIVE_MATERIALIZATION_GRAPH(S) = ∅

The Corrective-VIII battery proved rebinding immunity (``object.__setattr__``,
``__dict__`` rewrite, helper/retained/descriptor/closure vectors) but never
mutated shared storage *in place*: every committed evil detached P's
attribute instead of writing through a shared mutable object. The entering
O2 shape (snapshot ``list`` shared with the projection view, mutated via
``append``) therefore kept every VIII sensor GREEN while drifting canonical
``supported_platforms`` from ``('stripe',)`` to ``['stripe', 'shopify']``.

This battery closes the class at the consequence layer. Each end-to-end
evil attempts *in-place* mutation of projection-visible storage through a
distinct primitive and asserts the externally meaningful authoritative
field -- never money legs alone. On pristine bytes the storage is deeply
immutable (or an independent copy), so in-place mutation is impossible and
truth stays sovereign (GREEN). On the ``shared_mutable_alias`` controlled
defect the same evils write through shared storage: the runtime digest
tripwire refuses (or, without the tripwire, scope drifts) and the cell
turns RED. Exact byte restore returns GREEN.

Development mechanisms (used while designing the IX fix):
  D1 list append          D2 list extend + item assignment
  D3 retained alias later D4 nested/child in-place attempt
  D5 scope-metadata substitution (currency/window/platforms)

Holdout mechanisms (frozen after the fix, never used during development):
  H1 dict-style update attempt   H2 set-style add attempt
  H3 custom-mutable attempt      H4 shallow-copy shared-child attempt
  H5 delayed post-await mutation attempt

* P-IX-1 -- shared-list append/extend leaves scope sovereign (D1+D2).
* P-IX-2 -- retained-alias and nested in-place attempts leave truth sovereign (D3+D4).
* P-IX-3 -- scope-metadata conservation across platforms/currency/window (D5).
* P-IX-4 -- freeze boundary normalizes every mutable representation (unit).
* P-IX-5 -- snapshot type invariant refuses mutable shapes (unit).
* P-IX-6 -- holdout in-place primitives leave truth sovereign (H1..H5, end-to-end).
* P-IX-7 -- authoritative field census: registry covers output, every field proven.
* P-IX-8 -- renderer emits sovereign scope under in-place attack.
* P-IX-9 -- B2.3 95-not-76 truth preserved under in-place attack.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any

import pytest

from app.finance_reconciliation.authoritative_fields import (
    AUTHORITATIVE_FIELD_REGISTRY,
    assert_registry_covers_output,
    assert_snapshot_types_immutable,
    authoritative_field_names,
    freeze_platform_scope,
)
from app.finance_reconciliation.canonical_sink import (
    SINK_REGISTRY,
    FinalCanonicalOutput,
    _SINK_IMPLEMENTATIONS,
    render_governed_external,
    require_registered_sink,
)
from app.trust.refusal import tenant_hash

from test_b26_p1_corrective_v_consequence import (
    _auth_token,
    _execute,
    _scope,
    _seed_ratio_tenant,
)
from test_b26_p1_corrective_vii_consequence import (  # noqa: F401  (import guard)
    _mint_custom,
)


@pytest.fixture(autouse=True)
async def _fresh_engines_per_test():
    yield
    from app.db.session import b23_engine
    from app.db.session import engine as app_engine

    await b23_engine.dispose()
    await app_engine.dispose()


def _swap_coordinated(sink_id: str, func: Any) -> tuple[Any, Any]:
    """Install a coordinated evil binding (registry+impl, recomputed hash)."""
    from app.finance_reconciliation.canonical_sink import (
        SinkRegistration,
        _implementation_hash,
    )

    pristine_registration = SINK_REGISTRY[sink_id]
    pristine_implementation = _SINK_IMPLEMENTATIONS[sink_id]
    evil_registration = SinkRegistration(
        sink_id=sink_id,
        implementation=f"{func.__module__}.{func.__qualname__}",
        implementation_hash=_implementation_hash(func),
        contract_version=pristine_registration.contract_version,
        output_contract=pristine_registration.output_contract,
        sovereign_source=pristine_registration.sovereign_source,
        tenant_authority_mode=pristine_registration.tenant_authority_mode,
        database_capability_mode=pristine_registration.database_capability_mode,
        provenance_mode=pristine_registration.provenance_mode,
        projection_policy=pristine_registration.projection_policy,
        version="v9.9-ix-probe",
        required_runtime_proof_ids=pristine_registration.required_runtime_proof_ids,
    )
    SINK_REGISTRY[sink_id] = evil_registration
    _SINK_IMPLEMENTATIONS[sink_id] = func
    return pristine_registration, pristine_implementation


def _restore_coordinated(sink_id: str, pristine: tuple[Any, Any]) -> None:
    registration, implementation = pristine
    SINK_REGISTRY[sink_id] = registration
    _SINK_IMPLEMENTATIONS[sink_id] = implementation
    assert require_registered_sink(sink_id) == registration


# ---------------------------------------------------------------------------
# Development evils D1..D5: in-place shared-storage mutation attempts.
# Each evil is defensive: on deeply immutable pristine storage the in-place
# primitive raises (AttributeError/TypeError) and the evil becomes a no-op,
# which is exactly the safe outcome. On shared-mutable defective storage
# the same primitive succeeds and corrupts the snapshot (RED).
# ---------------------------------------------------------------------------


def _ix_d1_list_append(context: Any) -> dict[str, Any]:
    try:
        context.supported_platforms.append("shopify")
    except (AttributeError, TypeError):
        pass
    return {}


def _ix_d2_list_extend_item(context: Any) -> dict[str, Any]:
    try:
        context.supported_platforms.extend(["shopify"])
    except (AttributeError, TypeError):
        pass
    try:
        context.supported_platforms[0] = "shopify"
    except (AttributeError, TypeError, IndexError):
        pass
    try:
        context.supported_platforms[:] = ("shopify",)
    except (AttributeError, TypeError):
        pass
    return {}


_IX_D3_RETAINED: list[Any] = []


def _ix_d3_retained_alias_late(context: Any) -> dict[str, Any]:
    _IX_D3_RETAINED.append(context.supported_platforms)
    for held in _IX_D3_RETAINED:
        for primitive in ("append", "extend", "add", "update"):
            try:
                getattr(held, primitive)("shopify")
            except (AttributeError, TypeError):
                pass
        try:
            held[0] = "shopify"
        except (AttributeError, TypeError, IndexError, KeyError):
            pass
    return {}


def _ix_d4_nested_child(context: Any) -> dict[str, Any]:
    scope = context.supported_platforms
    # Nested-child attempt: if the scope (or any member) carries mutable
    # children (tuple-with-list, object-with-list), mutate them in place.
    if isinstance(scope, (list, bytearray)):
        try:
            scope.append("shopify")
        except (AttributeError, TypeError):
            pass
    for member in list(scope) if isinstance(scope, (list, tuple)) else []:
        if isinstance(member, list):
            try:
                member.append("shopify")
            except (AttributeError, TypeError):
                pass
        if isinstance(member, dict):
            try:
                member["shopify"] = True
            except (AttributeError, TypeError):
                pass
        inner = getattr(member, "platforms", None)
        if isinstance(inner, list):
            try:
                inner.append("shopify")
            except (AttributeError, TypeError):
                pass
    # Shallow-copy shared-child attempt: copy shares nested storage, then
    # mutate the copy's child in place.
    import copy as _copy

    try:
        shallow = _copy.copy(scope)
        if isinstance(shallow, list):
            shallow.append("shopify")
        if isinstance(shallow, tuple):
            for member in shallow:
                if isinstance(member, list):
                    member.append("shopify")
    except (AttributeError, TypeError):
        pass
    return {}


def _ix_d5_scope_metadata_substitution(context: Any) -> dict[str, Any]:
    # Rebinding attempts (covered by VIII too) plus in-place attempts on
    # every scope-metadata channel. Sovereignty -- not the mechanism -- is
    # asserted: final platforms/currency/window/tenant must equal S.
    try:
        object.__setattr__(context, "currency_code", "EUR")
    except (AttributeError, TypeError):
        pass
    try:
        object.__setattr__(context, "supported_platforms", ("shopify",))
    except (AttributeError, TypeError):
        pass
    try:
        context.supported_platforms.append("shopify")  # type: ignore[union-attr]
    except (AttributeError, TypeError):
        pass
    return {}


# ---------------------------------------------------------------------------
# Holdout evils H1..H5 (frozen after fix design, never used during development).
# ---------------------------------------------------------------------------


def _ix_h1_dict_style(context: Any) -> dict[str, Any]:
    scope = context.supported_platforms
    for primitive, argument in (
        ("update", {"shopify": True}),
        ("__setitem__", ("shopify", True)),
        ("setdefault", ("shopify", True)),
    ):
        try:
            getattr(scope, primitive)(argument)
        except (AttributeError, TypeError):
            pass
    try:
        scope["shopify"] = True  # type: ignore[index]
    except (AttributeError, TypeError, IndexError, KeyError):
        pass
    return {}


def _ix_h2_set_style(context: Any) -> dict[str, Any]:
    scope = context.supported_platforms
    for primitive in ("add", "update", "discard"):
        try:
            getattr(scope, primitive)("shopify")
        except (AttributeError, TypeError):
            pass
    return {}


class _IxEvilSequence(list):
    """Custom mutable sequence stand-in (never registered; in-place only)."""


def _ix_h3_custom_mutable(context: Any) -> dict[str, Any]:
    scope = context.supported_platforms
    # If scope ever becomes a custom mutable sequence/mapping, exercise its
    # in-place protocol. On pristine tuples every branch is a no-op.
    for primitive in ("append", "extend", "insert", "add", "update"):
        try:
            method = getattr(scope, primitive)
        except AttributeError:
            continue
        try:
            if primitive == "insert":
                method(0, "shopify")
            elif primitive in ("update", "add"):
                method("shopify")
            else:
                method("shopify")
        except (AttributeError, TypeError):
            pass
    return {}


def _ix_h4_shallow_copy_child(context: Any) -> dict[str, Any]:
    import copy as _copy

    scope = context.supported_platforms
    try:
        twin = _copy.copy(scope)
    except (AttributeError, TypeError):
        return {}
    try:
        twin.append("shopify")  # type: ignore[union-attr]
    except (AttributeError, TypeError):
        pass
    try:
        twin["shopify"] = True  # type: ignore[index]
    except (AttributeError, TypeError, IndexError, KeyError):
        pass
    return {}


def _ix_h5_delayed_mutation(context: Any) -> dict[str, Any]:
    # Delayed in-place mutation through a retained alias: the alias is
    # captured now and mutated before return (still inside projection
    # execution, so the digest tripwire brackets it).
    held = context.supported_platforms
    try:
        held.append("stripe-clone")  # type: ignore[union-attr]
    except (AttributeError, TypeError):
        pass
    try:
        held.append("shopify")  # type: ignore[union-attr]
    except (AttributeError, TypeError):
        pass
    return {}


# ---------------------------------------------------------------------------
# P-IX-1: shared-list append/extend leaves scope sovereign.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("evil", [_ix_d1_list_append, _ix_d2_list_extend_item])
async def test_p_ix_1_shared_list_in_place_sovereign(evil: Any) -> None:
    sink_id = "future_finance_projection"
    tenant_a = _seed_ratio_tenant(76000, 80000, f"ix1-{evil.__name__}")
    pristine = _swap_coordinated(sink_id, evil)
    try:
        output = await _execute(sink_id, tenant_a)
        assert output.supported_platforms == ("stripe",)
        assert output.matched_minor == 76000
        assert output.connected_minor == 80000
        assert output.coverage_percent == Decimal("95.00")
    finally:
        _restore_coordinated(sink_id, pristine)


# ---------------------------------------------------------------------------
# P-IX-2: retained-alias and nested in-place attempts leave truth sovereign.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("evil", [_ix_d3_retained_alias_late, _ix_d4_nested_child])
async def test_p_ix_2_retained_nested_in_place_sovereign(evil: Any) -> None:
    sink_id = "future_finance_projection"
    tenant_a = _seed_ratio_tenant(76000, 80000, f"ix2-{evil.__name__}")
    pristine = _swap_coordinated(sink_id, evil)
    try:
        output = await _execute(sink_id, tenant_a)
        assert output.supported_platforms == ("stripe",)
        assert output.matched_minor == 76000
        assert output.connected_minor == 80000
        assert output.coverage_percent == Decimal("95.00")
    finally:
        _restore_coordinated(sink_id, pristine)
        _IX_D3_RETAINED.clear()


# ---------------------------------------------------------------------------
# P-IX-3: scope-metadata conservation (platforms/currency/window/tenant).
# ---------------------------------------------------------------------------


async def test_p_ix_3_scope_metadata_conservation() -> None:
    from test_b26_p1_corrective_v_consequence import (  # noqa: PLC0415
        WINDOW_END as _WE,
        WINDOW_START as _WS,
    )

    sink_id = "future_finance_projection"
    tenant_a = _seed_ratio_tenant(76000, 80000, "ix3-scope")
    pristine = _swap_coordinated(sink_id, _ix_d5_scope_metadata_substitution)
    try:
        output = await _execute(sink_id, tenant_a)
        # Metadata describing the financial derivation scope is as sovereign
        # as the money legs: legs computed over stripe must present stripe.
        assert output.supported_platforms == ("stripe",)
        assert output.currency_code == "USD"
        assert output.window_start == _WS
        assert output.window_end == _WE
        assert output.tenant_id_hash == tenant_hash(tenant_a)
        assert output.matched_minor == 76000
        assert output.connected_minor == 80000
        assert output.coverage_percent == Decimal("95.00")
        assert output.zero_denominator is False
    finally:
        _restore_coordinated(sink_id, pristine)


# ---------------------------------------------------------------------------
# P-IX-4: freeze boundary normalizes every mutable representation.
# ---------------------------------------------------------------------------


def test_p_ix_4_freeze_boundary_normalizes_mutable_class() -> None:
    # Lawful inputs normalize to equal immutable tuples.
    assert freeze_platform_scope(("stripe",)) == ("stripe",)
    assert freeze_platform_scope(["stripe"]) == ("stripe",)
    assert freeze_platform_scope({"stripe"}) == ("stripe",)
    assert freeze_platform_scope(frozenset({"stripe"})) == ("stripe",)
    # Order is preserved for sequences (no semantic rewrite at this layer).
    assert freeze_platform_scope(["stripe", "shopify"]) == ("stripe", "shopify")
    # Unordered sets normalize deterministically: repeated freezing of the
    # same set yields the identical tuple (set iteration order is
    # process-dependent, so the boundary sorts it).
    assert freeze_platform_scope({"stripe", "shopify"}) == ("shopify", "stripe")
    assert freeze_platform_scope({"stripe", "shopify"}) == freeze_platform_scope(
        {"shopify", "stripe"}
    )
    assert freeze_platform_scope(frozenset({"stripe", "shopify"})) == (
        "shopify",
        "stripe",
    )
    # Un governed shapes refuse fail-closed (new shapes must be declared).
    for hostile in (
        {"stripe": True},
        {"platforms": ["stripe"]},
        bytearray(b"stripe"),
        "stripe",
        42,
        None,
        object(),
    ):
        try:
            freeze_platform_scope(hostile)
        except (ValueError, TypeError):
            pass
        else:
            raise AssertionError(f"freeze accepted ungoverned shape: {hostile!r}")
    # Non-str members refuse (tuple-with-mutable-child cannot be frozen
    # implicitly: the caller must declare the new shape).
    for hostile_member in (["stripe", ["shopify"]], [("stripe",)], [{"s": 1}]):
        try:
            freeze_platform_scope(hostile_member)
        except (ValueError, TypeError):
            pass
        else:
            raise AssertionError(f"freeze accepted mutable member: {hostile_member!r}")
    # MappingProxyType over mutable backing storage refuses: the proxy is
    # not a governed sequence shape even though it is read-only at the
    # surface.
    try:
        freeze_platform_scope(MappingProxyType({"stripe": True}))
    except (ValueError, TypeError):
        pass
    else:
        raise AssertionError("freeze accepted mapping-proxy backing storage")


# ---------------------------------------------------------------------------
# P-IX-5: snapshot type invariant refuses mutable shapes.
# ---------------------------------------------------------------------------


def test_p_ix_5_snapshot_type_invariant_refuses_mutable() -> None:
    lawful = {
        "sink_id": "future_finance_projection",
        "contract_version": "b2.6-p1-semantic-authority-v6",
        "tenant_id_hash": "hash",
        "currency_code": "USD",
        "window_start": datetime(2026, 1, 1),
        "window_end": datetime(2026, 2, 1),
        "supported_platforms": ("stripe",),
        "matched_minor": 76000,
        "connected_minor": 80000,
        "coverage_percent": Decimal("95.00"),
        "zero_denominator": False,
        "provenance_mode": "RE_DERIVE_ON_READ",
        "sovereign_producer": "producer",
    }
    assert_snapshot_types_immutable(**lawful)
    # Each mutable representative must refuse.
    for field, hostile in (
        ("supported_platforms", ["stripe"]),
        ("supported_platforms", {"stripe"}),
        ("supported_platforms", bytearray(b"s")),
        ("supported_platforms", ("stripe", ["shopify"])),
        ("matched_minor", True),
        ("matched_minor", "76000"),
        ("coverage_percent", "95.00"),
        ("zero_denominator", 1),
        ("window_start", "2026-01-01"),
    ):
        mutated = dict(lawful)
        mutated[field] = hostile
        try:
            assert_snapshot_types_immutable(**mutated)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invariant accepted mutable {field}: {hostile!r}")


# ---------------------------------------------------------------------------
# P-IX-6: holdout in-place primitives leave truth sovereign.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "evil",
    [
        _ix_h1_dict_style,
        _ix_h2_set_style,
        _ix_h3_custom_mutable,
        _ix_h4_shallow_copy_child,
        _ix_h5_delayed_mutation,
    ],
)
async def test_p_ix_6_holdout_in_place_sovereign(evil: Any) -> None:
    sink_id = "future_finance_projection"
    tenant_a = _seed_ratio_tenant(76000, 80000, f"ix6-{evil.__name__}")
    pristine = _swap_coordinated(sink_id, evil)
    try:
        output = await _execute(sink_id, tenant_a)
        assert output.supported_platforms == ("stripe",)
        assert output.matched_minor == 76000
        assert output.connected_minor == 80000
        assert output.coverage_percent == Decimal("95.00")
    finally:
        _restore_coordinated(sink_id, pristine)


# ---------------------------------------------------------------------------
# P-IX-7: authoritative field census completeness.
# ---------------------------------------------------------------------------


def test_p_ix_7_authoritative_field_census_complete() -> None:
    assert_registry_covers_output(FinalCanonicalOutput)
    # Every authoritative field carries a full isolation obligation.
    for name in authoritative_field_names():
        spec = AUTHORITATIVE_FIELD_REGISTRY[name]
        assert spec.sovereign_source, name
        assert spec.snapshot_point, name
        assert spec.allowed_type_family, name
        assert spec.projection_representation, name
        assert spec.alias_policy, name
        assert spec.externalization_policy, name
    # The mutable-risk scope field is explicitly storage-disjoint by policy.
    scope_spec = AUTHORITATIVE_FIELD_REGISTRY["supported_platforms"]
    assert "storage-disjoint" in scope_spec.alias_policy
    assert "tuple[str, ...]" in scope_spec.allowed_type_family
    # Provenance: every FinalCanonicalOutput field is classified.
    import dataclasses as _dataclasses

    declared = {field.name for field in _dataclasses.fields(FinalCanonicalOutput)}
    assert set(AUTHORITATIVE_FIELD_REGISTRY) == declared


# ---------------------------------------------------------------------------
# P-IX-8: renderer emits sovereign scope under in-place attack.
# ---------------------------------------------------------------------------


async def test_p_ix_8_renderer_emits_sovereign_under_in_place_mutation() -> None:
    sink_id = "future_finance_projection"
    tenant_a = _seed_ratio_tenant(76000, 80000, "ix8-render")
    pristine = _swap_coordinated(sink_id, _ix_d1_list_append)
    try:
        rendered = await render_governed_external(
            sink_id, auth_token=_auth_token(tenant_a), **_scope()
        )
        assert rendered["supported_platforms"] == ["stripe"]
        assert rendered["matched_minor"] == 76000
        assert rendered["connected_minor"] == 80000
        assert rendered["coverage_percent"] == "95.00"
        assert rendered["authority"] == "canonical_B2.6_financial_truth"
        assert rendered["tenant_id_hash"] == tenant_hash(tenant_a)
    finally:
        _restore_coordinated(sink_id, pristine)


# ---------------------------------------------------------------------------
# P-IX-9: B2.3 95-not-76 truth preserved under in-place attack.
# ---------------------------------------------------------------------------


async def test_p_ix_9_golden_truth_preserved_under_in_place_mutation() -> None:
    from app.finance_reconciliation.coverage_authority import (  # noqa: PLC0415
        independent_coverage_percent,
    )

    sink_id = "future_finance_projection"
    tenant_a = _seed_ratio_tenant(76000, 80000, "ix9-golden")
    pristine = _swap_coordinated(sink_id, _ix_d2_list_extend_item)
    try:
        output = await _execute(sink_id, tenant_a)
        assert (output.matched_minor, output.connected_minor) == (76000, 80000)
        assert output.coverage_percent == Decimal("95.00")
        assert output.supported_platforms == ("stripe",)
        assert independent_coverage_percent(76000, 80000) == (Decimal("95.00"), False)
    finally:
        _restore_coordinated(sink_id, pristine)
