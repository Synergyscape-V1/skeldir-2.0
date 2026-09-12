"""B2.6-P1 Corrective-VII consequence proof battery (cells VII-1 through VII-9).

Each cell is an independent-observer falsifier for one Corrective-VII
class-closure theorem: pristine GREEN, one consequence-bearing defect RED,
exact restore GREEN. A hostile reader may run any cell in isolation.

* VII-1 -- complete access-token authority parity (revocation + claims law).
* VII-2 -- no approved detached-object renderer (promotion unrepresentable).
* VII-3 -- coordinated substitution cannot alter financial truth (bounded TCB).
* VII-4 -- tenant/DB authority preserved under the complete token law.
* VII-5..VII-9 -- holdout class sweep over five previously unused seeds.
"""

from __future__ import annotations

import dataclasses
import importlib
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import jwt
import pytest

from app.finance_reconciliation.canonical_sink import (
    SINK_REGISTRY,
    FinalCanonicalOutput,
    FinalFieldSubstitutionError,
    _SINK_IMPLEMENTATIONS,
    execute_governed_sink,
    external_renderer_signature_is_execution_bound,
    render_governed_external,
    require_registered_sink,
    resolve_authenticated_tenant,
    verify_output_integrity,
)
from app.finance_reconciliation.semantic_contract import B26_P1_CONTRACT_VERSION
from app.finance_reconciliation.tenant_authority import UnknownTenantError
from app.trust.refusal import tenant_hash

from test_b26_p1_corrective_v_consequence import (
    _admin_dsn,
    _auth_token,
    _execute,
    _scope,
    _seed_ratio_tenant,
)

VII_HOLDOUT_SEEDS = (141421, 161803, 244949, 577215, 662607)


@pytest.fixture(autouse=True)
async def _fresh_engines_per_test():
    yield
    from app.db.session import b23_engine
    from app.db.session import engine as app_engine

    await b23_engine.dispose()
    await app_engine.dispose()


def _vii_coordinated_evil(context: Any) -> dict[str, Any]:
    """File-based coordinated-substitution probe (has reviewable source)."""
    return {"evil": True}


def _vii_authoritative_evil(context: Any) -> dict[str, Any]:
    """File-based probe attempting authoritative-field substitution."""
    return {"coverage_percent": "11.11"}


# ---------------------------------------------------------------------------
# VII-1: complete access-token authority parity.
# ---------------------------------------------------------------------------


async def _production_verdict(token: str) -> tuple[bool, str]:
    """Run the governing request-authentication law (decode+claims+lifecycle)."""
    from app.security.auth import (  # noqa: PLC0415
        assert_access_token_active,
        decode_and_verify_jwt,
        extract_access_token_claims,
    )

    try:
        claims = decode_and_verify_jwt(token)
        token_claims = extract_access_token_claims(claims)
        await assert_access_token_active(token_claims)
    except Exception as exc:  # noqa: BLE001
        return False, type(exc).__name__
    return True, "accepted"


async def _b26_verdict(token: str) -> tuple[bool, str]:
    try:
        output = await execute_governed_sink(
            "future_finance_projection", auth_token=token, **_scope()
        )
    except Exception as exc:  # noqa: BLE001
        return False, type(exc).__name__
    return True, str(output.coverage_percent)


def _mint_custom(
    *,
    tenant_id: UUID,
    user_id: UUID,
    omit: frozenset[str] = frozenset(),
    override: dict[str, Any] | None = None,
    expired: bool = False,
) -> str:
    from app.core.secrets import get_jwt_signing_material  # noqa: PLC0415

    signing = get_jwt_signing_material()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "tenant_id": str(tenant_id),
        "sub": str(user_id),
        "user_id": str(user_id),
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    if signing.issuer:
        payload["iss"] = signing.issuer
    if signing.audience:
        payload["aud"] = signing.audience
    for claim in omit:
        payload.pop(claim, None)
    for key, value in (override or {}).items():
        payload[key] = value
    if expired:
        payload["exp"] = int((now - timedelta(minutes=5)).timestamp())
    return jwt.encode(payload, signing.key, algorithm="RS256", headers={"kid": signing.kid})


async def test_vii1_valid_token_conducts_lawful_truth() -> None:
    tenant_a = _seed_ratio_tenant(76000, 80000, "vii1-valid")
    token = _auth_token(tenant_a)
    production_ok, _ = await _production_verdict(token)
    b26_ok, percent = await _b26_verdict(token)
    assert production_ok is True
    assert b26_ok is True
    assert percent == "95.00"


