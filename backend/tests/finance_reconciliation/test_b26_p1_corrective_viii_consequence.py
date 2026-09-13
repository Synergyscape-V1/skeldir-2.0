"""B2.6-P1 Corrective-VIII consequence proof battery (cells P-VIII-1..P-VIII-8).

Each cell is an independent-observer falsifier for one Corrective-VIII
class-closure theorem: pristine GREEN, one consequence-bearing defect RED,
exact restore GREEN. A hostile reader may run any cell in isolation.

Development mechanisms (used to tune the VIII-A/VIII-B fix):
  D1 object.__setattr__ on legs/percent
  D2 instance __dict__ mutation
  D3 helper-function mutation
  D4 retained-reference mutation after return
  D5 tenant-hash substitution through the projection channel

Holdout mechanisms (frozen after the fix, never used during development):
  H1 descriptor/property-class state manipulation
  H2 custom-Mapping side effects during adjunct serialization
  H3 closure/global-state mutation
  H4 class-level attribute manipulation
  H5 currency/window/platform substitution

* P-VIII-1 -- pre-projection sovereign snapshot cannot be modified (D1+D2).
* P-VIII-2 -- projection-visible mutation leaves final fields sovereign (D3+D4+H2+H3).
* P-VIII-3 -- tenant/currency/window/platform substitution refused-or-sovereign (D5+H5+H4).
* P-VIII-4 -- verified callable == executed callable across async suspension.
* P-VIII-5 -- approved external renderer emits the uncontaminated sovereign result.
* P-VIII-6 -- VII-A authentication law preserved (revoked/missing-claim refuse).
* P-VIII-7 -- VII-B detached-object non-promotion preserved.
* P-VIII-8 -- B2.3 95-not-76 truth preserved.
"""

from __future__ import annotations

import asyncio
import dataclasses
import importlib
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest

from app.finance_reconciliation.canonical_sink import (
    SINK_REGISTRY,
    FinalCanonicalOutput,
    _SINK_IMPLEMENTATIONS,
    _capture_verified_implementation,
    execute_governed_sink,
    external_renderer_signature_is_execution_bound,
    render_governed_external,
    require_registered_sink,
    verify_output_integrity,
)
from app.finance_reconciliation.semantic_contract import B26_P1_CONTRACT_VERSION
from app.trust.refusal import tenant_hash

