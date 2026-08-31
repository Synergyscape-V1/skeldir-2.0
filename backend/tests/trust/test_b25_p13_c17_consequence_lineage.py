"""Corrective XVII falsifiers for consequence authority and lineage."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.secrets import get_database_url, get_migration_database_url
from app.db.dsn import to_asyncpg_postgres_dsn
from app.tasks.enqueue import TENANT_SCOPED_TASK_NAMES
from app.trust.audit import (
    reconcile_stale_trust_issuance_states,
    record_trust_export_attempt_started,
)
from app.trust.issuance_session import trust_issuance_database_url
from app.trust.issuance_session import dispose_trust_issuance_engine
from app.trust.signer_session import dispose_trust_signer_engine
from app.trust.signer_session import trust_signer_database_url
from app.trust.jwks import build_jwks_response
from app.trust.machine_identity import AgentScope
from app.trust.key_registry import TrustKeyRegistry, TrustSigningKey
from app.trust.runtime_keys import load_runtime_signing_registry
from app.trust.signer_gateway import (
    TrustSignerGatewayError,
    assert_public_api_signer_isolation,
)
from app.trust.signer_service import assert_signer_process_custody
from test_b25_p13_c15_issuance_truth import (
    _configure_signing,
    _grant_scope,
    _issuance_rows,
    _query_envelope,
    _seed_tenant,
)
from test_b25_p13_e2e_trust_closure import (
    _build_authenticated_app,
    _worker_database_url,
)


_DB_PROOF = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_C17_DB_PROOF") != "1",
    reason="Corrective XVII consequence-lineage proofs require PostgreSQL",
)


async def _lineage(engine, tenant_id: UUID) -> tuple[dict, list[dict]]:
    del engine
    lineage_engine = create_async_engine(
        to_asyncpg_postgres_dsn(trust_issuance_database_url())
    )
    async with lineage_engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        log = (
            (
                await connection.execute(
                    text(
                        """
                    SELECT audit_ref, issuance_state, issuance_attempt_count,
                           issuance_unknown_outcome_count, known_signature_at,
                           issued_attempt_id, issued_signature, issued_envelope
                    FROM public.trust_access_log
                    WHERE tenant_id = :t AND event_type = 'issuance'
                    ORDER BY created_at DESC LIMIT 1
                    """
                    ),
                    {"t": str(tenant_id)},
                )
            )
            .mappings()
            .one()
        )
        attempts = (
            (
                await connection.execute(
                    text(
                        """
                    SELECT id, attempt_number, attempt_state, signature_known_at,
                           signing_key_id, signature, signed_envelope
                    FROM public.trust_issuance_attempts
                    WHERE tenant_id = :t AND audit_ref = :r
                    ORDER BY attempt_number
                    """
                    ),
                    {"t": str(tenant_id), "r": log["audit_ref"]},
                )
            )
            .mappings()
            .all()
        )
    await lineage_engine.dispose()
    return dict(log), [dict(row) for row in attempts]


@_DB_PROOF
@pytest.mark.asyncio
async def test_c17_real_signer_consequence_is_exactly_persisted(monkeypatch) -> None:
    _configure_signing(monkeypatch, seed=b"b25-p13-c17-positive")
    engine = create_async_engine(to_asyncpg_postgres_dsn(_worker_database_url()))
    try:
        tenant_id, token, subject_ref = await _seed_tenant(engine, "c17-positive")
        response = await _query_envelope(
            _build_authenticated_app(),
            tenant_id=tenant_id,
            token=token,
            subject_ref=subject_ref,
            idempotency_key=f"c17-positive-{uuid4().hex}",
        )
        assert response.status_code == 200, response.text
        envelope = response.json()["envelopes"][0]
        log, attempts = await _lineage(engine, tenant_id)
        assert log["issuance_state"] == "issued"
        assert log["issued_envelope"] == envelope
        assert bytes(log["issued_signature"]) == bytes(attempts[0]["signature"])
        assert attempts[0]["attempt_state"] == "issued"
        assert attempts[0]["signed_envelope"] == envelope
        assert log["issued_attempt_id"] == attempts[0]["id"]
        print("\nc17_exact_consequence_correspondence=1")
    finally:
        await engine.dispose()


@_DB_PROOF
@pytest.mark.asyncio
async def test_c17_public_api_and_signer_are_real_separate_processes(
    monkeypatch,
) -> None:
    """The public API operates with JWKS+issuer only; signer owns key+signer DSN."""
    _configure_signing(monkeypatch, seed=b"b25-p13-c17-process-boundary")
    signing_registry = load_runtime_signing_registry()
    public_jwks = json.dumps(build_jwks_response(signing_registry.public_only()))
    shared_secret = "c17-process-boundary-shared-secret-0001"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])

    signer_env = os.environ.copy()
    signer_env["TESTING"] = "0"
    signer_env["DATABASE_URL"] = signer_env["TRUST_SIGNER_DATABASE_URL"]
    signer_env["TRUST_SIGNER_SHARED_SECRET"] = shared_secret
    signer_env.pop("TRUST_ISSUANCE_DATABASE_URL", None)
    signer_env.pop("MIGRATION_DATABASE_URL", None)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.trust.signer_service:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=signer_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            for _ in range(60):
                try:
                    health = await client.get(f"http://127.0.0.1:{port}/health/live")
                    if health.status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.1)
            else:
                output = process.stdout.read() if process.stdout else ""
                raise AssertionError(f"signer process did not become ready: {output}")

        # This is the public API's actual secret topology for the request.
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.delenv("TRUST_SIGNER_DATABASE_URL", raising=False)
        monkeypatch.delenv("SKELDIR_TRUST_SIGNING_KEY_SEED_B64URL", raising=False)
        monkeypatch.setenv("SKELDIR_TRUST_PUBLIC_JWKS_JSON", public_jwks)
        monkeypatch.setenv("TRUST_SIGNER_URL", f"http://127.0.0.1:{port}")
        monkeypatch.setenv("TRUST_SIGNER_SHARED_SECRET", shared_secret)

        engine = create_async_engine(to_asyncpg_postgres_dsn(_worker_database_url()))
        try:
            tenant_id, token, subject_ref = await _seed_tenant(
                engine, "c17-process-boundary"
            )
            response = await _query_envelope(
                _build_authenticated_app(),
                tenant_id=tenant_id,
                token=token,
                subject_ref=subject_ref,
                idempotency_key=f"c17-process-boundary-{uuid4().hex}",
            )
            assert response.status_code == 200, response.text
            log, attempts = await _lineage(engine, tenant_id)
            assert log["issuance_state"] == "issued"
            assert attempts[0]["attempt_state"] == "issued"
            assert "TRUST_SIGNER_DATABASE_URL" not in os.environ
            assert "SKELDIR_TRUST_SIGNING_KEY_SEED_B64URL" not in os.environ
            print("\nc17_real_process_custody_boundary=1")
        finally:
            await engine.dispose()
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


@_DB_PROOF
@pytest.mark.asyncio
async def test_c17_completion_failure_preserves_known_signature_and_retry(
    monkeypatch,
) -> None:
    _configure_signing(monkeypatch, seed=b"b25-p13-c17-known")
    engine = create_async_engine(to_asyncpg_postgres_dsn(_worker_database_url()))
    try:
        tenant_id, token, subject_ref = await _seed_tenant(engine, "c17-known")
        from app.api import trust_api

        original_complete = trust_api.record_trust_issuance_completed

        async def fail_completion(**_kwargs) -> None:
            raise RuntimeError("c17_completion_projection_failure")

        monkeypatch.setattr(
            trust_api, "record_trust_issuance_completed", fail_completion
        )
        key = f"c17-known-{uuid4().hex}"
        with pytest.raises(RuntimeError, match="c17_completion_projection_failure"):
            await _query_envelope(
                _build_authenticated_app(),
                tenant_id=tenant_id,
                token=token,
                subject_ref=subject_ref,
                idempotency_key=key,
            )
        log, attempts = await _lineage(engine, tenant_id)
        assert log["issuance_state"] == "signature_known"
        assert log["known_signature_at"] is not None
        assert attempts[0]["attempt_state"] == "signature_known"
        exact_artifact = attempts[0]["signed_envelope"]

        # A restart discards process-local handles and pools. Recovery must use
        # only the committed exact artifact, even after the active key rotates.
        await dispose_trust_signer_engine()
        await dispose_trust_issuance_engine()
        issued_at = datetime.fromisoformat(
            str(exact_artifact["created_at"]).replace("Z", "+00:00")
        )
        old_private = Ed25519PrivateKey.from_private_bytes(
            hashlib.sha256(b"b25-p13-c17-known").digest()
        )
        old_verification_key = TrustSigningKey(
            kid=str(exact_artifact["signing_key_id"]),
            algorithm="ed25519",
            public_key=old_private.public_key(),
            private_key=None,
            state="verification_only",
            valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            valid_until=issued_at + timedelta(days=365),
            retired_at=issued_at + timedelta(seconds=1),
        )
        monkeypatch.setenv(
            "SKELDIR_TRUST_PUBLIC_JWKS_JSON",
            json.dumps(build_jwks_response(TrustKeyRegistry((old_verification_key,)))),
        )
        _configure_signing(
            monkeypatch,
            kid="kid:b25-p13-c17-rotated",
            seed=b"b25-p13-c17-rotated",
        )

        monkeypatch.setattr(
            trust_api, "record_trust_issuance_completed", original_complete
        )
        retry = await _query_envelope(
            _build_authenticated_app(),
            tenant_id=tenant_id,
            token=token,
            subject_ref=subject_ref,
            idempotency_key=key,
        )
        assert retry.status_code == 200, retry.text
        assert retry.json()["envelopes"][0] == exact_artifact
        log, attempts = await _lineage(engine, tenant_id)
        assert log["issuance_state"] == "issued"
        assert log["issuance_attempt_count"] == 1
        assert len(attempts) == 1 and attempts[0]["attempt_state"] == "issued"
        print("\nc17_strongest_known_fact_retry=1")
        print("c17_restart_key_rotation_reservice=1")
    finally:
        await engine.dispose()


@_DB_PROOF
@pytest.mark.asyncio
async def test_c17_issuer_cannot_manufacture_signer_consequence(monkeypatch) -> None:
    _configure_signing(monkeypatch, seed=b"b25-p13-c17-fabrication")
    worker = create_async_engine(to_asyncpg_postgres_dsn(_worker_database_url()))
    issuer = create_async_engine(to_asyncpg_postgres_dsn(trust_issuance_database_url()))
    signer = create_async_engine(to_asyncpg_postgres_dsn(trust_signer_database_url()))
    try:
        tenant_id, token, subject_ref = await _seed_tenant(worker, "c17-forgery")
        other_tenant_id, _other_token, _other_subject = await _seed_tenant(
            worker, "c17-forgery-other"
        )
        # Stop after durable authorization so the exact audit experiment begins
        # from the same legitimate state as production.
        from app.api import trust_api

        async def stop_before_attempt(**_kwargs):
            raise RuntimeError("c17_stop_before_attempt")

        monkeypatch.setattr(
            trust_api, "record_trust_issuance_attempt_started", stop_before_attempt
        )
        with pytest.raises(RuntimeError, match="c17_stop_before_attempt"):
            await _query_envelope(
                _build_authenticated_app(),
                tenant_id=tenant_id,
                token=token,
                subject_ref=subject_ref,
                idempotency_key=f"c17-forgery-{uuid4().hex}",
            )
        async with worker.begin() as connection:
            await connection.execute(
                text("SELECT set_config('app.current_tenant_id', :t, true)"),
                {"t": str(tenant_id)},
            )
            audit_ref = (
                await connection.execute(
                    text(
                        "SELECT audit_ref FROM public.trust_access_log "
                        "WHERE tenant_id=:t AND event_type='issuance'"
                    ),
                    {"t": str(tenant_id)},
                )
            ).scalar_one()
        attempt_id = uuid4()
        async with issuer.begin() as connection:
            await connection.execute(
                text("SELECT set_config('app.current_tenant_id', :t, true)"),
                {"t": str(tenant_id)},
            )
            await connection.execute(
                text(
                    """
                    UPDATE public.trust_access_log
                    SET issuance_state='signing', issuance_attempted_at=now(),
                        issuance_attempt_count=issuance_attempt_count+1
                    WHERE tenant_id=:t AND audit_ref=:r
                    """
                ),
                {"t": str(tenant_id), "r": audit_ref},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO public.trust_issuance_attempts
                        (id, tenant_id, audit_ref, attempt_number, attempt_state)
                    VALUES (:a, :t, :r, 1, 'signing')
                    """
                ),
                {"a": str(attempt_id), "t": str(tenant_id), "r": audit_ref},
            )

        with pytest.raises(Exception, match="trust_attempt_authority_violation:signer"):
            async with issuer.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('app.current_tenant_id', :t, true)"),
                    {"t": str(tenant_id)},
                )
                await connection.execute(
                    text(
                        """
                        UPDATE public.trust_issuance_attempts
                        SET attempt_state='signature_known', signature_known_at=now(),
                            signing_key_id='kid:fabricated',
                            signature_hash='sha256:' || repeat('a',64),
                            signature=decode(repeat('ab',64),'hex'),
                            signed_envelope_hash='sha256:' || repeat('b',64),
                            signed_envelope='{}'::jsonb
                        WHERE tenant_id=:t AND id=:a
                        """
                    ),
                    {"t": str(tenant_id), "a": str(attempt_id)},
                )
        with pytest.raises(Exception, match="transition:signing->issued"):
            async with issuer.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('app.current_tenant_id', :t, true)"),
                    {"t": str(tenant_id)},
                )
                await connection.execute(
                    text(
                        """
                        UPDATE public.trust_access_log SET issuance_state='issued',
                            issued_at=now(), issued_attempt_id=:a,
                            known_signature_at=now(),
                            issued_signing_key_id='kid:fabricated',
                            issued_signature_hash='sha256:' || repeat('a',64),
                            issued_signature=decode(repeat('ab',64),'hex'),
                            issued_envelope='{}'::jsonb
                        WHERE tenant_id=:t AND audit_ref=:r
                        """
                    ),
                    {"t": str(tenant_id), "r": audit_ref, "a": str(attempt_id)},
                )
        # The pre-XVII batch-completion surface still exists in app.trust.audit
        # for the C15 closure contract, but nothing in production calls it any
        # more. Prove it is physically inert rather than assuming it: invoked
        # directly, under the legitimate issuer principal, with well-shaped but
        # fabricated evidence, it cannot reach `issued`.
        from app.trust.audit import record_trust_issuance_batch_completed

        with pytest.raises(Exception, match="transition:signing->issued"):
            await record_trust_issuance_batch_completed(
                tenant_id=tenant_id,
                completions=[
                    (
                        audit_ref,
                        {
                            "signing_key_id": "kid:fabricated",
                            "signature_hash": "sha256:" + "a" * 64,
                            "signature": "ed25519:"
                            + base64.urlsafe_b64encode(b"\xab" * 64)
                            .decode("ascii")
                            .rstrip("="),
                        },
                    )
                ],
            )
        # The signer credential alone can author the evidence row, but it
        # cannot cause completion: recovery independently verifies the exact
        # artifact with public key authority before the issuer projection.
        async with signer.begin() as connection:
            await connection.execute(
                text("SELECT set_config('app.current_tenant_id', :t, true)"),
                {"t": str(tenant_id)},
            )
            known_at = (
                await connection.execute(
                    text(
                        """
                        UPDATE public.trust_issuance_attempts
                        SET attempt_state='signature_known', signature_known_at=now(),
                            signing_key_id='kid:fabricated',
                            signature_hash='sha256:' || repeat('a',64),
                            signature=decode(repeat('ab',64),'hex'),
                            signed_envelope_hash='sha256:' || repeat('b',64),
                            signed_envelope='{}'::jsonb
                        WHERE tenant_id=:t AND id=:a
                        RETURNING signature_known_at
                        """
                    ),
                    {"t": str(tenant_id), "a": str(attempt_id)},
                )
            ).scalar_one()
            await connection.execute(
                text(
                    """
                    UPDATE public.trust_access_log
                    SET issuance_state='signature_known', known_signature_at=:known,
                        issued_attempt_id=:a
                    WHERE tenant_id=:t AND audit_ref=:r
                    """
                ),
                {
                    "t": str(tenant_id),
                    "r": audit_ref,
                    "a": str(attempt_id),
                    "known": known_at,
                },
            )
        refused = await reconcile_stale_trust_issuance_states(
            tenant_id=tenant_id,
            stale_before=datetime.now(timezone.utc) + timedelta(seconds=1),
            batch_size=10,
        )
        assert refused["invalid_signature_known_refused"] == 1
        log, _attempts = await _lineage(worker, tenant_id)
        assert log["issuance_state"] == "signature_known"
        with pytest.raises(
            Exception, match="trust_attempt_authority_violation:identity"
        ):
            async with issuer.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('app.current_tenant_id', :t, true)"),
                    {"t": str(tenant_id)},
                )
                await connection.execute(
                    text(
                        """
                        UPDATE public.trust_issuance_attempts SET tenant_id=:other
                        WHERE tenant_id=:t AND id=:a
                        """
                    ),
                    {
                        "t": str(tenant_id),
                        "other": str(other_tenant_id),
                        "a": str(attempt_id),
                    },
                )
        print("\nc17_issuer_fabrication_refusals=4")
        print("c17_raw_signer_invalid_completion_refused=1")
    finally:
        await signer.dispose()
        await issuer.dispose()
        await worker.dispose()