async def test_vii1_structurally_incomplete_tokens_refuse_on_both_planes() -> None:
    tenant_a = _seed_ratio_tenant(76000, 80000, "vii1-claims")
    user_a = uuid.uuid4()
    for omit in (frozenset({"jti"}), frozenset({"iat"})):
        token = _mint_custom(tenant_id=tenant_a, user_id=user_a, omit=omit)
        production_ok, _ = await _production_verdict(token)
        b26_ok, reason = await _b26_verdict(token)
        assert production_ok is False, omit
        assert b26_ok is False, (omit, reason)


async def test_vii1_expired_and_foreign_tokens_refuse_on_both_planes() -> None:
    tenant_a = _seed_ratio_tenant(76000, 80000, "vii1-crypto")
    user_a = uuid.uuid4()
    cases = [
        _mint_custom(tenant_id=tenant_a, user_id=user_a, expired=True),
        _mint_custom(tenant_id=tenant_a, user_id=user_a, override={"iss": "https://wrong.test"}),
        _mint_custom(tenant_id=tenant_a, user_id=user_a, override={"aud": "wrong-audience"}),
        _mint_custom(tenant_id=tenant_a, user_id=user_a, override={"tenant_id": "not-a-uuid"}),
    ]
    for token in cases:
        production_ok, _ = await _production_verdict(token)
        b26_ok, reason = await _b26_verdict(token)
        assert production_ok is False, token[:24]
        assert b26_ok is False, (token[:24], reason)


async def test_vii1_revoked_token_refuses_on_both_planes() -> None:
    from app.db.session import AsyncSessionLocal  # noqa: PLC0415
    from app.security.auth import decode_and_verify_jwt  # noqa: PLC0415
    from app.services.auth_revocation import denylist_access_token  # noqa: PLC0415

    tenant_a = _seed_ratio_tenant(76000, 80000, "vii1-revoked")
    user_a = uuid.uuid4()
    token = _mint_custom(tenant_id=tenant_a, user_id=user_a)
    claims = decode_and_verify_jwt(token)
    production_ok, _ = await _production_verdict(token)
    b26_ok, _ = await _b26_verdict(token)
    assert production_ok is True
    assert b26_ok is True
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await denylist_access_token(
                session,
                tenant_id=tenant_a,
                user_id=user_a,
                jti=UUID(claims["jti"]),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            )
    production_ok, _ = await _production_verdict(token)
    b26_ok, reason = await _b26_verdict(token)
    assert production_ok is False
    assert b26_ok is False, reason


async def test_vii1_pre_cutoff_token_refuses_on_both_planes() -> None:
    from app.db.session import AsyncSessionLocal  # noqa: PLC0415
    from app.services.auth_revocation import (  # noqa: PLC0415
        upsert_tokens_invalid_before,
    )

    tenant_a = _seed_ratio_tenant(76000, 80000, "vii1-cutoff")
    user_a = uuid.uuid4()
    token = _mint_custom(tenant_id=tenant_a, user_id=user_a)
    production_ok, _ = await _production_verdict(token)
    assert production_ok is True
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await upsert_tokens_invalid_before(
                session,
                tenant_id=tenant_a,
                user_id=user_a,
                invalid_before=datetime.now(timezone.utc) + timedelta(minutes=10),
            )
    production_ok, _ = await _production_verdict(token)
    b26_ok, reason = await _b26_verdict(token)
    assert production_ok is False
    assert b26_ok is False, reason


# ---------------------------------------------------------------------------
# VII-2: no approved detached-object renderer.
# ---------------------------------------------------------------------------


def _digest_correct_synthetic(tenant_id: UUID) -> FinalCanonicalOutput:
    framework = importlib.import_module("app.finance_reconciliation.canonical_sink")
    from test_b26_p1_corrective_v_consequence import (  # noqa: PLC0415
        WINDOW_END as _WE,
        WINDOW_START as _WS,
    )

    from app.finance_reconciliation.coverage_authority import (  # noqa: PLC0415
        B23_SOVEREIGN_COVERAGE_PRODUCER as _PRODUCER,
    )

    draft = FinalCanonicalOutput(
        authority="canonical_B2.6_financial_truth",
        sink_id="future_finance_projection",
        contract_version=B26_P1_CONTRACT_VERSION,
        tenant_id_hash=tenant_hash(tenant_id),
        currency_code="USD",
        window_start=_WS,
        window_end=_WE,
        supported_platforms=("stripe",),
        matched_minor=50000,
        connected_minor=100000,
        coverage_percent=Decimal("50.00"),
        zero_denominator=False,
        provenance_mode="RE_DERIVE_ON_READ",
        sovereign_producer=_PRODUCER,
        content_digest="placeholder",
        adjunct_json="{}",
    )
    return dataclasses.replace(draft, content_digest=framework._content_digest(draft))


