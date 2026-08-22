"""C7 behavioural conservation proofs against a real PostgreSQL instance.

Every test here executes production SQL, production triggers, or the production
planner task against a live database. None of them assert on source text. They
exist because the C6 proof model closed behavioural claims -- privilege
convergence, planner liveness, backlog conservation, invalidation coverage --
with in-memory string substitutions fed to text validators, so a green tree
coexisted with reproducible runtime defects.

The static half of C7 lives in scripts/ci/validate_b25_p13_c7_closure.py and
refuses to claim any obligation named here.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, InternalError, ProgrammingError

from app.bayesian.fit_planner import MAX_WAIT_SECONDS, QUIET_PERIOD_SECONDS
from app.core.secrets import get_database_url
from app.db.dsn import to_sync_postgres_dsn


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_C7_DB_PROOF") != "1",
    reason="B2.5-P13 C7 conservation physics proofs are opt-in locally",
)

REPO_ROOT = Path(__file__).resolve().parents[3]
WINDOW_START = datetime(2026, 7, 1, tzinfo=timezone.utc)
WINDOW_END = WINDOW_START + timedelta(days=31)

# Governed terminal fit authority, mirrored from the C7 migration. The static
# gate proves this list equals the migration's and the read model's derived set;
# this suite proves the database actually enforces every entry.
GOVERNED_FIT_COLUMNS = (
    "id", "tenant_id", "model_type", "model_version", "source_window_start",
    "source_window_end", "source_snapshot_hash", "status",
    "data_completeness_status", "fallback_applied", "fallback_reason",
    "created_at", "completed_at", "updated_at", "diagnostic_status",
    "diagnostic_failure_reason", "credible_interval_status", "confidence_bucket",
    "confidence_bucket_reason", "confidence_policy_version",
    "confidence_semantics_version", "confidence_deterministic_revenue_minor",
    "confidence_deterministic_row_count", "confidence_match_verdict_count",
    "confidence_currency_count", "confidence_classified_at",
    "confidence_evidence_snapshot_hash", "source_read_started_at",
    "source_read_completed_at", "artifact_ref", "artifact_hash",
)

# A legal replacement value per governed column, so the mutation matrix proves
# the guard fires on a genuine change rather than on a type error.
_MUTATIONS: dict[str, str] = {
    "id": "gen_random_uuid()",
    "tenant_id": "gen_random_uuid()",
    "model_type": "'mutated_model'",
    "model_version": "'mutated-version'",
    "source_window_start": "timestamptz '2020-01-01'",
    "source_window_end": "timestamptz '2030-01-01'",
    "source_snapshot_hash": "repeat('b', 64)",
    "status": "'cancelled'",
    # Must differ from the seeded value or IS DISTINCT FROM is false and the
    # guard correctly does nothing, which would read as a coverage gap.
    "data_completeness_status": "'partial'",
    "fallback_applied": "true",
    "fallback_reason": "'mutated_reason'",
    "created_at": "now() + interval '1 day'",
    "completed_at": "now() + interval '1 day'",
    "updated_at": "now() + interval '1 day'",
    "diagnostic_status": "'passed'",
    "diagnostic_failure_reason": "'mutated'",
    "credible_interval_status": "'available'",
    "confidence_bucket": "'HIGH'",
    "confidence_bucket_reason": "'MUTATED'",
    "confidence_policy_version": "'mutated-policy'",
    "confidence_semantics_version": "'mutated-semantics'",
    "confidence_deterministic_revenue_minor": "999999",
    "confidence_deterministic_row_count": "999",
    "confidence_match_verdict_count": "999",
    "confidence_currency_count": "9",
    # Evidence timestamps are also guarded by temporal plausibility, which
    # refuses future values ahead of the terminal guard. A past value keeps
    # the mutation genuine and the terminal guard the thing being measured.
    "confidence_classified_at": "now() - interval '1 day'",
    "confidence_evidence_snapshot_hash": "repeat('c', 64)",
    "source_read_started_at": "now() - interval '1 day'",
    "source_read_completed_at": "now() - interval '1 day'",
    "artifact_ref": "'mutated/ref'",
    "artifact_hash": "repeat('d', 64)",
}

# Which guard must refuse each column. Identity is protected by the dispatch
# fence, which fires ahead of the terminal-truth trigger and binds every fit,
# not only terminal ones; everything else is terminal-truth authority. Asserting
# the specific guard stops this matrix from passing because some unrelated
# constraint happened to reject the statement.
_EXPECTED_GUARD: dict[str, str] = {
    column: "b24_terminal_fit_truth_immutable" for column in GOVERNED_FIT_COLUMNS
}
_EXPECTED_GUARD["id"] = "b24_dispatch_immutable_fit_authority"
_EXPECTED_GUARD["tenant_id"] = "b24_dispatch_immutable_fit_authority"


def _worker_url() -> str:
    """The suite runs on the dedicated worker login, as the planner does."""

    return to_sync_postgres_dsn(get_database_url())


def _url_as(username: str, password: str) -> str:
    return to_sync_postgres_dsn(
        make_url(get_database_url())
        .set(username=username, password=password)
        .render_as_string(hide_password=False)
    )


def _engine(url: str):
    return create_engine(url, pool_pre_ping=True, future=True)


def _bind_tenant(conn, tenant_id: uuid.UUID) -> None:
    conn.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant, false)"),
        {"tenant": str(tenant_id)},
    )


def _new_tenant(conn, label: str) -> uuid.UUID:
    tenant_id = uuid.uuid4()
    conn.execute(
        text(
            "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
            " VALUES (:id, :name, :hash, :email)"
        ),
        {
            "id": str(tenant_id),
            "name": f"c7-{label}-{tenant_id.hex[:8]}",
            "hash": uuid.uuid4().hex,
            "email": f"c7-{tenant_id.hex[:8]}@example.test",
        },
    )
    _bind_tenant(conn, tenant_id)
    return tenant_id


def _append_dirty(conn, tenant_id: uuid.UUID, *, group: str, age_seconds: int) -> None:
    _bind_tenant(conn, tenant_id)
    conn.execute(
        text(
            "INSERT INTO public.b24_dirty_events (tenant_id, model_type,"
            " model_version, source_window_start, source_window_end, dirty_reason,"
            " source_family, observed_at, status) VALUES (:tenant, 'mmm', :version,"
            " :ws, :we, 'c7_conservation_probe', 'b23_revenue_events',"
            " now() - make_interval(secs => :age), 'pending')"
        ),
        {
            "tenant": str(tenant_id),
            "version": f"c7-{group}",
            "ws": WINDOW_START,
            "we": WINDOW_END,
            "age": age_seconds,
        },
    )


def _wakeup(conn, tenant_id: uuid.UUID):
    return conn.execute(
        text(
            "SELECT status, wakeup_revision, next_eligible_at"
            " FROM public.b24_fit_planner_wakeups WHERE tenant_id = :tenant"
        ),
        {"tenant": str(tenant_id)},
    ).all()


def _unplanned(conn, tenant_id: uuid.UUID) -> int:
    _bind_tenant(conn, tenant_id)
    return int(
        conn.execute(
            text(
                "SELECT count(*) FROM public.b24_dirty_events WHERE tenant_id = :tenant"
                " AND status IN ('pending', 'authority_retry_ready')"
            ),
            {"tenant": str(tenant_id)},
        ).scalar_one()
    )


def _lease(conn, owner: str, tenant_id: uuid.UUID) -> int | None:
    rows = conn.execute(
        text(
            "SELECT tenant_id, wakeup_revision FROM"
            " public.b24_due_fit_planner_tenants(:owner, 100)"
        ),
        {"owner": owner},
    ).all()
    for row in rows:
        if str(row[0]) == str(tenant_id):
            return int(row[1])
    return None


def _ack(
    conn,
    tenant_id: uuid.UUID,
    owner: str,
    revision: int | None,
    *,
    succeeded: bool = True,
    quiet_period: int = QUIET_PERIOD_SECONDS,
) -> str:
    _bind_tenant(conn, tenant_id)
    return str(
        conn.execute(
            text(
                "SELECT public.b24_complete_fit_planner_wakeup("
                ":tenant, :owner, :revision, :succeeded, :quiet, :max_wait)"
            ),
            {
                "tenant": str(tenant_id),
                "owner": owner,
                "revision": revision,
                "succeeded": succeeded,
                "quiet": quiet_period,
                "max_wait": MAX_WAIT_SECONDS,
            },
        ).scalar_one()
    )



def _residual(conn, tenant_id: uuid.UUID, quiet_period: int):
    """Read the tenant's residual planning obligation as the planner sees it."""

    _bind_tenant(conn, tenant_id)
    return conn.execute(
        text(
            "SELECT eligible_group_count, next_eligible_at FROM"
            " public.b24_fit_planner_residual_obligation(:tenant, :quiet, :max_wait)"
        ),
        {
            "tenant": str(tenant_id),
            "quiet": quiet_period,
            "max_wait": MAX_WAIT_SECONDS,
        },
    ).one()