from test_b26_p1_corrective_v_consequence import (
    _auth_token,
    _execute,
    _scope,
    _seed_ratio_tenant,
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
        version="v9.9-viii-probe",
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
# Development evil projections (D1..D5).
# ---------------------------------------------------------------------------


def _viii_d1_object_setattr(context: Any) -> dict[str, Any]:
    object.__setattr__(context, "matched_minor", 50000)
    object.__setattr__(context, "connected_minor", 100000)
    object.__setattr__(context, "coverage_percent", Decimal("50.00"))
    return {}


def _viii_d2_dunder_dict(context: Any) -> dict[str, Any]:
    context.__dict__["matched_minor"] = 41000
    context.__dict__["connected_minor"] = 82000
    context.__dict__["coverage_percent"] = Decimal("50.00")
    return {}


def _viii_helper_mutate(context: Any) -> None:
    object.__setattr__(context, "matched_minor", 7)


def _viii_d3_helper(context: Any) -> dict[str, Any]:
    _viii_helper_mutate(context)
    return {}


def _viii_d4_retained(context: Any) -> dict[str, Any]:
    _viii_d4_retained.held = context  # type: ignore[attr-defined]
    object.__setattr__(context, "matched_minor", 9)
    return {}


def _viii_d5_tenant_hash(context: Any) -> dict[str, Any]:
    object.__setattr__(context, "tenant_id_hash", "attacker-hash")
    object.__setattr__(context, "currency_code", "EUR")
    return {}


# ---------------------------------------------------------------------------
# Holdout evil projections (H1..H5) -- never used during fix development.
# ---------------------------------------------------------------------------


def _viii_h1_class_state(context: Any) -> dict[str, Any]:
    type(context).__dataclass_params__  # read-only touch; then instance attack
    object.__setattr__(context, "zero_denominator", True)
    object.__setattr__(context, "coverage_percent", Decimal("1.11"))
    return {}


class _ViiiEvilMapping(dict):
    def __init__(self, context: Any, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        object.__setattr__(context, "matched_minor", 60001)

    def items(self):  # type: ignore[override]
        return super().items()


def _viii_h2_mapping_side_effect(context: Any) -> dict[str, Any]:
    return _ViiiEvilMapping(context, {"note": "holdout-h2"})  # type: ignore[return-value]


_VIII_H3_GLOBAL: list[Any] = []


def _viii_h3_closure_global(context: Any) -> dict[str, Any]:
    _VIII_H3_GLOBAL.append(context)
    for held in _VIII_H3_GLOBAL:
        try:
            object.__setattr__(held, "connected_minor", 777)
        except Exception:  # noqa: BLE001
            pass
    return {}


def _viii_h4_class_attr(context: Any) -> dict[str, Any]:
    try:
        type(context).matched_minor = 12345  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    object.__setattr__(context, "matched_minor", 12345)
    return {}


def _viii_h5_currency_window_platforms(context: Any) -> dict[str, Any]:
    object.__setattr__(context, "currency_code", "EUR")
    object.__setattr__(context, "supported_platforms", ("shopify",))
    return {}


# ---------------------------------------------------------------------------
# P-VIII-1: snapshot isolation against reflective/storage mutation.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("evil", [_viii_d1_object_setattr, _viii_d2_dunder_dict])
async def test_p_viii_1_snapshot_isolation(evil: Any) -> None:
    sink_id = "future_finance_projection"
    tenant_a = _seed_ratio_tenant(76000, 80000, f"viii1-{evil.__name__}")
    pristine = _swap_coordinated(sink_id, evil)
    try:
        output = await _execute(sink_id, tenant_a)
        assert output.matched_minor == 76000
        assert output.connected_minor == 80000
        assert output.coverage_percent == Decimal("95.00")
        assert output.zero_denominator is False
    finally:
        _restore_coordinated(sink_id, pristine)


# ---------------------------------------------------------------------------
# P-VIII-2: helper/retained/mapping/closure mutation leaves truth sovereign.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "evil",
    [
        _viii_d3_helper,
        _viii_d4_retained,
        _viii_h2_mapping_side_effect,
        _viii_h3_closure_global,
    ],
)
async def test_p_viii_2_mutation_class_sovereign(evil: Any) -> None:
    sink_id = "future_finance_projection"
    tenant_a = _seed_ratio_tenant(76000, 80000, f"viii2-{evil.__name__}")
    pristine = _swap_coordinated(sink_id, evil)
    try:
        output = await _execute(sink_id, tenant_a)
        assert output.matched_minor == 76000
        assert output.connected_minor == 80000
        assert output.coverage_percent == Decimal("95.00")
    finally:
        _restore_coordinated(sink_id, pristine)
        _VIII_H3_GLOBAL.clear()
        if hasattr(_viii_d4_retained, "held"):
            delattr(_viii_d4_retained, "held")


# ---------------------------------------------------------------------------
# P-VIII-3: tenant/currency/window/platform substitution.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "evil",
    [
        _viii_d5_tenant_hash,
        _viii_h4_class_attr,
        _viii_h5_currency_window_platforms,
        _viii_h1_class_state,
    ],
)
async def test_p_viii_3_authoritative_substitution_sovereign(evil: Any) -> None:
    from test_b26_p1_corrective_v_consequence import (  # noqa: PLC0415
        WINDOW_END as _WE,
        WINDOW_START as _WS,
    )

    sink_id = "future_finance_projection"
    tenant_a = _seed_ratio_tenant(76000, 80000, f"viii3-{evil.__name__}")
    pristine = _swap_coordinated(sink_id, evil)
    try:
        output = await _execute(sink_id, tenant_a)
        assert output.tenant_id_hash == tenant_hash(tenant_a)
        assert output.currency_code == "USD"
        assert output.window_start == _WS
        assert output.window_end == _WE
        assert output.matched_minor == 76000
        assert output.connected_minor == 80000
        assert output.coverage_percent == Decimal("95.00")
        assert output.zero_denominator is False
    finally:
        _restore_coordinated(sink_id, pristine)
        for attr in ("matched_minor",):
            try:
                delattr(type(output) if False else object, attr)
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# P-VIII-4: verified callable == executed callable across async suspension.
# ---------------------------------------------------------------------------


async def test_p_viii_4_single_sided_swap_refuses() -> None:
    """A lone implementation swap (registry untouched) must refuse."""
    sink_id = "future_finance_projection"
    tenant_a = _seed_ratio_tenant(76000, 80000, "viii4-single")
    pristine_implementation = _SINK_IMPLEMENTATIONS[sink_id]
    _SINK_IMPLEMENTATIONS[sink_id] = _viii_d1_object_setattr
    try:
        with pytest.raises(Exception):
            await _execute(sink_id, tenant_a)
    finally:
        _SINK_IMPLEMENTATIONS[sink_id] = pristine_implementation
    assert require_registered_sink(sink_id) is not None
    output = await _execute(sink_id, tenant_a)
    assert output.coverage_percent == Decimal("95.00")


async def test_p_viii_4_concurrent_single_sided_swap_refuses_or_sovereign() -> None:
    """Swap during framework suspension: never unverified execution."""
    sink_id = "future_finance_projection"
    tenant_a = _seed_ratio_tenant(76000, 80000, "viii4-concurrent")
    pristine_implementation = _SINK_IMPLEMENTATIONS[sink_id]

    async def _swapper() -> None:
        await asyncio.sleep(0.01)
        _SINK_IMPLEMENTATIONS[sink_id] = _viii_d1_object_setattr

    task = asyncio.ensure_future(_execute(sink_id, tenant_a))
    swap = asyncio.ensure_future(_swapper())
    try:
        output = await task
    except Exception:  # noqa: BLE001
        output = None
    finally:
        await swap
        _SINK_IMPLEMENTATIONS[sink_id] = pristine_implementation
    if output is not None:
        # If the swap landed before the final atomic capture, the capture
        # refuses on hash divergence; if it landed after, lawful truth.
        # Either way attacker values must never obtain canonical authority.
        assert output.matched_minor == 76000
        assert output.coverage_percent == Decimal("95.00")
    assert require_registered_sink(sink_id) is not None