@_DB_PROOF
@pytest.mark.asyncio
async def test_c17_recovery_promotes_known_and_preserves_unknown_lineage(
    monkeypatch,
) -> None:
    _configure_signing(monkeypatch, seed=b"b25-p13-c17-recovery")
    engine = create_async_engine(to_asyncpg_postgres_dsn(_worker_database_url()))
    try:
        tenant_id, token, subject_ref = await _seed_tenant(engine, "c17-recovery")
        from app.api import trust_api

        original_complete = trust_api.record_trust_issuance_completed

        async def fail_completion(**_kwargs) -> None:
            raise RuntimeError("c17_recovery_boundary")

        monkeypatch.setattr(
            trust_api, "record_trust_issuance_completed", fail_completion
        )
        with pytest.raises(RuntimeError, match="c17_recovery_boundary"):
            await _query_envelope(
                _build_authenticated_app(),
                tenant_id=tenant_id,
                token=token,
                subject_ref=subject_ref,
                idempotency_key=f"c17-recovery-{uuid4().hex}",
            )
        monkeypatch.setattr(
            trust_api, "record_trust_issuance_completed", original_complete
        )
        result = await reconcile_stale_trust_issuance_states(
            tenant_id=tenant_id,
            stale_before=datetime.now(timezone.utc) + timedelta(seconds=1),
            batch_size=1,
        )
        assert result["signature_known_to_issued"] == 1
        log, attempts = await _lineage(engine, tenant_id)
        assert log["issuance_state"] == "issued"
        assert attempts[0]["attempt_state"] == "issued"
        print("\nc17_durable_recovery_convergence=1")
    finally:
        await engine.dispose()