def _bounded_pass(conn, tenant_id: uuid.UUID, *, limit: int, quiet_period: int) -> int:
    """One bounded planner pass, using the production debounce arithmetic."""

    _bind_tenant(conn, tenant_id)
    result = conn.execute(
        text(
            "UPDATE public.b24_dirty_events SET status = 'leased',"
            " planner_owner = 'c7-probe', leased_at = now(),"
            " lease_expires_at = now() + interval '300 seconds'"
            " WHERE tenant_id = :tenant AND status = 'pending'"
            " AND model_version IN ("
            "   SELECT model_version FROM public.b24_dirty_events"
            "   WHERE tenant_id = :tenant AND status = 'pending'"
            "   GROUP BY model_type, model_version, source_window_start,"
            "            source_window_end, source_snapshot_hash"
            "   HAVING max(observed_at) <= now() - make_interval(secs => :quiet)"
            "      OR min(observed_at) <= now() - make_interval(secs => :stale)"
            "   ORDER BY min(observed_at) LIMIT :limit)"
        ),
        {
            "tenant": str(tenant_id),
            "quiet": quiet_period,
            "stale": max(quiet_period, MAX_WAIT_SECONDS),
            "limit": limit,
        },
    )
    return int(result.rowcount or 0)



def _migration_engine():
    """Seeding identity. The dispatch fence is owned by the migration principal."""

    url = os.environ.get("MIGRATION_DATABASE_URL")
    if not url:
        url = _url_as("migration_owner", "migration_owner")
    return _engine(to_sync_postgres_dsn(url))


_FENCED = (
    ("public.bayesian_model_fits", "trg_b24_dispatch_fence_fits"),
    ("public.bayesian_artifacts", "trg_b24_dispatch_fence_artifacts"),
)


