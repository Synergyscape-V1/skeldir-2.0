"""B2.5-P10 adversarial Trust API surface proofs."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import trust_api, trust_keys
from app.core.secrets import get_database_url, get_migration_database_url
from app.db.dsn import to_asyncpg_postgres_dsn
from app.trust.key_registry import TrustKeyRegistry, TrustSigningKey
from app.trust.canonicalization import (
    canonicalize_envelope_payload,
    canonicalize_signature_material,
)
from app.trust.signing import encode_ed25519_signature, prepare_payload_for_signing
from app.trust.audit import (
    TrustAuditRequest,
    record_trust_audit_event,
)
from app.trust.machine_auth import MachineCallerContext, _check_rate_limit
from app.trust.machine_identity import AgentScope
from app.trust.refusal import tagged_sha256, tenant_hash
from app.trust.verification import verify_trust_envelope
from app.trust.builder import build_unsigned_trust_envelope as production_builder
from app.trust.source_adapters import MatchVerdictSource


ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / "contracts/trust-api/examples"
P10_RUNTIME_PATH = ROOT / "backend/app/api/trust_api.py"
P9_AUTH_PATH = ROOT / "backend/app/trust/machine_auth.py"


def _utc(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _registry() -> TrustKeyRegistry:
    private_key = Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"b25-p10-route-test-key").digest()
    )
    key = TrustSigningKey(
        kid="kid:b25-p10-route-test",
        algorithm="ed25519",
        public_key=private_key.public_key(),
        private_key=private_key,
        state="active",
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    return TrustKeyRegistry((key,))


async def _async_registry() -> TrustKeyRegistry:
    return _registry()


def _unsigned_fixture() -> dict[str, object]:
    payload = json.loads(
        (EXAMPLES / "deterministic_only_verified.json").read_text(encoding="utf-8")
    )
    now = datetime.now(timezone.utc)
    payload["created_at"] = _utc(now)
    payload["valid_until"] = _utc(now + timedelta(days=1))
    return payload


def _cryptographically_sign_fixture(
    payload: dict[str, object], registry: TrustKeyRegistry
) -> dict[str, object]:
    key = registry.active_signing_key()
    prepared = prepare_payload_for_signing(
        payload,
        signing_key_id=key.kid,
        signing_algorithm=key.algorithm,
    )
    assert key.private_key is not None
    prepared["signature"] = encode_ed25519_signature(
        key.private_key.sign(canonicalize_signature_material(prepared))
    )
    canonicalize_envelope_payload(prepared)
    return prepared


def _caller() -> MachineCallerContext:
    return MachineCallerContext(
        agent_client_id=uuid4(),
        tenant_id=uuid4(),
        audience="b25-p10-test-agent",
        scopes=frozenset({AgentScope.ENVELOPE_READ, AgentScope.ENVELOPE_VERIFY}),
        nonce_value="p10-test-nonce",
        request_identity_hash="sha256:" + "1" * 64,
    )


def _headers(tenant_id: object | None = None) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-machine-token-value",
        "X-Tenant-ID": str(tenant_id or uuid4()),
        "X-Trust-Nonce": "nonce-0123456789abcdef",
        "X-Correlation-ID": str(uuid4()),
        "X-Idempotency-Key": "p10-test-idempotency",
    }


def _route_app() -> FastAPI:
    app = FastAPI()
    app.include_router(trust_api.router, prefix="/api")
    return app


@pytest.mark.asyncio
async def test_authorized_happy_path_returns_signed_verifiable_safe_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _route_app()
    caller = _caller()
    registry = _registry()

    async def fake_session():
        yield object()

    async def fake_scope() -> MachineCallerContext:
        return caller

    async def fake_build(*args, **kwargs):
        return SimpleNamespace(authorized_envelope=_unsigned_fixture())

    app.dependency_overrides[trust_api.get_machine_db_session] = fake_session
    app.dependency_overrides[trust_api.require_envelope_read_tenant_context] = (
        fake_scope
    )

    async def fake_registry() -> TrustKeyRegistry:
        return registry

    app.dependency_overrides[trust_api.get_runtime_signing_registry] = fake_registry
    monkeypatch.setattr(
        trust_api,
        "build_unsigned_trust_envelope_with_audit",
        fake_build,
    )
    monkeypatch.setattr(
        trust_api,
        "sign_trust_envelope",
        lambda payload, *, key_registry: _cryptographically_sign_fixture(
            payload, key_registry
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/trust/v1/envelopes/match_verdict/"
            "urn:skeldir:match_verdict:00000000-0000-0000-0000-000000000001",
            headers=_headers(caller.tenant_id),
        )

    assert response.status_code == 200, response.text
    envelope = response.json()
    assert envelope["signature"].startswith("ed25519:")
    assert envelope["semantic_truth_hash"].startswith("sha256:")
    assert envelope["audit_ref"].startswith("urn:skeldir:audit:")
    assert envelope["policy_action_authority"]["policy_state"] == "read_only"
    assert "tenant_id" not in envelope
    assert str(caller.tenant_id) not in response.text
    result = verify_trust_envelope(
        envelope,
        key_registry=registry.public_only(),
    )
    assert result.verification_status == "verified", result.reason_code


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {
            "subject_types": ["match_verdict"],
            "subject_refs": [
                f"urn:skeldir:match_verdict:{index}" for index in range(51)
            ],
        },
        {
            "subject_types": ["match_verdict"],
            "subject_refs": ["urn:skeldir:match_verdict:*"],
        },
        {
            "subject_types": ["match_verdict"],
            "subject_refs": ["urn:skeldir:match_verdict:one"],
            "where": {"or": [{"anything": "unbounded"}]},
        },
        {
            "subject_types": ["match_verdict"],
            "subject_refs": ["urn:skeldir:match_verdict:one"],
            "created_at_after": "2026-01-01T00:00:00Z",
            "created_at_before": "2026-02-01T00:00:01Z",
        },
        {
            "subject_types": ["match_verdict"],
            "subject_refs": ["urn:skeldir:match_verdict:one"],
            "policy_action_authority": {"policy_state": "approval_required"},
        },
        {
            "subject_types": ["match_verdict"],
            "subject_refs": ["urn:skeldir:match_verdict:one"],
            "schema_version": "trust-envelope-schema-v0",
        },
        {
            "subject_types": ["match_verdict"],
            "subject_refs": ["x" * (64 * 1024)],
        },
        {
            "subject_types": ["match_verdict", "match_verdict"],
            "subject_refs": ["urn:skeldir:match_verdict:one"],
        },
    ],
)
async def test_unbounded_or_authority_elevating_query_rejected_before_db(
    payload: dict[str, object],
) -> None:
    app = _route_app()
    db_touches = 0

    async def touched_session():
        nonlocal db_touches
        db_touches += 1
        yield object()

    app.dependency_overrides[trust_api.get_machine_db_session] = touched_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/trust/v1/envelopes/query",
            headers=_headers(),
            json=payload,
        )

    expected_status = 413 if payload["subject_refs"] == ["x" * (64 * 1024)] else 422
    assert response.status_code == expected_status, response.text
    assert db_touches == 0


def test_query_contract_accepts_only_bounded_exact_inputs() -> None:
    after = datetime(2026, 7, 1, tzinfo=timezone.utc)
    query = trust_api.TrustQueryRequest(
        subject_types=[trust_api.TrustSubjectType.MATCH_VERDICT],
        subject_refs=["urn:skeldir:match_verdict:exact-reference"],
        created_at_after=after,
        created_at_before=after + timedelta(days=30),
    )
    assert len(query.subject_types) == 1
    assert len(query.subject_refs) == 1
    operation = _route_app().openapi()["paths"]["/api/trust/v1/envelopes/query"]["post"]
    assert operation["requestBody"]["required"] is True
    rendered = json.dumps(operation["requestBody"], sort_keys=True)
    assert '"maxItems": 50' in rendered
    assert '"additionalProperties": false' in rendered


@pytest.mark.asyncio
async def test_verify_oracle_rejects_unauthenticated_before_crypto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _route_app()
    crypto_calls = 0

    async def fake_session():
        yield object()

    def counted_verify(*args, **kwargs):
        nonlocal crypto_calls
        crypto_calls += 1
        raise AssertionError("crypto must not execute")

    app.dependency_overrides[trust_api.get_machine_db_session] = fake_session
    app.dependency_overrides[trust_api.get_runtime_verification_registry] = (
        _async_registry
    )
    monkeypatch.setattr(trust_api, "verify_trust_envelope", counted_verify)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/trust/v1/verify",
            headers={
                "X-Tenant-ID": str(uuid4()),
                "X-Correlation-ID": str(uuid4()),
                "X-Trust-Nonce": "nonce-0123456789abcdef",
            },
            json=_unsigned_fixture(),
        )

    assert response.status_code == 401
    assert crypto_calls == 0


@pytest.mark.asyncio
async def test_verify_oracle_rate_limit_fails_before_crypto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _route_app()
    crypto_calls = 0

    async def rate_limited() -> MachineCallerContext:
        raise HTTPException(status_code=429, detail="Authentication failed.")

    def counted_verify(*args, **kwargs):
        nonlocal crypto_calls
        crypto_calls += 1
        raise AssertionError("crypto must not execute")

    app.dependency_overrides[trust_api.require_envelope_verify_scope] = rate_limited
    app.dependency_overrides[trust_api.get_runtime_verification_registry] = (
        _async_registry
    )
    monkeypatch.setattr(trust_api, "verify_trust_envelope", counted_verify)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/trust/v1/verify",
            headers=_headers(),
            json=_unsigned_fixture(),
        )

    assert response.status_code == 429
    assert crypto_calls == 0


def test_rate_limit_atomic_storm_enforces_exact_limit_without_deadlock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 7, 20, 15, 0, 30, tzinfo=timezone.utc)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz is not None else fixed_now.replace(tzinfo=None)

    monkeypatch.setattr("app.trust.machine_auth.datetime", FrozenDateTime)
    lock = threading.Lock()
    counts: dict[tuple[object, ...], int] = {}
    windows: set[tuple[str, str]] = set()
    statements: list[str] = []

    class Session:
        async def execute(self, statement, params=None):
            sql = str(statement)
            statements.append(sql)
            assert params is not None
            key = (
                params["tenant_id"],
                params["agent_client_id"],
                params["window_start"],
                params["window_end"],
            )
            with lock:
                counts[key] = counts.get(key, 0) + 1
                count = counts[key]
                windows.add((params["window_start"], params["window_end"]))

            class Result:
                def first(self):
                    return (count,)

            return Result()

        async def commit(self):
            return None

    tenant_id = uuid4()
    client_id = uuid4()

    def attempt() -> bool:
        return asyncio.run(
            _check_rate_limit(
                Session(),
                tenant_id=tenant_id,
                agent_client_id=client_id,
                request_limit=10,
            )
        )

    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(attempt) for _ in range(50)]
        results = [future.result(timeout=5) for future in as_completed(futures)]

    assert sum(results) == 10
    assert len(windows) == 1
    assert all("ON CONFLICT" in statement for statement in statements)
    assert all("RETURNING request_count" in statement for statement in statements)
    assert all("FOR UPDATE" not in statement.upper() for statement in statements)


def test_p10_runtime_has_no_compute_llm_or_mutation_imports() -> None:
    source = P10_RUNTIME_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "app.llm",
        "app.tasks",
        "app.bayesian",
        "celery",
        "delay(",
        "apply_async(",
    ):
        assert forbidden not in source
    assert "TrustEnvelopeBuildRequest" in source
    assert "build_unsigned_trust_envelope_with_audit" in source
    assert "sign_trust_envelope" in source
    assert '"tenant_id" in payload' in source


def test_rate_limit_path_has_single_atomic_statement_and_stable_bucket() -> None:
    source = P9_AUTH_PATH.read_text(encoding="utf-8")
    section = source.split("async def _check_rate_limit", 1)[1].split(
        "def _machine_request_identity_hash", 1
    )[0]
    assert "ON CONFLICT" in section
    assert "RETURNING request_count" in section
    assert "bucket_epoch" in section
    assert "FOR UPDATE" not in section.upper()
    assert section.count("db_session.execute") == 1


@pytest.mark.asyncio
async def test_read_only_snapshot_allows_only_trust_access_log_write() -> None:
    statements: list[str] = []

    class Mappings:
        def first(self):
            return {
                "audit_ref": "urn:skeldir:audit:issuance:p10",
                "audit_hash": tagged_sha256("audit"),
                "idempotency_key_hash": tagged_sha256("idempotency"),
                "request_identity_hash": tagged_sha256("request"),
                "event_type": "issuance",
                "status": "success",
                "replayed": False,
            }

    class Result:
        def mappings(self):
            return Mappings()

    class Session:
        async def execute(self, statement, params):
            statements.append(str(statement))
            return Result()

    tenant_id = uuid4()
    request = TrustAuditRequest(
        tenant_id=tenant_id,
        event_type="issuance",
        status="success",
        idempotency_key="p10-read-only-snapshot",
        subject_type="match_verdict",
        subject_ref_hash=tagged_sha256("subject"),
        tenant_id_hash=tenant_hash(tenant_id),
        policy_state="read_only",
        reason_code=None,
        created_at=datetime.now(timezone.utc),
        created_at_source="request_issuance_context",
        semantic_truth_hash=tagged_sha256("semantic"),
        envelope_hash=tagged_sha256("envelope"),
    )
    await record_trust_audit_event(Session(), request, access_log_only=True)

    writes = [statement for statement in statements if "INSERT INTO" in statement]
    assert len(writes) == 1
    assert "INSERT INTO public.trust_access_log" in writes[0]
    assert "trust_envelope_issuance_log" not in "\n".join(statements)
    assert "trust_scope_denial_events" not in "\n".join(statements)
    assert "trust_replay_events" not in "\n".join(statements)
    assert "access_log_only=True" in P10_RUNTIME_PATH.read_text(encoding="utf-8")


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P10_POSTGRES_PROOF") != "1",
    reason="B2.5-P10 PostgreSQL snapshot proof is opt-in for local runs",
)
async def test_postgres_before_after_snapshot_only_access_log_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    migration_engine = create_async_engine(
        to_asyncpg_postgres_dsn(get_migration_database_url())
    )
    runtime_engine = create_async_engine(to_asyncpg_postgres_dsn(get_database_url()))
    runtime_sessions = async_sessionmaker(runtime_engine, expire_on_commit=False)
    tracked_tables = (
        "trust_access_log",
        "trust_envelope_issuance_log",
        "trust_scope_denial_events",
        "trust_replay_events",
        "trust_request_nonces",
        "trust_rate_limit_state",
        "bayesian_model_fits",
        "bayesian_artifacts",
        "b23_match_task_dispatches",
    )

    async def snapshot() -> dict[str, int]:
        counts: dict[str, int] = {}
        async with migration_engine.connect() as connection:
            await connection.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            for table in tracked_tables:
                value = await connection.scalar(
                    text(
                        f"SELECT count(*) FROM public.{table} WHERE tenant_id = :tenant_id"
                    ),
                    {"tenant_id": str(tenant_id)},
                )
                counts[table] = int(value or 0)
        return counts

    try:
        async with migration_engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO public.tenants (
                        id, name, api_key_hash, notification_email
                    ) VALUES (
                        :tenant_id, :name, :api_key_hash, :notification_email
                    )
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "name": f"B25 P10 snapshot tenant {tenant_id}",
                    "api_key_hash": f"b25-p10-{tenant_id}",
                    "notification_email": "b25-p10@example.invalid",
                },
            )

        async def fake_builder(_session, request, **_kwargs):
            verdict_id = request.subject_ref.rsplit(":", 1)[1]
            observed = request.request_context["created_at"] - timedelta(seconds=1)
            source = MatchVerdictSource(
                id=UUID(verdict_id),
                tenant_id=request.tenant_id,
                webhook_ingress_identity_id=None,
                provider="shopify",
                canonical_commerce_reference="p10-snapshot-order",
                provider_native_event_reference="p10-snapshot-event",
                provider_native_commerce_reference="p10-snapshot-order",
                status="matched_confirmed",
                match_quality="high",
                canonical_net_verified_amount_minor=12345,
                currency_code="USD",
                last_transition_at=observed,
                created_at=observed,
                updated_at=observed,
            )
            return await production_builder(object(), request, source=source)

        import app.trust.audit as audit_module

        monkeypatch.setattr(
            audit_module, "AsyncSessionLocal", runtime_sessions, raising=False
        )
        monkeypatch.setattr(audit_module, "build_unsigned_trust_envelope", fake_builder)
        monkeypatch.setattr("app.db.session.AsyncSessionLocal", runtime_sessions)

        before = await snapshot()
        caller = _caller()
        caller = MachineCallerContext(
            agent_client_id=caller.agent_client_id,
            tenant_id=tenant_id,
            audience=caller.audience,
            scopes=caller.scopes,
            nonce_value=caller.nonce_value,
            request_identity_hash=caller.request_identity_hash,
        )
        result = await trust_api._issue_signed_envelope(
            session=object(),
            caller=caller,
            subject_type="match_verdict",
            subject_ref=f"urn:skeldir:match_verdict:{uuid4()}",
            idempotency_key=f"p10-postgres-snapshot-{uuid4()}",
            key_registry=_registry(),
            issued_at=datetime.now(timezone.utc),
        )
        after = await snapshot()

        assert result is not None
        assert result["signature"].startswith("ed25519:")
        assert after["trust_access_log"] == before["trust_access_log"] + 1
        for table in tracked_tables[1:]:
            assert after[table] == before[table], table
    finally:
        await runtime_engine.dispose()
        await migration_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P10_POSTGRES_PROOF") != "1",
    reason="B2.5-P10 PostgreSQL rate-limit proof is opt-in for local runs",
)
async def test_postgres_rate_limit_storm_is_atomic_and_exact() -> None:
    tenant_id = uuid4()
    agent_client_id = uuid4()
    migration_engine = create_async_engine(
        to_asyncpg_postgres_dsn(get_migration_database_url())
    )
    runtime_engine = create_async_engine(
        to_asyncpg_postgres_dsn(get_database_url()),
        pool_size=20,
        max_overflow=30,
    )
    runtime_sessions = async_sessionmaker(runtime_engine, expire_on_commit=False)
    try:
        async with migration_engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO public.tenants (
                        id, name, api_key_hash, notification_email
                    ) VALUES (
                        :tenant_id, :name, :api_key_hash, :notification_email
                    )
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "name": f"B25 P10 rate tenant {tenant_id}",
                    "api_key_hash": f"b25-p10-rate-{tenant_id}",
                    "notification_email": "b25-p10-rate@example.invalid",
                },
            )
            await connection.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO public.agent_clients (
                        id, tenant_id, client_name, client_display_hash,
                        audience, status
                    ) VALUES (
                        :agent_client_id, :tenant_id, :client_name,
                        :client_display_hash, :audience, 'active'
                    )
                    """
                ),
                {
                    "agent_client_id": str(agent_client_id),
                    "tenant_id": str(tenant_id),
                    "client_name": f"p10-rate-{agent_client_id}",
                    "client_display_hash": "sha256:" + "a" * 64,
                    "audience": "b25-p10-rate-proof",
                },
            )

        async def attempt() -> bool:
            async with runtime_sessions() as session:
                await session.execute(
                    text(
                        "SELECT set_config('app.current_tenant_id', :tenant_id, true)"
                    ),
                    {"tenant_id": str(tenant_id)},
                )
                return await _check_rate_limit(
                    session,
                    tenant_id=tenant_id,
                    agent_client_id=agent_client_id,
                    request_limit=10,
                )

        results = await asyncio.wait_for(
            asyncio.gather(*(attempt() for _ in range(50))),
            timeout=20,
        )
        assert sum(results) == 10

        async with migration_engine.connect() as connection:
            await connection.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            rows = (
                await connection.execute(
                    text(
                        """
                        SELECT request_count
                        FROM public.trust_rate_limit_state
                        WHERE tenant_id = :tenant_id
                          AND agent_client_id = :agent_client_id
                        """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "agent_client_id": str(agent_client_id),
                    },
                )
            ).all()
        assert rows == [(50,)]
    finally:
        await runtime_engine.dispose()
        await migration_engine.dispose()