def test_c17_reconciler_is_tenant_dispatch_authorized() -> None:
    assert (
        "app.tasks.maintenance.reconcile_trust_issuance_for_tenant"
        in TENANT_SCOPED_TASK_NAMES
    )
    print("\nc17_reconciler_dispatch_authorized=1")


def test_c17_signer_and_issuer_credentials_are_distinct() -> None:
    assert os.getenv("TRUST_SIGNER_DATABASE_URL") != get_database_url()
    assert os.getenv("TRUST_SIGNER_DATABASE_URL") != trust_issuance_database_url()


def test_c17_process_custody_guards_fail_closed(monkeypatch) -> None:
    monkeypatch.setenv("TESTING", "0")
    monkeypatch.setenv("SKELDIR_TRUST_SIGNING_KEY_SEED_B64URL", "private-material")
    monkeypatch.setenv("TRUST_SIGNER_DATABASE_URL", "postgresql://signer")
    with pytest.raises(
        TrustSignerGatewayError,
        match="public_api_forbidden_signer_authority:TRUST_SIGNER_DATABASE_URL",
    ):
        assert_public_api_signer_isolation()

    monkeypatch.setenv("TRUST_SIGNER_SHARED_SECRET", "x" * 32)
    monkeypatch.setenv("TRUST_ISSUANCE_DATABASE_URL", "postgresql://issuer")
    with pytest.raises(
        RuntimeError,
        match="trust_signer_forbidden_authority:TRUST_ISSUANCE_DATABASE_URL",
    ):
        assert_signer_process_custody()
    print("\nc17_process_custody_guards=2")