def _seed_fit(tenant_id: uuid.UUID, *, status: str, snapshot_hash: str) -> uuid.UUID:
    """Create one fit in a state the dispatch fence will not admit directly.

    The fence exists to stop a worker minting fit authority without a lease; it
    is not the guard under test here, so it is suspended for the insert and
    restored immediately. The terminal-truth and lifecycle triggers stay armed
    throughout, which is the whole point of the experiment.
    """

    fit_id = uuid.uuid4()
    engine = _migration_engine()
    try:
        with engine.begin() as conn:
            _bind_tenant(conn, tenant_id)
            # DDL is transactional here: an abort restores the fence with the
            # rest of the statement, so no restoration handler is needed and a
            # failing insert reports its own cause instead of a masked one.
            for table, trigger in _FENCED:
                conn.execute(text(f"ALTER TABLE {table} DISABLE TRIGGER {trigger}"))
            if True:
                conn.execute(
                    text(
                        "INSERT INTO public.bayesian_model_fits (id, tenant_id,"
                        " model_type, model_version, source_window_start,"
                        " source_window_end, source_snapshot_hash, status,"
                        " data_completeness_status, created_at, completed_at)"
                        " VALUES (:id, :tenant, 'mmm', 'c7-fit', :ws, :we, :hash,"
                        " :status, 'complete', now(), now())"
                    ),
                    {
                        "id": str(fit_id),
                        "tenant": str(tenant_id),
                        "ws": WINDOW_START,
                        "we": WINDOW_END,
                        "hash": snapshot_hash,
                        "status": status,
                    },
                )
            for table, trigger in _FENCED:
                conn.execute(text(f"ALTER TABLE {table} ENABLE TRIGGER {trigger}"))
    finally:
        engine.dispose()
    return fit_id


def _seed_artifact(tenant_id: uuid.UUID, fit_id: uuid.UUID) -> uuid.UUID:
    """Create one active artifact that satisfies the real B2.4-P8 contract."""

    artifact_id = uuid.uuid4()
    payload = b"c7-posterior-summary"
    # ck_bayesian_artifacts_internal_uri pins the exact reference shape.
    reference = (
        f"b24://artifact/{tenant_id}/{fit_id}/posterior_summary/"
        f"{artifact_id.hex[:12]}"
    )
    engine = _migration_engine()
    try:
        with engine.begin() as conn:
            _bind_tenant(conn, tenant_id)
            for table, trigger in _FENCED:
                conn.execute(text(f"ALTER TABLE {table} DISABLE TRIGGER {trigger}"))
            conn.execute(
                text(
                    "INSERT INTO public.bayesian_artifacts (id, tenant_id, fit_id,"
                    " artifact_type, artifact_ref, artifact_hash, storage_backend,"
                    " artifact_uri_internal, artifact_size_bytes, retention_class,"
                    " expires_at, payload_bytes, payload_byte_count,"
                    " lifecycle_status) VALUES (:id, :tenant, :fit,"
                    " 'posterior_summary', :ref, :hash, 'postgres', :ref, :size,"
                    " 'standard', now() + interval '30 days', :payload, :size,"
                    " 'active')"
                ),
                {
                    "id": str(artifact_id),
                    "tenant": str(tenant_id),
                    "fit": str(fit_id),
                    "ref": reference,
                    "hash": "f" * 64,
                    "size": len(payload),
                    "payload": payload,
                },
            )
            for table, trigger in _FENCED:
                conn.execute(text(f"ALTER TABLE {table} ENABLE TRIGGER {trigger}"))
    finally:
        engine.dispose()
    return artifact_id



# ---------------------------------------------------------------------------
# BEHAVIORAL: upgrade-safe least privilege (C7-B)
# ---------------------------------------------------------------------------
def test_c7_reprovision_cannot_restore_runtime_authority() -> None:
    """Re-running the real provisioner against a hardened database is monotonic."""

    admin_dsn = os.environ["SKELDIR_B25_P13_C7_ADMIN_DSN"]
    database_name = make_url(get_database_url()).database
    engine = _engine(_worker_url())
    try:
        with engine.connect() as conn:
            before = bool(
                conn.execute(
                    text("SELECT has_schema_privilege('app_user','public','CREATE')")
                ).scalar_one()
            )
        assert before is False, "database under proof is not at the hardened head"

        completed = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/database/prepare_migration_authority_boundary.py"),
                "--admin-dsn", admin_dsn,
                "--database-name", str(database_name),
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "runtime_schema_hardening_applied=true" in completed.stdout
        assert "authority_monotonic=true" in completed.stdout

        with engine.connect() as conn:
            after = bool(
                conn.execute(
                    text("SELECT has_schema_privilege('app_user','public','CREATE')")
                ).scalar_one()
            )
            usage = bool(
                conn.execute(
                    text("SELECT has_schema_privilege('app_user','public','USAGE')")
                ).scalar_one()
            )
        # The exact reproduction Report 40 recorded: true -> false -> true.
        # It must now terminate at false.
        assert after is False, "reprovisioning restored revoked runtime CREATE"
        assert usage is True, "reprovisioning removed required runtime USAGE"
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# BEHAVIORAL: worker authority is a runtime identity property (C7-C)
# ---------------------------------------------------------------------------
def test_c7_worker_functions_reject_non_worker_identity() -> None:
    """The API principal cannot drive the planner, and cannot become the worker."""

    api_engine = _engine(_url_as("app_user", "app_user"))
    try:
        with api_engine.connect() as conn:
            with pytest.raises(DBAPIError) as excinfo:
                conn.execute(
                    text(
                        "SELECT tenant_id FROM"
                        " public.b24_due_fit_planner_tenants('celery:intruder', 1)"
                    )
                )
            assert "b24_due_fit_planner_tenants" in str(excinfo.value) or (
                "permission denied" in str(excinfo.value).lower()
            )
        # The directive's named experiment: no runtime principal may assume the
        # worker role, whether by inheritance or by explicit SET ROLE.
        for principal in ("app_user", "app_rw", "app_ro"):
            with api_engine.connect() as conn:
                inherits = bool(
                    conn.execute(
                        text("SELECT pg_has_role(:role, 'app_worker', 'USAGE')"),
                        {"role": principal},
                    ).scalar_one()
                )
                member = bool(
                    conn.execute(
                        text("SELECT pg_has_role(:role, 'app_worker', 'MEMBER')"),
                        {"role": principal},
                    ).scalar_one()
                )
                assert not inherits, f"{principal} inherits app_worker authority"
                assert not member, f"{principal} can SET ROLE app_worker"
        with api_engine.connect() as conn:
            with pytest.raises(DBAPIError):
                conn.execute(text("SET ROLE app_worker"))
    finally:
        api_engine.dispose()


