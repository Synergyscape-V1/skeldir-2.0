"""B2.5-P13 C21 — B2.4 freshness authority and durable issuance history.

Corrective XXI, Exit Gates XXI-A (freshness authority conservation), XXI-B
(lawful invalidation lifecycle), XXI-C (durable issuance authority conservation),
XXI-D (lawful issuance lifecycle) and XXI-E (process x consequence authority).

Audit 65 physically executed, on protected main, as the real API database login:

    app_user: UPDATE b24_dirty_events SET source_snapshot_hash = <the fit's hash>

and watched the confidence projection's ``has_later_dirty_evidence`` predicate
flip from TRUE to FALSE -- a stale posterior became eligible for Trust without
any Bayesian recomputation. It then executed

    app_user: UPDATE trust_envelope_issuance_log
              SET envelope_hash = ..., semantic_truth_hash = ...

and rewrote what durable history says Skeldir signed.

This proof does not read a privilege catalogue and conclude. It connects as the
real PostgreSQL login each production process uses, runs the real historical
statements, and requires the database itself to refuse -- then runs the lawful
planner and issuance paths and requires them to succeed, because a fence that
also blocks the legitimate author is not a fix.

The staleness predicate executed here is *sliced out of
``app/confidence_projection/read_model.py`` at runtime*, not restated. A future
edit that changes which columns carry freshness authority changes what this test
attacks, so the proof cannot drift away from the surface it protects.

Each remediation expresses authority twice -- a privilege layer and a
consequence layer -- so the negative controls sever each independently and then
both together. Only the both-severed case may reproduce the audit's RED; that is
what makes the two green layers non-vacuous rather than merely co-present.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import psycopg2
import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_C21_AUTHORITY_PROOF") != "1",
    reason="C21 authority proof requires a provisioned production role graph",
)


REPO_ROOT = Path(__file__).resolve().parents[3]
READ_MODEL = REPO_ROOT / "backend" / "app" / "confidence_projection" / "read_model.py"

PRINCIPALS = (
    "app_user",
    "app_worker",
    "app_rw",
    "app_ro",
    "app_dispatch_publisher",
    "app_celery_transport",
    "app_trust_issuer",
    "app_trust_signer",
)

# The historical grants, verbatim from the migrations that authored them.
_HISTORICAL_DIRTY_GRANT = (
    "GRANT SELECT, INSERT, UPDATE ON public.b24_dirty_events TO app_user"
)
_FENCED_DIRTY_GRANT = (
    "REVOKE ALL ON TABLE public.b24_dirty_events FROM app_user; "
    "GRANT SELECT, INSERT ON TABLE public.b24_dirty_events TO app_user"
)
_HISTORICAL_ISSUANCE_GRANT = (
    "GRANT SELECT, INSERT, UPDATE ON TABLE public.trust_envelope_issuance_log"
    " TO app_user"
)
_FENCED_ISSUANCE_GRANT = (
    "REVOKE ALL ON TABLE public.trust_envelope_issuance_log FROM app_user; "
    "GRANT SELECT, INSERT ON TABLE public.trust_envelope_issuance_log TO app_user"
)
# app_rw keeps SELECT+INSERT after C21 -- `record_trust_audit_event` writes this
# relation from whichever session composes a Trust read, and the C9 lane composes
# one under the worker principal. Restoring the *fence* therefore means restoring
# that, not stripping the role: a control that leaves the database in a state the
# migration never produces is a control that breaks the next experiment.
_HISTORICAL_ISSUANCE_GRANT_RW = (
    "GRANT SELECT, INSERT, UPDATE ON TABLE public.trust_envelope_issuance_log"
    " TO app_rw"
)
_FENCED_ISSUANCE_GRANT_RW = (
    "REVOKE ALL ON TABLE public.trust_envelope_issuance_log FROM app_rw; "
    "GRANT SELECT, INSERT ON TABLE public.trust_envelope_issuance_log TO app_rw"
)

_MODEL_TYPE = "bayesian_attribution_confidence"
_MODEL_VERSION = "b25-p13-c21-v1"


# ---------------------------------------------------------------------------
# The production staleness predicate, executed rather than restated.
# ---------------------------------------------------------------------------


def _production_staleness_predicate() -> str:
    """Slice the exact ``has_later_dirty_evidence`` EXISTS block from the read model.

    Restating the predicate here would let the fence and the surface it protects
    drift apart silently: a future migration could move freshness authority onto
    a column this file never attacks, and this proof would stay green while the
    audit's defect returned. Reading the block out of the shipped module means
    the experiment always attacks whatever the projection actually consults.
    """

    model = READ_MODEL.read_text(encoding="utf-8")
    end = model.find("AS has_later_dirty_evidence")
    assert end > 0, "read model no longer exposes has_later_dirty_evidence"
    start = model.rfind("EXISTS (", 0, end)
    assert start > 0, "has_later_dirty_evidence is not an EXISTS block"
    block = model[start:end].strip()
    assert "b24_source_windows_overlap" in block, block
    return (
        "WITH requested_fit AS ("
        " SELECT tenant_id, model_type, model_version, source_window_start,"
        "        source_window_end, source_snapshot_hash, source_read_started_at,"
        "        created_at"
        " FROM public.bayesian_model_fits WHERE id = %s"
        ") SELECT " + block + " AS has_later_dirty_evidence FROM requested_fit"
    )


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------


def _admin_dsn() -> str:
    for name in (
        "C21_ADMIN_DATABASE_URL",
        "C20_ADMIN_DATABASE_URL",
        "C19_ADMIN_DATABASE_URL",
        "MIGRATION_DATABASE_URL",
    ):
        value = os.getenv(name, "").strip()
        if value:
            return value
    raise RuntimeError(
        "C21 authority proof needs an owner/superuser DSN: set C21_ADMIN_DATABASE_URL"
    )


def _admin_connection():
    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    return conn


def _role_connection(role: str):
    parts = urlsplit(_admin_dsn().replace("postgresql+psycopg2://", "postgresql://"))
    conn = psycopg2.connect(
        dbname=parts.path.lstrip("/"),
        host=parts.hostname,
        port=parts.port or 5432,
        user=role,
        password=os.getenv(f"C21_{role.upper()}_PASSWORD", role),
    )
    conn.autocommit = False
    return conn


def _bind_tenant(cursor, tenant_id) -> None:
    cursor.execute(
        "SELECT set_config('app.current_tenant_id', %s, false)", (str(tenant_id),)
    )


def _as_principal(
    role: str,
    tenant_id,
    statement: str,
    params: tuple[Any, ...],
    *,
    label: str,
) -> dict[str, Any]:
    """Run one statement as one real production login and record the physics."""

    outcome: dict[str, Any] = {"principal": role, "label": label}
    conn = _role_connection(role)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT session_user, current_user")
            outcome["session_user"], outcome["current_user"] = cursor.fetchone()
            _bind_tenant(cursor, tenant_id)
            cursor.execute(statement, params)
            outcome["rowcount"] = cursor.rowcount
        conn.commit()
        outcome["result"] = "ALLOWED"
    except psycopg2.Error as exc:
        conn.rollback()
        outcome["result"] = "REFUSED"
        outcome["sqlstate"] = exc.pgcode
        outcome["error"] = str(exc).strip().splitlines()[0]
    finally:
        conn.close()
    return outcome


def _principal_sees_row(role: str, tenant_id, relation: str, row_id) -> int:
    """Non-vacuity: the attacker's own session can see the row it will attack.

    Corrective XX's lesson was ``UPDATE 0`` -- RLS hid the row, the guard never
    executed, and psql exited zero. Every forbidden experiment below asserts
    this first, so a refusal can never be a row that was not there.
    """

    conn = _role_connection(role)
    try:
        with conn.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            cursor.execute(
                f"SELECT count(*) FROM public.{relation} WHERE id = %s", (str(row_id),)
            )
            return int(cursor.fetchone()[0])
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Fixtures: one legitimate stale-fit universe and one issued envelope.
# ---------------------------------------------------------------------------


def _seed_universe(cursor) -> dict[str, Any]:
    """A lawful fit, and later lawful invalidation evidence that stales it."""

    tenant_id = uuid.uuid4()
    label = tenant_id.hex[:8]
    window_start = datetime(2026, 8, 22, 0, 0, tzinfo=timezone.utc)
    window_end = window_start + timedelta(days=1)
    read_started = window_end + timedelta(hours=1)
    read_completed = read_started + timedelta(minutes=5)
    observed_at = read_started + timedelta(hours=2)
    fit_hash = uuid.uuid4().hex + uuid.uuid4().hex
    dirty_hash = uuid.uuid4().hex + uuid.uuid4().hex

    cursor.execute(
        "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
        " VALUES (%s, %s, %s, %s)",
        (str(tenant_id), f"c21-{label}", uuid.uuid4().hex, f"c21-{label}@example.invalid"),
    )
    _bind_tenant(cursor, tenant_id)
    cursor.execute(
        "INSERT INTO public.bayesian_model_fits (tenant_id, model_type, model_version,"
        " source_window_start, source_window_end, source_snapshot_hash,"
        " source_read_started_at, source_read_completed_at, status)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending') RETURNING id",
        (
            str(tenant_id),
            _MODEL_TYPE,
            _MODEL_VERSION,
            window_start,
            window_end,
            fit_hash,
            read_started,
            read_completed,
        ),
    )
    fit_id = cursor.fetchone()[0]
    # event_hash and source_event_id are populated exactly as `append_dirty_event`
    # populates them: a NULL-seeded fixture would make a NULL-rewrite probe a
    # no-op and hide whichever bypass it was written to look for.
    cursor.execute(
        "INSERT INTO public.b24_dirty_events (tenant_id, model_type, model_version,"
        " source_window_start, source_window_end, dirty_reason, source_family,"
        " event_hash, source_event_id, source_snapshot_hash, observed_at, status)"
        " VALUES (%s, %s, %s, %s, %s, 'attribution_event_ingested',"
        " 'attribution_events', %s, %s, %s, %s, 'pending') RETURNING id",
        (
            str(tenant_id),
            _MODEL_TYPE,
            _MODEL_VERSION,
            window_start,
            window_end,
            uuid.uuid4().hex + uuid.uuid4().hex,
            str(uuid.uuid4()),
            dirty_hash,
            observed_at,
        ),
    )
    dirty_id = cursor.fetchone()[0]
    return {
        "tenant_id": tenant_id,
        "fit_id": fit_id,
        "dirty_id": dirty_id,
        "fit_hash": fit_hash,
        "dirty_hash": dirty_hash,
        "window_start": window_start,
        "window_end": window_end,
        "read_started": read_started,
        "observed_at": observed_at,
    }


def _seed_issuance(cursor, tenant_id) -> dict[str, Any]:
    """One completed issuance row, shaped exactly as ``trust/audit.py`` writes it."""

    def digest() -> str:
        return "sha256:" + uuid.uuid4().hex + uuid.uuid4().hex

    _bind_tenant(cursor, tenant_id)
    cursor.execute(
        "INSERT INTO public.trust_envelope_issuance_log (tenant_id, access_audit_ref,"
        " idempotency_key_hash, subject_type, subject_ref_hash, envelope_hash,"
        " semantic_truth_hash, policy_state, audit_ref, audit_hash, status)"
        " VALUES (%s, %s, %s, 'allocation', %s, %s, %s, 'issued', %s, %s, 'success')"
        " RETURNING id, envelope_hash, semantic_truth_hash, subject_ref_hash,"
        "           policy_state, audit_hash, status",
        (
            str(tenant_id),
            f"c21-access-{uuid.uuid4().hex[:12]}",
            digest(),
            digest(),
            digest(),
            digest(),
            f"c21-audit-{uuid.uuid4().hex[:12]}",
            digest(),
        ),
    )
    row = cursor.fetchone()
    return {
        "issuance_id": row[0],
        "envelope_hash": row[1],
        "semantic_truth_hash": row[2],
        "subject_ref_hash": row[3],
        "policy_state": row[4],
        "audit_hash": row[5],
        "status": row[6],
    }


def _issuance_state(cursor, issuance_id) -> tuple:
    cursor.execute(
        "SELECT envelope_hash, semantic_truth_hash, subject_ref_hash, policy_state,"
        " audit_hash, status FROM public.trust_envelope_issuance_log WHERE id = %s",
        (str(issuance_id),),
    )
    return tuple(cursor.fetchone())


_GUARDED_RELATIONS = (
    "b24_dirty_events",
    "trust_envelope_issuance_log",
    "trust_replay_events",
    "trust_scope_denial_events",
    "trust_access_log",
)


def _privilege_snapshot(cursor) -> dict[str, dict[str, list[str]]]:
    """Effective privileges on every relation a C21 falsifier may touch."""

    from tests.trust.test_b25_p13_c20_runtime_authority import (  # noqa: PLC0415
        _effective_privileges,
    )

    return {
        relation: {
            principal: sorted(operations)
            for principal, operations in _effective_privileges(cursor, relation).items()
        }
        for relation in _GUARDED_RELATIONS
    }


def _assert_privileges_restored(cursor, before: dict[str, dict[str, list[str]]]) -> None:
    """A falsifier must hand back the exact privilege state it was given.

    Not "the state the contract says" -- *the state it found*. Restoring to an
    assumed-correct fence looks identical to restoring correctly right up until
    the assumption is wrong, and then it silently normalises a defect out of the
    database and every check that runs afterwards goes green over it. The first
    version of the issuance control restored app_rw to nothing instead of to the
    SELECT+INSERT the migration produces, and a controlled-defect dry run showed
    the same class of masking: the freshness control's restore erased a
    deliberately reintroduced overgrant before the authority-contract assertion
    could see it.

    Whether the state it was given is *lawful* is a separate question, asked by
    the authority-contract equality against a pristine migrated database.
    """

    after = _privilege_snapshot(cursor)
    assert after == before, {
        relation: {"before": before[relation], "after": after[relation]}
        for relation in _GUARDED_RELATIONS
        if before[relation] != after[relation]
    }


def _record_evidence(payload: dict[str, Any]) -> None:
    target = os.getenv("C21_EVIDENCE_PATH", "").strip()
    if not target:
        evidence = os.getenv("C19_EVIDENCE_PATH", "").strip()
        if not evidence:
            return
        target = str(
            Path(evidence).with_name("b25_p13_c21_authority_evidence.json")
        )
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    existing.update(payload)
    path.write_text(
        json.dumps(existing, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Asserted first, before any experiment mutates a grant.
# ---------------------------------------------------------------------------


def test_c21_the_migrated_authority_contract_holds_before_any_mutation() -> None:
    """The database as the migrations built it, judged before anything moves.

    Every other test in this module severs a fence and puts it back. A
    controlled-defect dry run showed why that ordering matters: an overgrant
    deliberately reintroduced *by the migration* was erased by the first
    falsifier's restore, and every check that ran afterwards went green over a
    defect that was really there. So the as-migrated state is judged here, at
    the top of the file, where nothing has touched it yet -- and the CI job runs
    the three-universe comparison before this module for the same reason.
    """

    from tests.trust.test_b25_p13_c20_runtime_authority import (  # noqa: PLC0415
        _contract_violations,
    )

    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            violations = _contract_violations(cursor)
            snapshot = _privilege_snapshot(cursor)
    finally:
        conn.close()
    _record_evidence({"c21_as_migrated_privileges": snapshot})
    assert violations == [], violations


# ---------------------------------------------------------------------------
# Gate XXI-A: the API principal cannot alter the meaning of invalidation evidence.
# ---------------------------------------------------------------------------


def test_c21_freshness_authority_is_conserved_against_the_api_principal() -> None:
    predicate = _production_staleness_predicate()
    evidence: dict[str, Any] = {"gate": "XXI-A", "predicate_source": str(READ_MODEL)}
    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            universe = _seed_universe(cursor)
            _bind_tenant(cursor, universe["tenant_id"])
            cursor.execute(predicate, (str(universe["fit_id"]),))
            before = cursor.fetchone()[0]
        evidence["tenant_id"] = str(universe["tenant_id"])
        evidence["fit_id"] = str(universe["fit_id"])
        evidence["dirty_id"] = str(universe["dirty_id"])
        evidence["has_later_dirty_evidence_before"] = before
        assert before is True, "the fixture is not a stale fit; nothing to defend"

        # Non-vacuity: the attacker can see its target before it attacks it.
        visible = _principal_sees_row(
            "app_user", universe["tenant_id"], "b24_dirty_events", universe["dirty_id"]
        )
        evidence["app_user_sees_target_row"] = visible
        assert visible == 1, "app_user cannot see the row, so a refusal proves nothing"

        # Every column the projection's freshness predicate reads, plus the two
        # provenance columns that say what the invalidation evidence *is*.
        attempts: dict[str, Any] = {}
        for column, value in (
            ("source_snapshot_hash", universe["fit_hash"]),
            ("source_window_start", universe["window_start"] + timedelta(days=400)),
            ("source_window_end", universe["window_end"] + timedelta(days=400)),
            ("observed_at", universe["read_started"] - timedelta(days=1)),
            ("dirty_reason", "rewritten_by_the_api"),
            ("source_family", "rewritten_by_the_api"),
            ("model_type", "mmm"),
            ("model_version", "rewritten"),
            ("tenant_id", str(uuid.uuid4())),
        ):
            outcome = _as_principal(
                "app_user",
                universe["tenant_id"],
                f"UPDATE public.b24_dirty_events SET {column} = %s WHERE id = %s",
                (value, str(universe["dirty_id"])),
                label=f"app_user rewrites {column}",
            )
            assert outcome["result"] == "REFUSED", outcome
            assert outcome["session_user"] == "app_user", outcome
            assert outcome.get("sqlstate") == "42501", outcome
            with conn.cursor() as cursor:
                _bind_tenant(cursor, universe["tenant_id"])
                cursor.execute(predicate, (str(universe["fit_id"]),))
                outcome["has_later_dirty_evidence_after"] = cursor.fetchone()[0]
            assert outcome["has_later_dirty_evidence_after"] is True, outcome
            attempts[column] = outcome
        evidence["forbidden_rewrites"] = attempts

        # DELETE is the same attack by another route: remove the evidence and the
        # stale fit is current again.
        deletion = _as_principal(
            "app_user",
            universe["tenant_id"],
            "DELETE FROM public.b24_dirty_events WHERE id = %s",
            (str(universe["dirty_id"]),),
            label="app_user deletes the invalidation evidence",
        )
        evidence["app_user_delete"] = deletion
        assert deletion["result"] == "REFUSED", deletion

        # Tenant-GUC substitution buys nothing: the authority is gone whichever
        # tenant the caller claims to be.
        cross_tenant = _as_principal(
            "app_user",
            uuid.uuid4(),
            "UPDATE public.b24_dirty_events SET source_snapshot_hash = %s WHERE id = %s",
            (universe["fit_hash"], str(universe["dirty_id"])),
            label="app_user rewrites under a substituted tenant GUC",
        )
        evidence["app_user_cross_tenant"] = cross_tenant
        assert cross_tenant["result"] == "REFUSED", cross_tenant

        with conn.cursor() as cursor:
            _bind_tenant(cursor, universe["tenant_id"])
            cursor.execute(predicate, (str(universe["fit_id"]),))
            evidence["has_later_dirty_evidence_after_all"] = cursor.fetchone()[0]
        assert evidence["has_later_dirty_evidence_after_all"] is True
    finally:
        conn.close()

    _record_evidence({"c21_freshness_authority": evidence})


# ---------------------------------------------------------------------------
# Gate XXI-B: the fence does not strand legitimate invalidation.
# ---------------------------------------------------------------------------


def test_c21_lawful_invalidation_lifecycle_still_conducts() -> None:
    predicate = _production_staleness_predicate()
    evidence: dict[str, Any] = {"gate": "XXI-B"}
    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            universe = _seed_universe(cursor)
        tenant_id = universe["tenant_id"]

        # 1. The API principal still appends new invalidation evidence -- this is
        #    what `append_dirty_event` does from ingestion and the attribution
        #    worker, and a fence that blocked it would strand every future
        #    recomputation obligation.
        appended = _as_principal(
            "app_user",
            tenant_id,
            "INSERT INTO public.b24_dirty_events (tenant_id, model_type, model_version,"
            " source_window_start, source_window_end, dirty_reason, source_family,"
            " observed_at, status) VALUES (%s, %s, %s, %s, %s,"
            " 'attribution_event_ingested', 'attribution_events', %s, 'pending')",
            (
                str(tenant_id),
                _MODEL_TYPE,
                _MODEL_VERSION,
                universe["window_start"],
                universe["window_end"],
                universe["observed_at"] + timedelta(minutes=1),
            ),
            label="API appends invalidation evidence",
        )
        evidence["api_appends_evidence"] = appended
        assert appended["result"] == "ALLOWED", appended
        assert appended["rowcount"] == 1, appended

        # 2. The planner leases the obligation.
        leased = _as_principal(
            "app_worker",
            tenant_id,
            "UPDATE public.b24_dirty_events SET status = 'leased',"
            " planner_owner = 'c21-planner', leased_at = now(),"
            " lease_expires_at = now() + interval '300 seconds', updated_at = now()"
            " WHERE id = %s",
            (str(universe["dirty_id"]),),
            label="planner leases the obligation",
        )
        evidence["planner_leases"] = leased
        assert leased["result"] == "ALLOWED", leased
        assert leased["rowcount"] == 1, leased

        # 3. The planner binds the resolved source snapshot on the one lawful
        #    transition that resolves it -- `mark_authority_waiting_dirty_events`.
        resolved_hash = uuid.uuid4().hex + uuid.uuid4().hex
        bound = _as_principal(
            "app_worker",
            tenant_id,
            "UPDATE public.b24_dirty_events SET status = 'authority_waiting',"
            " source_snapshot_hash = %s, authority_retry_count = 0,"
            " authority_wait_started_at = COALESCE(authority_wait_started_at, now()),"
            " updated_at = now() WHERE id = %s AND status = 'leased'",
            (resolved_hash, str(universe["dirty_id"])),
            label="planner binds the resolved snapshot",
        )
        evidence["planner_binds_snapshot"] = bound
        assert bound["result"] == "ALLOWED", bound
        assert bound["rowcount"] == 1, bound

        # 4. Ordinary lifecycle transitions keep working.
        reactivated = _as_principal(
            "app_worker",
            tenant_id,
            "UPDATE public.b24_dirty_events SET status = 'authority_retry_ready',"
            " authority_reactivated_at = now(), updated_at = now() WHERE id = %s",
            (str(universe["dirty_id"]),),
            label="planner reactivates a waiting obligation",
        )
        evidence["planner_reactivates"] = reactivated
        assert reactivated["result"] == "ALLOWED", reactivated
        assert reactivated["rowcount"] == 1, reactivated

        dispatched = _as_principal(
            "app_worker",
            tenant_id,
            "UPDATE public.b24_dirty_events SET status = 'dispatched',"
            " dispatched_at = now(), updated_at = now() WHERE id = %s",
            (str(universe["dirty_id"]),),
            label="planner terminates the obligation",
        )
        evidence["planner_dispatches"] = dispatched
        assert dispatched["result"] == "ALLOWED", dispatched

        # 5. The old fit is still stale, and only a genuinely new fit -- one that
        #    read the superseding snapshot -- is current. A repair that made
        #    stale evidence permanently unresolvable would fail here.
        with conn.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            cursor.execute(predicate, (str(universe["fit_id"]),))
            evidence["old_fit_stale"] = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO public.bayesian_model_fits (tenant_id, model_type,"
                " model_version, source_window_start, source_window_end,"
                " source_snapshot_hash, source_read_started_at,"
                " source_read_completed_at, status) VALUES"
                " (%s, %s, %s, %s, %s, %s, %s, %s, 'pending') RETURNING id",
                (
                    str(tenant_id),
                    _MODEL_TYPE,
                    _MODEL_VERSION,
                    universe["window_start"],
                    universe["window_end"],
                    resolved_hash,
                    universe["observed_at"] + timedelta(hours=1),
                    universe["observed_at"] + timedelta(hours=1, minutes=5),
                ),
            )
            new_fit_id = cursor.fetchone()[0]
            cursor.execute(predicate, (str(new_fit_id),))
            evidence["new_fit_stale"] = cursor.fetchone()[0]
        evidence["new_fit_id"] = str(new_fit_id)
        assert evidence["old_fit_stale"] is True, evidence
        assert evidence["new_fit_stale"] is False, evidence
    finally:
        conn.close()

    _record_evidence({"c21_lawful_invalidation": evidence})


# ---------------------------------------------------------------------------
# Gate XXI-A active falsifier: each freshness layer, severed alone then together.
# ---------------------------------------------------------------------------


def _dirty_authority_triggerdefs(cursor) -> dict[str, str]:
    cursor.execute(
        "SELECT tgname, pg_get_triggerdef(oid) FROM pg_trigger"
        " WHERE tgrelid = 'public.b24_dirty_events'::regclass"
        "   AND tgname = 'trg_b24_dirty_event_authority'"
    )
    return {name: definition for name, definition in cursor.fetchall()}


def test_c21_each_freshness_layer_is_independently_load_bearing() -> None:
    predicate = _production_staleness_predicate()
    evidence: dict[str, Any] = {"gate": "XXI-A active falsifier"}
    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            universe = _seed_universe(cursor)
            saved = _dirty_authority_triggerdefs(cursor)
            privileges_before = _privilege_snapshot(cursor)
        assert len(saved) == 1, saved
        evidence["guard_trigger"] = sorted(saved)
        tenant_id = universe["tenant_id"]

        def rewrite(label: str) -> dict[str, Any]:
            outcome = _as_principal(
                "app_user",
                tenant_id,
                "UPDATE public.b24_dirty_events SET source_snapshot_hash = %s"
                " WHERE id = %s",
                (universe["fit_hash"], str(universe["dirty_id"])),
                label=label,
            )
            with conn.cursor() as cursor:
                _bind_tenant(cursor, tenant_id)
                cursor.execute(predicate, (str(universe["fit_id"]),))
                outcome["has_later_dirty_evidence_after"] = cursor.fetchone()[0]
            return outcome

        pristine = rewrite("pristine")
        evidence["pristine"] = pristine
        assert pristine["result"] == "REFUSED", pristine
        assert pristine["has_later_dirty_evidence_after"] is True, pristine

        # (1) Restore the historical grant. The consequence layer must refuse.
        with conn.cursor() as cursor:
            cursor.execute(_HISTORICAL_DIRTY_GRANT)
        grant_only = rewrite("historical grant restored")
        evidence["historical_grant_restored"] = grant_only
        assert grant_only["result"] == "REFUSED", grant_only
        assert grant_only.get("sqlstate") == "42501", grant_only
        assert "freshness authority" in grant_only.get("error", ""), grant_only
        assert grant_only["has_later_dirty_evidence_after"] is True, grant_only

        # (2) Sever the consequence layer. The privilege layer must refuse.
        with conn.cursor() as cursor:
            cursor.execute(_FENCED_DIRTY_GRANT)
            for name in saved:
                cursor.execute(f"DROP TRIGGER {name} ON public.b24_dirty_events")
        trigger_only = rewrite("guard trigger severed")
        evidence["guard_trigger_severed"] = trigger_only
        assert trigger_only["result"] == "REFUSED", trigger_only
        assert trigger_only["has_later_dirty_evidence_after"] is True, trigger_only

        # (3) Sever both. The audit's defect must reappear exactly -- this is what
        #     proves the two green layers above are not vacuously green.
        with conn.cursor() as cursor:
            cursor.execute(_HISTORICAL_DIRTY_GRANT)
        historical = rewrite("both layers severed")
        evidence["both_layers_severed"] = historical
        assert historical["result"] == "ALLOWED", historical
        assert historical["rowcount"] == 1, historical
        assert historical["has_later_dirty_evidence_after"] is False, historical

        # (4) Exact restoration, verified by identity of the trigger definition.
        with conn.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            cursor.execute(
                "UPDATE public.b24_dirty_events SET source_snapshot_hash = %s"
                " WHERE id = %s",
                (universe["dirty_hash"], str(universe["dirty_id"])),
            )
            cursor.execute(_FENCED_DIRTY_GRANT)
            for definition in saved.values():
                cursor.execute(definition)
            restored_defs = _dirty_authority_triggerdefs(cursor)
        evidence["exact_restore_identical"] = restored_defs == saved
        assert restored_defs == saved, restored_defs
        restored = rewrite("after exact restoration")
        evidence["after_exact_restoration"] = restored
        assert restored["result"] == "REFUSED", restored
        assert restored["has_later_dirty_evidence_after"] is True, restored
        with conn.cursor() as cursor:
            _assert_privileges_restored(cursor, privileges_before)
    finally:
        conn.close()

    _record_evidence({"c21_freshness_layer_falsifier": evidence})


# ---------------------------------------------------------------------------
# Gate XXI-C: durable issuance history cannot be rewritten by ordinary runtime.
# ---------------------------------------------------------------------------


def test_c21_durable_issuance_history_is_conserved() -> None:
    evidence: dict[str, Any] = {"gate": "XXI-C"}
    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            universe = _seed_universe(cursor)
            issuance = _seed_issuance(cursor, universe["tenant_id"])
            durable_before = _issuance_state(cursor, issuance["issuance_id"])
        tenant_id = universe["tenant_id"]
        evidence["issuance_id"] = str(issuance["issuance_id"])
        evidence["durable_before"] = list(durable_before)

        visible = _principal_sees_row(
            "app_user",
            tenant_id,
            "trust_envelope_issuance_log",
            issuance["issuance_id"],
        )
        evidence["app_user_sees_target_row"] = visible
        assert visible == 1, "app_user cannot see the issuance row; refusal proves nothing"

        def forged() -> str:
            return "sha256:" + uuid.uuid4().hex + uuid.uuid4().hex

        attempts: dict[str, Any] = {}
        for column, value in (
            ("envelope_hash", forged()),
            ("semantic_truth_hash", forged()),
            ("subject_ref_hash", forged()),
            ("audit_hash", forged()),
            ("policy_state", "rewritten_by_the_api"),
            ("subject_type", "campaign"),
            ("access_audit_ref", "rewritten_by_the_api"),
            ("status", "success"),
        ):
            outcome = _as_principal(
                "app_user",
                tenant_id,
                f"UPDATE public.trust_envelope_issuance_log SET {column} = %s"
                " WHERE id = %s",
                (value, str(issuance["issuance_id"])),
                label=f"app_user rewrites issued {column}",
            )
            assert outcome["result"] == "REFUSED", outcome
            assert outcome["session_user"] == "app_user", outcome
            assert outcome.get("sqlstate") == "42501", outcome
            attempts[column] = outcome
        evidence["forbidden_rewrites"] = attempts

        deletion = _as_principal(
            "app_user",
            tenant_id,
            "DELETE FROM public.trust_envelope_issuance_log WHERE id = %s",
            (str(issuance["issuance_id"]),),
            label="app_user deletes durable issuance history",
        )
        evidence["app_user_delete"] = deletion
        assert deletion["result"] == "REFUSED", deletion

        # Every other runtime principal is fenced too: no process may restate
        # another process's cryptographic consequence.
        siblings: dict[str, Any] = {}
        for role in ("app_worker", "app_trust_issuer", "app_trust_signer"):
            outcome = _as_principal(
                role,
                tenant_id,
                "UPDATE public.trust_envelope_issuance_log SET envelope_hash = %s"
                " WHERE id = %s",
                (forged(), str(issuance["issuance_id"])),
                label=f"{role} rewrites issued envelope_hash",
            )
            assert outcome["result"] == "REFUSED", outcome
            siblings[role] = outcome
        evidence["sibling_principals"] = siblings

        with conn.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            durable_after = _issuance_state(cursor, issuance["issuance_id"])
        evidence["durable_after"] = list(durable_after)
        assert durable_after == durable_before, (durable_before, durable_after)
    finally:
        conn.close()

    _record_evidence({"c21_issuance_authority": evidence})


# ---------------------------------------------------------------------------
# Gate XXI-D: the lawful issuance recording path still succeeds.
# ---------------------------------------------------------------------------


def test_c21_lawful_issuance_recording_still_succeeds() -> None:
    evidence: dict[str, Any] = {"gate": "XXI-D"}
    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            universe = _seed_universe(cursor)
        tenant_id = universe["tenant_id"]

        def digest() -> str:
            return "sha256:" + uuid.uuid4().hex + uuid.uuid4().hex

        idempotency = digest()
        insert_sql = (
            "INSERT INTO public.trust_envelope_issuance_log (tenant_id,"
            " access_audit_ref, idempotency_key_hash, subject_type, subject_ref_hash,"
            " envelope_hash, semantic_truth_hash, policy_state, audit_ref, audit_hash,"
            " status) VALUES (%s, %s, %s, 'allocation', %s, %s, %s, 'issued', %s, %s,"
            " 'success') ON CONFLICT (tenant_id, idempotency_key_hash) DO NOTHING"
        )
        params = (
            str(tenant_id),
            f"c21-access-{uuid.uuid4().hex[:12]}",
            idempotency,
            digest(),
            digest(),
            digest(),
            f"c21-audit-{uuid.uuid4().hex[:12]}",
            digest(),
        )

        # This is `_insert_issuance_log`, verbatim in shape, under the principal
        # the API session factory actually uses.
        recorded = _as_principal(
            "app_user", tenant_id, insert_sql, params, label="API records issuance"
        )
        evidence["issuance_recorded"] = recorded
        assert recorded["result"] == "ALLOWED", recorded
        assert recorded["rowcount"] == 1, recorded

        # The bounded retry path: an idempotent replay must still be admitted and
        # must not attempt to restate the durable row.
        replay = _as_principal(
            "app_user", tenant_id, insert_sql, params, label="API replays issuance"
        )
        evidence["issuance_replayed"] = replay
        assert replay["result"] == "ALLOWED", replay
        assert replay["rowcount"] == 0, replay

        with conn.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            cursor.execute(
                "SELECT count(*) FROM public.trust_envelope_issuance_log"
                " WHERE tenant_id = %s AND idempotency_key_hash = %s",
                (str(tenant_id), idempotency),
            )
            evidence["durable_rows"] = int(cursor.fetchone()[0])
        assert evidence["durable_rows"] == 1, evidence

        # The trust access log keeps its lawful replay-counter UPDATE: fencing
        # issuance history must not fence the audit ledger's own state machine.
        audit_ref = f"urn:skeldir:audit:c21-{uuid.uuid4().hex[:12]}"
        access_insert = _as_principal(
            "app_user",
            tenant_id,
            "INSERT INTO public.trust_access_log (tenant_id, event_type, status,"
            " request_identity_hash, idempotency_key_hash, subject_type,"
            " policy_state, audit_ref, audit_hash, issuance_state)"
            " VALUES (%s, 'issuance', 'success', %s, %s, 'allocation', 'issued',"
            " %s, %s, 'authorized')",
            (str(tenant_id), digest(), digest(), audit_ref, digest()),
            label="API records a trust access event",
        )
        evidence["access_log_insert"] = access_insert
        assert access_insert["result"] == "ALLOWED", access_insert
        access_update = _as_principal(
            "app_user",
            tenant_id,
            "UPDATE public.trust_access_log SET replay_count = replay_count + 1,"
            " last_replayed_at = now(), updated_at = now() WHERE audit_ref = %s",
            (audit_ref,),
            label="API increments the replay counter",
        )
        evidence["access_log_replay_update"] = access_update
        assert access_update["result"] == "ALLOWED", access_update
        assert access_update["rowcount"] == 1, access_update
    finally:
        conn.close()

    _record_evidence({"c21_lawful_issuance": evidence})


# ---------------------------------------------------------------------------
# Gate XXI-C active falsifier: each issuance layer, severed alone then together.
# ---------------------------------------------------------------------------


def _issuance_triggerdefs(cursor) -> dict[str, str]:
    cursor.execute(
        "SELECT tgname, pg_get_triggerdef(oid) FROM pg_trigger"
        " WHERE tgrelid = 'public.trust_envelope_issuance_log'::regclass"
        "   AND tgname = 'trg_trust_issuance_history_immutable'"
    )
    return {name: definition for name, definition in cursor.fetchall()}


def test_c21_each_issuance_layer_is_independently_load_bearing() -> None:
    evidence: dict[str, Any] = {"gate": "XXI-C active falsifier"}
    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            universe = _seed_universe(cursor)
            issuance = _seed_issuance(cursor, universe["tenant_id"])
            saved = _issuance_triggerdefs(cursor)
            durable_before = _issuance_state(cursor, issuance["issuance_id"])
            privileges_before = _privilege_snapshot(cursor)
        assert len(saved) == 1, saved
        evidence["guard_trigger"] = sorted(saved)
        tenant_id = universe["tenant_id"]

        def rewrite(label: str) -> dict[str, Any]:
            return _as_principal(
                "app_user",
                tenant_id,
                "UPDATE public.trust_envelope_issuance_log SET envelope_hash = %s,"
                " semantic_truth_hash = %s WHERE id = %s",
                (
                    "sha256:" + uuid.uuid4().hex + uuid.uuid4().hex,
                    "sha256:" + uuid.uuid4().hex + uuid.uuid4().hex,
                    str(issuance["issuance_id"]),
                ),
                label=label,
            )

        pristine = rewrite("pristine")
        evidence["pristine"] = pristine
        assert pristine["result"] == "REFUSED", pristine

        # (1) Restore the historical grant. The immutability trigger must refuse.
        with conn.cursor() as cursor:
            cursor.execute(_HISTORICAL_ISSUANCE_GRANT)
        grant_only = rewrite("historical grant restored")
        evidence["historical_grant_restored"] = grant_only
        assert grant_only["result"] == "REFUSED", grant_only
        assert grant_only.get("sqlstate") == "42501", grant_only
        assert "durable trust issuance history" in grant_only.get("error", ""), grant_only

        # (1b) The inherited path is the same defect wearing a different hat.
        with conn.cursor() as cursor:
            cursor.execute(_FENCED_ISSUANCE_GRANT)
            cursor.execute(_HISTORICAL_ISSUANCE_GRANT_RW)
        inherited = rewrite("inherited app_rw grant restored")
        evidence["inherited_grant_restored"] = inherited
        assert inherited["result"] == "REFUSED", inherited
        assert inherited.get("sqlstate") == "42501", inherited
        with conn.cursor() as cursor:
            cursor.execute(_FENCED_ISSUANCE_GRANT_RW)

        # (2) Sever the consequence layer. The privilege layer must refuse.
        with conn.cursor() as cursor:
            for name in saved:
                cursor.execute(
                    f"DROP TRIGGER {name} ON public.trust_envelope_issuance_log"
                )
        trigger_only = rewrite("immutability trigger severed")
        evidence["guard_trigger_severed"] = trigger_only
        assert trigger_only["result"] == "REFUSED", trigger_only

        # (3) Sever both: the audit's rewrite must reappear exactly.
        with conn.cursor() as cursor:
            cursor.execute(_HISTORICAL_ISSUANCE_GRANT)
        historical = rewrite("both layers severed")
        evidence["both_layers_severed"] = historical
        assert historical["result"] == "ALLOWED", historical
        assert historical["rowcount"] == 1, historical
        with conn.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            reproduced = _issuance_state(cursor, issuance["issuance_id"])
        evidence["durable_after_historical_rewrite"] = list(reproduced)
        assert reproduced != durable_before, reproduced

        # (4) Exact restoration, then the same attempt again.
        with conn.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            cursor.execute(
                "UPDATE public.trust_envelope_issuance_log SET envelope_hash = %s,"
                " semantic_truth_hash = %s WHERE id = %s",
                (
                    durable_before[0],
                    durable_before[1],
                    str(issuance["issuance_id"]),
                ),
            )
            cursor.execute(_FENCED_ISSUANCE_GRANT)
            for definition in saved.values():
                cursor.execute(definition)
            restored_defs = _issuance_triggerdefs(cursor)
            restored_state = _issuance_state(cursor, issuance["issuance_id"])
        evidence["exact_restore_identical"] = restored_defs == saved
        assert restored_defs == saved, restored_defs
        assert restored_state == durable_before, restored_state
        restored = rewrite("after exact restoration")
        evidence["after_exact_restoration"] = restored
        assert restored["result"] == "REFUSED", restored
        with conn.cursor() as cursor:
            _assert_privileges_restored(cursor, privileges_before)
    finally:
        conn.close()

    _record_evidence({"c21_issuance_layer_falsifier": evidence})


# ---------------------------------------------------------------------------
# Gate XXI-E: the consequence relations are inside the machine-checked contract,
# and the trigger layer's one escape hatch stays out of runtime reach.
# ---------------------------------------------------------------------------


def test_c21_new_consequence_relations_are_inside_the_authority_contract() -> None:
    """The C20 contract is asserted as an equality; C21 requires it to cover these.

    Both C21 defects existed because the authority map was derived from the
    relations someone had already thought about. Naming the new consequence
    relations here means a future edit that quietly drops one from the contract
    fails against this test rather than against an auditor.
    """

    from tests.trust.test_b25_p13_c20_runtime_authority import (  # noqa: PLC0415
        AUTHORITY_CONTRACT,
    )

    required = {
        "b24_dirty_events": {
            "app_user": {"SELECT", "INSERT"},
            "app_worker": {"SELECT", "INSERT", "UPDATE"},
            "app_ro": {"SELECT"},
            "app_rw": set(),
        },
        "trust_envelope_issuance_log": {
            "app_user": {"SELECT", "INSERT"},
            "app_worker": {"SELECT", "INSERT"},
            "app_ro": {"SELECT"},
            "app_rw": {"SELECT", "INSERT"},
        },
        "trust_replay_events": {
            "app_user": {"SELECT", "INSERT"},
            "app_worker": {"SELECT", "INSERT"},
            "app_ro": {"SELECT"},
            "app_rw": {"SELECT", "INSERT"},
        },
        "trust_scope_denial_events": {
            "app_user": {"SELECT", "INSERT"},
            "app_worker": {"SELECT", "INSERT"},
            "app_ro": {"SELECT"},
            "app_rw": {"SELECT", "INSERT"},
        },
        "trust_access_log": {
            "app_user": {"SELECT", "INSERT", "UPDATE"},
            "app_worker": {"SELECT", "INSERT", "UPDATE"},
            "app_ro": {"SELECT"},
            "app_rw": {"SELECT", "INSERT", "UPDATE"},
            "app_trust_issuer": {"SELECT", "UPDATE"},
            "app_trust_signer": {"SELECT", "UPDATE"},
        },
    }
    for relation, expected in required.items():
        assert relation in AUTHORITY_CONTRACT, (
            f"{relation} carries Trust consequence but is outside the authority"
            " contract, which is exactly how C21's two defects survived"
        )
        assert AUTHORITY_CONTRACT[relation] == expected, relation


def test_c21_no_runtime_principal_inherits_the_new_relation_owners() -> None:
    """Both new guards admit the relation owner, so nothing may reach it.

    The owner branch exists because the owner can drop the trigger outright and
    every environment migrates as it. That is only sound while no runtime login
    can act as the owner; an ownership transfer or a membership grant would open
    the consequence layer silently and leave only the privilege layer standing.
    """

    conn = _admin_connection()
    reachable: dict[str, list[str]] = {}
    try:
        with conn.cursor() as cursor:
            for relation in (
                "b24_dirty_events",
                "trust_envelope_issuance_log",
            ):
                cursor.execute(
                    "SELECT owner.rolname FROM pg_class AS relation"
                    " JOIN pg_roles AS owner ON owner.oid = relation.relowner"
                    " WHERE relation.oid = %s::regclass",
                    (f"public.{relation}",),
                )
                owner = cursor.fetchone()[0]
                found = []
                for principal in PRINCIPALS:
                    cursor.execute(
                        "SELECT 1 FROM pg_roles WHERE rolname = %s", (principal,)
                    )
                    if cursor.fetchone() is None:
                        continue
                    cursor.execute(
                        "SELECT pg_has_role(%s, %s, 'USAGE')", (principal, owner)
                    )
                    if cursor.fetchone()[0]:
                        found.append(principal)
                reachable[relation] = found
    finally:
        conn.close()
    assert reachable == {
        "b24_dirty_events": [],
        "trust_envelope_issuance_log": [],
    }, reachable


def test_c21_guards_admit_no_null_or_unknown_bypass() -> None:
    """SQL three-valued logic must not be a way through either new guard.

    Both guards branch on ``IS DISTINCT FROM``, which is NULL-safe by
    construction -- but "by construction" is an argument, and the directive asks
    for a probe. A NULL-valued rewrite of a nullable authority column is exactly
    the shape that would slip past an ``<>`` comparison.
    """

    evidence: dict[str, Any] = {"gate": "XXI-A/XXI-C NULL physics"}
    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            universe = _seed_universe(cursor)
            issuance = _seed_issuance(cursor, universe["tenant_id"])
            privileges_before = _privilege_snapshot(cursor)
        tenant_id = universe["tenant_id"]

        # Restore the historical grants so the *consequence* layer is the thing
        # under test: a privilege refusal would say nothing about NULL handling.
        with conn.cursor() as cursor:
            cursor.execute(_HISTORICAL_DIRTY_GRANT)
            cursor.execute(_HISTORICAL_ISSUANCE_GRANT)
        try:
            nulled_hash = _as_principal(
                "app_user",
                tenant_id,
                "UPDATE public.b24_dirty_events SET source_snapshot_hash = NULL"
                " WHERE id = %s",
                (str(universe["dirty_id"]),),
                label="app_user nulls the source snapshot",
            )
            evidence["dirty_null_snapshot"] = nulled_hash
            assert nulled_hash["result"] == "REFUSED", nulled_hash
            assert nulled_hash.get("sqlstate") == "42501", nulled_hash

            nulled_event = _as_principal(
                "app_user",
                tenant_id,
                "UPDATE public.b24_dirty_events SET event_hash = NULL,"
                " source_event_id = NULL WHERE id = %s",
                (str(universe["dirty_id"]),),
                label="app_user nulls nullable provenance columns",
            )
            evidence["dirty_null_provenance"] = nulled_event
            assert nulled_event["result"] == "REFUSED", nulled_event

            # A no-op UPDATE changes no authority and must stay lawful: the guard
            # is scoped to consequence, not to the statement keyword.
            noop = _as_principal(
                "app_user",
                tenant_id,
                "UPDATE public.b24_dirty_events SET updated_at = updated_at"
                " WHERE id = %s",
                (str(universe["dirty_id"]),),
                label="app_user performs a consequence-free update",
            )
            evidence["dirty_noop_update"] = noop
            assert noop["result"] == "ALLOWED", noop
            assert noop["rowcount"] == 1, noop

            # The issuance guard is unconditional, so even a self-assignment --
            # a statement that changes nothing -- is refused for a non-owner.
            self_assign = _as_principal(
                "app_user",
                tenant_id,
                "UPDATE public.trust_envelope_issuance_log"
                " SET envelope_hash = envelope_hash WHERE id = %s",
                (str(issuance["issuance_id"]),),
                label="app_user self-assigns the issued envelope hash",
            )
            evidence["issuance_self_assignment"] = self_assign
            assert self_assign["result"] == "REFUSED", self_assign
            assert self_assign.get("sqlstate") == "42501", self_assign
        finally:
            with conn.cursor() as cursor:
                cursor.execute(_FENCED_DIRTY_GRANT)
                cursor.execute(_FENCED_ISSUANCE_GRANT)
                _assert_privileges_restored(cursor, privileges_before)
    finally:
        conn.close()

    _record_evidence({"c21_null_physics": evidence})