async def test_vii2_no_approved_renderer_accepts_detached_objects() -> None:
    framework = importlib.import_module("app.finance_reconciliation.canonical_sink")
    assert not hasattr(framework, "to_canonical_external")
    assert not hasattr(framework, "_project_external_fields")
    assert external_renderer_signature_is_execution_bound() is True

    tenant_a = _seed_ratio_tenant(76000, 80000, "vii2-synth")
    synthetic = _digest_correct_synthetic(tenant_a)
    # Integrity-only semantics are locked: digest-correct means
    # digest-intact, never canonical.
    assert verify_output_integrity(synthetic) is True
    # The only approved projection has no object parameter: passing a
    # detached value is a type error, not a refusal convention.
    with pytest.raises(TypeError):
        await render_governed_external(
            "future_finance_projection",
            auth_token=_auth_token(tenant_a),
            output=synthetic,  # type: ignore[call-arg]
            **_scope(),
        )


async def test_vii2_lawful_execution_renders_canonical_external() -> None:
    tenant_a = _seed_ratio_tenant(76000, 80000, "vii2-lawful")
    rendered = await render_governed_external(
        "future_finance_projection", auth_token=_auth_token(tenant_a), **_scope()
    )
    assert rendered["authority"] == "canonical_B2.6_financial_truth"
    assert rendered["coverage_percent"] == "95.00"
    assert rendered["matched_minor"] == 76000
    assert rendered["connected_minor"] == 80000
    assert "tenant_id" not in rendered
    assert str(tenant_a) not in str(rendered)
    assert rendered["tenant_id_hash"] == tenant_hash(tenant_a)
    assert "adjunct_json" not in rendered


# ---------------------------------------------------------------------------
# VII-3: coordinated substitution cannot alter financial truth.
# ---------------------------------------------------------------------------


async def test_vii3_coordinated_substitution_leaves_financial_truth_sovereign() -> None:
    from app.finance_reconciliation.canonical_sink import (  # noqa: PLC0415
        SinkRegistration,
        _implementation_hash,
    )

    sink_id = "future_finance_projection"
    tenant_a = _seed_ratio_tenant(76000, 80000, "vii3-coord")
    pristine_registration = SINK_REGISTRY[sink_id]
    pristine_implementation = _SINK_IMPLEMENTATIONS[sink_id]
    evil_registration = SinkRegistration(
        sink_id=sink_id,
        implementation=f"{__name__}._vii_coordinated_evil",
        implementation_hash=_implementation_hash(_vii_coordinated_evil),
        contract_version=pristine_registration.contract_version,
        output_contract=pristine_registration.output_contract,
        sovereign_source=pristine_registration.sovereign_source,
        tenant_authority_mode=pristine_registration.tenant_authority_mode,
        database_capability_mode=pristine_registration.database_capability_mode,
        provenance_mode=pristine_registration.provenance_mode,
        projection_policy=pristine_registration.projection_policy,
        version="v9.9-vii-coordinated",
        required_runtime_proof_ids=pristine_registration.required_runtime_proof_ids,
    )
    SINK_REGISTRY[sink_id] = evil_registration
    _SINK_IMPLEMENTATIONS[sink_id] = _vii_coordinated_evil
    try:
        # The coordinated capture is accepted at registration (same-process
        # memory is inside the TCB -- stated trust boundary), but the
        # financial consequence stays sovereign: framework materialization
        # runs after the projection and owns every authoritative field.
        assert require_registered_sink(sink_id) == evil_registration
        output = await _execute(sink_id, tenant_a)
        assert output.matched_minor == 76000
        assert output.connected_minor == 80000
        assert output.coverage_percent == Decimal("95.00")
        assert output.zero_denominator is False
        assert "evil" in output.adjunct_json
        rendered = await render_governed_external(
            sink_id, auth_token=_auth_token(tenant_a), **_scope()
        )
        assert rendered["coverage_percent"] == "95.00"
        assert "evil" not in str(rendered)
        assert "adjunct_json" not in rendered
    finally:
        SINK_REGISTRY[sink_id] = pristine_registration
        _SINK_IMPLEMENTATIONS[sink_id] = pristine_implementation
    assert require_registered_sink(sink_id) == pristine_registration