# ---------------------------------------------------------------------------
# BEHAVIORAL: source-change causality (C7-D) and atomicity (C7-E)
# ---------------------------------------------------------------------------
def _seed_conversion_event(conn, tenant_id: uuid.UUID, index: int) -> uuid.UUID:
    event_id = uuid.uuid4()
    channel = f"c7_ch_{tenant_id.hex[:6]}_{index}"
    conn.execute(
        text(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES (:code, 'b25_p13_c7', true, :label,"
            " 'active') ON CONFLICT (code) DO NOTHING"
        ),
        {"code": channel, "label": f"C7 {index}"},
    )
    conn.execute(
        text(
            "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
            " correlation_id, session_id, revenue_cents, raw_payload,"
            " idempotency_key, event_type, channel, campaign_id,"
            " conversion_value_cents, currency, event_timestamp, processed_at,"
            " processing_status) VALUES (:id, :tenant, :at, :corr, :sess, 1000,"
            " '{}'::jsonb, :key, 'conversion', :channel, 'c7-campaign', 1000,"
            " 'USD', :at, :at, 'processed')"
        ),
        {
            "id": str(event_id),
            "tenant": str(tenant_id),
            "at": WINDOW_START + timedelta(days=4),
            "corr": str(uuid.uuid4()),
            "sess": str(uuid.uuid4()),
            "key": f"c7:{tenant_id.hex[:8]}:{index}",
            "channel": channel,
        },
    )
    return event_id


def _seed_verdict(conn, tenant_id: uuid.UUID, event_id: uuid.UUID, status: str) -> uuid.UUID:
    verdict_id = uuid.uuid4()
    reference = f"c7-order-{verdict_id.hex[:10]}"
    conn.execute(
        text(
            "INSERT INTO public.b23_match_verdicts (id, tenant_id,"
            " attribution_event_id, provider, canonical_commerce_reference,"
            " provider_native_event_reference, provider_native_commerce_reference,"
            " status, match_quality, attributed_amount_minor,"
            " verified_amount_minor, currency_code, last_transition_at,"
            " provisional_expires_at, pending_since,"
            " canonical_expected_gross_amount_minor,"
            " canonical_captured_gross_amount_minor,"
            " canonical_net_verified_amount_minor, discrepancy_amount_minor,"
            " discrepancy_ratio_bps, discrepancy_band) VALUES (:id, :tenant,"
            " :event, 'stripe', :ref, :ev_ref, :ref, :status, 'high', 1000, 1000,"
            " 'USD', :at, :at, :at, 1000, 1000, 1000, 0, 0, 'exact')"
        ),
        {
            "id": str(verdict_id),
            "tenant": str(tenant_id),
            "event": str(event_id),
            "ref": reference,
            "ev_ref": f"c7-ev-{verdict_id.hex[:10]}",
            "status": status,
            "at": WINDOW_START + timedelta(days=4),
        },
    )
    return verdict_id


def _in_snapshot(conn, tenant_id: uuid.UUID) -> list[tuple]:
    """The authoritative B2.4 verdict projection and filter, verbatim."""

    _bind_tenant(conn, tenant_id)
    return conn.execute(
        text(
            "SELECT id::text, status, match_quality, attributed_amount_minor,"
            " last_transition_at FROM public.b23_match_verdicts"
            " WHERE tenant_id = :tenant AND last_transition_at >= :ws"
            " AND last_transition_at < :we"
            " AND status IN ('matched_confirmed', 'adjusted')"
            " ORDER BY last_transition_at, id"
        ),
        {"tenant": str(tenant_id), "ws": WINDOW_START, "we": WINDOW_END},
    ).all()


def _dirty_count(conn, tenant_id: uuid.UUID) -> int:
    _bind_tenant(conn, tenant_id)
    return int(
        conn.execute(
            text(
                "SELECT count(*) FROM public.b24_dirty_events WHERE tenant_id = :tenant"
            ),
            {"tenant": str(tenant_id)},
        ).scalar_one()
    )


def test_c7_source_change_creates_durable_obligation() -> None:
    """matched_provisional -> matched_confirmed must invalidate B2.4 confidence.

    The exact production statement from
    app.revenue_verification.state_transitions.transition_stale_provisional_to_confirmed,
    which on main changed a B2.4 source relation with no dirty-marker call
    anywhere in the module.
    """

    engine = _engine(_worker_url())
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "invalidation")
            event_id = _seed_conversion_event(conn, tenant_id, 1)
            _seed_verdict(conn, tenant_id, event_id, "matched_provisional")
            before_rows = _in_snapshot(conn, tenant_id)
            before_dirty = _dirty_count(conn, tenant_id)
            assert before_rows == [], "provisional verdicts are outside the contract"

            conn.execute(
                text(
                    "WITH claimed AS (SELECT v.id FROM b23_match_verdicts v"
                    " WHERE v.tenant_id = :tenant AND v.status = 'matched_provisional'"
                    " AND v.provisional_expires_at <= now()"
                    " ORDER BY v.provisional_expires_at ASC, v.id ASC LIMIT 500"
                    " FOR UPDATE SKIP LOCKED)"
                    " UPDATE b23_match_verdicts target SET status = 'matched_confirmed',"
                    " confirmed_at = now(), last_transition_at = :at, updated_at = now()"
                    " FROM claimed WHERE target.id = claimed.id"
                    " AND target.tenant_id = :tenant"
                    " AND target.status = 'matched_provisional' RETURNING target.id"
                ),
                {"tenant": str(tenant_id), "at": WINDOW_START + timedelta(days=4)},
            )

            after_rows = _in_snapshot(conn, tenant_id)
            after_dirty = _dirty_count(conn, tenant_id)
            assert after_rows != before_rows, "the transition did not change source bytes"
            assert after_dirty > before_dirty, (
                "a committed B2.4 source change produced no invalidation"
            )
            # created_at is now(), which is transaction-constant, so ordering
            # cannot identify the newest row. Assert the invariant directly.
            reasons = {
                row[0]
                for row in conn.execute(
                    text(
                        "SELECT DISTINCT dirty_reason FROM public.b24_dirty_events"
                        " WHERE tenant_id = :tenant"
                    ),
                    {"tenant": str(tenant_id)},
                ).all()
            }
            assert "b23_match_verdicts_snapshot_changed" in reasons, reasons
            assert len(_wakeup(conn, tenant_id)) == 1, (
                "invalidation did not become a durable planning obligation"
            )
    finally:
        engine.dispose()


