"""B2.5-P10 follow-up corrective-action semantic and boundary proofs."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import trust_api, trust_keys
from app.trust.key_registry import TrustKeyRegistry, TrustSigningKey
from app.trust.machine_auth import MachineCallerContext, _check_rate_limit
from app.trust.machine_identity import AgentScope
from app.trust.reason_codes import ReasonCode
from app.trust.source_adapters import (
    MatchVerdictSource,
    SUPPORTED_P5_SUBJECT_TYPES,
    query_match_verdict_sources,
)
from app.trust.tenant_security import (
    TENANT_CONTEXT_EXTERNAL_REASON,
    TenantContextMissingException,
    assert_authenticated_tenant_context,
    record_tenant_context_failure_durable,
    tenant_context_missing_exception_handler,
)
from app.trust.jwks import registry_from_public_jwks
from app.trust.verification import verify_trust_envelope


def _utc(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _registry() -> TrustKeyRegistry:
    private_key = Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"b25-p10-corrective-wire-key").digest()
    )
    return TrustKeyRegistry(
        (
            TrustSigningKey(
                kid="kid:b25-p10-corrective-wire",
                algorithm="ed25519",
                public_key=private_key.public_key(),
                private_key=private_key,
                state="active",
                valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        )
    )


def test_runtime_key_authority_converges_across_fresh_worker_processes() -> None:
    seed = hashlib.sha256(b"b25-p10-cross-worker-governed-key").digest()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    env["SKELDIR_TRUST_SIGNING_KEY_SEED_B64URL"] = (
        base64.urlsafe_b64encode(seed).rstrip(b"=").decode("ascii")
    )
    env["SKELDIR_TRUST_SIGNING_KEY_ID"] = "kid:b25-p10-cross-worker"
    env["SKELDIR_TRUST_SIGNING_KEY_VALID_FROM"] = "2026-01-01T00:00:00Z"
    command = [
        sys.executable,
        "-c",
        (
            "import json; "
            "from app.trust.jwks import build_jwks_response; "
            "from app.trust.runtime_keys import load_runtime_verification_registry; "
            "print(json.dumps(build_jwks_response("
            "load_runtime_verification_registry()), sort_keys=True))"
        ),
    ]
    workers = [
        subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[3],
            env=env,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        for _ in range(2)
    ]
    assert workers[0] == workers[1]
    assert '"kid": "kid:b25-p10-cross-worker"' in workers[0]
    assert "private" not in workers[0].lower()


def _unsigned_fixture() -> dict[str, object]:
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    payload = json.loads(
        (
            root / "contracts/trust-api/examples/deterministic_only_verified.json"
        ).read_text(encoding="utf-8")
    )
    now = datetime.now(timezone.utc)
    payload["created_at"] = _utc(now)
    payload["valid_until"] = _utc(now + timedelta(hours=1))
    return payload


def _caller(tenant_id: UUID | None = None) -> MachineCallerContext:
    return MachineCallerContext(
        agent_client_id=uuid4(),
        tenant_id=tenant_id or uuid4(),
        audience="b25-p10-corrective-agent",
        scopes=frozenset({AgentScope.ENVELOPE_READ, AgentScope.ENVELOPE_VERIFY}),
        nonce_value="nonce-0123456789abcdef",
        request_identity_hash="sha256:" + "1" * 64,
    )


def _headers(
    tenant_id: UUID, *, nonce: str = "nonce-0123456789abcdef"
) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-machine-token-value",
        "X-Tenant-ID": str(tenant_id),
        "X-Trust-Nonce": nonce,
        "X-Correlation-ID": str(uuid4()),
        "X-Idempotency-Key": "p10-corrective-idempotency",
    }


def _source(
    *,
    tenant_id: UUID,
    verdict_id: UUID | None = None,
    updated_at: datetime | None = None,
) -> MatchVerdictSource:
    observed = updated_at or datetime(2026, 7, 1, tzinfo=timezone.utc)
    return MatchVerdictSource(
        id=verdict_id or uuid4(),
        tenant_id=tenant_id,
        webhook_ingress_identity_id=None,
        provider="stripe",
        canonical_commerce_reference="order-display",
        provider_native_event_reference="event-display",
        provider_native_commerce_reference="commerce-display",
        status="matched_confirmed",
        match_quality="exact",
        canonical_net_verified_amount_minor=12345,
        currency_code="USD",
        last_transition_at=observed,
        created_at=observed - timedelta(days=1),
        updated_at=observed,
    )


def _route_app() -> FastAPI:
    app = FastAPI()
    app.include_router(trust_api.router, prefix="/api")
    app.include_router(trust_keys.router, prefix="/api")
    app.add_exception_handler(
        TenantContextMissingException,
        tenant_context_missing_exception_handler,
    )
    return app


async def _fake_session_dependency():
    yield object()


def test_contract_adapter_parity_and_reserved_taxonomy_are_explicit() -> None:
    supported = {value.value for value in trust_api.SUPPORTED_TRUST_SUBJECT_TYPES}
    reserved = {value.value for value in trust_api.RESERVED_TRUST_SUBJECT_TYPES}
    assert (
        supported
        == SUPPORTED_P5_SUBJECT_TYPES
        == {
            "match_verdict",
            "confidence_projection",
        }
    )
    assert supported.isdisjoint(reserved)
    assert supported | reserved == {value.value for value in trust_api.TrustSubjectType}


@pytest.mark.asyncio
async def test_reserved_subject_type_is_typed_and_never_false_absence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _route_app()
    caller = _caller()
    build_calls = 0

    async def trusted() -> MachineCallerContext:
        return caller

    async def signing_registry() -> TrustKeyRegistry:
        return _registry()

    async def forbidden_build(*args, **kwargs):
        nonlocal build_calls
        build_calls += 1
        raise AssertionError("reserved subject must not reach P5")

    app.dependency_overrides[trust_api.get_machine_db_session] = (
        _fake_session_dependency
    )
    app.dependency_overrides[trust_api.get_runtime_signing_registry] = (
        lambda: _registry()
    )
    app.dependency_overrides[trust_api.require_envelope_read_tenant_context] = trusted
    app.dependency_overrides[trust_api.get_runtime_signing_registry] = signing_registry
    monkeypatch.setattr(
        trust_api,
        "build_unsigned_trust_envelope_with_audit",
        forbidden_build,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/trust/v1/envelopes/revenue_claim/urn:skeldir:revenue:reserved",
            headers=_headers(caller.tenant_id),
        )

    assert response.status_code == 422
    assert response.json() == {
        "status": "refused",
        "reason_code": ReasonCode.UNSUPPORTED_SUBJECT_TYPE.value,
    }
    assert build_calls == 0


def test_expanded_lookup_limit_applies_after_cartesian_normalization() -> None:
    refs = [f"urn:skeldir:match_verdict:{uuid4()}" for _ in range(50)]
    accepted = trust_api.TrustQueryRequest(
        subject_types=[trust_api.TrustSubjectType.MATCH_VERDICT],
        subject_refs=refs,
    )
    assert len(accepted.subject_refs) == 50

    with pytest.raises(ValueError, match="expanded_lookup_pair_limit_exceeded"):
        trust_api.TrustQueryRequest(
            subject_types=[
                trust_api.TrustSubjectType.MATCH_VERDICT,
                trust_api.TrustSubjectType.REVENUE_CLAIM,
            ],
            subject_refs=refs,
        )


@pytest.mark.asyncio
async def test_temporal_query_selects_by_persisted_subject_updated_at_before_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _route_app()
    tenant_id = uuid4()
    caller = _caller(tenant_id)
    historical = _source(
        tenant_id=tenant_id,
        updated_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
    )
    current = _source(
        tenant_id=tenant_id,
        updated_at=datetime(2026, 7, 15, tzinfo=timezone.utc),
    )
    selected_sources: list[UUID] = []

    async def trusted() -> MachineCallerContext:
        return caller

    async def signing_registry() -> TrustKeyRegistry:
        return _registry()

    async def select_sources(
        *args, updated_at_after=None, updated_at_before=None, **kwargs
    ):
        assert updated_at_after is not None and updated_at_before is not None
        return tuple(
            source
            for source in (historical, current)
            if updated_at_after <= source.updated_at <= updated_at_before
        )

    async def issue(*, source=None, **kwargs):
        assert source is not None
        selected_sources.append(source.id)
        return {
            "subject_type": "match_verdict",
            "subject_ref": f"urn:skeldir:match_verdict:{source.id}",
            "signature": "ed25519:test",
        }

    app.dependency_overrides[trust_api.get_machine_db_session] = (
        _fake_session_dependency
    )
    app.dependency_overrides[trust_api.require_envelope_read_tenant_context] = trusted
    app.dependency_overrides[trust_api.get_runtime_signing_registry] = signing_registry
    monkeypatch.setattr(trust_api, "query_match_verdict_sources", select_sources)
    monkeypatch.setattr(trust_api, "_issue_signed_envelope", issue)

    payload = {
        "subject_types": ["match_verdict"],
        "subject_refs": [
            f"urn:skeldir:match_verdict:{historical.id}",
            f"urn:skeldir:match_verdict:{current.id}",
        ],
        "created_at_after": "2026-01-01T00:00:00Z",
        "created_at_before": "2026-01-31T00:00:00Z",
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/trust/v1/envelopes/query",
            headers=_headers(tenant_id),
            json=payload,
        )

    assert response.status_code == 200
    assert selected_sources == [historical.id]
    assert response.json()["envelopes"][0]["subject_ref"].endswith(str(historical.id))


@pytest.mark.asyncio
async def test_bounded_source_sql_uses_persisted_chronology_and_no_offset() -> None:
    tenant_id = uuid4()
    verdict_id = uuid4()
    source = _source(tenant_id=tenant_id, verdict_id=verdict_id)
    statements: list[str] = []
    params_seen: list[dict[str, object]] = []

    class Result:
        def mappings(self):
            return [source.__dict__]

    class Session:
        async def execute(self, statement, params):
            statements.append(str(statement))
            params_seen.append(params)
            return Result()

    after = source.updated_at - timedelta(seconds=1)
    before = source.updated_at + timedelta(seconds=1)
    rows = await query_match_verdict_sources(
        Session(),
        tenant_id=tenant_id,
        subject_refs=[f"urn:skeldir:match_verdict:{verdict_id}"],
        updated_at_after=after,
        updated_at_before=before,
        row_limit=50,
    )

    sql = statements[0].upper()
    assert len(rows) == 1
    assert "UPDATED_AT >=" in sql and "UPDATED_AT <=" in sql
    assert "ORDER BY UPDATED_AT ASC, ID ASC" in sql
    assert "LIMIT" in sql and "OFFSET" not in sql
    assert params_seen[0]["row_limit"] == 50
    assert params_seen[0]["updated_at_after"] == after
    assert params_seen[0]["updated_at_before"] == before


def test_fixed_wire_budgets_close_mathematically() -> None:
    assert trust_api.MAX_SERIALIZED_ENVELOPE_BYTES <= 256 * 1024
    assert trust_api.MAX_RETURNED_OUTCOMES <= 50
    assert trust_api.MAX_SIGNATURES_PER_REQUEST <= 50
    assert trust_api.MAX_ISSUANCE_AUDIT_EFFECTS <= 50
    assert (
        trust_api.MAX_RETURNED_OUTCOMES * trust_api.MAX_SERIALIZED_ENVELOPE_BYTES + 1024
        <= trust_api.MAX_AGGREGATE_RESPONSE_BYTES
        <= 4 * 1024 * 1024
    )


@pytest.mark.asyncio
async def test_individual_wire_budget_fails_typed_before_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caller = _caller()

    async def fake_build(*args, **kwargs):
        return SimpleNamespace(unsigned_payload={"safe": True})

    monkeypatch.setattr(
        trust_api,
        "build_unsigned_trust_envelope_with_audit",
        fake_build,
    )
    monkeypatch.setattr(
        trust_api,
        "sign_trust_envelope",
        lambda *args, **kwargs: {
            "signature": "ed25519:test",
            "bounded": "x" * trust_api.MAX_SERIALIZED_ENVELOPE_BYTES,
        },
    )

    with pytest.raises(
        trust_api.TrustResponseBudgetExceeded,
        match="individual_envelope_budget_exceeded",
    ):
        await trust_api._issue_signed_envelope(
            session=object(),
            caller=caller,
            subject_type="match_verdict",
            subject_ref=f"urn:skeldir:match_verdict:{uuid4()}",
            idempotency_key="wire-budget",
            key_registry=_registry(),
            issued_at=datetime.now(timezone.utc),
        )


@pytest.mark.asyncio
async def test_verify_body_budget_rejects_before_auth_and_crypto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _route_app()
    auth_calls = 0
    crypto_calls = 0

    async def auth(*args, **kwargs):
        nonlocal auth_calls
        auth_calls += 1
        return _caller()

    def verify(*args, **kwargs):
        nonlocal crypto_calls
        crypto_calls += 1
        raise AssertionError("oversized verification must not reach crypto")

    monkeypatch.setattr(trust_api, "authenticate_machine_caller", auth)
    monkeypatch.setattr(trust_api, "verify_trust_envelope", verify)
    app.dependency_overrides[trust_api.get_machine_db_session] = (
        _fake_session_dependency
    )
    app.dependency_overrides[trust_api.get_runtime_signing_registry] = (
        lambda: _registry()
    )
    tenant_id = uuid4()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/trust/v1/verify",
            headers=_headers(tenant_id),
            content=b"{" + b"x" * trust_api.MAX_VERIFY_BODY_BYTES + b"}",
        )

    assert response.status_code == 413
    assert auth_calls == 0
    assert crypto_calls == 0


@pytest.mark.asyncio
async def test_tenant_context_assertion_accepts_exact_non_bypass_identity() -> None:
    caller = _caller()
    request = SimpleNamespace(
        headers={
            "X-Tenant-ID": str(caller.tenant_id),
            "X-Correlation-ID": str(uuid4()),
        },
        state=SimpleNamespace(),
        scope={},
        method="GET",
    )

    class Result:
        def first(self):
            return (str(caller.tenant_id), False)

    class Session:
        async def execute(self, statement):
            return Result()

    assert (
        await assert_authenticated_tenant_context(request, Session(), caller) is caller
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "guc_value,bypass",
    [
        (None, False),
        ("", False),
        (str(uuid4()), False),
        ("not-a-uuid", False),
        (None, True),
    ],
)
async def test_missing_invalid_mismatched_or_bypass_tenant_context_fails_hard(
    guc_value: str | None,
    bypass: bool,
) -> None:
    caller = _caller()
    request = SimpleNamespace(
        headers={
            "X-Tenant-ID": str(caller.tenant_id),
            "X-Correlation-ID": str(uuid4()),
        },
        state=SimpleNamespace(),
        scope={},
        method="GET",
    )

    class Result:
        def first(self):
            return (guc_value, bypass)

    class Session:
        async def execute(self, statement):
            return Result()

    with pytest.raises(TenantContextMissingException):
        await assert_authenticated_tenant_context(request, Session(), caller)


@pytest.mark.asyncio
async def test_tenant_context_handler_invokes_autonomous_audit_and_sanitizes_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _route_app()
    caller = _caller()
    audit_failures: list[TenantContextMissingException] = []

    async def session():
        class Result:
            def first(self):
                return (None, False)

        class MissingGucSession:
            async def execute(self, statement):
                return Result()

        yield MissingGucSession()

    async def authenticated() -> MachineCallerContext:
        return caller

    async def signing_registry() -> TrustKeyRegistry:
        return _registry()

    async def capture_audit(exc: TenantContextMissingException) -> None:
        audit_failures.append(exc)

    app.dependency_overrides[trust_api.get_machine_db_session] = session
    app.dependency_overrides[trust_api.require_envelope_read_scope] = authenticated
    app.dependency_overrides[trust_api.get_runtime_signing_registry] = signing_registry
    monkeypatch.setattr(
        "app.trust.tenant_security.record_tenant_context_failure_durable",
        capture_audit,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/api/trust/v1/envelopes/match_verdict/urn:skeldir:match_verdict:{uuid4()}",
            headers=_headers(caller.tenant_id),
        )

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "reason_code": TENANT_CONTEXT_EXTERNAL_REASON,
    }
    assert len(audit_failures) == 1
    assert audit_failures[0].tenant_id == caller.tenant_id
    assert "current_tenant" not in response.text
    assert str(caller.tenant_id) not in response.text


@pytest.mark.asyncio
async def test_tenant_context_audit_binds_trusted_client_route_stage_and_correlation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caller = _caller()
    correlation_id = str(uuid4())
    exc = TenantContextMissingException(
        tenant_id=caller.tenant_id,
        agent_client_id=caller.agent_client_id,
        correlation_identity=correlation_id,
        route_template="/api/trust/v1/envelopes/query",
        method="POST",
    )
    captured: list[tuple[object, bool]] = []

    async def writer(session, request, *, access_log_only=False):
        _ = session
        captured.append((request, access_log_only))

    monkeypatch.setattr(
        "app.trust.tenant_security.record_trust_audit_event",
        writer,
    )

    class AuditSession:
        async def connection(self):
            return self

        async def execute(self, *args, **kwargs):
            return None

        async def commit(self):
            return None

    class AuditContext:
        async def __aenter__(self):
            return AuditSession()

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    await record_tenant_context_failure_durable(
        exc,
        audit_session_factory=AuditContext,
    )

    request, access_log_only = captured[0]
    assert access_log_only is True
    assert request.tenant_id == caller.tenant_id
    assert request.event_type == "scope_denial"
    assert request.reason_code is ReasonCode.TENANT_CONTEXT_MISSING
    assert request.idempotency_key == correlation_id
    assert request.evidence_refs_allowed is False
    assert "envelopes/query" in request.subject_type
    assert "post_auth_transaction_rls_assertion" in request.subject_type
    assert request.audience_id_hash.startswith("sha256:")


@pytest.mark.asyncio
async def test_tenant_context_audit_writer_failure_remains_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caller = _caller()
    exc = TenantContextMissingException(
        tenant_id=caller.tenant_id,
        agent_client_id=caller.agent_client_id,
        correlation_identity=str(uuid4()),
        route_template="/api/trust/v1/verify",
        method="POST",
    )

    async def broken_writer(*args, **kwargs):
        raise RuntimeError("database internals must not escape")

    monkeypatch.setattr(
        "app.trust.tenant_security.record_tenant_context_failure_durable",
        broken_writer,
    )
    response = await tenant_context_missing_exception_handler(SimpleNamespace(), exc)
    assert response.status_code == 503
    assert json.loads(response.body) == {
        "status": "unavailable",
        "reason_code": TENANT_CONTEXT_EXTERNAL_REASON,
    }
    assert "tenant-context audit persistence failed" in caplog.text.lower()


@pytest.mark.asyncio
async def test_client_visible_wire_verifies_through_published_jwks_and_mutation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _route_app()
    caller = _caller()
    registry = _registry()

    async def trusted() -> MachineCallerContext:
        return caller

    async def signing_registry() -> TrustKeyRegistry:
        return registry

    async def fake_build(*args, **kwargs):
        return SimpleNamespace(unsigned_payload=_unsigned_fixture())

    app.dependency_overrides[trust_api.get_machine_db_session] = (
        _fake_session_dependency
    )
    app.dependency_overrides[trust_api.require_envelope_read_tenant_context] = trusted
    app.dependency_overrides[trust_api.get_runtime_signing_registry] = signing_registry
    monkeypatch.setattr(
        trust_api,
        "build_unsigned_trust_envelope_with_audit",
        fake_build,
    )
    monkeypatch.setattr(
        trust_keys,
        "load_runtime_verification_registry",
        lambda: registry.public_only(),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        envelope_response = await client.get(
            f"/api/trust/v1/envelopes/match_verdict/urn:skeldir:match_verdict:{uuid4()}",
            headers=_headers(caller.tenant_id),
        )
        jwks_response = await client.get(
            "/api/trust/v1/keys/jwks",
            headers={"X-Correlation-ID": str(uuid4())},
        )

    envelope = envelope_response.json()
    public_registry = registry_from_public_jwks(jwks_response.json())
    assert envelope_response.status_code == jwks_response.status_code == 200
    assert (
        verify_trust_envelope(
            envelope, key_registry=public_registry
        ).verification_status
        == "verified"
    )
    mutated = dict(envelope)
    mutated["match_verdict_status"] = "unmatched"
    assert (
        verify_trust_envelope(mutated, key_registry=public_registry).verification_status
        == "rejected"
    )


@pytest.mark.asyncio
async def test_verify_projection_guard_covers_success_and_failure_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _route_app()
    caller = _caller()

    async def trusted() -> MachineCallerContext:
        return caller

    async def verification_registry() -> TrustKeyRegistry:
        return _registry().public_only()

    class UnsafeResult:
        def external_projection(self):
            return {
                "verification_status": "rejected",
                "tenant_id": str(caller.tenant_id),
            }

    app.dependency_overrides[trust_api.require_envelope_verify_tenant_context] = trusted
    app.dependency_overrides[trust_api.get_runtime_verification_registry] = (
        verification_registry
    )
    monkeypatch.setattr(
        trust_api, "verify_trust_envelope", lambda *a, **k: UnsafeResult()
    )

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/trust/v1/verify",
            headers=_headers(caller.tenant_id),
            json=_unsigned_fixture(),
        )

    assert response.status_code == 500
    assert str(caller.tenant_id) not in response.text


@pytest.mark.asyncio
async def test_fixed_window_boundary_burst_is_explicit_and_bounded() -> None:
    tenant_id = uuid4()
    client_id = uuid4()
    lock = asyncio.Lock()
    counts: dict[tuple[datetime, datetime], int] = {}

    class Session:
        async def execute(self, statement, params):
            key = (params["window_start"], params["window_end"])
            async with lock:
                counts[key] = counts.get(key, 0) + 1
                count = counts[key]

            class Result:
                def first(self):
                    return (count,)

            return Result()

        async def commit(self):
            return None

    limit = 10
    before = datetime(2026, 8, 2, 12, 0, 59, 999999, tzinfo=timezone.utc)
    after = datetime(2026, 8, 2, 12, 1, 0, 1, tzinfo=timezone.utc)

    async def attempt(at_time: datetime) -> bool:
        return await _check_rate_limit(
            Session(),
            tenant_id=tenant_id,
            agent_client_id=client_id,
            request_limit=limit,
            at_time=at_time,
        )

    results = await asyncio.gather(
        *(attempt(before) for _ in range(limit)),
        *(attempt(after) for _ in range(limit)),
    )
    assert sum(results) == 2 * limit
    assert sorted(counts.values()) == [limit, limit]


@pytest.mark.asyncio
async def test_rate_window_driver_parameters_are_aware_native_datetimes() -> None:
    captured: dict[str, object] = {}

    class Result:
        def first(self):
            return (1,)

    class Session:
        async def execute(self, statement, params):
            captured.update(params)
            return Result()

        async def commit(self):
            return None

    observed = datetime(2026, 8, 2, 12, 0, 30, tzinfo=timezone(timedelta(hours=-5)))
    assert await _check_rate_limit(
        Session(),
        tenant_id=uuid4(),
        agent_client_id=uuid4(),
        at_time=observed,
    )
    for key in ("window_start", "window_end"):
        value = captured[key]
        assert isinstance(value, datetime)
        assert value.tzinfo is not None and value.utcoffset() is not None
        assert value.utcoffset() == timedelta(0)


@pytest.mark.asyncio
@pytest.mark.parametrize("nonce", ["x" * 15, "x" * 257])
async def test_nonce_contract_rejects_out_of_range_before_hash_or_persistence(
    nonce: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _route_app()
    hash_calls = 0
    persistence_calls = 0

    def request_hash(*args, **kwargs):
        nonlocal hash_calls
        hash_calls += 1
        return "sha256:" + "0" * 64

    async def nonce_insert(*args, **kwargs):
        nonlocal persistence_calls
        persistence_calls += 1
        return True

    async def denial_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.trust.machine_auth._machine_request_identity_hash",
        request_hash,
    )
    monkeypatch.setattr(
        "app.trust.machine_auth._atomic_nonce_insert",
        nonce_insert,
    )
    monkeypatch.setattr(
        "app.trust.machine_auth._write_denial_audit",
        denial_audit,
    )
    app.dependency_overrides[trust_api.get_machine_db_session] = (
        _fake_session_dependency
    )
    app.dependency_overrides[trust_api.get_runtime_signing_registry] = (
        lambda: _registry()
    )
    tenant_id = uuid4()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/api/trust/v1/envelopes/match_verdict/urn:skeldir:match_verdict:{uuid4()}",
            headers=_headers(tenant_id, nonce=nonce),
        )

    assert response.status_code in {401, 422}
    assert hash_calls == 0
    assert persistence_calls == 0


def test_runtime_openapi_nonce_contract_matches_canonical_16_to_256() -> None:
    document = _route_app().openapi()
    for method, path in (
        ("get", "/api/trust/v1/envelopes/{subject_type}/{subject_ref}"),
        ("post", "/api/trust/v1/envelopes/query"),
        ("post", "/api/trust/v1/verify"),
    ):
        operation = document["paths"][path][method]
        nonce = next(
            parameter
            for parameter in operation["parameters"]
            if parameter["name"] == "X-Trust-Nonce"
        )
        assert nonce["schema"]["minLength"] == 16
        assert nonce["schema"]["maxLength"] == 256
