"""C12 authority-class, recovery-liveness, and session-boundary proofs."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from app.bayesian.dispatch_outbox import publish_due_recovery_rows_sync
from app.bayesian.dispatch_authority import (
    BAYESIAN_FIT_EXECUTION_TASK,
    BayesianDispatchClaim,
    BayesianDispatchLease,
    BayesianWorkerClaimAuthority,
    DispatchClaimOutcome,
    claim_fit_dispatch_sync,
    dispatch_payload_hash,
    register_worker_process_authority_sync,
)
from app.bayesian.fit_execution import (
    _build_sampler_input,
    _load_fit_for_execution,
    _replan_superseded_policy_bundle,
)
from app.core.secrets import get_database_url, get_migration_database_url
from app.db.dsn import to_sync_postgres_dsn
from app.inference_policy_registry import (
    CURRENT_POLICY_BUNDLE_HASH,
    current_policy_tuple,
)
from tests.test_b24_p9_postgres_runtime import (
    END,
    START,
    _claim_test_dispatch_lease,
    _set_tenant_context,
)
from tests.trust.test_b25_p13_c10_policy_transport_physics import (
    _observed_input,
    _seed_old_policy_fit,
)


PRIVILEGED_SESSION_SETTINGS = (
    "app.b24_recovery_reconciler",
    "app.b24_dispatch_claim_access",
    "app.b24_worker_authority_access",
    "app.b24_claim_capability_digest",
    "app.b24_fit_resolution_id",
)


db_proof = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_C12_DB_PROOF") != "1",
    reason="B2.5-P13 C12 PostgreSQL proof is opt-in locally",
)


def _engine(url: str):
    return create_engine(to_sync_postgres_dsn(url), poolclass=NullPool, future=True)


def _runtime_urls() -> tuple[str, str, str]:
    worker = get_database_url()
    migration = get_migration_database_url()
    app_user = make_url(worker).set(
        username="app_user", password="app_user"
    ).render_as_string(hide_password=False)
    return worker, app_user, migration


def _seed_fit(conn, *, tenant_id: UUID, fit_id: UUID, suffix: str) -> None:
    _set_tenant_context(conn, tenant_id)
    policy = current_policy_tuple()
    conn.execute(
        text(
            """
            INSERT INTO public.bayesian_model_fits (
                tenant_id, id, model_type, model_version,
                source_window_start, source_window_end, source_snapshot_hash,
                source_read_started_at, source_read_completed_at,
                status, eligibility_status, data_completeness_status,
                fallback_applied, max_runtime_seconds, max_samples, max_cores,
                inference_profile_version, runtime_policy_version,
                sampling_policy_version, diagnostic_policy_version,
                policy_bundle_hash, authorized_chains,
                authorized_posterior_draws_total
            ) VALUES (
                :tenant_id, :fit_id, 'bayesian_attribution_confidence',
                'b24-p6-real-fit-v1', :start, :end, :snapshot,
                now(), now(), 'queued', 'eligible', 'complete', false,
                240, 8000, 1, :profile, :runtime, :sampling, :diagnostic,
                :bundle, 4, 4000
            )
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "fit_id": str(fit_id),
            "start": START,
            "end": END,
            "snapshot": suffix[0] * 64,
            "profile": policy["inference_profile_version"],
            "runtime": policy["runtime_policy_version"],
            "sampling": policy["sampling_policy_version"],
            "diagnostic": policy["diagnostic_policy_version"],
            "bundle": CURRENT_POLICY_BUNDLE_HASH,
        },
    )