def test_c7_invalidation_is_transactionally_coupled() -> None:
    """No committed source truth may exist without its invalidation."""

    engine = _engine(_worker_url())
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "atomic")
            event_id = _seed_conversion_event(conn, tenant_id, 1)
            verdict_id = _seed_verdict(conn, tenant_id, event_id, "matched_confirmed")

        # Crash injection: mutate the source, observe the obligation appear in
        # the same transaction, then abort. Neither consequence may survive.
        connection = engine.connect()
        transaction = connection.begin()
        _bind_tenant(connection, tenant_id)
        before = _dirty_count(connection, tenant_id)
        connection.execute(
            text(
                "UPDATE public.b23_match_verdicts SET match_quality = 'medium',"
                " updated_at = now() WHERE tenant_id = :tenant AND id = :id"
            ),
            {"tenant": str(tenant_id), "id": str(verdict_id)},
        )
        during = _dirty_count(connection, tenant_id)
        assert during == before + 1, "source change did not invalidate in-transaction"
        transaction.rollback()
        connection.close()

        with engine.begin() as conn:
            _bind_tenant(conn, tenant_id)
            assert _dirty_count(conn, tenant_id) == before
            quality = conn.execute(
                text(
                    "SELECT match_quality FROM public.b23_match_verdicts WHERE id = :id"
                ),
                {"id": str(verdict_id)},
            ).scalar_one()
            assert quality == "high", "source mutation survived its rolled-back txn"
    finally:
        engine.dispose()


