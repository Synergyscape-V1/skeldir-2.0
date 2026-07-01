"""B2.5-P7 provenance and trust-audit substrate tests."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.secrets import get_database_url, get_migration_database_url
from app.db.dsn import to_asyncpg_postgres_dsn
from app.trust.audit import (
    TrustAuditError,
    TrustAuditRequest,
    attach_audit_to_unsigned_payload,
    build_audit_record,
    build_unsigned_trust_envelope_with_audit,
    record_trust_audit_event,
    record_trust_audit_event_durable,
)
from app.trust.audit_hash import compute_audit_hash
from app.trust.builder import TrustEnvelopeBuildRequest
from app.trust.canonicalization import canonicalize_envelope_payload
from app.trust.provenance import (
    REQUIRED_P7_PROVENANCE_SOURCE_CLASSES,
    build_match_verdict_provenance_chain,
    canonicalize_provenance_chain,
    required_source_class_names,
)
from app.trust.reason_codes import ReasonCode
from app.trust.refusal import tagged_sha256, tenant_hash
from app.trust.source_adapters import MatchVerdictSource


ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = (
    ROOT
    / "alembic/versions/007_skeldir_foundation"
    / "202607011200_b25_p7_trust_audit_provenance.py"
)


class _FakeMappings:
    def __init__(self, row: dict[str, object] | None) -> None:
        self._row = row

    def first(self) -> dict[str, object] | None:
        return self._row


class _FakeResult:
    def __init__(self, row: dict[str, object] | None = None) -> None:
        self._row = row

    def mappings(self) -> _FakeMappings:
        return _FakeMappings(self._row)


class FakeTrustSession:
    def __init__(self, row: dict[str, object] | None) -> None:
        self.row = row
        self.statements: list[str] = []
        self.params: list[dict[str, object]] = []
        self.access_seen: set[tuple[str, str]] = set()

    async def execute(
        self, statement: object, params: dict[str, object]
    ) -> _FakeResult:
        sql = str(statement)
        self.statements.append(sql)
        self.params.append(dict(params))
        if "FROM public.b23_match_verdicts" in sql:
            if str(params["tenant_id"]) != str(
                self.row.get("tenant_id") if self.row else ""
            ):
                return _FakeResult(None)
            return _FakeResult(self.row)
        if "INSERT INTO public.trust_access_log" in sql:
            key = (str(params["event_type"]), str(params["idempotency_key_hash"]))
            replayed = key in self.access_seen
            self.access_seen.add(key)
            return _FakeResult(
                {
                    "audit_ref": params["audit_ref"],
                    "audit_hash": params["audit_hash"],
                    "idempotency_key_hash": params["idempotency_key_hash"],
                    "request_identity_hash": params["request_identity_hash"],
                    "event_type": params["event_type"],
                    "status": params["status"],
                    "replayed": replayed,
                }
            )
        return _FakeResult(None)


class FakeAuditSessionFactory:
    def __init__(self, session: FakeTrustSession) -> None:
        self.session = session

    def __call__(self) -> "FakeAuditSessionFactory":
        return self

    async def __aenter__(self) -> FakeTrustSession:
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def _row(
    *,
    tenant_id: UUID | None = None,
    verdict_id: UUID | None = None,
    reference: str = "order-1001",
) -> dict[str, object]:
    now = datetime(2026, 7, 1, 16, 0, 0, tzinfo=timezone.utc)
    return {
        "id": verdict_id or uuid4(),
        "tenant_id": tenant_id or uuid4(),
        "webhook_ingress_identity_id": uuid4(),
        "provider": "shopify",
        "canonical_commerce_reference": reference,
        "provider_native_event_reference": "evt_1001",
        "provider_native_commerce_reference": "order-1001",
        "status": "matched_confirmed",
        "match_quality": "high",
        "canonical_net_verified_amount_minor": 12345,
        "currency_code": "USD",
        "last_transition_at": now,
        "created_at": now,
        "updated_at": now,
    }


def _source(row: dict[str, object]) -> MatchVerdictSource:
    return MatchVerdictSource(
        id=UUID(str(row["id"])),
        tenant_id=UUID(str(row["tenant_id"])),
        webhook_ingress_identity_id=UUID(str(row["webhook_ingress_identity_id"])),
        provider=str(row["provider"]),
        canonical_commerce_reference=str(row["canonical_commerce_reference"]),
        provider_native_event_reference=str(row["provider_native_event_reference"]),
        provider_native_commerce_reference=str(
            row["provider_native_commerce_reference"]
        ),
        status=str(row["status"]),
        match_quality=str(row["match_quality"]),
        canonical_net_verified_amount_minor=row["canonical_net_verified_amount_minor"],
        currency_code=str(row["currency_code"]),
        last_transition_at=row["last_transition_at"],  # type: ignore[arg-type]
        created_at=row["created_at"],  # type: ignore[arg-type]
        updated_at=row["updated_at"],  # type: ignore[arg-type]
    )


def _request(tenant_id: UUID, verdict_id: UUID) -> TrustEnvelopeBuildRequest:
    return TrustEnvelopeBuildRequest(
        tenant_id=tenant_id,
        subject_type="match_verdict",
        subject_ref=f"urn:skeldir:match_verdict:{verdict_id}",
        request_context={
            "created_at": datetime(2026, 7, 1, 16, 0, 1, tzinfo=timezone.utc),
            "valid_until": datetime(2026, 7, 2, 16, 0, 1, tzinfo=timezone.utc),
            "audience_id": "p7-test-agent",
        },
    )


def test_required_source_registry_and_canonical_order_are_stable() -> None:
    row = _row()
    chain = build_match_verdict_provenance_chain(
        source=_source(row),
        display_data={
            "raw_text_sha256": None,
            "display_transform": "none",
            "text_disposition_version": "text-disposition-v1",
        },
        money_authority_projection={
            "status": "accepted_authoritative_minor_units",
            "source_domain": "b23_match_verdicts",
        },
        reason_code=None,
    )

    assert len(REQUIRED_P7_PROVENANCE_SOURCE_CLASSES) == 14
    assert "audit_access_record_ref" in required_source_class_names()
    assert "money_authority_source" in required_source_class_names()
    assert canonicalize_provenance_chain(list(reversed(chain))) == chain
    assert {entry["provenance_type"] for entry in chain} >= {
        "webhook_signature",
        "provider_native_reference",
        "match_verdict",
        "policy_decision",
        "text_disposition",
        "money_authority",
        "reason_code_decision",
        "explicit_unavailable",
    }


@pytest.mark.asyncio
async def test_successful_issuance_writes_audit_and_attaches_ref_hash() -> None:
    tenant_id = uuid4()
    verdict_id = uuid4()
    session = FakeTrustSession(_row(tenant_id=tenant_id, verdict_id=verdict_id))

    result = await build_unsigned_trust_envelope_with_audit(
        session,
        _request(tenant_id, verdict_id),
        idempotency_key="p7-success-key",
        audit_session_factory=FakeAuditSessionFactory(session),
    )

    assert result.unsigned_payload is not None
    payload = result.unsigned_payload
    canonicalize_envelope_payload(payload)
    assert payload["audit_ref"].startswith("urn:skeldir:audit:issuance:")
    assert payload["audit_hash"].startswith("sha256:")
    assert payload["audit_ref"] == result.audit_record.audit_ref
    assert {entry["provenance_type"] for entry in payload["provenance_chain"]} >= {
        "audit_access_record",
        "audit_hash",
    }
    assert str(tenant_id) not in str(payload)
    assert "INSERT INTO public.trust_access_log" in "\n".join(session.statements)
    assert "INSERT INTO public.trust_envelope_issuance_log" in "\n".join(
        session.statements
    )


@pytest.mark.asyncio
async def test_idempotent_retry_reuses_audit_identity_without_duplicate_conflict() -> (
    None
):
    tenant_id = uuid4()
    verdict_id = uuid4()
    session = FakeTrustSession(_row(tenant_id=tenant_id, verdict_id=verdict_id))
    request = _request(tenant_id, verdict_id)

    first = await build_unsigned_trust_envelope_with_audit(
        session,
        request,
        idempotency_key="same-key",
        audit_session_factory=FakeAuditSessionFactory(session),
    )
    second = await build_unsigned_trust_envelope_with_audit(
        session,
        request,
        idempotency_key="same-key",
        audit_session_factory=FakeAuditSessionFactory(session),
    )

    assert second.audit_record.replayed is True
    assert first.audit_record.audit_ref == second.audit_record.audit_ref
    assert first.audit_record.audit_hash == second.audit_record.audit_hash


@pytest.mark.asyncio
async def test_scope_denial_audit_suppresses_subject_evidence_refs() -> None:
    tenant_id = uuid4()
    request = TrustAuditRequest(
        tenant_id=tenant_id,
        event_type="scope_denial",
        status="refused",
        idempotency_key="scope-denied",
        subject_type="match_verdict",
        subject_ref_hash=tagged_sha256("subject"),
        tenant_id_hash=tenant_hash(tenant_id),
        policy_state="read_only",
        reason_code=ReasonCode.SCOPE_DENIED,
        evidence_refs_allowed=False,
        created_at=datetime(2026, 7, 1, 16, 0, 0, tzinfo=timezone.utc),
    )
    session = FakeTrustSession(None)

    record = await record_trust_audit_event(session, request)

    assert record.audit_ref.startswith("urn:skeldir:audit:scope_denial:")
    joined = "\n".join(session.statements)
    assert "INSERT INTO public.trust_scope_denial_events" in joined
    assert "subject_ref_hash,\n                status" in joined
    assert "\n                NULL,\n                :status" in joined
    assert all(
        params.get("subject_ref_hash") is None
        for params in session.params
        if params.get("event_type") == "scope_denial"
    )


def test_audit_hash_is_canonical_and_semantic_mutations_change_it() -> None:
    material_a = {
        "status": "success",
        "audit_ref": "urn:skeldir:audit:issuance:abc",
        "subject_ref_hash": tagged_sha256("subject"),
    }
    material_b = {
        "subject_ref_hash": tagged_sha256("subject"),
        "audit_ref": "urn:skeldir:audit:issuance:abc",
        "status": "success",
    }
    material_c = {**material_a, "status": "refused"}

    assert compute_audit_hash(material_a) == compute_audit_hash(material_b)
    assert compute_audit_hash(material_a) != compute_audit_hash(material_c)


@pytest.mark.asyncio
async def test_attach_audit_recomputes_payload_hash_inputs() -> None:
    tenant_id = uuid4()
    verdict_id = uuid4()
    session = FakeTrustSession(_row(tenant_id=tenant_id, verdict_id=verdict_id))
    build = await async_build(session, _request(tenant_id, verdict_id))
    assert build.unsigned_payload is not None
    audit_request = TrustAuditRequest(
        tenant_id=tenant_id,
        event_type="issuance",
        status="success",
        idempotency_key="manual-attach",
        subject_type="match_verdict",
        subject_ref_hash=str(build.unsigned_payload["subject_ref_hash"]),
        tenant_id_hash=str(build.unsigned_payload["tenant_id_hash"]),
        policy_state="read_only",
        reason_code=None,
        semantic_truth_hash=str(build.unsigned_payload["semantic_truth_hash"]),
        created_at=datetime(2026, 7, 1, 16, 0, 0, tzinfo=timezone.utc),
    )
    record = build_audit_record(audit_request)

    payload = attach_audit_to_unsigned_payload(
        build.unsigned_payload,
        audit_record=record,
        observed_at="2026-07-01T16:00:01Z",
    )

    canonicalize_envelope_payload(payload)
    assert payload["audit_ref"] == record.audit_ref
    assert payload["signature"] == "p5-unsigned-placeholder-signature"


async def async_build(session: FakeTrustSession, request: TrustEnvelopeBuildRequest):
    from app.trust.builder import build_unsigned_trust_envelope

    return await build_unsigned_trust_envelope(session, request)


def test_migration_declares_force_rls_and_idempotency_constraints() -> None:
    migration = MIGRATION_PATH.read_text(encoding="utf-8")
    for table in (
        "trust_access_log",
        "trust_envelope_issuance_log",
        "trust_replay_events",
        "trust_scope_denial_events",
    ):
        assert f"CREATE TABLE public.{table}" in migration
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in migration
        assert f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY" in migration
        assert f"tenant_isolation_policy_{table}" in migration
    assert "current_setting('app.current_tenant_id', true)::uuid" in migration
    assert "uq_trust_access_log_idempotency" in migration
    assert "uq_trust_issuance_idempotency" in migration
    assert "ck_trust_scope_denial_no_evidence_leak" in migration


def test_trust_audit_request_rejects_live_clock_default_gap() -> None:
    tenant_id = uuid4()
    with pytest.raises(TrustAuditError, match="audit_created_at_required"):
        TrustAuditRequest(  # type: ignore[arg-type, call-arg]
            tenant_id=tenant_id,
            event_type="issuance",
            status="success",
            idempotency_key="missing-created-at",
            subject_type="match_verdict",
            subject_ref_hash=tagged_sha256("subject"),
            tenant_id_hash=tenant_hash(tenant_id),
            policy_state="read_only",
            reason_code=None,
            created_at=None,
        )

    with pytest.raises(TrustAuditError, match="audit_created_at_timezone_required"):
        TrustAuditRequest(
            tenant_id=tenant_id,
            event_type="issuance",
            status="success",
            idempotency_key="naive-created-at",
            subject_type="match_verdict",
            subject_ref_hash=tagged_sha256("subject"),
            tenant_id_hash=tenant_hash(tenant_id),
            policy_state="read_only",
            reason_code=None,
            created_at=datetime(2026, 7, 1, 16, 0, 0),
        )


@pytest.mark.asyncio
async def test_durable_audit_writer_uses_dedicated_session_factory() -> None:
    tenant_id = uuid4()
    session = FakeTrustSession(None)
    request = TrustAuditRequest(
        tenant_id=tenant_id,
        event_type="issuance",
        status="success",
        idempotency_key="durable-factory",
        subject_type="match_verdict",
        subject_ref_hash=tagged_sha256("subject"),
        tenant_id_hash=tenant_hash(tenant_id),
        policy_state="read_only",
        reason_code=None,
        semantic_truth_hash=tagged_sha256("semantic"),
        envelope_hash=tagged_sha256("envelope"),
        created_at=datetime(2026, 7, 1, 16, 0, 0, tzinfo=timezone.utc),
    )

    record = await record_trust_audit_event_durable(
        request,
        audit_session_factory=FakeAuditSessionFactory(session),
    )

    assert record.audit_ref.startswith("urn:skeldir:audit:issuance:")
    assert "set_config('app.current_tenant_id'" in "\n".join(session.statements)
    assert "INSERT INTO public.trust_access_log" in "\n".join(session.statements)


def _postgres_proof_enabled() -> bool:
    return os.getenv("SKELDIR_B25_P7_POSTGRES_PROOF") == "1"


async def _insert_tenant_for_postgres_proof(migration_url: str, tenant_id: UUID) -> None:
    engine = create_async_engine(to_asyncpg_postgres_dsn(migration_url))
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO public.tenants (
                        id,
                        name,
                        api_key_hash,
                        notification_email
                    )
                    VALUES (
                        :tenant_id,
                        :name,
                        :api_key_hash,
                        :notification_email
                    )
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "name": f"B25 P7 tenant {tenant_id}",
                    "api_key_hash": f"b25-p7-{tenant_id}",
                    "notification_email": "b25-p7@example.invalid",
                },
            )
    finally:
        await engine.dispose()


def _postgres_audit_request(
    *,
    tenant_id: UUID,
    idempotency_key: str,
    created_at: datetime,
) -> TrustAuditRequest:
    return TrustAuditRequest(
        tenant_id=tenant_id,
        event_type="issuance",
        status="success",
        idempotency_key=idempotency_key,
        subject_type="match_verdict",
        subject_ref_hash=tagged_sha256({"subject": idempotency_key}),
        tenant_id_hash=tenant_hash(tenant_id),
        policy_state="read_only",
        reason_code=None,
        semantic_truth_hash=tagged_sha256({"semantic": idempotency_key}),
        envelope_hash=tagged_sha256({"envelope": idempotency_key}),
        created_at=created_at,
    )


async def _audit_row_count(
    session_factory,
    *,
    tenant_id: UUID,
    audit_ref: str,
) -> int:
    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            count = await session.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM public.trust_access_log
                    WHERE tenant_id = :tenant_id
                      AND audit_ref = :audit_ref
                    """
                ),
                {"tenant_id": str(tenant_id), "audit_ref": audit_ref},
            )
            return int(count or 0)


