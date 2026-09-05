"""B2.5-P14 Corrective IV Exit Gate 1 -- terminal provenance conservation.

The proposition::

    after a signer-confirmed issuance is terminal,
    every field required to reconstruct what was signed and why it was issued
    stays causally consistent for the full supported lifecycle

Two independent audits produced the counterexample this suite exists to close.
On protected main, once a lawful terminal issuance existed, ordinary runtime
principals could ``UPDATE`` the parent ``trust_access_log`` row's identity
columns -- ``envelope_hash``, ``semantic_truth_hash``, ``status`` and the rest --
and leave the durable record and the witness it is referentially bound to
disagreeing about what was signed.

The root cause was not a missing column in a list. The C16/C17-B guard computes
``consequence_changed`` over the issuance state machine and returns *before* its
terminal and principal checks when nothing on that list changed, so an UPDATE
that touched only truth-bearing identity columns never reached any of them. The
sibling guard on ``trust_issuance_attempts`` has no such short-circuit and was
correctly fenced -- which is the control that identifies the short-circuit rather
than the column list as the defect.

This suite therefore measures the *partition*, not a list of remembered columns:
it reads ``trust_access_log``'s live column set from the catalog and requires
every column to be classified, so a future column is a failing test until
someone decides which side of the fence it belongs on.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import psycopg2
import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P14_GATE0_PROOF") != "1",
    reason="P14 Corrective IV proofs require a provisioned production role graph",
)


# The partition the migration encodes. Operational metadata a holder of UPDATE
# may write; the issuance state machine C16/C17-B adjudicates; everything else
# is the immutable causal witness.
OPERATIONAL_COLUMNS = ("replay_count", "last_replayed_at", "updated_at")

ISSUANCE_MACHINE_COLUMNS = (
    "issuance_state",
    "issued_at",
    "issuance_attempted_at",
    "issuance_outcome_unknown_at",
    "known_signature_at",
    "issued_attempt_id",
    "issued_signing_key_id",
    "issued_signature_hash",
    "issued_signature",
    "issued_envelope",
    "issuance_attempt_count",
    "issuance_unknown_outcome_count",
)

# Every witness column, with a mutation that is *type-valid* for it. A refusal
# has to come from the fence, not from a CHECK the fixture tripped by accident.
WITNESS_MUTATIONS: tuple[tuple[str, str], ...] = (
    ("event_type", "'read'"),
    ("status", "'degraded'"),
    ("request_identity_hash", "'sha256:' || repeat('0', 63) || '5'"),
    ("idempotency_key_hash", "'sha256:' || repeat('0', 63) || '5'"),
    ("subject_type", "'export'"),
    ("subject_ref_hash", "'sha256:' || repeat('0', 63) || '5'"),
    ("envelope_hash", "'sha256:' || repeat('0', 63) || '5'"),
    ("semantic_truth_hash", "'sha256:' || repeat('0', 63) || '5'"),
    ("policy_state", "'blocked'"),
    ("reason_code", "'p14_r4_probe'"),
    ("audit_ref", "'urn:skeldir:audit:p14-r4-rewritten'"),
    ("audit_hash", "'sha256:' || repeat('0', 63) || '5'"),
    ("evidence_refs_allowed", "false"),
    ("created_at", "now() - interval '400 days'"),
    ("tenant_id", "gen_random_uuid()"),
    ("id", "gen_random_uuid()"),
)

UPDATE_HOLDERS = ("app_user", "app_worker", "app_trust_issuer", "app_trust_signer")


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------


def _admin_dsn() -> str:
    for name in (
        "P14_ADMIN_DATABASE_URL",
        "C21_ADMIN_DATABASE_URL",
        "C20_ADMIN_DATABASE_URL",
        "MIGRATION_DATABASE_URL",
    ):
        value = os.getenv(name, "").strip()
        if value:
            return value.replace("postgresql+psycopg2://", "postgresql://")
    raise RuntimeError("P14_ADMIN_DATABASE_URL is required for the Gate 1 proof")


def _admin_connection():
    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    return conn


def _role_connection(role: str):
    parts = urlsplit(_admin_dsn())
    conn = psycopg2.connect(
        dbname=parts.path.lstrip("/"),
        host=parts.hostname,
        port=parts.port or 5432,
        user=role,
        password=os.getenv(f"P14_{role.upper()}_PASSWORD", role),
    )
    conn.autocommit = False
    return conn


def _bind_tenant(cursor, tenant_id) -> None:
    cursor.execute(
        "SELECT set_config('app.current_tenant_id', %s, false)", (str(tenant_id),)
    )


def _digest() -> str:
    return "sha256:" + uuid.uuid4().hex + uuid.uuid4().hex


def _record_evidence(payload: dict[str, Any]) -> None:
    target = os.getenv("P14_EVIDENCE_PATH", "").strip()
    if not target:
        return
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    existing.update(payload)
    path.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------------------
# The lawful lineage, driven through the real production logins.
# ---------------------------------------------------------------------------


def _seed_tenant(cursor) -> uuid.UUID:
    tenant_id = uuid.uuid4()
    label = tenant_id.hex[:8]
    cursor.execute(
        "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
        " VALUES (%s, %s, %s, %s)",
        (
            str(tenant_id),
            f"p14r4-{label}",
            uuid.uuid4().hex,
            f"p14r4-{label}@example.invalid",
        ),
    )
    return tenant_id


def _drive_lawful_terminal_issuance(tenant_id) -> dict[str, str]:
    """Authorize, attempt, sign, complete and project, as the real principals.

    Nothing here runs as the owner: ``app_user`` authorizes, ``app_trust_issuer``
    opens the attempt and completes it, ``app_trust_signer`` records the
    signature consequence. The terminal projection therefore passes the P14
    Gate 0 consequence guard on its merits.
    """

    material = {
        "audit_ref": f"urn:skeldir:audit:p14r4-{uuid.uuid4().hex}",
        "request_identity_hash": _digest(),
        "idempotency_key_hash": _digest(),
        "subject_type": "match_verdict",
        "subject_ref_hash": _digest(),
        "envelope_hash": _digest(),
        "semantic_truth_hash": _digest(),
        "policy_state": "read_only",
        "audit_hash": _digest(),
    }

    user = _role_connection("app_user")
    try:
        with user.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            cursor.execute(
                "INSERT INTO public.trust_access_log (tenant_id, event_type, status,"
                " request_identity_hash, idempotency_key_hash, subject_type,"
                " subject_ref_hash, envelope_hash, semantic_truth_hash, policy_state,"
                " audit_ref, audit_hash, evidence_refs_allowed, issuance_state)"
                " VALUES (%s,'issuance','success',%s,%s,%s,%s,%s,%s,%s,%s,%s,true,"
                "'authorized')",
                (
                    str(tenant_id),
                    material["request_identity_hash"],
                    material["idempotency_key_hash"],
                    material["subject_type"],
                    material["subject_ref_hash"],
                    material["envelope_hash"],
                    material["semantic_truth_hash"],
                    material["policy_state"],
                    material["audit_ref"],
                    material["audit_hash"],
                ),
            )
        user.commit()
    finally:
        user.close()

    attempt_id = uuid.uuid4()
    issuer = _role_connection("app_trust_issuer")
    try:
        with issuer.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            cursor.execute(
                "UPDATE public.trust_access_log SET issuance_state='signing',"
                " issuance_attempted_at=now(), issuance_attempt_count=1"
                " WHERE tenant_id=%s AND audit_ref=%s",
                (str(tenant_id), material["audit_ref"]),
            )
            cursor.execute(
                "INSERT INTO public.trust_issuance_attempts"
                " (id, tenant_id, audit_ref, attempt_number, attempt_state)"
                " VALUES (%s,%s,%s,1,'signing')",
                (str(attempt_id), str(tenant_id), material["audit_ref"]),
            )
        issuer.commit()
    finally:
        issuer.close()

    signer = _role_connection("app_trust_signer")
    try:
        with signer.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            cursor.execute(
                "UPDATE public.trust_issuance_attempts"
                " SET attempt_state='signature_known', signature_known_at=now(),"
                " signing_key_id='kid:p14r4', signature_hash='sha256:'||repeat('a',64),"
                " signature=decode(repeat('ab',64),'hex'),"
                " signed_envelope_hash='sha256:'||repeat('b',64),"
                " signed_envelope='{}'::jsonb"
                " WHERE tenant_id=%s AND id=%s RETURNING signature_known_at",
                (str(tenant_id), str(attempt_id)),
            )
            known_at = cursor.fetchone()[0]
            cursor.execute(
                "UPDATE public.trust_access_log SET issuance_state='signature_known',"
                " known_signature_at=%s, issued_attempt_id=%s"
                " WHERE tenant_id=%s AND audit_ref=%s",
                (known_at, str(attempt_id), str(tenant_id), material["audit_ref"]),
            )
        signer.commit()
    finally:
        signer.close()

    issuer = _role_connection("app_trust_issuer")
    try:
        with issuer.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            cursor.execute(
                "UPDATE public.trust_access_log SET issuance_state='issued',"
                " issued_at=now(), issued_signing_key_id='kid:p14r4',"
                " issued_signature_hash='sha256:'||repeat('a',64),"
                " issued_signature=decode(repeat('ab',64),'hex'),"
                " issued_envelope='{}'::jsonb"
                " WHERE tenant_id=%s AND audit_ref=%s",
                (str(tenant_id), material["audit_ref"]),
            )
            cursor.execute(
                "UPDATE public.trust_issuance_attempts SET attempt_state='issued',"
                " issued_at=now() WHERE tenant_id=%s AND id=%s",
                (str(tenant_id), str(attempt_id)),
            )
            cursor.execute(
                "INSERT INTO public.trust_envelope_issuance_log (tenant_id,"
                " access_audit_ref, idempotency_key_hash, subject_type,"
                " subject_ref_hash, envelope_hash, semantic_truth_hash, policy_state,"
                " audit_ref, audit_hash, status)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'success')",
                (
                    str(tenant_id),
                    material["audit_ref"],
                    material["idempotency_key_hash"],
                    material["subject_type"],
                    material["subject_ref_hash"],
                    material["envelope_hash"],
                    material["semantic_truth_hash"],
                    material["policy_state"],
                    material["audit_ref"],
                    material["audit_hash"],
                ),
            )
        issuer.commit()
    finally:
        issuer.close()
    return material


def _attempt_update(role: str, tenant_id, audit_ref: str, column: str, expr: str):
    outcome: dict[str, Any] = {"principal": role, "column": column}
    conn = _role_connection(role)
    try:
        with conn.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            cursor.execute(
                f"UPDATE public.trust_access_log SET {column} = {expr}"
                " WHERE tenant_id = %s AND audit_ref = %s",
                (str(tenant_id), audit_ref),
            )
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


# ---------------------------------------------------------------------------
# The partition is total over the relation's real columns.
# ---------------------------------------------------------------------------


def test_p14_r4_the_witness_partition_covers_every_access_log_column() -> None:
    """Every live column is classified, and the fence is the default.

    A column added by a later migration and never classified is a *witness*
    column at runtime -- the guard iterates ``to_jsonb(NEW)`` rather than a
    baked list -- and a failing assertion here, so the classification decision
    is made deliberately instead of by omission.
    """

    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_schema='public' AND table_name='trust_access_log'"
                " ORDER BY ordinal_position"
            )
            columns = [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()

    classified = (
        set(OPERATIONAL_COLUMNS)
        | set(ISSUANCE_MACHINE_COLUMNS)
        | {name for name, _ in WITNESS_MUTATIONS}
    )
    unclassified = sorted(set(columns) - classified)
    assert not unclassified, (
        "trust_access_log gained columns with no declared conservation class: "
        f"{unclassified}"
    )
    # And nothing is claimed twice.
    assert not set(OPERATIONAL_COLUMNS) & set(ISSUANCE_MACHINE_COLUMNS)
    assert not set(OPERATIONAL_COLUMNS) & {n for n, _ in WITNESS_MUTATIONS}
    assert not set(ISSUANCE_MACHINE_COLUMNS) & {n for n, _ in WITNESS_MUTATIONS}
    _record_evidence({"p14_r4_access_log_columns": columns})


# ---------------------------------------------------------------------------
# Exit Gate 1 -- the post-terminal mutation matrix.
# ---------------------------------------------------------------------------


def test_p14_r4_post_terminal_witness_is_immutable_under_every_update_holder() -> None:
    """The audits' counterexample, run field by field under every real login."""

    admin = _admin_connection()
    try:
        with admin.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
        material = _drive_lawful_terminal_issuance(tenant_id)

        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT issuance_state FROM public.trust_access_log"
                " WHERE tenant_id=%s AND audit_ref=%s",
                (str(tenant_id), material["audit_ref"]),
            )
            state = cursor.fetchone()[0]
            cursor.execute(
                "SELECT count(*) FROM public.trust_envelope_issuance_log"
                " WHERE tenant_id=%s AND access_audit_ref=%s",
                (str(tenant_id), material["audit_ref"]),
            )
            terminal_rows = cursor.fetchone()[0]
        # Positive control first: the experiment is only meaningful against a
        # lineage that genuinely reached terminal truth.
        assert state == "issued"
        assert terminal_rows == 1

        matrix = [
            _attempt_update(role, tenant_id, material["audit_ref"], column, expr)
            for role in UPDATE_HOLDERS
            for column, expr in WITNESS_MUTATIONS
        ]
        allowed = [row for row in matrix if row["result"] == "ALLOWED"]
        assert not allowed, f"post-terminal witness mutation accepted: {allowed}"
        for row in matrix:
            assert row["sqlstate"] == "42501", row
            # ``tenant_id`` was already fenced by the C16 tenant-rebind guard,
            # which fires first. Accepting only its own reason keeps this from
            # crediting the new fence for a refusal an older layer owns.
            expected = (
                "trust_issuance_authority_violation:tenant_rebind"
                if row["column"] == "tenant_id"
                else "trust_access_log_witness_immutable"
            )
            assert expected in row["error"], row

        # And the two records still agree about what was signed.
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT ledger.envelope_hash = terminal.envelope_hash"
                "   AND ledger.semantic_truth_hash = terminal.semantic_truth_hash"
                "   AND ledger.idempotency_key_hash = terminal.idempotency_key_hash"
                "   AND ledger.subject_ref_hash = terminal.subject_ref_hash"
                "   AND ledger.audit_hash = terminal.audit_hash"
                "   AND ledger.policy_state = terminal.policy_state"
                "   AND ledger.status = terminal.status"
                " FROM public.trust_access_log AS ledger"
                " JOIN public.trust_envelope_issuance_log AS terminal"
                "   ON terminal.tenant_id = ledger.tenant_id"
                "  AND terminal.access_audit_ref = ledger.audit_ref"
                " WHERE ledger.tenant_id = %s AND ledger.audit_ref = %s",
                (str(tenant_id), material["audit_ref"]),
            )
            agrees = cursor.fetchone()[0]
        assert agrees is True
    finally:
        admin.close()

    _record_evidence(
        {
            "p14_r4_post_terminal_mutation_matrix": matrix,
            "p14_r4_post_terminal_allowed_count": 0,
        }
    )