def test_c7_non_snapshot_transition_does_not_invalidate() -> None:
    """Invalidation must be precise, not merely present.

    pending -> unmatched is excluded from the B2.4 source set on both sides, so
    it cannot change snapshot bytes and must not manufacture planner work.
    """

    engine = _engine(_worker_url())
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "precision")
            event_id = _seed_conversion_event(conn, tenant_id, 1)
            verdict_id = _seed_verdict(conn, tenant_id, event_id, "pending")
            before_rows = _in_snapshot(conn, tenant_id)
            before_dirty = _dirty_count(conn, tenant_id)

            conn.execute(
                text(
                    "UPDATE public.b23_match_verdicts SET status = 'unmatched',"
                    " unmatched_marked_at = now(), last_transition_at = :at,"
                    " updated_at = now() WHERE tenant_id = :tenant AND id = :id"
                    " AND status = 'pending'"
                ),
                {
                    "tenant": str(tenant_id),
                    "id": str(verdict_id),
                    "at": WINDOW_START + timedelta(days=4),
                },
            )
            assert _in_snapshot(conn, tenant_id) == before_rows
            assert _dirty_count(conn, tenant_id) == before_dirty, (
                "an excluded-on-both-sides transition over-invalidated"
            )
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# BEHAVIORAL: planner obligation conservation (C7-F/G/H/I)
# ---------------------------------------------------------------------------
def test_c7_pre_debounce_pass_cannot_strand_dirty_work() -> None:
    """A planner pass before quiet-period maturity retains the obligation.

    Maturity is real elapsed time against a short quiet period; no row is edited
    to fake it, and no second dirty event rescues the first.
    """

    # The quiet period must comfortably exceed this test's own setup latency.
    # At 3s a cold connection pool could mature the event before the
    # "pre-debounce" pass ran, so the pass would legitimately plan it and the
    # experiment would silently measure nothing.
    quiet = 12
    engine = _engine(_worker_url())
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "pre-debounce")
            _append_dirty(conn, tenant_id, group="only", age_seconds=0)
            assert _unplanned(conn, tenant_id) == 1
            assert len(_wakeup(conn, tenant_id)) == 1

            revision = _lease(conn, "celery:early", tenant_id)
            assert revision is not None
            # Assert the precondition rather than assuming it: this pass is only
            # a pre-debounce pass if the planner considers nothing eligible yet.
            eligible_now, due_at = _residual(conn, tenant_id, quiet)
            assert eligible_now == 0, (
                "setup outran the quiet period, so this was not a pre-debounce"
                f" pass: eligible={eligible_now}"
            )
            assert due_at is not None
            assert _bounded_pass(conn, tenant_id, limit=25, quiet_period=quiet) == 0
            disposition = _ack(
                conn, tenant_id, "celery:early", revision, quiet_period=quiet
            )
            assert disposition == "deferred", disposition
            assert len(_wakeup(conn, tenant_id)) == 1, "the only wakeup was destroyed"
            assert _unplanned(conn, tenant_id) == 1
            assert _lease(conn, "celery:spin", tenant_id) is None, (
                "a deferred tenant must not be re-leased before it is due"
            )

        # Real elapsed time only. Nothing is edited to fake maturity; the
        # deferral the database computed must expire on its own.
        time.sleep(quiet + 2)

        with engine.begin() as conn:
            matured, _ = _residual(conn, tenant_id, quiet)
            assert matured == 1, f"the deferred work never matured: eligible={matured}"
            revision = _lease(conn, "celery:mature", tenant_id)
            assert revision is not None, "the deferred obligation never became due"
            assert _bounded_pass(conn, tenant_id, limit=25, quiet_period=quiet) == 1
            disposition = _ack(
                conn, tenant_id, "celery:mature", revision, quiet_period=quiet
            )
            assert disposition == "deleted", disposition
            assert _unplanned(conn, tenant_id) == 0
            assert _wakeup(conn, tenant_id) == []
    finally:
        engine.dispose()


def test_c7_bounded_backlog_drains_without_new_stimulus() -> None:
    """N due groups above candidate_limit drain through ordinary cycles."""

    total_groups, limit = 5, 2
    engine = _engine(_worker_url())
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "backlog")
            for index in range(total_groups):
                _append_dirty(conn, tenant_id, group=f"g{index}", age_seconds=600)
            assert _unplanned(conn, tenant_id) == total_groups

            processed, passes, dispositions = 0, 0, []
            while passes < total_groups + 3:
                revision = _lease(conn, f"celery:pass{passes}", tenant_id)
                if revision is None:
                    break
                processed += _bounded_pass(
                    conn, tenant_id, limit=limit, quiet_period=QUIET_PERIOD_SECONDS
                )
                disposition = _ack(conn, tenant_id, f"celery:pass{passes}", revision)
                dispositions.append(disposition)
                passes += 1
                if disposition == "deleted":
                    break

            assert processed == total_groups, (
                f"lost work: {processed}/{total_groups} after {passes} passes"
            )
            assert dispositions[:-1] == ["retained_eligible"] * (len(dispositions) - 1)
            assert dispositions[-1] == "deleted"
            assert _unplanned(conn, tenant_id) == 0
            assert _wakeup(conn, tenant_id) == []
    finally:
        engine.dispose()


def test_c7_stale_revision_ack_cannot_destroy_newer_obligation() -> None:
    """New evidence during an active lease survives the older planner's ack."""

    engine = _engine(_worker_url())
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "overlap")
            _append_dirty(conn, tenant_id, group="first", age_seconds=600)
            revision_a = _lease(conn, "celery:A", tenant_id)
            assert revision_a is not None

            _append_dirty(conn, tenant_id, group="second", age_seconds=600)
            revision_b = _lease(conn, "celery:B", tenant_id)
            assert revision_b == revision_a + 1, (
                "new evidence did not invalidate the active lease"
            )

            disposition = _ack(conn, tenant_id, "celery:A", revision_a)
            assert disposition == "stale_revision", disposition
            surviving = _wakeup(conn, tenant_id)
            assert len(surviving) == 1
            assert int(surviving[0][1]) == revision_b
            assert _unplanned(conn, tenant_id) == 2
    finally:
        engine.dispose()


def test_c7_expired_lease_is_reclaimed_and_completed() -> None:
    """A planner that dies before acknowledging delays work but never loses it."""

    engine = _engine(_worker_url())
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "reclaim")
            _append_dirty(conn, tenant_id, group="only", age_seconds=600)
            assert _lease(conn, "celery:dead", tenant_id) is not None
            assert _lease(conn, "celery:thief", tenant_id) is None, (
                "a live lease was stolen"
            )

            # The owner is gone; only lease expiry may release it.
            released = conn.execute(
                text(
                    "UPDATE public.b24_fit_planner_wakeups"
                    " SET lease_expires_at = now() - interval '1 second'"
                    " WHERE tenant_id = :tenant"
                ),
                {"tenant": str(tenant_id)},
            )
            assert released.rowcount == 1

            revision = _lease(conn, "celery:successor", tenant_id)
            assert revision is not None, "expired lease was not reclaimable"
            assert _bounded_pass(
                conn, tenant_id, limit=25, quiet_period=QUIET_PERIOD_SECONDS
            ) == 1
            assert _ack(conn, tenant_id, "celery:successor", revision) == "deleted"
            assert _unplanned(conn, tenant_id) == 0
    finally:
        engine.dispose()