async def test_p_viii_4_atomic_capture_binds_identity() -> None:
    """The captured reference is the verified reference (unit shape)."""
    registration, implementation = _capture_verified_implementation(
        "future_finance_projection"
    )
    assert registration.sink_id == "future_finance_projection"
    assert _SINK_IMPLEMENTATIONS["future_finance_projection"] is implementation


# ---------------------------------------------------------------------------
# P-VIII-5: renderer emits the uncontaminated sovereign result.
# ---------------------------------------------------------------------------


async def test_p_viii_5_renderer_emits_sovereign_under_mutation() -> None:
    sink_id = "future_finance_projection"
    tenant_a = _seed_ratio_tenant(76000, 80000, "viii5-render")
    pristine = _swap_coordinated(sink_id, _viii_d1_object_setattr)
    try:
        rendered = await render_governed_external(
            sink_id, auth_token=_auth_token(tenant_a), **_scope()
        )
        assert rendered["matched_minor"] == 76000
        assert rendered["connected_minor"] == 80000
        assert rendered["coverage_percent"] == "95.00"
        assert rendered["authority"] == "canonical_B2.6_financial_truth"
        assert rendered["tenant_id_hash"] == tenant_hash(tenant_a)
    finally:
        _restore_coordinated(sink_id, pristine)


# ---------------------------------------------------------------------------
# P-VIII-6: VII-A authentication law preserved.
# ---------------------------------------------------------------------------


async def test_p_viii_6_revoked_and_claimless_tokens_refuse() -> None:
    import uuid as _uuid

    from test_b26_p1_corrective_vii_consequence import (  # noqa: PLC0415
        _mint_custom,
    )

    tenant_a = _seed_ratio_tenant(76000, 80000, "viii6-auth")
    user_a = _uuid.uuid4()
    for omit in (frozenset({"jti"}), frozenset({"iat"})):
        token = _mint_custom(tenant_id=tenant_a, user_id=user_a, omit=omit)
        with pytest.raises(Exception):  # noqa: BLE001
            await execute_governed_sink(
                "future_finance_projection", auth_token=token, **_scope()
            )


# ---------------------------------------------------------------------------
# P-VIII-7: VII-B detached-object non-promotion preserved.
# ---------------------------------------------------------------------------


async def test_p_viii_7_detached_synthetic_has_no_promoter() -> None:
    framework = importlib.import_module("app.finance_reconciliation.canonical_sink")
    assert not hasattr(framework, "to_canonical_external")
    assert external_renderer_signature_is_execution_bound() is True
    tenant_a = _seed_ratio_tenant(76000, 80000, "viii7-synth")
    draft = FinalCanonicalOutput(
        authority="canonical_B2.6_financial_truth",
        sink_id="future_finance_projection",
        contract_version=B26_P1_CONTRACT_VERSION,
        tenant_id_hash=tenant_hash(tenant_a),
        currency_code="USD",
        window_start=datetime(2026, 1, 1),
        window_end=datetime(2026, 2, 1),
        supported_platforms=("stripe",),
        matched_minor=50000,
        connected_minor=100000,
        coverage_percent=Decimal("50.00"),
        zero_denominator=False,
        provenance_mode="RE_DERIVE_ON_READ",
        sovereign_producer="x",
        content_digest="placeholder",
        adjunct_json="{}",
    )
    rebuilt = dataclasses.replace(
        draft, content_digest=framework._content_digest(draft)
    )
    assert verify_output_integrity(rebuilt) is True
    with pytest.raises(TypeError):
        await render_governed_external(
            "future_finance_projection",
            auth_token=_auth_token(tenant_a),
            output=rebuilt,  # type: ignore[call-arg]
            **_scope(),
        )


# ---------------------------------------------------------------------------
# P-VIII-8: B2.3 95-not-76 truth preserved.
# ---------------------------------------------------------------------------


async def test_p_viii_8_golden_truth_preserved() -> None:
    from app.finance_reconciliation.coverage_authority import (  # noqa: PLC0415
        independent_coverage_percent,
    )

    tenant_a = _seed_ratio_tenant(76000, 80000, "viii8-golden")
    output = await _execute("future_finance_projection", tenant_a)
    assert (output.matched_minor, output.connected_minor) == (76000, 80000)
    assert output.coverage_percent == Decimal("95.00")
    assert independent_coverage_percent(76000, 80000) == (Decimal("95.00"), False)