@_DB_PROOF
@pytest.mark.asyncio
async def test_c17_export_refusal_leaves_no_unreachable_issued_row(monkeypatch) -> None:
    """A durably issued export envelope stays reachable after a late refusal.

    Audit 59 established the reverse: a page could sign, durably commit
    ``issued``, then be discarded by a later refusal, and no retry could ever
    recover it because the attempt transition refused to re-enter a terminal
    row. The invariant is reachability, so this proves reachability directly
    rather than proving that one anticipated refusal class is prevented.
    """
    _configure_signing(monkeypatch, seed=b"b25-p13-c17-export-reservice")
    engine = create_async_engine(to_asyncpg_postgres_dsn(_worker_database_url()))
    try:
        tenant_id, token, subject_urn = await _seed_tenant(engine, "c17-reservice")
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('app.current_tenant_id', :t, true)"),
                {"t": str(tenant_id)},
            )
            client_id = (
                await connection.execute(
                    text(
                        "SELECT id FROM public.agent_clients "
                        "WHERE tenant_id = :t ORDER BY created_at LIMIT 1"
                    ),
                    {"t": str(tenant_id)},
                )
            ).scalar_one()
            await _grant_scope(
                connection,
                tenant_id=tenant_id,
                agent_client_id=client_id,
                scope=AgentScope.EXPORT_CREATE_LIMITED.value,
            )

        from app.api import trust_export

        signings = 0
        original_signer = trust_export.request_trust_envelope_signature

        async def counted_signer(**kwargs):
            nonlocal signings
            signings += 1
            return await original_signer(**kwargs)

        monkeypatch.setattr(
            trust_export, "request_trust_envelope_signature", counted_signer
        )

        idempotency_key = f"c17-reservice-{uuid4().hex}"

        def _headers() -> dict[str, str]:
            return {
                "Authorization": f"Bearer {token}",
                "X-Tenant-ID": str(tenant_id),
                "X-Trust-Nonce": f"c17-reservice-{uuid4().hex}",
                "X-Correlation-ID": str(uuid4()),
                "X-Idempotency-Key": idempotency_key,
            }

        app = FastAPI()
        app.include_router(trust_export.router, prefix="/api")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # A refusal that lands after per-envelope issuance is durable.
            monkeypatch.setattr(trust_export, "MAX_EXPORT_ARTIFACT_BYTES", 1)
            refused = await client.post(
                "/api/trust/v1/exports/match-verdicts",
                headers=_headers(),
                json={"subject_refs": [subject_urn]},
            )
            assert refused.status_code == 413, refused.text
            rows = await _issuance_rows(engine, tenant_id)
            assert len(rows) == 1, rows
            assert rows[0]["issuance_state"] == "issued", rows
            signings_after_refusal = signings

            # The same request, retried once the refusal condition is gone,
            # must serve that exact durable artifact instead of failing closed,
            # and must not produce a second cryptographic consequence.
            monkeypatch.setattr(trust_export, "MAX_EXPORT_ARTIFACT_BYTES", 5_000_000)
            recovered = await client.post(
                "/api/trust/v1/exports/match-verdicts",
                headers=_headers(),
                json={"subject_refs": [subject_urn]},
            )

        assert recovered.status_code == 200, recovered.text
        served = recovered.json()["envelopes"][0]
        assert signings == signings_after_refusal, "retry re-signed a durable artifact"
        log, attempts = await _lineage(engine, tenant_id)
        assert log["issuance_state"] == "issued"
        assert log["issued_envelope"] == served
        assert len(attempts) == 1, attempts
        assert attempts[0]["attempt_state"] == "issued"
        print("\nc17_durable_export_reservice=1")
    finally:
        await engine.dispose()