def test_c7_bulk_ingestion_does_not_serialize_on_the_wakeup_row() -> None:
    """PR #661's hot-row correction survives obligation conservation.

    A pending wakeup with no deferral already represents all unplanned work, so
    bulk ingestion must not touch it once created.
    """

    engine = _engine(_worker_url())
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "hot-row")
            for index in range(250):
                _append_dirty(conn, tenant_id, group=f"bulk{index}", age_seconds=600)
            rows = _wakeup(conn, tenant_id)
            assert len(rows) == 1
            status, revision, next_eligible_at = rows[0]
            assert status == "pending"
            assert int(revision) == 1, (
                "bulk ingestion bumped the revision and re-serialised the hot row"
            )
            assert next_eligible_at is None
            assert _unplanned(conn, tenant_id) == 250
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# BEHAVIORAL: complete confidence dependency authority (C7-K/L)
# ---------------------------------------------------------------------------
def test_c7_every_governed_fit_column_is_frozen_when_terminal() -> None:
    """A runtime mutation matrix over the whole governed dependency set.

    Static membership proves the registry names created_at. Only this proves the
    database refuses to move it once the fit is terminal, and it proves the same
    for every other governed column rather than the handful C5 enumerated.

    Two phases, because two independent guards stand in front of a terminal fit
    and the fence fires first:

      1. Production configuration -- both guards armed, no dispatch lease held.
         Every governed column must be refused by one of them. This is the claim
         that matters operationally: the mutation is impossible.

      2. Fence suspended, terminal-truth guard alone. Every governed column must
         be refused by b24_terminal_fit_truth_immutable specifically. This is the
         claim C7-K/L makes: the dependency registry itself covers all of them,
         and none is protected only by accident of the fence being in the way.
    """

    tenant_engine = _engine(_worker_url())
    try:
        with tenant_engine.begin() as conn:
            tenant_id = _new_tenant(conn, "terminal")
    finally:
        tenant_engine.dispose()
    fit_id = _seed_fit(tenant_id, status="succeeded", snapshot_hash="a" * 64)

    accepted_in_production: list[str] = []
    engine = _engine(_worker_url())
    try:
        for column in GOVERNED_FIT_COLUMNS:
            expression = _MUTATIONS[column]
            connection = engine.connect()
            transaction = connection.begin()
            try:
                _bind_tenant(connection, tenant_id)
                connection.execute(
                    text(
                        f"UPDATE public.bayesian_model_fits SET {column} = {expression}"
                        " WHERE tenant_id = :tenant AND id = :id"
                    ),
                    {"tenant": str(tenant_id), "id": str(fit_id)},
                )
            except (DBAPIError, InternalError, ProgrammingError) as exc:
                assert (
                    "b24_terminal_fit_truth_immutable" in str(exc)
                    or "b24_dispatch_immutable_fit_authority" in str(exc)
                    or "b24_dispatch_fence_rejected" in str(exc)
                ), f"{column} was refused by an unrelated constraint: {exc}"
            else:
                accepted_in_production.append(column)
            finally:
                transaction.rollback()
                connection.close()
    finally:
        engine.dispose()

    assert not accepted_in_production, (
        "governed fit columns mutate freely on a terminal fit in the production"
        " configuration: " + ",".join(accepted_in_production)
    )

    # Phase 2: isolate the terminal-truth guard. The dispatch fence is suspended
    # only for the duration of this transaction and is restored by its rollback,
    # so the registry's own coverage is what is being measured.
    unprotected: list[str] = []
    wrong_guard: list[str] = []
    migration_engine = _migration_engine()
    try:
        connection = migration_engine.connect()
        outer = connection.begin()
        try:
            _bind_tenant(connection, tenant_id)
            connection.execute(
                text(
                    "ALTER TABLE public.bayesian_model_fits"
                    " DISABLE TRIGGER trg_b24_dispatch_fence_fits"
                )
            )
            for column in GOVERNED_FIT_COLUMNS:
                expression = _MUTATIONS[column]
                savepoint = connection.begin_nested()
                try:
                    connection.execute(
                        text(
                            "UPDATE public.bayesian_model_fits"
                            f" SET {column} = {expression}"
                            " WHERE tenant_id = :tenant AND id = :id"
                        ),
                        {"tenant": str(tenant_id), "id": str(fit_id)},
                    )
                except (DBAPIError, InternalError, ProgrammingError) as exc:
                    if "b24_terminal_fit_truth_immutable" not in str(exc):
                        wrong_guard.append(f"{column}:{exc.__class__.__name__}")
                else:
                    unprotected.append(column)
                finally:
                    savepoint.rollback()
        finally:
            outer.rollback()
            connection.close()
    finally:
        migration_engine.dispose()

    assert not unprotected, (
        "governed fit columns are not covered by the terminal dependency"
        " registry: " + ",".join(unprotected)
    )
    assert not wrong_guard, (
        "terminal guard did not refuse these governed columns: "
        + ",".join(wrong_guard)
    )