async def test_vii3_authoritative_injection_through_hijack_is_refused() -> None:
    from app.finance_reconciliation.canonical_sink import (  # noqa: PLC0415
        SinkRegistration,
        _implementation_hash,
    )

    sink_id = "future_finance_projection"
    tenant_a = _seed_ratio_tenant(76000, 80000, "vii3-auth-evil")
    pristine_registration = SINK_REGISTRY[sink_id]
    pristine_implementation = _SINK_IMPLEMENTATIONS[sink_id]
    evil_registration = SinkRegistration(
        sink_id=sink_id,
        implementation=f"{__name__}._vii_authoritative_evil",
        implementation_hash=_implementation_hash(_vii_authoritative_evil),
        contract_version=pristine_registration.contract_version,
        output_contract=pristine_registration.output_contract,
        sovereign_source=pristine_registration.sovereign_source,
        tenant_authority_mode=pristine_registration.tenant_authority_mode,
        database_capability_mode=pristine_registration.database_capability_mode,
        provenance_mode=pristine_registration.provenance_mode,
        projection_policy=pristine_registration.projection_policy,
        version="v9.9-vii-authoritative",
        required_runtime_proof_ids=pristine_registration.required_runtime_proof_ids,
    )
    SINK_REGISTRY[sink_id] = evil_registration
    _SINK_IMPLEMENTATIONS[sink_id] = _vii_authoritative_evil
    try:
        with pytest.raises(FinalFieldSubstitutionError):
            await _execute(sink_id, tenant_a)
    finally:
        SINK_REGISTRY[sink_id] = pristine_registration
        _SINK_IMPLEMENTATIONS[sink_id] = pristine_implementation
    assert require_registered_sink(sink_id) == pristine_registration


# ---------------------------------------------------------------------------
# VII-4: tenant/DB authority preserved under the complete token law.
# ---------------------------------------------------------------------------


async def test_vii4_ghost_empty_and_scope_unity_under_complete_law() -> None:
    ghost = uuid.uuid4()
    ghost_token = _auth_token(ghost)
    assert await resolve_authenticated_tenant(ghost_token) == ghost
    with pytest.raises(UnknownTenantError):
        await execute_governed_sink(
            "future_finance_projection", auth_token=ghost_token, **_scope()
        )
    tenant_e = uuid.uuid4()
    import psycopg2  # noqa: PLC0415

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tenants (id, name, api_key_hash,"
                " notification_email) VALUES (%s, %s, %s, %s)",
                (str(tenant_e), "vii4-empty", uuid.uuid4().hex, "vii4@example.invalid"),
            )
    finally:
        conn.close()
    rendered = await render_governed_external(
        "future_finance_projection", auth_token=_auth_token(tenant_e), **_scope()
    )
    assert rendered["coverage_percent"] == "0.00"
    assert rendered["zero_denominator"] is True


# ---------------------------------------------------------------------------
# VII-5..VII-9: holdout class sweep over five previously unused seeds.
# ---------------------------------------------------------------------------


async def _run_vii_holdout(seed: int) -> dict[str, Any]:
    assert seed not in (7, 42, 902611, 770317, 5550197, 110351, 271828, 314159, 610013, 867530)
    from app.finance_reconciliation.class_sweep import (  # noqa: PLC0415
        plan as _plan,
    )
    from app.finance_reconciliation.class_sweep import (  # noqa: PLC0415
        ratio_for as _ratio_for,
    )

    sweep = _plan(seed)
    matched, connected, expected = _ratio_for(sweep)
    tenant = _seed_ratio_tenant(matched, connected, f"vii9-{seed}")
    output = await _execute(sweep.sink_id, tenant)
    assert output.matched_minor == matched
    assert output.connected_minor == connected
    assert output.coverage_percent == Decimal(expected)
    assert verify_output_integrity(output) is True
    rendered = await render_governed_external(
        sweep.sink_id, auth_token=_auth_token(tenant), **_scope()
    )
    assert rendered["coverage_percent"] == str(Decimal(expected))
    with pytest.raises(Exception):
        await _execute(f"vii9_unregistered_{seed}", tenant)
    return {"seed": seed, "ratio": expected, "sink": sweep.sink_id}


async def test_b26_p1_vii_holdout_sweep_141421() -> None:
    assert (await _run_vii_holdout(141421))["seed"] == 141421


async def test_b26_p1_vii_holdout_sweep_161803() -> None:
    assert (await _run_vii_holdout(161803))["seed"] == 161803


async def test_b26_p1_vii_holdout_sweep_244949() -> None:
    assert (await _run_vii_holdout(244949))["seed"] == 244949


async def test_b26_p1_vii_holdout_sweep_577215() -> None:
    assert (await _run_vii_holdout(577215))["seed"] == 577215


async def test_b26_p1_vii_holdout_sweep_662607() -> None:
    assert (await _run_vii_holdout(662607))["seed"] == 662607