def test_p14_r4_the_witness_is_immutable_before_terminalization_too() -> None:
    """Fencing only after terminal state would leave the class open.

    A witness column rewritten while the ledger is still ``authorized`` is
    projected into terminal history by the Gate 0 agreement guard, and the
    durable record then faithfully records a falsified witness. The fence
    therefore starts at INSERT, which is both the narrower repair and the total
    one.
    """

    admin = _admin_connection()
    try:
        with admin.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
        material = {
            "audit_ref": f"urn:skeldir:audit:p14r4-{uuid.uuid4().hex}",
            "semantic_truth_hash": _digest(),
        }
        user = _role_connection("app_user")
        try:
            with user.cursor() as cursor:
                _bind_tenant(cursor, tenant_id)
                cursor.execute(
                    "INSERT INTO public.trust_access_log (tenant_id, event_type,"
                    " status, request_identity_hash, idempotency_key_hash,"
                    " subject_type, subject_ref_hash, envelope_hash,"
                    " semantic_truth_hash, policy_state, audit_ref, audit_hash,"
                    " evidence_refs_allowed, issuance_state)"
                    " VALUES (%s,'issuance','success',%s,%s,'match_verdict',%s,%s,"
                    " %s,'read_only',%s,%s,true,'authorized')",
                    (
                        str(tenant_id),
                        _digest(),
                        _digest(),
                        _digest(),
                        _digest(),
                        material["semantic_truth_hash"],
                        material["audit_ref"],
                        _digest(),
                    ),
                )
            user.commit()
        finally:
            user.close()

        outcome = _attempt_update(
            "app_user",
            tenant_id,
            material["audit_ref"],
            "semantic_truth_hash",
            "'sha256:' || repeat('0', 63) || '5'",
        )
        assert outcome["result"] == "REFUSED", outcome
        assert "trust_access_log_witness_immutable:semantic_truth_hash" in (
            outcome["error"]
        )
    finally:
        admin.close()