async def _postgres_audit_counts(
    session_factory,
    *,
    tenant_id: UUID,
    audit_ref: str,
    idempotency_key_hash: str,
) -> dict[str, int]:
    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            access_count = await session.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM public.trust_access_log
                    WHERE tenant_id = :tenant_id
                      AND audit_ref = :audit_ref
                    """
                ),
                {"tenant_id": str(tenant_id), "audit_ref": audit_ref},
            )
            replay_count = await session.scalar(
                text(
                    """
                    SELECT replay_count
                    FROM public.trust_access_log
                    WHERE tenant_id = :tenant_id
                      AND audit_ref = :audit_ref
                    """
                ),
                {"tenant_id": str(tenant_id), "audit_ref": audit_ref},
            )
            issuance_count = await session.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM public.trust_envelope_issuance_log
                    WHERE tenant_id = :tenant_id
                      AND idempotency_key_hash = :idempotency_key_hash
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "idempotency_key_hash": idempotency_key_hash,
                },
            )
            replay_event_count = await session.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM public.trust_replay_events
                    WHERE tenant_id = :tenant_id
                      AND original_audit_ref = :audit_ref
                    """
                ),
                {"tenant_id": str(tenant_id), "audit_ref": audit_ref},
            )
            return {
                "access_count": int(access_count or 0),
                "replay_count": int(replay_count or 0),
                "issuance_count": int(issuance_count or 0),
                "replay_event_count": int(replay_event_count or 0),
            }


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _postgres_proof_enabled(),
    reason="B2.5-P7 PostgreSQL audit durability proof is opt-in for local runs",
)
async def test_postgres_audit_durability_survives_caller_rollback() -> None:
    database_url = get_database_url()
    migration_url = get_migration_database_url()
    assert "sqlite" not in database_url.lower()
    assert database_url.startswith("postgresql")
    tenant_id = uuid4()
    await _insert_tenant_for_postgres_proof(migration_url, tenant_id)

    engine = create_async_engine(to_asyncpg_postgres_dsn(database_url))
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        rollback_request = _postgres_audit_request(
            tenant_id=tenant_id,
            idempotency_key="rollback-coupled-negative",
            created_at=datetime(2026, 7, 1, 16, 30, 0, tzinfo=timezone.utc),
        )
        rollback_record = build_audit_record(rollback_request)
        async with session_factory() as caller_session:
            await caller_session.begin()
            await caller_session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            await record_trust_audit_event(caller_session, rollback_request)
            await caller_session.rollback()
        assert (
            await _audit_row_count(
                session_factory,
                tenant_id=tenant_id,
                audit_ref=rollback_record.audit_ref,
            )
            == 0
        )

        created_at = datetime(2026, 7, 1, 16, 31, 0, tzinfo=timezone.utc)
        durable_request = _postgres_audit_request(
            tenant_id=tenant_id,
            idempotency_key="durable-postgres-proof",
            created_at=created_at,
        )
        async with session_factory() as caller_session:
            await caller_session.begin()
            await caller_session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            first = await record_trust_audit_event_durable(
                durable_request,
                audit_session_factory=session_factory,
            )
            await caller_session.rollback()

        assert (
            await _audit_row_count(
                session_factory,
                tenant_id=tenant_id,
                audit_ref=first.audit_ref,
            )
            == 1
        )

        delayed_retry = await record_trust_audit_event_durable(
            durable_request,
            audit_session_factory=session_factory,
        )
        assert delayed_retry.replayed is True
        assert delayed_retry.audit_ref == first.audit_ref
        assert delayed_retry.audit_hash == first.audit_hash
        assert durable_request.created_at == created_at

        counts = await _postgres_audit_counts(
            session_factory,
            tenant_id=tenant_id,
            audit_ref=first.audit_ref,
            idempotency_key_hash=first.idempotency_key_hash,
        )
        assert counts == {
            "access_count": 1,
            "replay_count": 1,
            "issuance_count": 1,
            "replay_event_count": 1,
        }
    finally:
        await engine.dispose()