def test_raw_tenant_and_float_money_response_guards_fire() -> None:
    with pytest.raises(RuntimeError, match="raw_tenant_id_response_forbidden"):
        trust_api._assert_external_payload_safe({"nested": {"tenant_id": str(uuid4())}})
    with pytest.raises(RuntimeError, match="floating_point_money_response_forbidden"):
        trust_api._assert_external_payload_safe({"verified_revenue_minor": 12.34})


def test_runtime_private_seed_never_appears_in_public_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = hashlib.sha256(b"b25-p10-runtime-secret").digest()
    encoded = base64.urlsafe_b64encode(seed).rstrip(b"=").decode("ascii")
    monkeypatch.setenv("SKELDIR_TRUST_SIGNING_KEY_SEED_B64URL", encoded)
    monkeypatch.setenv("SKELDIR_TRUST_SIGNING_KEY_ID", "kid:b25-p10-runtime")
    monkeypatch.setenv("SKELDIR_TRUST_SIGNING_KEY_VALID_FROM", "2026-01-01T00:00:00Z")
    monkeypatch.delenv("SKELDIR_TRUST_PUBLIC_JWKS_JSON", raising=False)

    registry = trust_api.load_runtime_verification_registry()
    jwks = registry.jwks()
    rendered = json.dumps(jwks, sort_keys=True)
    assert encoded not in rendered
    assert "private" not in rendered.lower()
    assert "seed" not in rendered.lower()
    assert all(key.private_key is None for key in registry.keys)