def test_p14_r4_operational_metadata_remains_writable() -> None:
    """The narrow repair keeps the one lawful UPDATE the API actually performs.

    ``_upsert_access_log``'s replay path is ``ON CONFLICT DO UPDATE SET
    replay_count = replay_count + 1, last_replayed_at = now(), updated_at =
    now()``. Solving Gate 1 by revoking UPDATE would have broken it; the fence
    is a column partition precisely so it does not.
    """

    admin = _admin_connection()
    try:
        with admin.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
        material = _drive_lawful_terminal_issuance(tenant_id)
        outcomes = [
            _attempt_update(role, tenant_id, material["audit_ref"], column, expr)
            for role in UPDATE_HOLDERS
            for column, expr in (
                ("replay_count", "replay_count + 1"),
                ("last_replayed_at", "now()"),
                ("updated_at", "now()"),
            )
        ]
        refused = [row for row in outcomes if row["result"] != "ALLOWED"]
        assert not refused, f"lawful operational metadata write refused: {refused}"

        # The real replay statement, verbatim in shape, still conducts.
        user = _role_connection("app_user")
        try:
            with user.cursor() as cursor:
                _bind_tenant(cursor, tenant_id)
                cursor.execute(
                    "UPDATE public.trust_access_log"
                    " SET replay_count = replay_count + 1, last_replayed_at = now(),"
                    "     updated_at = now()"
                    " WHERE tenant_id = %s AND audit_ref = %s"
                    " RETURNING replay_count",
                    (str(tenant_id), material["audit_ref"]),
                )
                replay_count = cursor.fetchone()[0]
            user.commit()
        finally:
            user.close()
        assert replay_count >= 1
    finally:
        admin.close()


