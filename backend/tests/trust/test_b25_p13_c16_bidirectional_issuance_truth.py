"""Corrective XVI runtime falsifiers for bidirectional issuance truth."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.dsn import to_asyncpg_postgres_dsn
from app.core.secrets import get_database_url
from app.tasks.beat_schedule import build_beat_schedule
from app.trust.audit import (
    reconcile_stale_trust_issuance_states,
    record_trust_issuance_attempt_started,
)
from app.trust.issuance_session import (
    TRUST_ISSUANCE_PRINCIPAL,
    trust_issuance_database_url,
)
from app.trust.export_artifact import verify_export_artifact
from app.trust.machine_identity import AgentScope
from app.trust.signing import decode_ed25519_signature
from test_b25_p13_c15_issuance_truth import (
    _configure_signing,
    _grant_scope,
    _issuance_rows,
    _query_envelope,
    _seed_tenant,
)
from test_b25_p13_e2e_trust_closure import (
    _TERMINALIZE_FIT_SQL,
    _build_authenticated_app,
    _seed_open_leased_fit,
    _terminalize_params,
    _worker_database_url,
)


_DB_PROOF = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_C16_DB_PROOF") != "1",
    reason="Corrective XVI durable-truth proofs require PostgreSQL and are opt-in",
)


@_DB_PROOF
@pytest.mark.asyncio
async def test_c16_post_signature_completion_failure_retains_known_signature(
    monkeypatch,
) -> None:
    """Cross the real signing boundary, then fail only the completion write.

    The signing function executes genuinely and its signed result is captured.
    Only the subsequent completion projection is forced to fail. C17 writes the
    exact signer consequence before that projection, so durable history must
    retain ``signature_known`` and the exact signed artifact rather than
    regressing a known fact to ``signature_outcome_unknown``.
    """

    _configure_signing(monkeypatch, seed=b"b25-p13-c16-reproduction")
    engine = create_async_engine(
        to_asyncpg_postgres_dsn(_worker_database_url()), future=True
    )
    try:
        tenant_id, token, subject_urn = await _seed_tenant(engine, "c16-repro")
        app = _build_authenticated_app()

        from app.api import trust_api

        captured: list[dict] = []
        original_signer = trust_api.request_trust_envelope_signature

        async def capture_real_signature(**kwargs):
            signed = await original_signer(**kwargs)
            captured.append(signed)
            return signed

        async def fail_completion_write(**_kwargs) -> None:
            raise RuntimeError("c16_injected_completion_write_failure")

        monkeypatch.setattr(
            trust_api, "request_trust_envelope_signature", capture_real_signature
        )
        monkeypatch.setattr(
            trust_api,
            "record_trust_issuance_completed",
            fail_completion_write,
        )

        with pytest.raises(RuntimeError, match="c16_injected_completion_write_failure"):
            await _query_envelope(
                app,
                tenant_id=tenant_id,
                token=token,
                subject_ref=subject_urn,
                idempotency_key=f"c16-repro-{uuid4().hex}",
            )

        assert len(captured) == 1, "the falsifier must cross the real signing boundary"
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            verified = await client.post(
                "/api/trust/v1/verify",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-ID": str(tenant_id),
                    "X-Trust-Nonce": f"c16-verify-{uuid4().hex}",
                    "X-Correlation-ID": str(uuid4()),
                },
                json=captured[0],
            )
        assert verified.status_code == 200, verified.text
        assert verified.json()["verification_status"] == "verified", verified.text

        rows = await _issuance_rows(engine, tenant_id)
        assert len(rows) == 1, rows
        assert rows[0]["issuance_state"] == "signature_known", rows
        issuer_engine = create_async_engine(
            to_asyncpg_postgres_dsn(trust_issuance_database_url()), future=True
        )
        try:
            async with issuer_engine.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('app.current_tenant_id', :t, true)"),
                    {"t": str(tenant_id)},
                )
                retained_signature = (
                    await connection.execute(
                        text(
                            """
                            SELECT signature FROM public.trust_issuance_attempts
                            WHERE tenant_id = :t AND audit_ref = :r
                            """
                        ),
                        {"t": str(tenant_id), "r": rows[0]["audit_ref"]},
                    )
                ).scalar_one()
        finally:
            await issuer_engine.dispose()
        assert bytes(retained_signature) == decode_ed25519_signature(
            captured[0]["signature"]
        )
        assert rows[0]["issuance_attempted_at"] is not None, rows
        assert rows[0]["issuance_outcome_unknown_at"] is None, rows
        observations = [
            "real_signature_captured",
            "public_verification_passed",
            "write_ahead_attempt_retained",
            "strongest_known_signature_retained",
        ]
        print("\nc16_post_signature_boundary_observations=" + str(len(observations)))
    finally:
        await engine.dispose()


@_DB_PROOF
@pytest.mark.asyncio
async def test_c16_export_413_occurs_after_durable_signature_completion(
    monkeypatch,
) -> None:
    """A post-signature export 413 cannot strand an authorization row."""

    _configure_signing(monkeypatch, seed=b"b25-p13-c16-export-reproduction")
    engine = create_async_engine(
        to_asyncpg_postgres_dsn(_worker_database_url()), future=True
    )
    try:
        tenant_id, token, subject_urn = await _seed_tenant(engine, "c16-export")
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

        captured: list[dict] = []
        original_signer = trust_export.request_trust_envelope_signature

        async def capture_real_signature(**kwargs):
            signed = await original_signer(**kwargs)
            captured.append(signed)
            return signed

        monkeypatch.setattr(
            trust_export,
            "request_trust_envelope_signature",
            capture_real_signature,
        )
        monkeypatch.setattr(trust_export, "MAX_EXPORT_ARTIFACT_BYTES", 1)
        export_idempotency_key = f"c16-export-{uuid4().hex}"
        app = FastAPI()
        app.include_router(trust_export.router, prefix="/api")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/trust/v1/exports/match-verdicts",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-ID": str(tenant_id),
                    "X-Trust-Nonce": f"c16-export-{uuid4().hex}",
                    "X-Correlation-ID": str(uuid4()),
                    "X-Idempotency-Key": export_idempotency_key,
                },
                json={"subject_refs": [subject_urn]},
            )
            retry = await client.post(
                "/api/trust/v1/exports/match-verdicts",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-ID": str(tenant_id),
                    "X-Trust-Nonce": f"c16-export-retry-{uuid4().hex}",
                    "X-Correlation-ID": str(uuid4()),
                    "X-Idempotency-Key": export_idempotency_key,
                },
                json={"subject_refs": [subject_urn]},
            )

        assert response.status_code == 413, response.text
        assert retry.status_code == 413, retry.text
        assert len(captured) == 1, "the 413 falsifier must occur after real signing"
        rows = await _issuance_rows(engine, tenant_id)
        assert len(rows) == 1, rows
        assert rows[0]["issuance_state"] == "issued", rows
        assert len(rows[0]["issued_signature"]) == 64, rows
        issuer_engine = create_async_engine(
            to_asyncpg_postgres_dsn(trust_issuance_database_url()), future=True
        )
        try:
            async with issuer_engine.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('app.current_tenant_id', :t, true)"),
                    {"t": str(tenant_id)},
                )
                wrapper_rows = (
                    (
                        await connection.execute(
                            text(
                                """
                            SELECT attempt_state, signature, signed_artifact
                            FROM public.trust_export_artifact_attempts
                            WHERE tenant_id = :t ORDER BY attempt_number
                            """
                            ),
                            {"t": str(tenant_id)},
                        )
                    )
                    .mappings()
                    .all()
                )
        finally:
            await issuer_engine.dispose()
        assert len(wrapper_rows) == 1
        assert wrapper_rows[0]["attempt_state"] == "issued"
        assert len(wrapper_rows[0]["signature"]) == 64
        registry = await trust_export.get_runtime_signing_registry()
        verification = verify_export_artifact(
            dict(wrapper_rows[0]["signed_artifact"]),
            key_registry=registry.public_only(),
        )
        assert verification.verification_status == "verified"
        observations = [
            "real_export_signature_captured",
            "response_budget_refused_413",
            "issued_state_durable_before_413",
            "raw_signature_evidence_retained",
        ]
        print("\nc16_export_boundary_observations=" + str(len(observations)))
        print("c17_export_wrapper_correspondence=1")
    finally:
        await engine.dispose()


@_DB_PROOF
@pytest.mark.asyncio
async def test_c16_database_refuses_every_weak_principal_completion_claim(
    monkeypatch,
) -> None:
    """Exercise the Corrective XVI role x state matrix against live PostgreSQL.

    Audit 58 Finding 2 established that a CHECK constraint proves shape, never
    consequence: the ordinary ``app_user`` role could stamp a structurally
    plausible but entirely fabricated completed issuance. Shape alone cannot
    close that, because any principal able to write the row can also write 64
    fabricated bytes. The database therefore narrows the transition authority
    to ``app_trust_issuer`` and enforces it with ``session_user``, which no
    ``SET ROLE`` can forge.

    Every ordinary runtime principal must be refused for every consequence-
    bearing mutation, and the narrowed principal must itself remain bounded by
    the transition graph, terminal immutability, tenant binding and monotonic
    lineage -- otherwise the remediation would merely relocate the forgery.
    """

    _configure_signing(monkeypatch, seed=b"b25-p13-c16-db-physics")
    worker_engine = create_async_engine(
        to_asyncpg_postgres_dsn(_worker_database_url()), future=True
    )
    runtime_engine = create_async_engine(
        to_asyncpg_postgres_dsn(get_database_url()), future=True
    )
    issuer_engine = create_async_engine(
        to_asyncpg_postgres_dsn(trust_issuance_database_url()), future=True
    )
    try:
        tenant_id, token, subject_urn = await _seed_tenant(worker_engine, "c16-db")
        issued_idempotency_key = f"c16-db-{uuid4().hex}"
        response = await _query_envelope(
            _build_authenticated_app(),
            tenant_id=tenant_id,
            token=token,
            subject_ref=subject_urn,
            idempotency_key=issued_idempotency_key,
        )
        assert response.status_code == 200, response.text
        issued_ref = (await _issuance_rows(worker_engine, tenant_id))[0]["audit_ref"]

        # A pre-signature row lets the matrix drive forbidden predecessors as
        # well as terminal rows. It is cloned from the real issued row under an
        # ordinary principal, which the trigger permits only in `authorized` --
        # itself one of the matrix outcomes being asserted.
        pre_ref = f"urn:skeldir:audit:issuance:{uuid4().hex}"
        async with worker_engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('app.current_tenant_id', :t, true)"),
                {"t": str(tenant_id)},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO public.trust_access_log (
                        tenant_id, event_type, status, audit_ref,
                        request_identity_hash, idempotency_key_hash,
                        subject_type, policy_state, audit_hash,
                        issuance_state, envelope_hash
                    )
                    SELECT tenant_id, 'issuance', 'success', :new_ref,
                           request_identity_hash,
                           'sha256:' || md5(random()::text) || md5(random()::text),
                           subject_type, policy_state, audit_hash,
                           'authorized', envelope_hash
                    FROM public.trust_access_log
                    WHERE tenant_id = :t AND audit_ref = :issued
                    """
                ),
                {"t": str(tenant_id), "issued": issued_ref, "new_ref": pre_ref},
            )

        sig64 = "decode(repeat('ab',64),'hex')"
        good_hash = "'sha256:' || repeat('a',64)"
        mutations = (
            (
                "issued_null_crypto",
                pre_ref,
                "issuance_state='issued', issued_at=now(), issuance_attempted_at=now(),"
                " issuance_attempt_count=1, issued_signing_key_id='kid:x',"
                " issued_signature_hash=NULL, issued_signature=NULL",
            ),
            (
                "issued_malformed_crypto",
                pre_ref,
                "issuance_state='issued', issued_at=now(), issuance_attempted_at=now(),"
                " issuance_attempt_count=1, issued_signing_key_id='kid:x',"
                " issued_signature_hash='not-a-hash', issued_signature=decode('ab','hex')",
            ),
            (
                "issued_fabricated_well_shaped",
                pre_ref,
                f"issuance_state='issued', issued_at=now(), issuance_attempted_at=now(),"
                f" issuance_attempt_count=1, issued_signing_key_id='kid:forged',"
                f" issued_signature_hash={good_hash}, issued_signature={sig64}",
            ),
            (
                "issued_missing_key_identity",
                pre_ref,
                f"issuance_state='issued', issued_at=now(), issuance_attempted_at=now(),"
                f" issuance_attempt_count=1, issued_signing_key_id=NULL,"
                f" issued_signature_hash={good_hash}, issued_signature={sig64}",
            ),
            (
                "unissued_carries_crypto",
                pre_ref,
                f"issued_signing_key_id='kid:forged',"
                f" issued_signature_hash={good_hash}, issued_signature={sig64}",
            ),
            (
                "terminal_issuance_denied",
                issued_ref,
                "issuance_state='failed', issued_at=NULL, issuance_attempted_at=NULL,"
                " issued_signing_key_id=NULL, issued_signature_hash=NULL,"
                " issued_signature=NULL",
            ),
            (
                "terminal_signature_substituted",
                issued_ref,
                f"issued_signing_key_id='kid:swapped',"
                f" issued_signature_hash={good_hash}, issued_signature={sig64}",
            ),
            ("legacy_state_claimed", pre_ref, "issuance_state='issued_legacy'"),
            (
                "cross_tenant_rebind",
                pre_ref,
                "tenant_id='22222222-2222-2222-2222-222222222222'",
            ),
            (
                "lineage_regressed",
                pre_ref,
                "issuance_attempt_count=0, issuance_unknown_outcome_count=0,"
                " issuance_state='signing', issuance_attempted_at=now()",
            ),
        )

        async def _refusal(engine, expected_role: str, mutation: str, ref: str) -> str:
            with pytest.raises(Exception) as excinfo:
                async with engine.begin() as connection:
                    role = (
                        await connection.execute(text("SELECT current_user"))
                    ).scalar_one()
                    assert role == expected_role, role
                    await connection.execute(
                        text("SELECT set_config('app.current_tenant_id', :t, true)"),
                        {"t": str(tenant_id)},
                    )
                    await connection.execute(
                        text(
                            "UPDATE public.trust_access_log SET "
                            + mutation
                            + " WHERE tenant_id = :tenant_id AND audit_ref = :audit_ref"
                        ),
                        {"tenant_id": str(tenant_id), "audit_ref": ref},
                    )
            return str(excinfo.value)

        ordinary_refusals = 0
        for _label, ref, mutation in mutations:
            message = await _refusal(runtime_engine, "app_user", mutation, ref)
            assert "trust_issuance_authority_violation" in message, message
            ordinary_refusals += 1

        # The narrowed principal holds authority and is still bounded by it.
        issuer_refusals = 0
        for _label, ref, mutation in mutations:
            message = await _refusal(
                issuer_engine, TRUST_ISSUANCE_PRINCIPAL, mutation, ref
            )
            assert (
                "trust_issuance_authority_violation" in message
                or "violates check constraint" in message
            ), message
            issuer_refusals += 1

        # A fabricated row cannot be born complete either.
        with pytest.raises(Exception) as insert_error:
            async with runtime_engine.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('app.current_tenant_id', :t, true)"),
                    {"t": str(tenant_id)},
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO public.trust_access_log (
                            tenant_id, event_type, status, audit_ref,
                            request_identity_hash, idempotency_key_hash,
                            subject_type, policy_state, audit_hash,
                            issuance_state, issued_at, issuance_attempted_at,
                            issued_signing_key_id, issued_signature_hash,
                            issued_signature, envelope_hash
                        )
                        SELECT tenant_id, 'issuance', 'success',
                               'urn:skeldir:audit:issuance:' || md5(random()::text),
                               request_identity_hash, idempotency_key_hash,
                               subject_type, policy_state, audit_hash,
                               'issued', now(), now(), 'kid:forged',
                               'sha256:' || repeat('a', 64),
                               decode(repeat('ab', 64), 'hex'), envelope_hash
                        FROM public.trust_access_log
                        WHERE tenant_id = :tenant_id AND audit_ref = :audit_ref
                        """
                    ),
                    {"tenant_id": str(tenant_id), "audit_ref": issued_ref},
                )
        assert "trust_issuance_authority_violation" in str(insert_error.value)

        # Positive control: the legitimate API lineage completed above and an
        # exact retry re-serves it, while unknown-attempt counters remain
        # monotonic even though the issuer cannot manufacture completion.
        async with issuer_engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('app.current_tenant_id', :t, true)"),
                {"t": str(tenant_id)},
            )
            await connection.execute(
                text(
                    """
                    UPDATE public.trust_access_log
                    SET issuance_state = 'signing', issuance_attempted_at = now(),
                        issuance_attempt_count = issuance_attempt_count + 1
                    WHERE tenant_id = :t AND audit_ref = :r
                    """
                ),
                {"t": str(tenant_id), "r": pre_ref},
            )
            await connection.execute(
                text(
                    """
                    UPDATE public.trust_access_log
                    SET issuance_state = 'signature_outcome_unknown',
                        issuance_outcome_unknown_at = now(),
                        issuance_unknown_outcome_count =
                            issuance_unknown_outcome_count + 1
                    WHERE tenant_id = :t AND audit_ref = :r
                    """
                ),
                {"t": str(tenant_id), "r": pre_ref},
            )
            await connection.execute(
                text(
                    """
                    UPDATE public.trust_access_log
                    SET issuance_state = 'signing',
                        issuance_outcome_unknown_at = NULL,
                        issuance_attempted_at = now(),
                        issuance_attempt_count = issuance_attempt_count + 1
                    WHERE tenant_id = :t AND audit_ref = :r
                    """
                ),
                {"t": str(tenant_id), "r": pre_ref},
            )
            lineage = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT issuance_state, issuance_attempt_count,
                               issuance_unknown_outcome_count
                        FROM public.trust_access_log
                        WHERE tenant_id = :t AND audit_ref = :r
                        """
                        ),
                        {"t": str(tenant_id), "r": pre_ref},
                    )
                )
                .mappings()
                .one()
            )
        assert lineage["issuance_state"] == "signing"
        assert lineage["issuance_attempt_count"] == 2
        assert lineage["issuance_unknown_outcome_count"] == 1
        replay = await _query_envelope(
            _build_authenticated_app(),
            tenant_id=tenant_id,
            token=token,
            subject_ref=subject_urn,
            idempotency_key=issued_idempotency_key,
        )
        assert replay.status_code == 200, replay.text
        assert replay.json() == response.json()

        print("\nc16_ordinary_principal_completion_refusals=" + str(ordinary_refusals))
        print("c16_issuer_principal_bounded_refusals=" + str(issuer_refusals))
        print("c16_fabricated_insert_refused=1")
        print(
            "c16_retained_retry_lineage="
            + str(lineage["issuance_attempt_count"])
            + ":"
            + str(lineage["issuance_unknown_outcome_count"])
        )
    finally:
        await issuer_engine.dispose()
        await runtime_engine.dispose()
        await worker_engine.dispose()