def _seed_dispatch(
    conn,
    *,
    tenant_id: UUID,
    fit_id: UUID,
    status: str = "pending",
    recovery_due: bool = False,
) -> UUID:
    dispatch_id = uuid4()
    _set_tenant_context(conn, tenant_id)
    conn.execute(
        text(
            """
            INSERT INTO public.b24_fit_dispatch_outbox (
                tenant_id, id, fit_id, dispatch_key, task_name, attempt_id,
                payload_hash, status, next_attempt_at, next_recovery_at,
                lease_expires_at, assignment_reason
            ) VALUES (
                :tenant_id, :dispatch_id, :fit_id, :dispatch_key,
                'app.tasks.bayesian.execute_fit_intent', :attempt_id,
                :payload_hash, :status, now(),
                CASE WHEN :recovery_due THEN now() - interval '1 minute'
                     ELSE now() + interval '1 hour' END,
                CASE WHEN :recovery_due THEN now() - interval '1 minute'
                     ELSE NULL END,
                CASE WHEN :recovery_due THEN 'c12_recovery_probe'
                     ELSE NULL END
            )
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "dispatch_id": str(dispatch_id),
            "fit_id": str(fit_id),
            "dispatch_key": f"c12:{tenant_id}:{fit_id}:{dispatch_id}",
            "attempt_id": str(uuid4()),
            "payload_hash": "a" * 64,
            "status": status,
            "recovery_due": recovery_due,
        },
    )
    return dispatch_id


@pytest.mark.integration
@db_proof
def test_c12_catalog_has_no_self_issued_privileged_policy() -> None:
    _, _, migration_url = _runtime_urls()
    migration = _engine(migration_url)
    try:
        with migration.begin() as conn:
            policies = conn.execute(
                text(
                    """
                    SELECT tablename, policyname,
                           COALESCE(qual, '') || ' ' || COALESCE(with_check, '')
                               AS expression
                    FROM pg_policies
                    WHERE schemaname = 'public'
                    """
                )
            ).mappings()
            policy_rows = list(policies)
            for setting in PRIVILEGED_SESSION_SETTINGS:
                assert not [
                    row for row in policy_rows if setting in row["expression"]
                ], setting

            internal = {
                row["policyname"]: row
                for row in policy_rows
                if row["policyname"].startswith("c12_")
            }
            assert {
                "c12_dispatch_internal_select",
                "c12_dispatch_internal_update",
                "c12_recovery_internal_select",
                "c12_recovery_internal_insert",
                "c12_recovery_internal_update",
                "c12_worker_authority_internal_select",
                "c12_worker_authority_internal_insert",
                "c12_worker_authority_internal_update",
            } <= set(internal)
            for row in internal.values():
                expression = row["expression"].lower()
                assert "current_user" in expression
                assert "session_user" in expression

            direct_grants = conn.execute(
                text(
                    """
                    SELECT grantee, privilege_type
                    FROM information_schema.role_table_grants
                    WHERE table_schema = 'public'
                      AND table_name = 'b24_worker_process_authority'
                      AND grantee IN (
                          'app_user', 'app_worker', 'app_dispatch_publisher',
                          'app_rw', 'app_ro'
                      )
                    """
                )
            ).all()
            assert direct_grants == []
    finally:
        migration.dispose()


@pytest.mark.integration
@db_proof
def test_c12_arbitrary_session_state_has_no_cross_tenant_consequence(
    test_tenant_pair,
) -> None:
    worker_url, app_user_url, _ = _runtime_urls()
    worker = _engine(worker_url)
    app_user = _engine(app_user_url)
    tenant_a, tenant_b = test_tenant_pair
    fit_a, fit_b = uuid4(), uuid4()
    try:
        with worker.begin() as conn:
            _seed_fit(conn, tenant_id=tenant_a, fit_id=fit_a, suffix="a")
            _seed_dispatch(conn, tenant_id=tenant_a, fit_id=fit_a)
        with worker.begin() as conn:
            _seed_fit(conn, tenant_id=tenant_b, fit_id=fit_b, suffix="b")
            dispatch_b = _seed_dispatch(
                conn, tenant_id=tenant_b, fit_id=fit_b
            )

        with worker.begin() as conn:
            _set_tenant_context(conn, tenant_a)
            for setting in PRIVILEGED_SESSION_SETTINGS[:-1]:
                conn.execute(
                    text("SELECT set_config(:setting, :value, true)"),
                    {"setting": setting, "value": "f" * 64 if setting.endswith("digest") else "on"},
                )
            conn.execute(
                text("SELECT set_config('app.b24_fit_resolution_id', :fit, true)"),
                {"fit": str(fit_b)},
            )
            wrong_dispatches = conn.scalar(
                text(
                    """
                    SELECT count(*) FROM public.b24_fit_dispatch_outbox
                    WHERE tenant_id = :tenant_b
                    """
                ),
                {"tenant_b": str(tenant_b)},
            )
            wrong_fits = conn.scalar(
                text(
                    """
                    SELECT count(*) FROM public.bayesian_model_fits
                    WHERE tenant_id = :tenant_b AND id = :fit_b
                    """
                ),
                {"tenant_b": str(tenant_b), "fit_b": str(fit_b)},
            )
            update = conn.execute(
                text(
                    """
                    UPDATE public.b24_fit_dispatch_outbox
                    SET last_error = 'c12-hostile'
                    WHERE tenant_id = :tenant_b AND id = :dispatch_b
                    """
                ),
                {"tenant_b": str(tenant_b), "dispatch_b": str(dispatch_b)},
            )
            assert int(wrong_dispatches or 0) == 0
            assert int(wrong_fits or 0) == 0
            assert update.rowcount == 0

        with app_user.begin() as conn:
            conn.execute(
                text("SELECT set_config('app.b24_worker_authority_access','on',true)")
            )
            with pytest.raises(DBAPIError, match="permission denied"):
                conn.execute(
                    text(
                        """
                        INSERT INTO public.b24_worker_process_authority (
                            generation_id, pid, parent_pid, topology_fingerprint,
                            process_token_digest, status, registered_at, expires_at
                        ) VALUES (
                            :generation, 9001, 1, :fingerprint, :digest,
                            'active', now(), now() + interval '1 hour'
                        )
                        """
                    ),
                    {
                        "generation": f"c12-hostile-{uuid4().hex}",
                        "fingerprint": "a" * 64,
                        "digest": "b" * 64,
                    },
                )
    finally:
        app_user.dispose()
        worker.dispose()


@pytest.mark.integration
@db_proof
def test_c12_session_residue_is_inert_and_worker_engine_is_nonpooled(
    test_tenant_pair,
) -> None:
    worker_url, _, _ = _runtime_urls()
    worker = _engine(worker_url)
    tenant_a, tenant_b = test_tenant_pair
    fit_a, fit_b = uuid4(), uuid4()
    try:
        with worker.begin() as conn:
            _seed_fit(conn, tenant_id=tenant_a, fit_id=fit_a, suffix="c")
        with worker.begin() as conn:
            _seed_fit(conn, tenant_id=tenant_b, fit_id=fit_b, suffix="d")

        with worker.connect() as conn:
            first_pid = conn.scalar(text("SELECT pg_backend_pid()"))
            conn.execute(text("SET app.b24_recovery_reconciler = 'on'"))
            conn.commit()
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_a)},
            )
            assert (
                conn.scalar(
                    text(
                        """
                        SELECT count(*) FROM public.bayesian_model_fits
                        WHERE tenant_id = :tenant_b
                        """
                    ),
                    {"tenant_b": str(tenant_b)},
                )
                == 0
            )
            conn.rollback()

        with worker.connect() as conn:
            second_pid = conn.scalar(text("SELECT pg_backend_pid()"))
            residue = conn.scalar(
                text("SELECT current_setting('app.b24_recovery_reconciler', true)")
            )
            assert second_pid != first_pid
            assert residue in (None, "")
    finally:
        worker.dispose()


@pytest.mark.integration
@db_proof
def test_c12_bounded_claim_and_recovery_operations_remain_live(
    test_tenant_pair,
) -> None:
    worker_url, _, _ = _runtime_urls()
    worker = _engine(worker_url)
    tenant_a, _ = test_tenant_pair
    claim_fit_id = uuid4()
    recovery_fit_id = uuid4()
    published: list[UUID] = []
    try:
        with worker.begin() as conn:
            _seed_fit(
                conn, tenant_id=tenant_a, fit_id=claim_fit_id, suffix="e"
            )
            lease = _claim_test_dispatch_lease(
                conn,
                tenant_id=tenant_a,
                fit_id=claim_fit_id,
                generation_id=f"c12-claim-{uuid4().hex}",
                assignment_reason="c12_claim_liveness",
            )
            assert lease.tenant_id == tenant_a
            assert lease.fit_id == claim_fit_id

        with worker.begin() as conn:
            _seed_fit(
                conn, tenant_id=tenant_a, fit_id=recovery_fit_id, suffix="f"
            )
            recovery_dispatch_id = _seed_dispatch(
                conn,
                tenant_id=tenant_a,
                fit_id=recovery_fit_id,
                status="dispatched",
                recovery_due=True,
            )
            conn.execute(
                text(
                    """
                    UPDATE public.b24_fit_dispatch_outbox
                    SET next_recovery_at = now() - interval '100 years',
                        lease_expires_at = now() - interval '100 years'
                    WHERE tenant_id = :tenant_id AND id = :dispatch_id
                    """
                ),
                {
                    "tenant_id": str(tenant_a),
                    "dispatch_id": str(recovery_dispatch_id),
                },
            )

        with worker.begin() as conn:
            created = conn.scalar(
                text("SELECT public.b24_create_fit_recovery_wakeups(10)")
            )
            assert int(created or 0) >= 1
            _set_tenant_context(conn, tenant_a)
            # The reconciler is intentionally global. Earlier suites may have
            # legitimate due rows, so make this witness deterministically first
            # instead of assuming a clean database or consuming every backlog.
            conn.execute(
                text(
                    """
                    UPDATE public.b24_fit_recovery_outbox
                    SET created_at = now() - interval '100 years'
                    WHERE tenant_id = :tenant_id
                      AND dispatch_id = :dispatch_id
                    """
                ),
                {
                    "tenant_id": str(tenant_a),
                    "dispatch_id": str(recovery_dispatch_id),
                },
            )

        def _capture(row) -> str:
            published.append(row.dispatch_id)
            return f"c12-recovery-{row.dispatch_id}"

        with worker.begin() as conn:
            rows = publish_due_recovery_rows_sync(
                conn,
                publish=_capture,
                batch_size=10,
                stale_publishing_seconds=1,
            )
            assert recovery_dispatch_id in {row.dispatch_id for row in rows}
            assert recovery_dispatch_id in published

        with worker.begin() as conn:
            _set_tenant_context(conn, tenant_a)
            state = conn.execute(
                text(
                    """
                    SELECT recovery.status, dispatch.status
                    FROM public.b24_fit_recovery_outbox recovery
                    JOIN public.b24_fit_dispatch_outbox dispatch
                      ON dispatch.tenant_id = recovery.tenant_id
                     AND dispatch.id = recovery.dispatch_id
                    WHERE recovery.tenant_id = :tenant_id
                      AND recovery.dispatch_id = :dispatch_id
                    """
                ),
                {
                    "tenant_id": str(tenant_a),
                    "dispatch_id": str(recovery_dispatch_id),
                },
            ).one()
            assert tuple(state) == ("published", "dispatched")
    finally:
        worker.dispose()


@pytest.mark.integration
@db_proof
def test_c12_ordinary_roles_cannot_reach_privilege_transitively() -> None:
    worker_url, app_user_url, _ = _runtime_urls()
    for url in (worker_url, app_user_url):
        engine = _engine(url)
        try:
            with engine.begin() as conn:
                principal = str(conn.scalar(text("SELECT session_user")))
                for privileged_role in (
                    "migration_owner",
                    "app_dispatch_publisher",
                ):
                    assert not conn.scalar(
                        text("SELECT pg_has_role(:role, 'MEMBER')"),
                        {"role": privileged_role},
                    ), (principal, privileged_role)
                    with pytest.raises(DBAPIError, match="permission denied"):
                        with conn.begin_nested():
                            conn.execute(text(f"SET ROLE {privileged_role}"))
        finally:
            engine.dispose()


@pytest.mark.integration
@db_proof
def test_c12_competing_workers_preserve_one_producing_regime(
    test_tenant_pair,
) -> None:
    """Concurrent delivery yields one claimant and one attributable regime."""

    worker_url, _, _ = _runtime_urls()
    worker = _engine(worker_url)
    tenant_id, _ = test_tenant_pair
    fit_id = uuid4()
    dispatch_id = uuid4()
    attempt_id = uuid4()
    generation_id = f"c12-race-{uuid4().hex[:16]}"
    process_token = f"c12-race-token-{uuid4().hex}"
    authority = BayesianWorkerClaimAuthority(
        generation_id=generation_id,
        pid=os.getpid(),
        process_token=process_token,
    )
    claim = BayesianDispatchClaim(
        dispatch_id=dispatch_id,
        fit_id=fit_id,
        task_name=BAYESIAN_FIT_EXECUTION_TASK,
        attempt_id=attempt_id,
        payload_hash=dispatch_payload_hash(fit_id=fit_id),
        recovery_generation=0,
    )
    try:
        _seed_old_policy_fit(worker, tenant_id=tenant_id, fit_id=fit_id)
        with worker.begin() as conn:
            register_worker_process_authority_sync(
                conn,
                generation_id=generation_id,
                pid=os.getpid(),
                parent_pid=os.getppid(),
                topology_fingerprint="c" * 64,
                process_token=process_token,
            )
            _set_tenant_context(conn, tenant_id)
            conn.execute(
                text(
                    """
                    INSERT INTO public.b24_fit_dispatch_outbox (
                        tenant_id, id, fit_id, dispatch_key, task_name,
                        attempt_id, payload_hash, assigned_worker_generation,
                        assignment_generation, assignment_expires_at,
                        assignment_reason, status, next_attempt_at,
                        next_recovery_at
                    ) VALUES (
                        :tenant_id, :dispatch_id, :fit_id, :dispatch_key,
                        :task_name, :attempt_id, :payload_hash, :generation,
                        1, now() + interval '10 minutes', 'c12_race',
                        'dispatched', now(), now() + interval '1 hour'
                    )
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "dispatch_id": str(dispatch_id),
                    "fit_id": str(fit_id),
                    "dispatch_key": f"c12-race:{dispatch_id}",
                    "task_name": BAYESIAN_FIT_EXECUTION_TASK,
                    "attempt_id": str(attempt_id),
                    "payload_hash": claim.payload_hash,
                    "generation": generation_id,
                },
            )

        barrier = Barrier(2)

        def _compete():
            with worker.begin() as conn:
                barrier.wait(timeout=10)
                return claim_fit_dispatch_sync(
                    conn,
                    claim=claim,
                    worker_authority=authority,
                    lease_seconds=300,
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: _compete(), range(2)))

        leases = [row for row in outcomes if isinstance(row, BayesianDispatchLease)]
        refusals = [row for row in outcomes if isinstance(row, DispatchClaimOutcome)]
        assert len(leases) == 1
        assert refusals == [DispatchClaimOutcome.ACTIVE_LEASE]

        lease = leases[0]
        with worker.begin() as conn:
            row = _load_fit_for_execution(
                conn,
                tenant_id=tenant_id,
                fit_id=fit_id,
                dispatch_lease=lease,
            )
            assert row is not None and row["policy_bundle_hash"] == "1" * 64
            replanned = _replan_superseded_policy_bundle(
                conn, tenant_id=tenant_id, fit_id=fit_id
            )
            assert replanned is not None
            row.update(replanned)
            sampler_input = _build_sampler_input(
                row,
                execution_id=f"c12-race-{uuid4().hex}",
                observed_input=_observed_input(tenant_id),
            )

        with worker.begin() as conn:
            _set_tenant_context(conn, tenant_id)
            lineage = conn.execute(
                text(
                    """
                    SELECT from_policy_bundle_hash, to_policy_bundle_hash,
                           transition_sequence
                    FROM public.b24_fit_policy_replan_lineage
                    WHERE tenant_id = :tenant_id AND fit_id = :fit_id
                    ORDER BY transition_sequence
                    """
                ),
                {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
            ).mappings().all()
        assert len(lineage) == 1
        assert lineage[0]["from_policy_bundle_hash"] == "1" * 64
        assert lineage[0]["to_policy_bundle_hash"] == CURRENT_POLICY_BUNDLE_HASH
        assert replanned["policy_bundle_hash"] == CURRENT_POLICY_BUNDLE_HASH
        assert replanned["authorized_chains"] == 4
        assert sampler_input["max_samples"] == 8000
        assert sampler_input["max_cores"] == 1
    finally:
        worker.dispose()