def test_p14_r4_the_witness_fence_is_independently_load_bearing() -> None:
    """GREEN -> meaningful RED -> exact restore -> GREEN, on real DDL.

    Removing the fence must make the audits' counterexample succeed again, and
    restoring the exact trigger definition must close it. Without this, a green
    matrix above could be measuring a privilege that happened to be absent
    rather than a fence that is present.
    """

    admin = _admin_connection()
    try:
        with admin.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
        material = _drive_lawful_terminal_issuance(tenant_id)

        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT pg_get_triggerdef(oid) FROM pg_catalog.pg_trigger"
                " WHERE tgname = 'trg_trust_access_log_witness_immutability'"
                "   AND NOT tgisinternal"
            )
            triggerdef = cursor.fetchone()[0]
        assert triggerdef

        fenced = _attempt_update(
            "app_user",
            tenant_id,
            material["audit_ref"],
            "semantic_truth_hash",
            "'sha256:' || repeat('0', 63) || '5'",
        )
        assert fenced["result"] == "REFUSED", fenced

        try:
            with admin.cursor() as cursor:
                cursor.execute(
                    "DROP TRIGGER trg_trust_access_log_witness_immutability"
                    " ON public.trust_access_log"
                )
            severed = _attempt_update(
                "app_user",
                tenant_id,
                material["audit_ref"],
                "semantic_truth_hash",
                "'sha256:' || repeat('0', 63) || '5'",
            )
            # RED for the predicted cause: without the fence the audits'
            # counterexample succeeds, and the two records disagree.
            assert severed["result"] == "ALLOWED", severed
            with admin.cursor() as cursor:
                cursor.execute(
                    "SELECT ledger.semantic_truth_hash = terminal.semantic_truth_hash"
                    " FROM public.trust_access_log AS ledger"
                    " JOIN public.trust_envelope_issuance_log AS terminal"
                    "   ON terminal.tenant_id = ledger.tenant_id"
                    "  AND terminal.access_audit_ref = ledger.audit_ref"
                    " WHERE ledger.tenant_id = %s AND ledger.audit_ref = %s",
                    (str(tenant_id), material["audit_ref"]),
                )
                assert cursor.fetchone()[0] is False
        finally:
            with admin.cursor() as cursor:
                cursor.execute(triggerdef)

        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT pg_get_triggerdef(oid) FROM pg_catalog.pg_trigger"
                " WHERE tgname = 'trg_trust_access_log_witness_immutability'"
                "   AND NOT tgisinternal"
            )
            restored = cursor.fetchone()[0]
        assert restored == triggerdef

        with admin.cursor() as cursor:
            tenant_two = _seed_tenant(cursor)
        second = _drive_lawful_terminal_issuance(tenant_two)
        reclosed = _attempt_update(
            "app_user",
            tenant_two,
            second["audit_ref"],
            "semantic_truth_hash",
            "'sha256:' || repeat('0', 63) || '5'",
        )
        assert reclosed["result"] == "REFUSED", reclosed
    finally:
        admin.close()