@_DB_PROOF
@pytest.mark.asyncio
async def test_c16_catalog_survey_has_no_implicit_nullable_check_operands(
    monkeypatch,
) -> None:
    """Survey every public CHECK and directly falsify both non-Trust defects."""

    _configure_signing(monkeypatch, seed=b"b25-p13-c16-null-survey")
    engine = create_async_engine(
        to_asyncpg_postgres_dsn(_worker_database_url()), future=True
    )
    try:
        tenant_id, _token, _subject_urn = await _seed_tenant(engine, "c16-null-survey")
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('app.current_tenant_id', :t, true)"),
                {"t": str(tenant_id)},
            )
            surveyed = (
                await connection.execute(
                    text(
                        r"""
                        WITH checks AS (
                            SELECT constraint_row.oid,
                                   constraint_row.conrelid,
                                   constraint_row.conname,
                                   pg_get_constraintdef(
                                       constraint_row.oid, true
                                   ) AS definition
                            FROM pg_constraint AS constraint_row
                            JOIN pg_class AS relation
                              ON relation.oid = constraint_row.conrelid
                            JOIN pg_namespace AS namespace
                              ON namespace.oid = relation.relnamespace
                            WHERE constraint_row.contype = 'c'
                              AND namespace.nspname = 'public'
                        ), nullable_columns AS (
                            SELECT attribute.attrelid, attribute.attname
                            FROM pg_attribute AS attribute
                            WHERE attribute.attnum > 0
                              AND NOT attribute.attisdropped
                              AND NOT attribute.attnotnull
                        )
                        SELECT DISTINCT checks.conname, nullable_columns.attname
                        FROM checks
                        JOIN nullable_columns
                          ON nullable_columns.attrelid = checks.conrelid
                        WHERE lower(checks.definition) ~ (
                            '\m' || lower(nullable_columns.attname) || '\M'
                        )
                          AND lower(checks.definition) !~ (
                            '\m' || lower(nullable_columns.attname)
                            || '\M[[:space:]]+is[[:space:]]+'
                            || '(not[[:space:]]+)?null'
                        )
                        ORDER BY checks.conname, nullable_columns.attname
                        """
                    )
                )
            ).all()
            assert surveyed == [], surveyed

            fit_id, snapshot_hash = await _seed_open_leased_fit(
                connection,
                tenant_id=tenant_id,
                label="c16-null-survey",
                index=116,
            )
            refused: list[str] = []
            with pytest.raises(
                IntegrityError,
                match="ck_bayesian_model_fits_available_confidence_complete",
            ):
                async with connection.begin_nested():
                    await connection.execute(
                        text(_TERMINALIZE_FIT_SQL),
                        _terminalize_params(
                            tenant_id=tenant_id,
                            fit_id=fit_id,
                            snapshot_hash=snapshot_hash,
                            deterministic_revenue_minor=None,
                            deterministic_row_count=None,
                            match_verdict_count=None,
                            currency_count=None,
                            evidence_snapshot_hash=None,
                        ),
                    )
            refused.append("classified_confidence_without_evidence")

            with pytest.raises(
                IntegrityError,
                match=(
                    "ck_bayesian_model_fits_" "available_interval_requires_passed_diagn"
                ),
            ):
                async with connection.begin_nested():
                    await connection.execute(
                        text(
                            """
                            UPDATE public.bayesian_model_fits
                            SET divergence_count = NULL
                            WHERE tenant_id = :tenant_id AND id = :fit_id
                            """
                        ),
                        {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
                    )
            refused.append("available_interval_without_divergence_count")

        print("\nc16_nullable_check_candidates=" + str(len(surveyed)))
        print("c16_nullable_check_mutations_refused=" + str(len(refused)))
    finally:
        await engine.dispose()


@_DB_PROOF
@pytest.mark.asyncio
async def test_c16_reconciler_bounds_authorized_and_signing_states(
    monkeypatch,
) -> None:
    """Prove the scheduled mechanism terminates both non-terminal states."""

    _configure_signing(monkeypatch, seed=b"b25-p13-c16-reconcile")
    engine = create_async_engine(
        to_asyncpg_postgres_dsn(_worker_database_url()), future=True
    )
    try:
        tenant_id, token, subject_urn = await _seed_tenant(engine, "c16-reconcile")
        app = _build_authenticated_app()
        from app.api import trust_api

        original_attempt = trust_api.record_trust_issuance_attempt_started

        async def stop_before_attempt(**_kwargs) -> None:
            raise RuntimeError("c16_stop_before_attempt")

        monkeypatch.setattr(
            trust_api, "record_trust_issuance_attempt_started", stop_before_attempt
        )
        for _ in range(2):
            with pytest.raises(RuntimeError, match="c16_stop_before_attempt"):
                await _query_envelope(
                    app,
                    tenant_id=tenant_id,
                    token=token,
                    subject_ref=subject_urn,
                    idempotency_key=f"c16-reconcile-{uuid4().hex}",
                )
        monkeypatch.setattr(
            trust_api, "record_trust_issuance_attempt_started", original_attempt
        )
        rows = await _issuance_rows(engine, tenant_id)
        assert [row["issuance_state"] for row in rows] == [
            "authorized",
            "authorized",
        ]
        await record_trust_issuance_attempt_started(
            tenant_id=tenant_id,
            audit_ref=rows[1]["audit_ref"],
        )
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('app.current_tenant_id', :t, true)"),
                {"t": str(tenant_id)},
            )
            await connection.execute(
                text(
                    """
                    UPDATE public.trust_access_log
                    SET updated_at = now() - interval '1 hour'
                    WHERE tenant_id = :t AND event_type = 'issuance'
                    """
                ),
                {"t": str(tenant_id)},
            )

        result = await reconcile_stale_trust_issuance_states(
            tenant_id=tenant_id,
            stale_before=datetime.now(timezone.utc) - timedelta(minutes=5),
            batch_size=10,
        )
        assert result == {
            "authorized_to_failed": 1,
            "signing_to_unknown": 1,
            "signature_known_to_issued": 0,
            "invalid_signature_known_refused": 0,
        }
        states = sorted(
            row["issuance_state"] for row in await _issuance_rows(engine, tenant_id)
        )
        assert states == ["failed", "signature_outcome_unknown"], states
        print("\nc16_reconciled_nonterminal_states=" + str(sum(result.values())))
    finally:
        await engine.dispose()


def test_c16_reconciler_is_registered_in_beat_schedule() -> None:
    schedule = build_beat_schedule()
    entry = schedule["b25-p13-trust-issuance-reconciler"]
    assert entry["task"] == (
        "app.tasks.maintenance.reconcile_trust_issuance_all_tenants"
    )
    observations = ["scheduled", "bounded_interval", "bounded_batch"]
    assert float(entry["schedule"]) <= 60.0
    assert entry["kwargs"]["stale_seconds"] == 900
    assert entry["kwargs"]["batch_size"] == 100
    print("\nc16_reconciler_schedule_observations=" + str(len(observations)))