def _artifact_statement(tenant_id: uuid.UUID, statement: str, params: dict):
    """Run one artifact statement with only the lifecycle guard in the way.

    The artifact dispatch fence refuses any update from a process that holds no
    dispatch lease, so it would mask whichever lifecycle transition is under
    test. It is suspended for this statement and restored by the surrounding
    transaction; b24_enforce_artifact_lifecycle stays armed throughout.
    Returns the raised exception, or None when the statement succeeded.
    """

    engine = _migration_engine()
    try:
        connection = engine.connect()
        transaction = connection.begin()
        try:
            _bind_tenant(connection, tenant_id)
            connection.execute(
                text(
                    "ALTER TABLE public.bayesian_artifacts"
                    " DISABLE TRIGGER trg_b24_dispatch_fence_artifacts"
                )
            )
            savepoint = connection.begin_nested()
            try:
                connection.execute(text(statement), params)
            except (DBAPIError, InternalError, ProgrammingError) as exc:
                savepoint.rollback()
                return exc
            savepoint.commit()
            connection.execute(
                text(
                    "ALTER TABLE public.bayesian_artifacts"
                    " ENABLE TRIGGER trg_b24_dispatch_fence_artifacts"
                )
            )
            transaction.commit()
            return None
        except BaseException:
            transaction.rollback()
            raise
        finally:
            connection.close()
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# BEHAVIORAL: non-fit decision authority lifecycle (C7-M)
# ---------------------------------------------------------------------------
def test_c7_artifact_and_dirty_lifecycle_transitions_are_governed() -> None:
    """Legitimate degradation is allowed; silent rewriting of history is not."""

    engine = _engine(_worker_url())
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "lifecycle")
        fit_id = _seed_fit(tenant_id, status="succeeded", snapshot_hash="e" * 64)
        artifact_id = _seed_artifact(tenant_id, fit_id)

        # Legitimate degradation: active -> pruned is allowed and explainable.
        pruned = _artifact_statement(
            tenant_id,
            "UPDATE public.bayesian_artifacts SET lifecycle_status = 'pruned',"
            " payload_bytes = NULL, payload_byte_count = 0, pruned_at = now(),"
            " pruned_reason = 'retention_expired', updated_at = now()"
            " WHERE tenant_id = :tenant AND id = :id",
            {"tenant": str(tenant_id), "id": str(artifact_id)},
        )
        assert pruned is None, f"legitimate pruning was refused: {pruned}"

        # Resurrection would silently restore evidence a Trust read already
        # degraded on. Payload state is restored too, so the lifecycle trigger is
        # the only thing standing between this statement and success.
        resurrected = _artifact_statement(
            tenant_id,
            "UPDATE public.bayesian_artifacts SET lifecycle_status = 'active',"
            " payload_bytes = :payload, payload_byte_count = :size,"
            " artifact_size_bytes = :size, pruned_at = NULL, pruned_reason = NULL"
            " WHERE tenant_id = :tenant AND id = :id",
            {
                "tenant": str(tenant_id),
                "id": str(artifact_id),
                "payload": b"c7-posterior-summary",
                "size": len(b"c7-posterior-summary"),
            },
        )
        assert resurrected is not None, "a pruned artifact was resurrected"
        assert "b24_artifact_lifecycle_resurrection_forbidden" in str(resurrected), (
            f"resurrection refused by the wrong guard: {resurrected}"
        )

        # observed_at decides has_later_dirty_evidence, so it is immutable.
        with engine.begin() as conn:
            _append_dirty(conn, tenant_id, group="lifecycle", age_seconds=600)
            dirty_id = conn.execute(
                text(
                    "SELECT id FROM public.b24_dirty_events WHERE tenant_id = :tenant"
                    " ORDER BY created_at DESC LIMIT 1"
                ),
                {"tenant": str(tenant_id)},
            ).scalar_one()

        connection = engine.connect()
        transaction = connection.begin()
        try:
            _bind_tenant(connection, tenant_id)
            with pytest.raises(DBAPIError) as excinfo:
                connection.execute(
                    text(
                        "UPDATE public.b24_dirty_events"
                        " SET observed_at = now() - interval '10 days'"
                        " WHERE tenant_id = :tenant AND id = :id"
                    ),
                    {"tenant": str(tenant_id), "id": str(dirty_id)},
                )
            assert "b24_dirty_event_observed_at_immutable" in str(excinfo.value)
        finally:
            transaction.rollback()
            connection.close()

        # A terminal dirty disposition is final.
        with engine.begin() as conn:
            _bind_tenant(conn, tenant_id)
            conn.execute(
                text(
                    "UPDATE public.b24_dirty_events SET status = 'claimed',"
                    " claimed_at = now() WHERE tenant_id = :tenant AND id = :id"
                ),
                {"tenant": str(tenant_id), "id": str(dirty_id)},
            )
        connection = engine.connect()
        transaction = connection.begin()
        try:
            _bind_tenant(connection, tenant_id)
            with pytest.raises(DBAPIError) as excinfo:
                connection.execute(
                    text(
                        "UPDATE public.b24_dirty_events SET status = 'pending'"
                        " WHERE tenant_id = :tenant AND id = :id"
                    ),
                    {"tenant": str(tenant_id), "id": str(dirty_id)},
                )
            assert "b24_dirty_event_terminal_status_immutable" in str(excinfo.value)
        finally:
            transaction.rollback()
            connection.close()
    finally:
        engine.dispose()