def test_p14_r4_signing_attempt_evidence_stays_terminal() -> None:
    """The sibling relation, measured rather than assumed.

    ``trust_issuance_attempts`` has no early-return short-circuit, which is the
    control that identifies the short-circuit as the defect. Asserting it here
    keeps that control from silently disappearing.
    """

    admin = _admin_connection()
    try:
        with admin.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
        material = _drive_lawful_terminal_issuance(tenant_id)

        outcomes = []
        for role in ("app_trust_issuer", "app_trust_signer", "app_user", "app_worker"):
            conn = _role_connection(role)
            try:
                with conn.cursor() as cursor:
                    _bind_tenant(cursor, tenant_id)
                    cursor.execute(
                        "UPDATE public.trust_issuance_attempts"
                        " SET signature_hash = 'sha256:' || repeat('f', 64)"
                        " WHERE tenant_id = %s AND audit_ref = %s",
                        (str(tenant_id), material["audit_ref"]),
                    )
                conn.commit()
                outcomes.append((role, "ALLOWED"))
            except psycopg2.Error as exc:
                conn.rollback()
                outcomes.append((role, f"REFUSED:{exc.pgcode}"))
            finally:
                conn.close()
        assert all(result.startswith("REFUSED") for _, result in outcomes), outcomes
    finally:
        admin.close()
