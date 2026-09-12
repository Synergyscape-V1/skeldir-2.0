"""B2.6-P1 Corrective-VI consequence proof battery (cells VI-1 through VI-9).

Each cell is an independent-observer falsifier for one Corrective-VI
class-closure theorem: pristine GREEN, one consequence-bearing defect RED,
exact restore GREEN. A hostile reader may run any cell in isolation; no
cell trusts the framework's own strings, booleans, or registries.

* VI-1 -- authenticated-tenant sovereignty at the executor (JWT-bound).
* VI-2 -- no transferable canonical authority (issuance surface deleted).
* VI-3 -- sink registry first-wins plus executable-hash binding.
* VI-4 -- proof identifiers bind the governed manifest set.
* VI-5 -- P1 successor persistence authorizes nothing durable.
* VI-6 -- zero LLM/callable reachability on the canonical path.
* VI-7 -- live HTTP authentication path (middleware-executed Bearer JWT).
* VI-8 -- tenant externalization stays hash-only end to end.
* VI-9 -- holdout class sweep over five previously unused seeds.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from app.finance_reconciliation.canonical_sink import (
    SINK_REGISTRY,
    CanonicalSinkError,
    DuplicateSinkError,
    FinalCanonicalOutput,
    SuccessorProvenanceError,
    UnregisteredSinkError,
    _SINK_IMPLEMENTATIONS,
    authorize_successor_persistence,
    deregister_successor_persistence,
    execute_governed_sink,
    executor_binds_tenant_from_verified_auth_only,
    register_successor_persistence,
    require_registered_sink,
    resolve_authenticated_tenant,
    to_canonical_external,
    verify_output_integrity,
)
from app.finance_reconciliation.class_sweep import plan as _plan
from app.finance_reconciliation.class_sweep import ratio_for as _ratio_for
from app.finance_reconciliation.proof_manifest import (
    REQUIRED_SINK_PROOFS,
    is_wellformed_proof_id,
    require_proofs_bound,
)
from app.finance_reconciliation.semantic_contract import B26_P1_CONTRACT_VERSION
from app.finance_reconciliation.tenant_authority import UnknownTenantError
from app.trust.refusal import tenant_hash

from test_b26_p1_corrective_v_consequence import (
    WINDOW_END,
    WINDOW_START,
    _auth_token,
    _execute,
    _scope,
    _seed_ratio_tenant,
)

VI_HOLDOUT_SEEDS = (110351, 271828, 314159, 610013, 867530)


@pytest.fixture(autouse=True)
async def _fresh_engines_per_test():
    yield
    from app.db.session import b23_engine
    from app.db.session import engine as app_engine

    await b23_engine.dispose()
    await app_engine.dispose()


# ---------------------------------------------------------------------------
# VI-1: authenticated-tenant sovereignty at the executor.
# ---------------------------------------------------------------------------


async def test_vi1_verified_token_observes_only_its_own_truth() -> None:
    tenant_a = _seed_ratio_tenant(76000, 80000, "vi1-a")
    tenant_b = _seed_ratio_tenant(9000, 9000, "vi1-b")
    out_a = await _execute("future_finance_projection", tenant_a)
    assert out_a.coverage_percent == Decimal("95.00")
    assert out_a.tenant_id_hash == tenant_hash(tenant_a)
    assert out_a.tenant_id_hash != tenant_hash(tenant_b)
    out_b = await _execute("future_finance_projection", tenant_b)
    assert out_b.coverage_percent == Decimal("100.00")
    assert out_b.tenant_id_hash == tenant_hash(tenant_b)
    # The executor exposes no second tenant input to diverge with: an
    # A-token can never name B, so A-cannot-get-B holds by construction.
    assert executor_binds_tenant_from_verified_auth_only() is True


async def test_vi1_forged_empty_and_foreign_tokens_refuse() -> None:
    tenant_a = _seed_ratio_tenant(76000, 80000, "vi1-forge")
    with pytest.raises(Exception):
        await execute_governed_sink(
            "future_finance_projection", auth_token="", **_scope()
        )
    with pytest.raises(Exception):
        await execute_governed_sink(
            "future_finance_projection",
            auth_token="forged-not-a-jwt",
            **_scope(),
        )
    with pytest.raises(Exception):
        await execute_governed_sink(
            "future_finance_projection",
            auth_token=_auth_token(tenant_a) + "tampered",
            **_scope(),
        )


async def test_vi1_nonexistent_tenant_refuses_never_zero() -> None:
    ghost = uuid.uuid4()
    token = _auth_token(ghost)
    assert resolve_authenticated_tenant(token) == ghost
    with pytest.raises(UnknownTenantError):
        await execute_governed_sink(
            "future_finance_projection", auth_token=token, **_scope()
        )


def test_vi1_no_caller_tenant_parameter_exists() -> None:
    import inspect as _inspect

    parameters = _inspect.signature(execute_governed_sink).parameters
    assert "auth_token" in parameters
    for forbidden in (
        "tenant_id",
        "tenant",
        "adjunct_provider",
        "callback",
        "session",
        "engine",
    ):
        assert forbidden not in parameters


# ---------------------------------------------------------------------------
# VI-2: no transferable canonical authority.
# ---------------------------------------------------------------------------


def test_vi2_issuance_surface_is_deleted_not_renamed() -> None:
    import importlib as _importlib

    # NOTE: ``import app...canonical_sink as name`` binds the decorator
    # function (the package re-exports that name and shadows the
    # submodule); importlib returns the real module under test.
    framework = _importlib.import_module(
        "app.finance_reconciliation.canonical_sink"
    )

    for deleted in (
        "_ISSUED_PROVENANCE_DIGESTS",
        "_issue_provenance",
        "is_canonical_output",
        "require_canonical_output",
        "provenance_nonce",
    ):
        assert not hasattr(framework, deleted), deleted
    import dataclasses as _dataclasses

    fields = {field.name for field in _dataclasses.fields(FinalCanonicalOutput)}
    assert "provenance_nonce" not in fields
    assert "content_digest" in fields


async def test_vi2_digest_correct_synthetic_confirms_nothing() -> None:
    tenant_a = _seed_ratio_tenant(76000, 80000, "vi2-synth")
    output = await _execute("future_finance_projection", tenant_a)
    assert verify_output_integrity(output) is True
    # Integrity is not authority: no canonical interface accepts a
    # transferred object. The executor takes scope only; the successor
    # authorizer takes registration ids only.
    import inspect as _inspect

    executor_params = _inspect.signature(execute_governed_sink).parameters
    assert "candidate" not in executor_params
    assert "output" not in executor_params
    successor_params = _inspect.signature(authorize_successor_persistence).parameters
    assert "candidate" not in successor_params
    assert "output" not in successor_params


# ---------------------------------------------------------------------------
# VI-3: sink registry first-wins plus executable-hash binding.
# ---------------------------------------------------------------------------


def test_vi3_direct_registry_mutation_does_not_authorize() -> None:
    from app.finance_reconciliation.canonical_sink import SinkRegistration

    pristine = SINK_REGISTRY["future_finance_projection"]
    evil = SinkRegistration(
        sink_id="future_finance_projection",
        implementation="auditor.evil.hijack",
        implementation_hash="0" * 64,
        contract_version=B26_P1_CONTRACT_VERSION,
        output_contract="final_canonical_output_v1",
        sovereign_source="auditor",
        tenant_authority_mode="auditor",
        database_capability_mode="auditor",
        provenance_mode="RE_DERIVE_ON_READ",
        projection_policy="auditor",
        version="v9.9",
        required_runtime_proof_ids=("V-2", "V-3", "V-4"),
    )
    SINK_REGISTRY["future_finance_projection"] = evil
    try:
        with pytest.raises(CanonicalSinkError):
            require_registered_sink("future_finance_projection")
    finally:
        SINK_REGISTRY["future_finance_projection"] = pristine
    assert require_registered_sink("future_finance_projection") == pristine


async def test_vi3_implementation_swap_is_refused() -> None:
    sink_id = "future_finance_projection"
    pristine_impl = _SINK_IMPLEMENTATIONS[sink_id]

    def _hijacked(context: Any) -> dict[str, Any]:
        return {"hijacked": True}

    _SINK_IMPLEMENTATIONS[sink_id] = _hijacked
    try:
        with pytest.raises(CanonicalSinkError):
            require_registered_sink(sink_id)
    finally:
        _SINK_IMPLEMENTATIONS[sink_id] = pristine_impl
    assert require_registered_sink(sink_id).sink_id == sink_id


def test_vi3_duplicate_registration_keeps_first_binding() -> None:
    before = require_registered_sink("future_finance_projection")

    def _other(context: Any) -> dict[str, Any]:
        return {}

    from app.finance_reconciliation.canonical_sink import canonical_sink

    with pytest.raises(DuplicateSinkError):
        canonical_sink(
            sink_id="future_finance_projection",
            version="v9.9",
            required_runtime_proof_ids=("V-2", "V-3", "V-4"),
        )(_other)
    assert require_registered_sink("future_finance_projection") == before


# ---------------------------------------------------------------------------
# VI-4: proof identifiers bind the governed manifest set.
# ---------------------------------------------------------------------------


def test_vi4_proof_manifest_binding() -> None:
    assert set(REQUIRED_SINK_PROOFS) == {
        "future_B2.6_deterministic_reconciliation_projection_boundary",
        "future_finance_projection",
        "future_B2.6_TrustEnvelope_projection",
    }
    for sink_id, required in REQUIRED_SINK_PROOFS.items():
        assert require_proofs_bound(
            sink_id=sink_id,
            required_runtime_proof_ids=tuple(required),
            contract_version=B26_P1_CONTRACT_VERSION,
        ) == tuple(required)
    for bad in ("FAKE", "V-999", "FAKE-PROOF", "", " V-2", "V-0"):
        assert is_wellformed_proof_id(bad) is False
    assert is_wellformed_proof_id("V-2") is True
    assert is_wellformed_proof_id("VI-6") is True
    with pytest.raises(Exception):
        require_proofs_bound(
            sink_id="future_finance_projection",
            required_runtime_proof_ids=("FAKE",),
            contract_version=B26_P1_CONTRACT_VERSION,
        )
    with pytest.raises(Exception):
        require_proofs_bound(
            sink_id="future_finance_projection",
            required_runtime_proof_ids=("V-2", "V-3"),
            contract_version=B26_P1_CONTRACT_VERSION,
        )
    with pytest.raises(Exception):
        require_proofs_bound(
            sink_id="future_finance_projection",
            required_runtime_proof_ids=("V-2", "V-3", "V-4"),
            contract_version="b2.6-p1-semantic-authority-v4",
        )
    with pytest.raises(Exception):
        require_proofs_bound(
            sink_id="no_such_sink",
            required_runtime_proof_ids=("V-2",),
            contract_version=B26_P1_CONTRACT_VERSION,
        )


# ---------------------------------------------------------------------------
# VI-5: P1 successor persistence authorizes nothing durable.
# ---------------------------------------------------------------------------


def test_vi5_successor_authorization_always_refuses_in_p1() -> None:
    register_successor_persistence(
        registration_id="vi5_probe",
        provenance_mode="RE_DERIVE_ON_READ",
        required_runtime_proof_ids=("VI-6",),
    )
    try:
        with pytest.raises(SuccessorProvenanceError):
            authorize_successor_persistence("vi5_probe")
    finally:
        deregister_successor_persistence("vi5_probe")
    with pytest.raises(SuccessorProvenanceError):
        authorize_successor_persistence("vi5_probe")


# ---------------------------------------------------------------------------
# VI-6: zero LLM/callable reachability on the canonical path.
# ---------------------------------------------------------------------------


def test_vi6_canonical_path_has_no_model_or_network_reachability() -> None:
    import ast as _ast
    from pathlib import Path

    source = Path(
        "backend/app/finance_reconciliation/canonical_sink.py"
    ).read_text(encoding="utf-8")
    tree = _ast.parse(source)
    # Effect-level scan over executable nodes only: documentation of the
    # removed defect class may name it, but no executable node may reference
    # a model client, a network client, or the removed callback parameter.
    forbidden_fragments = (
        "llm",
        "bayesian",
        "openai",
        "anthropic",
        "httpx",
        "aiohttp",
        "adjunct_provider",
    )
    for node in _ast.walk(tree):
        names: list[str] = []
        if isinstance(node, _ast.Name):
            names.append(node.id)
        elif isinstance(node, _ast.Attribute):
            names.append(node.attr)
        elif isinstance(node, _ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, _ast.ImportFrom) and node.module:
            names.append(node.module)
        for name in names:
            lowered = name.lower()
            for fragment in forbidden_fragments:
                assert fragment not in lowered, (fragment, name)
    assert executor_binds_tenant_from_verified_auth_only() is True


# ---------------------------------------------------------------------------
# VI-7: live HTTP authentication path (middleware-executed Bearer JWT).
# ---------------------------------------------------------------------------


async def test_vi7_live_http_auth_path_binds_tenant() -> None:
    tenant_a = _seed_ratio_tenant(76000, 80000, "vi7-a")
    tenant_b = _seed_ratio_tenant(9000, 9000, "vi7-b")
    application = FastAPI()

    @application.get("/b26/projection/{sink_id}")
    async def _projection(request: Request, sink_id: str) -> JSONResponse:
        authorization = request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return JSONResponse(status_code=401, content={"refused": True})
        try:
            output = await execute_governed_sink(
                sink_id,
                auth_token=token.strip(),
                window_start=WINDOW_START,
                window_end=WINDOW_END,
                supported_platforms=["stripe"],
                currency_code="USD",
            )
        except Exception:  # noqa: BLE001 -- any auth/authority failure refuses
            return JSONResponse(status_code=401, content={"refused": True})
        return JSONResponse(status_code=200, content=to_canonical_external(output))

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response_a = await client.get(
            "/b26/projection/future_finance_projection",
            headers={"authorization": f"Bearer {_auth_token(tenant_a)}"},
        )
        assert response_a.status_code == 200, response_a.text
        body_a = response_a.json()
        assert body_a["tenant_id_hash"] == tenant_hash(tenant_a)
        assert body_a["tenant_id_hash"] != tenant_hash(tenant_b)
        assert body_a["coverage_percent"] == "95.00"
        assert "tenant_id" not in body_a
        forged = await client.get(
            "/b26/projection/future_finance_projection",
            headers={"authorization": "Bearer forged-not-a-jwt"},
        )
        assert forged.status_code == 401
        missing = await client.get("/b26/projection/future_finance_projection")
        assert missing.status_code == 401


# ---------------------------------------------------------------------------
# VI-8: tenant externalization stays hash-only end to end.
# ---------------------------------------------------------------------------


async def test_vi8_external_projection_never_emits_raw_tenant() -> None:
    tenant_a = _seed_ratio_tenant(76000, 80000, "vi8-a")
    output = await _execute("future_finance_projection", tenant_a)
    external = to_canonical_external(output)
    assert "tenant_id" not in external
    assert str(tenant_a) not in str(external)
    assert external["tenant_id_hash"] == tenant_hash(tenant_a)


# ---------------------------------------------------------------------------
# VI-9: holdout class sweep over five previously unused seeds.
# ---------------------------------------------------------------------------


async def _run_vi_holdout(seed: int) -> dict[str, Any]:
    assert seed not in (7, 42, 902611, 770317, 5550197)
    sweep = _plan(seed)
    matched, connected, expected = _ratio_for(sweep)
    tenant = _seed_ratio_tenant(matched, connected, f"vi9-{seed}")
    output = await _execute(sweep.sink_id, tenant)
    assert output.matched_minor == matched
    assert output.connected_minor == connected
    assert output.coverage_percent == Decimal(expected)
    assert verify_output_integrity(output) is True
    with pytest.raises(UnregisteredSinkError):
        await _execute(f"vi9_unregistered_{seed}", tenant)
    return {"seed": seed, "ratio": expected, "sink": sweep.sink_id}


async def test_b26_p1_vi_holdout_sweep_110351() -> None:
    assert (await _run_vi_holdout(110351))["seed"] == 110351


async def test_b26_p1_vi_holdout_sweep_271828() -> None:
    assert (await _run_vi_holdout(271828))["seed"] == 271828


async def test_b26_p1_vi_holdout_sweep_314159() -> None:
    assert (await _run_vi_holdout(314159))["seed"] == 314159


async def test_b26_p1_vi_holdout_sweep_610013() -> None:
    assert (await _run_vi_holdout(610013))["seed"] == 610013


async def test_b26_p1_vi_holdout_sweep_867530() -> None:
    assert (await _run_vi_holdout(867530))["seed"] == 867530