@_DB_PROOF
@pytest.mark.asyncio
async def test_c17_concurrent_export_attempts_allocate_distinct_lineage() -> None:
    """Concurrent exports of one reference set each get their own attempt row.

    Two concurrent exports of the same subject set share a binding hash and a
    page start. Each will produce its own real wrapper signature, so each needs
    its own durably accounted attempt; an allocation that reads the next
    attempt number and then inserts it loses that race against its own unique
    constraint.
    """
    tenant_id = uuid4()
    migration_engine = create_async_engine(
        to_asyncpg_postgres_dsn(get_migration_database_url())
    )
    try:
        async with migration_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO public.tenants"
                    "(id, name, api_key_hash, notification_email)"
                    " VALUES (:i, :n, :h, :e)"
                ),
                {
                    "i": str(tenant_id),
                    "n": f"c17-export-race-{tenant_id.hex[:8]}",
                    "h": f"hash:c17-export-race:{tenant_id.hex}",
                    "e": f"c17-race-{tenant_id.hex[:8]}@example.invalid",
                },
            )
    finally:
        await migration_engine.dispose()

    binding_hash = "sha256:" + hashlib.sha256(b"c17-export-race").hexdigest()
    concurrency = 6
    attempt_ids = await asyncio.gather(
        *(
            record_trust_export_attempt_started(
                tenant_id=tenant_id,
                request_binding_hash=binding_hash,
                page_start=0,
            )
            for _ in range(concurrency)
        )
    )
    assert len(set(attempt_ids)) == concurrency

    issuer_engine = create_async_engine(
        to_asyncpg_postgres_dsn(trust_issuance_database_url())
    )
    try:
        async with issuer_engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('app.current_tenant_id', :t, true)"),
                {"t": str(tenant_id)},
            )
            numbers = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT attempt_number
                        FROM public.trust_export_artifact_attempts
                        WHERE tenant_id = :t AND request_binding_hash = :b
                          AND page_start = 0
                        ORDER BY attempt_number
                        """
                        ),
                        {"t": str(tenant_id), "b": binding_hash},
                    )
                )
                .scalars()
                .all()
            )
    finally:
        await issuer_engine.dispose()

    assert numbers == list(range(1, concurrency + 1)), numbers
    print(f"\nc17_concurrent_export_attempt_lineage={concurrency}")