def test_main_mounts_all_p10_routes_and_preserves_public_jwks() -> None:
    main_source = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    route_source = P10_RUNTIME_PATH.read_text(encoding="utf-8")
    assert "app.include_router(trust_api.router" in main_source
    for path in (
        '"/trust/v1/envelopes/{subject_type}/{subject_ref}"',
        '"/trust/v1/envelopes/query"',
        '"/trust/v1/verify"',
    ):
        assert path in route_source
    keys_source = (ROOT / "backend/app/api/trust_keys.py").read_text(encoding="utf-8")
    assert '"/trust/v1/keys/jwks"' in keys_source
    assert 'openapi_extra={"security": []}' in keys_source


def test_runtime_openapi_declares_machine_bearer_default_deny() -> None:
    app = FastAPI()
    app.include_router(trust_api.router, prefix="/api")
    app.include_router(trust_keys.router, prefix="/api")
    document = app.openapi()

    assert document["components"]["securitySchemes"]["MachineBearer"] == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "opaque-machine-token",
    }
    for method, path in (
        ("get", "/api/trust/v1/envelopes/{subject_type}/{subject_ref}"),
        ("post", "/api/trust/v1/envelopes/query"),
        ("post", "/api/trust/v1/verify"),
    ):
        assert document["paths"][path][method]["security"] == [{"MachineBearer": []}]
    assert document["paths"]["/api/trust/v1/keys/jwks"]["get"]["security"] == []
