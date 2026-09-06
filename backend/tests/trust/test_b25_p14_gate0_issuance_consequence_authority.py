"""B2.5-P14 Gate 0 and the B2.7/B2.8 database physics.

Gate 0's proposition::

    successful issuance history  =>  lawful successful issuance consequence

Independent audit 67 physically executed, as the real ``app_worker`` login on
protected main::

    INSERT INTO trust_envelope_issuance_log (..., status) VALUES (..., 'success')

and received ``INSERT 0 1``. This suite reproduces that exact statement against
the current database, requires it refused for every principal without causal
responsibility for issuance, and then severs each remediation layer -- privilege,
referential binding, consequence guard -- independently and together. Only the
fully severed state may reproduce the audit's fabrication; that is what makes
the three green layers non-vacuous rather than merely co-present.

The suite connects as the real PostgreSQL logins the deployed processes use. It
does not read a privilege catalogue and conclude, and it does not assert that a
refusal happened without first proving the refused principal could see the state
it was attacking -- Corrective XX's lesson was that RLS can hide a row so
completely that a guard never runs and the experiment measures nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import psycopg2
import pytest

from app.explanation.templates import EXPLANATION_TEMPLATE_REGISTRY_HASH
from app.trust.machine_identity import generate_machine_token


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P14_GATE0_PROOF") != "1",
    reason="P14 Gate 0 proof requires a provisioned production role graph",
)


PRINCIPALS = (
    "app_user",
    "app_worker",
    "app_rw",
    "app_ro",
    "app_dispatch_publisher",
    "app_celery_transport",
    "app_trust_issuer",
    "app_trust_signer",
    "app_b28_requester",
    "app_b28_solver",
)

FENCED_RELATIONS = (
    "trust_envelope_issuance_log",
    "trust_replay_events",
    "trust_scope_denial_events",
)

P14_RELATIONS = (
    "b27_explanation_materializations",
    "b28_simulation_requests",
    "b28_simulation_results",
    "b28_proposals",
)

# The historical grant, verbatim from the migration that authored it.
_HISTORICAL_RW_GRANT = (
    "GRANT SELECT, INSERT ON TABLE public.trust_envelope_issuance_log TO app_rw"
)
_FENCED_RW_GRANT = (
    "REVOKE ALL ON TABLE public.trust_envelope_issuance_log FROM app_rw; "
    "GRANT SELECT ON TABLE public.trust_envelope_issuance_log TO app_rw"
)


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
    raise RuntimeError("P14_ADMIN_DATABASE_URL is required for the Gate 0 proof")


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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _seed_tenant(cursor) -> uuid.UUID:
    tenant_id = uuid.uuid4()
    label = tenant_id.hex[:8]
    cursor.execute(
        "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
        " VALUES (%s, %s, %s, %s)",
        (
            str(tenant_id),
            f"p14-{label}",
            uuid.uuid4().hex,
            f"p14-{label}@example.invalid",
        ),
    )
    return tenant_id


def _lawful_material(subject_type: str = "match_verdict") -> dict[str, str]:
    """The field set ``record_trust_audit_event`` writes to both relations.

    One ``_params(...)`` mapping produces the ledger row and the durable
    issuance row inside one transaction, so the two agree by construction. P14
    Gate 0 makes that agreement a database law rather than an accident of the
    call site.
    """

    audit_ref = f"urn:skeldir:audit:p14-{uuid.uuid4().hex}"
    return {
        "audit_ref": audit_ref,
        "request_identity_hash": _digest(),
        "idempotency_key_hash": _digest(),
        "subject_type": subject_type,
        "subject_ref_hash": _digest(),
        "envelope_hash": _digest(),
        "semantic_truth_hash": _digest(),
        "policy_state": "read_only",
        "audit_hash": _digest(),
    }


_LEDGER_INSERT = (
    "INSERT INTO public.trust_access_log (tenant_id, event_type, status,"
    " request_identity_hash, idempotency_key_hash, subject_type, subject_ref_hash,"
    " envelope_hash, semantic_truth_hash, policy_state, audit_ref, audit_hash,"
    " evidence_refs_allowed, issuance_state)"
    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)

_ISSUANCE_INSERT = (
    "INSERT INTO public.trust_envelope_issuance_log (tenant_id, access_audit_ref,"
    " idempotency_key_hash, subject_type, subject_ref_hash, envelope_hash,"
    " semantic_truth_hash, policy_state, audit_ref, audit_hash, status)"
    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'success')"
)


def _ledger_params(tenant_id, material: dict[str, str], *, event_type="issuance",
                   status="success") -> tuple[Any, ...]:
    return (
        str(tenant_id),
        event_type,
        status,
        material["request_identity_hash"],
        material["idempotency_key_hash"],
        material["subject_type"],
        material["subject_ref_hash"],
        material["envelope_hash"],
        material["semantic_truth_hash"],
        material["policy_state"],
        material["audit_ref"],
        material["audit_hash"],
        # P7 refuses evidence refs on a refusal/denial record; the ledger's own
        # CHECK says so, and a fixture that ignored it would not be a fixture of
        # the lawful path.
        event_type not in ("refusal", "scope_denial"),
        "authorized" if event_type == "issuance" else "not_applicable",
    )


def _issuance_params(tenant_id, material: dict[str, str]) -> tuple[Any, ...]:
    return (
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
    )


def _seed_ledger(cursor, tenant_id, material: dict[str, str]) -> None:
    _bind_tenant(cursor, tenant_id)
    cursor.execute(_LEDGER_INSERT, _ledger_params(tenant_id, material))


def _seed_completed_lineage(cursor, tenant_id, material: dict[str, str]) -> None:
    """Create a completed C16/C17 witness for the P14 trigger-only proof.

    This is a fixture for the database predicate. The P11/C17 topology tests
    separately prove the real API -> signer -> verification consequence path.
    """

    _seed_ledger(cursor, tenant_id, material)
    attempt_id = uuid.uuid4()
    issuer = _role_connection("app_trust_issuer")
    try:
        with issuer.cursor() as issuer_cursor:
            _bind_tenant(issuer_cursor, tenant_id)
            issuer_cursor.execute(
                "UPDATE public.trust_access_log SET issuance_state='signing', "
                "issuance_attempted_at=now(), issuance_attempt_count=1 "
                "WHERE tenant_id=%s AND audit_ref=%s",
                (str(tenant_id), material["audit_ref"]),
            )
            issuer_cursor.execute(
                "INSERT INTO public.trust_issuance_attempts "
                "(id, tenant_id, audit_ref, attempt_number, attempt_state) "
                "VALUES (%s, %s, %s, 1, 'signing')",
                (str(attempt_id), str(tenant_id), material["audit_ref"]),
            )
        issuer.commit()
    finally:
        issuer.close()

    signer = _role_connection("app_trust_signer")
    try:
        with signer.cursor() as signer_cursor:
            _bind_tenant(signer_cursor, tenant_id)
            signer_cursor.execute(
                "UPDATE public.trust_issuance_attempts "
                "SET attempt_state='signature_known', signature_known_at=now(), "
                "signing_key_id='kid:p14-fixture', "
                "signature_hash='sha256:' || repeat('a',64), "
                "signature=decode(repeat('ab',64),'hex'), "
                "signed_envelope_hash='sha256:' || repeat('b',64), "
                "signed_envelope='{}'::jsonb "
                "WHERE tenant_id=%s AND id=%s RETURNING signature_known_at",
                (str(tenant_id), str(attempt_id)),
            )
            known_at = signer_cursor.fetchone()[0]
            signer_cursor.execute(
                "UPDATE public.trust_access_log SET issuance_state='signature_known', "
                "known_signature_at=%s, issued_attempt_id=%s "
                "WHERE tenant_id=%s AND audit_ref=%s",
                (known_at, str(attempt_id), str(tenant_id), material["audit_ref"]),
            )
        signer.commit()
    finally:
        signer.close()

    issuer = _role_connection("app_trust_issuer")
    try:
        with issuer.cursor() as issuer_cursor:
            _bind_tenant(issuer_cursor, tenant_id)
            issuer_cursor.execute(
                "UPDATE public.trust_access_log "
                "SET issuance_state='issued', issued_at=now(), "
                "issued_signing_key_id='kid:p14-fixture', "
                "issued_signature_hash='sha256:' || repeat('a',64), "
                "issued_signature=decode(repeat('ab',64),'hex'), "
                "issued_envelope='{}'::jsonb "
                "WHERE tenant_id=%s AND audit_ref=%s",
                (str(tenant_id), material["audit_ref"]),
            )
            issuer_cursor.execute(
                "UPDATE public.trust_issuance_attempts SET attempt_state='issued', "
                "issued_at=now() WHERE tenant_id=%s AND id=%s",
                (str(tenant_id), str(attempt_id)),
            )
        issuer.commit()
    finally:
        issuer.close()


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


def _effective_privileges(cursor, relation: str) -> dict[str, list[str]]:
    observed: dict[str, list[str]] = {}
    for principal in PRINCIPALS:
        held: list[str] = []
        for operation in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            cursor.execute(
                "SELECT has_table_privilege(%s, %s, %s)",
                (principal, f"public.{relation}", operation),
            )
            if cursor.fetchone()[0]:
                held.append(operation)
        observed[principal] = held
    return observed


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
# Gate 0 -- the authority matrix as migrated, before anything mutates it.
# ---------------------------------------------------------------------------


def test_p14_gate0_migrated_authority_matrix_holds_before_any_mutation() -> None:
    """The as-migrated state is judged first, while nothing has touched it."""

    expected = {
        relation: {
            "app_user": ["INSERT", "SELECT"],
            "app_worker": ["SELECT"],
            "app_rw": ["SELECT"],
            "app_ro": ["SELECT"],
            "app_dispatch_publisher": [],
            "app_celery_transport": [],
            "app_trust_issuer": [],
            "app_trust_signer": [],
            "app_b28_requester": [],
            "app_b28_solver": [],
        }
        for relation in ("trust_replay_events", "trust_scope_denial_events")
    }
    expected["trust_envelope_issuance_log"] = {
        "app_user": ["SELECT"],
        "app_worker": ["SELECT"],
        "app_rw": ["SELECT"],
        "app_ro": ["SELECT"],
        "app_dispatch_publisher": [],
        "app_celery_transport": [],
        "app_trust_issuer": ["INSERT", "SELECT"],
        "app_trust_signer": [],
        # B2.5-P14 Corrective V. Both consequence guards read the terminal row
        # to decide source binding and to derive the action authority, and a
        # trigger runs under the caller's own privileges. Reading durable
        # issuance history is not authority over it: neither principal can add
        # to it, which the sole-writer assertion above continues to decide.
        "app_b28_requester": ["SELECT"],
        "app_b28_solver": ["SELECT"],
    }

    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            observed = {
                relation: {
                    principal: sorted(ops)
                    for principal, ops in _effective_privileges(cursor, relation).items()
                }
                for relation in FENCED_RELATIONS
            }
    finally:
        conn.close()

    _record_evidence({"gate0_as_migrated_authority_matrix": observed})
    assert observed == expected, observed


def test_p14_gate0_no_runtime_principal_reaches_the_relation_owner() -> None:
    """H-XXI-D01's shape, re-asserted for the P14 relations.

    A guard with an owner branch is only a guard if no runtime login can reach
    the owner.
    """

    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT owner.rolname
                FROM pg_catalog.pg_class AS relation
                JOIN pg_catalog.pg_roles AS owner ON owner.oid = relation.relowner
                JOIN pg_catalog.pg_namespace AS ns ON ns.oid = relation.relnamespace
                WHERE ns.nspname = 'public'
                  AND relation.relname = ANY(%s)
                """,
                (list(FENCED_RELATIONS + P14_RELATIONS),),
            )
            owners = [row[0] for row in cursor.fetchall()]
            assert owners, "no owners resolved"
            reachable: list[str] = []
            for owner in owners:
                for principal in PRINCIPALS:
                    cursor.execute(
                        "SELECT pg_has_role(%s, %s, 'USAGE')", (principal, owner)
                    )
                    if cursor.fetchone()[0]:
                        reachable.append(f"{principal}->{owner}")
            cursor.execute(
                "SELECT rolname, rolsuper, rolbypassrls FROM pg_catalog.pg_roles"
                " WHERE rolname = ANY(%s)",
                (list(PRINCIPALS),),
            )
            elevated = [
                row[0] for row in cursor.fetchall() if row[1] or row[2]
            ]
    finally:
        conn.close()

    assert reachable == [], reachable
    assert elevated == [], elevated


# ---------------------------------------------------------------------------
# Gate 0 -- the audit's exact statement, refused for every unrelated principal.
# ---------------------------------------------------------------------------


def test_p14_gate0_issuance_history_is_not_fabricable_by_any_unrelated_principal() -> None:
    """Audit 67 plus Agent-2's paired-ledger counterexample, under real roles."""

    evidence: dict[str, Any] = {"gate": "P14-GATE0-FABRICATION"}
    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)

        attempts: dict[str, Any] = {}
        for principal in (
            "app_worker",
            "app_dispatch_publisher",
            "app_celery_transport",
            "app_trust_issuer",
            "app_trust_signer",
        ):
            material = _lawful_material()
            attempts[principal] = _as_principal(
                principal,
                tenant_id,
                _ISSUANCE_INSERT,
                _issuance_params(tenant_id, material),
                label="fabricate terminal success with no signing consequence",
            )
        # Agent-2's first-red: app_user may authorize a request in the ledger,
        # but no API credential may turn that request into terminal history
        # before a signer-confirmed attempt exists.
        paired_material = _lawful_material()
        attempts["app_user_authorized_ledger"] = _as_principal(
            "app_user",
            tenant_id,
            _LEDGER_INSERT,
            _ledger_params(tenant_id, paired_material),
            label="API records an authorized issuance request",
        )
        attempts["app_user_paired_authorized_projection"] = _as_principal(
            "app_user",
            tenant_id,
            _ISSUANCE_INSERT,
            _issuance_params(tenant_id, paired_material),
            label="API pairs an authorized ledger with terminal history",
        )
        issuer_material = _lawful_material()
        with conn.cursor() as cursor:
            _seed_ledger(cursor, tenant_id, issuer_material)
        attempts["issuer_with_authorized_ledger"] = _as_principal(
            "app_trust_issuer",
            tenant_id,
            _ISSUANCE_INSERT,
            _issuance_params(tenant_id, issuer_material),
            label="issuer projects before signing completion",
        )
        evidence["attempts"] = attempts

        with conn.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            cursor.execute(
                "SELECT count(*) FROM public.trust_envelope_issuance_log"
                " WHERE tenant_id = %s",
                (str(tenant_id),),
            )
            evidence["durable_rows_after_attacks"] = int(cursor.fetchone()[0])
            cursor.execute(
                "SELECT count(*) FROM public.trust_issuance_attempts "
                "WHERE tenant_id = %s",
                (str(tenant_id),),
            )
            evidence["signing_attempts_after_attacks"] = int(cursor.fetchone()[0])
    finally:
        conn.close()

    for principal, attempt in attempts.items():
        if principal == "app_user_authorized_ledger":
            continue
        assert attempt["result"] == "REFUSED", attempt
        assert attempt["sqlstate"] == "42501", attempt
    assert evidence["durable_rows_after_attacks"] == 0, evidence
    assert evidence["signing_attempts_after_attacks"] == 0, evidence
    assert attempts["app_user_authorized_ledger"]["result"] == "ALLOWED"
    assert "permission denied" in attempts["app_user_paired_authorized_projection"]["error"]
    assert "requires an issued ledger" in attempts["issuer_with_authorized_ledger"]["error"]
    _record_evidence({"gate0_fabrication_refusals": evidence})


def test_p14_gate0_a_row_disagreeing_with_its_ledger_record_is_refused() -> None:
    """Durable history projects the ledger; it does not assert beside it."""

    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
            material = _lawful_material()
            _seed_completed_lineage(cursor, tenant_id, material)

        disagreements = {}
        for field in (
            "idempotency_key_hash",
            "subject_ref_hash",
            "envelope_hash",
            "semantic_truth_hash",
            "audit_hash",
        ):
            mutated = dict(material)
            mutated[field] = _digest()
            disagreements[field] = _as_principal(
                "app_trust_issuer",
                tenant_id,
                _ISSUANCE_INSERT,
                _issuance_params(tenant_id, mutated),
                label=f"durable row disagreeing on {field}",
            )
        policy_mutation = dict(material)
        policy_mutation["policy_state"] = "simulation_only"
        disagreements["policy_state"] = _as_principal(
            "app_trust_issuer",
            tenant_id,
            _ISSUANCE_INSERT,
            _issuance_params(tenant_id, policy_mutation),
            label="durable row disagreeing on policy_state",
        )
    finally:
        conn.close()

    for field, outcome in disagreements.items():
        assert outcome["result"] == "REFUSED", (field, outcome)
        assert outcome["sqlstate"] == "42501", (field, outcome)
        assert "agree with the audit ledger" in outcome["error"], (field, outcome)
    _record_evidence({"gate0_ledger_disagreement_refusals": disagreements})


def test_p14_gate0_a_refusal_ledger_record_cannot_carry_a_success_projection() -> None:
    """Only a successful issuance ledger record may be projected as issuance."""

    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
            material = _lawful_material()
            _bind_tenant(cursor, tenant_id)
            cursor.execute(
                _LEDGER_INSERT,
                _ledger_params(
                    tenant_id, material, event_type="refusal", status="refused"
                ),
            )
        outcome = _as_principal(
            "app_trust_issuer",
            tenant_id,
            _ISSUANCE_INSERT,
            _issuance_params(tenant_id, material),
            label="project a refusal ledger record as durable issuance",
        )
    finally:
        conn.close()

    assert outcome["result"] == "REFUSED", outcome
    assert outcome["sqlstate"] == "42501", outcome
    assert "successful issuance ledger record" in outcome["error"], outcome


# ---------------------------------------------------------------------------
# Gate 0 -- the lawful path still conducts.
# ---------------------------------------------------------------------------


def test_p14_gate0_lawful_issuance_recording_still_succeeds() -> None:
    """A fence that also blocks the legitimate author is not a fix."""

    evidence: dict[str, Any] = {"gate": "P14-GATE0-LAWFUL"}
    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
            material = _lawful_material(subject_type="match_verdict")
            _seed_completed_lineage(cursor, tenant_id, material)

        recorded = _as_principal(
            "app_trust_issuer",
            tenant_id,
            _ISSUANCE_INSERT + " ON CONFLICT (tenant_id, idempotency_key_hash)"
            " DO NOTHING",
            _issuance_params(tenant_id, material),
            label="issuer projects signer-confirmed issuance",
        )
        evidence["issuance_recorded"] = recorded

        # The bounded retry path: an idempotent replay is still admitted and
        # does not attempt to restate the durable row.
        replayed = _as_principal(
            "app_trust_issuer",
            tenant_id,
            _ISSUANCE_INSERT + " ON CONFLICT (tenant_id, idempotency_key_hash)"
            " DO NOTHING",
            _issuance_params(tenant_id, material),
            label="issuer replays completed issuance projection",
        )
        evidence["issuance_replayed"] = replayed

        with conn.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            cursor.execute(
                "SELECT count(*) FROM public.trust_envelope_issuance_log"
                " WHERE tenant_id = %s AND idempotency_key_hash = %s",
                (str(tenant_id), material["idempotency_key_hash"]),
            )
            evidence["durable_rows"] = int(cursor.fetchone()[0])
    finally:
        conn.close()

    assert recorded["result"] == "ALLOWED", recorded
    assert recorded["rowcount"] == 1, recorded
    assert replayed["result"] == "ALLOWED", replayed
    assert replayed["rowcount"] == 0, replayed
    assert evidence["durable_rows"] == 1, evidence
    _record_evidence({"gate0_lawful_conduction": evidence})


# ---------------------------------------------------------------------------
# Gate 0 -- each remediation layer is independently load-bearing.
# ---------------------------------------------------------------------------


def test_p14_gate0_each_layer_is_independently_load_bearing() -> None:
    """Sever privilege, binding and guard independently, then all together.

    Only the fully severed state may reproduce audit 67's fabrication. Anything
    less and one of the three layers is carrying the property alone, which is
    what "two green layers" is supposed to rule out.
    """

    evidence: dict[str, Any] = {"gate": "P14-GATE0-SEVERANCE"}
    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
            cursor.execute(
                "SELECT pg_get_triggerdef(oid) FROM pg_catalog.pg_trigger"
                " WHERE tgname = 'trg_trust_issuance_consequence_authority'"
                " AND NOT tgisinternal"
            )
            pristine_triggerdef = cursor.fetchone()[0]
            cursor.execute(
                "SELECT pg_get_constraintdef(oid) FROM pg_catalog.pg_constraint"
                " WHERE conname = 'fk_trust_issuance_log_access_audit'"
            )
            pristine_constraintdef = cursor.fetchone()[0]
        evidence["pristine_triggerdef"] = pristine_triggerdef
        evidence["pristine_constraintdef"] = pristine_constraintdef

        def fabricate(label: str) -> dict[str, Any]:
            return _as_principal(
                "app_worker",
                tenant_id,
                _ISSUANCE_INSERT,
                _issuance_params(tenant_id, _lawful_material()),
                label=label,
            )

        # 0. Pristine.
        evidence["pristine"] = fabricate("pristine")

        # 1. Privilege restored; binding and guard intact.
        with conn.cursor() as cursor:
            cursor.execute(_HISTORICAL_RW_GRANT)
        evidence["privilege_only_severed"] = fabricate("historical grant restored")

        # 2. Privilege restored and the guard dropped; the FK alone remains.
        with conn.cursor() as cursor:
            cursor.execute(
                "DROP TRIGGER trg_trust_issuance_consequence_authority"
                " ON public.trust_envelope_issuance_log"
            )
        evidence["privilege_and_guard_severed"] = fabricate(
            "historical grant restored, consequence guard dropped"
        )

        # 3. All three severed -- the historical capability must reappear.
        with conn.cursor() as cursor:
            cursor.execute(
                "ALTER TABLE public.trust_envelope_issuance_log"
                " DROP CONSTRAINT fk_trust_issuance_log_access_audit"
            )
        evidence["fully_severed"] = fabricate("all three layers severed")

        # 4. Exact restoration.
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM public.trust_envelope_issuance_log WHERE tenant_id = %s",
                (str(tenant_id),),
            )
            cursor.execute(
                "ALTER TABLE public.trust_envelope_issuance_log"
                " ADD CONSTRAINT fk_trust_issuance_log_access_audit"
                " FOREIGN KEY (tenant_id, access_audit_ref)"
                " REFERENCES public.trust_access_log (tenant_id, audit_ref)"
                " ON DELETE CASCADE"
            )
            cursor.execute(pristine_triggerdef)
            cursor.execute(_FENCED_RW_GRANT)
        evidence["restored"] = fabricate("exact restoration")

        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT pg_get_triggerdef(oid) FROM pg_catalog.pg_trigger"
                " WHERE tgname = 'trg_trust_issuance_consequence_authority'"
                " AND NOT tgisinternal"
            )
            evidence["restored_triggerdef"] = cursor.fetchone()[0]
            cursor.execute(
                "SELECT pg_get_constraintdef(oid) FROM pg_catalog.pg_constraint"
                " WHERE conname = 'fk_trust_issuance_log_access_audit'"
            )
            evidence["restored_constraintdef"] = cursor.fetchone()[0]
            evidence["restored_matrix"] = {
                principal: sorted(ops)
                for principal, ops in _effective_privileges(
                    cursor, "trust_envelope_issuance_log"
                ).items()
            }
    finally:
        conn.close()

    _record_evidence({"gate0_layer_severance": evidence})

    assert evidence["pristine"]["result"] == "REFUSED", evidence["pristine"]
    assert "permission denied" in evidence["pristine"]["error"]

    assert evidence["privilege_only_severed"]["result"] == "REFUSED"
    assert (
        "dedicated issuer alone"
        in evidence["privilege_only_severed"]["error"]
    ), evidence["privilege_only_severed"]

    assert evidence["privilege_and_guard_severed"]["result"] == "REFUSED"
    assert (
        "foreign key" in evidence["privilege_and_guard_severed"]["error"].lower()
    ), evidence["privilege_and_guard_severed"]

    # The historical defect, physically reproduced.
    assert evidence["fully_severed"]["result"] == "ALLOWED", evidence["fully_severed"]
    assert evidence["fully_severed"]["rowcount"] == 1

    assert evidence["restored"]["result"] == "REFUSED", evidence["restored"]
    assert "permission denied" in evidence["restored"]["error"]
    assert evidence["restored_triggerdef"] == pristine_triggerdef
    assert evidence["restored_constraintdef"] == pristine_constraintdef
    assert evidence["restored_matrix"]["app_worker"] == ["SELECT"]
    assert evidence["restored_matrix"]["app_rw"] == ["SELECT"]


# ---------------------------------------------------------------------------
# Gate 10 -- new Trust supersedes dependent explanations.
# ---------------------------------------------------------------------------


def _seed_terminal_issuance(
    cursor,
    tenant_id,
    *,
    semantic_truth: str | None = None,
    subject_ref: str | None = None,
    policy_state: str = "read_only",
) -> dict[str, str]:
    """Create one durable terminal issuance row for a downstream artifact to bind.

    Corrective IV made a downstream artifact the *consequence* of a real issued
    TrustEnvelope rather than a row that cites one, so every B2.7/B2.8 fixture
    below starts from an issuance that physically exists. Written under the
    owning connection: the P14 Gate 0 consequence guard exempts the owner for
    the reason it states, and the lawful issuer path is proved separately by
    ``test_p14_gate0_the_lawful_issuer_path_still_conducts``.
    """

    material = _lawful_material()
    material["policy_state"] = policy_state
    if semantic_truth is not None:
        material["semantic_truth_hash"] = semantic_truth
    if subject_ref is not None:
        material["subject_ref_hash"] = subject_ref
    _seed_ledger(cursor, tenant_id, material)
    cursor.execute(_ISSUANCE_INSERT, _issuance_params(tenant_id, material))
    return material


def _insert_materialization(
    cursor, tenant_id, *, cache_identity: str, semantic_truth: str, subject_ref: str
) -> uuid.UUID:
    issuance = _seed_terminal_issuance(
        cursor, tenant_id, semantic_truth=semantic_truth, subject_ref=subject_ref
    )
    _bind_tenant(cursor, tenant_id)
    cursor.execute(
        "INSERT INTO public.b27_explanation_materializations (tenant_id,"
        " cache_identity_hash, source_envelope_id, source_semantic_truth_hash,"
        " source_issuance_envelope_hash, explanation_template_registry_hash,"
        " subject_type, subject_ref_hash, projection_profile_id,"
        " projection_profile_version, projection_profile_hash,"
        " explanation_contract_version, policy_state, confidence_status,"
        " causal_status, fallback_applied, claim_count, narrative, claims)"
        " VALUES (%s, %s, %s, %s, %s, %s, 'match_verdict', %s,"
        " 'llm_explanation_projection_safe', 'v1', %s, 'b25-p14-explanation-v1',"
        " %s, 'unavailable', NULL, false, 0, '', '[]'::jsonb)"
        " RETURNING id",
        (
            str(tenant_id),
            cache_identity,
            "env_" + uuid.uuid4().hex,
            semantic_truth,
            issuance["envelope_hash"],
            EXPLANATION_TEMPLATE_REGISTRY_HASH,
            subject_ref,
            _digest(),
            issuance["policy_state"],
        ),
    )
    return cursor.fetchone()[0]


def test_p14_gate10_new_trust_supersedes_dependent_explanations() -> None:
    """A lawful T1 -> T2 transition marks the T1 materialization stale."""

    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
            subject_ref = _digest()
            t1_truth = _digest()
            materialization_id = _insert_materialization(
                cursor,
                tenant_id,
                cache_identity=_digest(),
                semantic_truth=t1_truth,
                subject_ref=subject_ref,
            )

            # A lawful new issuance for the same subject, carrying T2.
            material = _lawful_material()
            material["subject_ref_hash"] = subject_ref
            _seed_ledger(cursor, tenant_id, material)
            cursor.execute(_ISSUANCE_INSERT, _issuance_params(tenant_id, material))

            cursor.execute(
                "SELECT stale, superseded_at IS NOT NULL"
                " FROM public.b27_explanation_materializations WHERE id = %s",
                (str(materialization_id),),
            )
            stale, has_timestamp = cursor.fetchone()

            # An issuance carrying the *same* semantic truth must not stale it.
            fresh_id = _insert_materialization(
                cursor,
                tenant_id,
                cache_identity=_digest(),
                semantic_truth=material["semantic_truth_hash"],
                subject_ref=subject_ref,
            )
            same_material = _lawful_material()
            same_material["subject_ref_hash"] = subject_ref
            same_material["semantic_truth_hash"] = material["semantic_truth_hash"]
            _seed_ledger(cursor, tenant_id, same_material)
            cursor.execute(_ISSUANCE_INSERT, _issuance_params(tenant_id, same_material))
            cursor.execute(
                "SELECT stale FROM public.b27_explanation_materializations WHERE id = %s",
                (str(fresh_id),),
            )
            unchanged_stale = cursor.fetchone()[0]
    finally:
        conn.close()

    assert stale is True
    assert has_timestamp is True
    assert unchanged_stale is False


def test_p14_gate10_explanation_cache_identity_is_tenant_scoped_at_the_database() -> None:
    """Two tenants may hold the same cache identity without colliding."""

    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            tenant_a = _seed_tenant(cursor)
            tenant_b = _seed_tenant(cursor)
            shared_identity = _digest()
            _insert_materialization(
                cursor,
                tenant_a,
                cache_identity=shared_identity,
                semantic_truth=_digest(),
                subject_ref=_digest(),
            )
            _insert_materialization(
                cursor,
                tenant_b,
                cache_identity=shared_identity,
                semantic_truth=_digest(),
                subject_ref=_digest(),
            )
            # And a duplicate within one tenant is refused.
            _bind_tenant(cursor, tenant_a)
            with pytest.raises(psycopg2.errors.UniqueViolation):
                _insert_materialization(
                    cursor,
                    tenant_a,
                    cache_identity=shared_identity,
                    semantic_truth=_digest(),
                    subject_ref=_digest(),
                )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Gate 6 / Gate 7 -- B2.8 structural physics at the database.
# ---------------------------------------------------------------------------


def _session_user(cursor) -> str:
    cursor.execute("SELECT session_user")
    return cursor.fetchone()[0]


def _seed_agent_credential(cursor, tenant_id) -> dict[str, str]:
    """One live machine principal, which Corrective V made a precondition of a
    representable request."""
    client_id = uuid.uuid4()
    credential_id = uuid.uuid4()
    # Corrective VI: a real CSPRNG token whose plaintext the caller keeps. The
    # entering fixture stored `sha256(random bytes)` with no known preimage,
    # which was sufficient while the database only checked the credential *row*
    # and is not sufficient now that it verifies possession of the secret.
    secret = generate_machine_token()
    cursor.execute(
        "INSERT INTO public.agent_clients (id, tenant_id, client_name,"
        " client_display_hash, audience, status)"
        " VALUES (%s,%s,%s,%s,'trust-api','active')",
        (str(client_id), str(tenant_id), f"p14g0-{client_id.hex[:8]}", _digest()),
    )
    cursor.execute(
        "INSERT INTO public.agent_service_credentials (id, tenant_id,"
        " agent_client_id, token_prefix, token_hash, status)"
        " VALUES (%s,%s,%s,%s,%s,'active')",
        (
            str(credential_id),
            str(tenant_id),
            str(client_id),
            secret.token_prefix,
            secret.token_hash,
        ),
    )
    return {
        # Corrective VI: the plaintext is what mints a possession witness, so a
        # seeder that discarded it could no longer produce a lawful request.
        "token": secret.plaintext,
        "agent_client_id": str(client_id),
        "credential_id": str(credential_id),
        "requested_by": f"agent_client:{client_id}",
    }


def _channel_evidence(channel_count: int) -> list[dict[str, Any]]:
    """Evidence that clears every governed sufficiency threshold."""
    return [
        {
            "channel_id": f"channel{index}",
            "verified_revenue_minor": 100_000 * (index + 1),
            "conversion_count": 5 * (index + 1),
        }
        for index in range(channel_count)
    ]


def _sufficiency(channels: list[dict[str, Any]]) -> dict[str, Any]:
    reasons: list[str] = []
    n_channels = len(channels)
    conversions = sum(c["conversion_count"] for c in channels)
    revenue = sum(c["verified_revenue_minor"] for c in channels)
    with_evidence = sum(
        1
        for c in channels
        if c["conversion_count"] > 0 and c["verified_revenue_minor"] > 0
    )
    if n_channels < 2:
        reasons.append(f"channels_below_minimum:{n_channels}<2")
    if with_evidence < 2:
        reasons.append(f"channels_with_evidence_below_minimum:{with_evidence}<2")
    if conversions < 5:
        reasons.append(f"conversions_below_minimum:{conversions}<5")
    if revenue < 1:
        reasons.append(f"revenue_below_minimum:{revenue}<1")
    return {
        "sufficient": not reasons,
        "reasons": reasons,
        "observed_channels": n_channels,
        "observed_conversions": conversions,
        "observed_revenue_minor": revenue,
    }


def _canonical_input_material(
    envelope_id: str,
    semantic_truth_hash: str,
    budget: int,
    currency: str,
    channels: list[dict[str, Any]],
) -> str:
    """The exact bytes both the application and the database hash."""
    ordered = sorted(channels, key=lambda c: c["channel_id"])
    return json.dumps(
        {
            "contract_version": "b25-p14-simulation-v1",
            "source_envelope_id": envelope_id,
            "source_semantic_truth_hash": semantic_truth_hash,
            "total_budget_minor": budget,
            "currency": currency,
            "sufficiency_policy_version": "b25-p14-sufficiency-v1",
            "solver_profile": "b25-p14-deterministic-largest-remainder-v1",
            "channels": ordered,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _solver_allocation(channels: list[dict[str, Any]], budget: int) -> list[dict]:
    """The governed largest-remainder allocation, the only one a result may
    carry after Corrective V."""
    ordered = sorted(channels, key=lambda c: c["channel_id"])
    total_revenue = sum(c["verified_revenue_minor"] for c in ordered)
    weights = [
        (c["verified_revenue_minor"] * 10_000) // total_revenue for c in ordered
    ]
    weight_rem = [
        ((c["verified_revenue_minor"] * 10_000) % total_revenue, c["channel_id"])
        for c in ordered
    ]
    for _, channel_id in sorted(weight_rem, key=lambda i: (-i[0], i[1]))[
        : max(10_000 - sum(weights), 0)
    ]:
        weights[next(i for i, c in enumerate(ordered) if c["channel_id"] == channel_id)] += 1
    allocations = [
        (c["verified_revenue_minor"] * budget) // total_revenue for c in ordered
    ]
    rem = [
        ((c["verified_revenue_minor"] * budget) % total_revenue, c["channel_id"])
        for c in ordered
    ]
    for _, channel_id in sorted(rem, key=lambda i: (-i[0], i[1]))[
        : budget - sum(allocations)
    ]:
        allocations[
            next(i for i, c in enumerate(ordered) if c["channel_id"] == channel_id)
        ] += 1
    return [
        {
            "channel_id": c["channel_id"],
            "allocation_minor": allocation,
            "weight_basis_points": weight,
        }
        for c, allocation, weight in zip(ordered, allocations, weights)
    ]


def _insert_request(
    cursor,
    tenant_id,
    *,
    budget: int = 1000,
    channel_count: int = 2,
    policy_state: str = "simulation_only",
) -> dict[str, Any]:
    """Seed a durable issuance and the explicit request that projects from it.

    Returns the request's governed fields, because a result must now agree with
    them field by field: Corrective IV replaced "a request row exists" with "the
    result is the consequence of *this* request over *that* Trust".
    """

    issuance = _seed_terminal_issuance(cursor, tenant_id, policy_state=policy_state)
    principal = _seed_agent_credential(cursor, tenant_id)
    channels = _channel_evidence(channel_count)
    envelope_id = "env_" + uuid.uuid4().hex
    # Corrective V: the snapshot hash is the hash of the retained evidence, and
    # the sufficiency verdict is the adjudicator's, so a fixture cannot choose
    # either. This helper computes both the way the request-entry boundary does.
    material = _canonical_input_material(
        envelope_id, issuance["semantic_truth_hash"], budget, "USD", channels
    )
    request = {
        "request_ref": "req_" + uuid.uuid4().hex,
        "source_envelope_id": envelope_id,
        "source_semantic_truth_hash": issuance["semantic_truth_hash"],
        "source_issuance_envelope_hash": issuance["envelope_hash"],
        "input_snapshot_hash": "sha256:"
        + hashlib.sha256(material.encode("utf-8")).hexdigest(),
        "total_budget_minor": budget,
        "currency": "USD",
        "channel_count": channel_count,
        "channels": channels,
        "policy_state": issuance["policy_state"],
    }
    _bind_tenant(cursor, tenant_id)
    verdict = _sufficiency(channels)
    # Corrective VI: a request names a durable possession witness, and the only
    # way to obtain one is to present the credential's plaintext secret. This
    # helper is seeding lawful state for probes about *other* conjuncts, so it
    # takes the lawful route.
    cursor.execute(
        "SELECT public.b28_authenticate_request_possession(%s::uuid,%s,%s,%s,%s)",
        (
            str(tenant_id),
            principal["token"],
            request["request_ref"],
            request["source_issuance_envelope_hash"],
            request["input_snapshot_hash"],
        ),
    )
    request["request_authentication_id"] = str(cursor.fetchone()[0])
    cursor.execute(
        "INSERT INTO public.b28_simulation_requests (tenant_id, request_ref,"
        " requested_by, requested_by_agent_client_id, requested_by_credential_id,"
        " request_authority_principal, request_authentication_id,"
        " source_envelope_id,"
        " source_semantic_truth_hash, source_issuance_envelope_hash,"
        " input_snapshot_hash, total_budget_minor, currency, channel_count,"
        " channel_evidence, solver_profile, sufficiency_policy_version,"
        " sufficiency_verdict, sufficiency_reasons, observed_channels,"
        " observed_conversions, observed_revenue_minor)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,"
        " 'b25-p14-deterministic-largest-remainder-v1',"
        " 'b25-p14-sufficiency-v1',%s,%s,%s,%s,%s) RETURNING id",
        (
            str(tenant_id),
            request["request_ref"],
            principal["requested_by"],
            principal["agent_client_id"],
            principal["credential_id"],
            _session_user(cursor),
            request["request_authentication_id"],
            request["source_envelope_id"],
            request["source_semantic_truth_hash"],
            request["source_issuance_envelope_hash"],
            request["input_snapshot_hash"],
            request["total_budget_minor"],
            request["currency"],
            request["channel_count"],
            json.dumps(channels),
            verdict["sufficient"],
            verdict["reasons"],
            verdict["observed_channels"],
            verdict["observed_conversions"],
            verdict["observed_revenue_minor"],
        ),
    )
    request["id"] = cursor.fetchone()[0]
    return request


def _result_params(
    tenant_id,
    request: dict[str, Any],
    allocations: list[dict[str, Any]],
    *,
    action_authority: str | None = None,
    allocated_total: int | None = None,
) -> tuple[Any, ...]:
    derived = action_authority
    if derived is None:
        derived = (
            request["policy_state"]
            if request["policy_state"]
            in ("blocked", "read_only", "simulation_only", "proposal_required")
            else "proposal_required"
        )
    return (
        str(tenant_id),
        str(request["id"]),
        request["source_envelope_id"],
        request["source_semantic_truth_hash"],
        _digest(),
        request["input_snapshot_hash"],
        request["total_budget_minor"],
        request["total_budget_minor"] if allocated_total is None else allocated_total,
        request["currency"],
        derived,
        json.dumps(allocations),
    )


_RESULT_INSERT = (
    "INSERT INTO public.b28_simulation_results (tenant_id, request_id,"
    " source_envelope_id, source_semantic_truth_hash, projection_profile_hash,"
    " input_snapshot_hash, solver_profile, solver_consequence_kind,"
    " total_budget_minor,"
    " allocated_total_minor, currency, action_authority, allocations)"
    " VALUES (%s, %s, %s, %s, %s, %s, 'b25-p14-deterministic-largest-remainder-v1',"
    " 'governed_deterministic_consequence', %s, %s, %s, %s, %s::jsonb)"
)


def test_p14_gate6_a_simulation_result_cannot_exist_without_a_request() -> None:
    """Gate 6, twice: the consequence guard and, alone, the NOT NULL FK.

    The guard fires first because BEFORE triggers precede constraint checks, so
    the structural half is severed to be measured. Both layers are individually
    load-bearing, which is what stops a later change from leaving only one.
    """

    unbound = [
        None,
        "env_" + uuid.uuid4().hex,
        _digest(),
        _digest(),
        _digest(),
        1000,
        1000,
        "USD",
        "simulation_only",
        json.dumps([{"channel_id": "a", "allocation_minor": 1000}]),
    ]
    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
            _bind_tenant(cursor, tenant_id)
            with pytest.raises(psycopg2.Error) as excinfo:
                cursor.execute(_RESULT_INSERT, tuple([str(tenant_id)] + unbound))
            assert "b28_result_requires_explicit_request" in str(excinfo.value)

        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT pg_get_triggerdef(oid) FROM pg_catalog.pg_trigger"
                " WHERE tgname = 'trg_b28_result_consequence' AND NOT tgisinternal"
            )
            triggerdef = cursor.fetchone()[0]
            assert triggerdef

        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DROP TRIGGER trg_b28_result_consequence"
                    " ON public.b28_simulation_results"
                )
            with conn.cursor() as cursor:
                tenant_id2 = _seed_tenant(cursor)
                _bind_tenant(cursor, tenant_id2)
                with pytest.raises(psycopg2.errors.NotNullViolation):
                    cursor.execute(_RESULT_INSERT, tuple([str(tenant_id2)] + unbound))
        finally:
            with conn.cursor() as cursor:
                cursor.execute(triggerdef)

        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT pg_get_triggerdef(oid) FROM pg_catalog.pg_trigger"
                " WHERE tgname = 'trg_b28_result_consequence' AND NOT tgisinternal"
            )
            assert cursor.fetchone()[0] == triggerdef
    finally:
        conn.close()


def test_p14_gate7_the_database_refuses_a_non_conserving_allocation() -> None:
    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
            request = _insert_request(cursor, tenant_id)

            # Lawful: the parts sum to the whole, and -- Corrective V -- they
            # are the parts the governed solver computes over the request's own
            # retained evidence. Any other conserving split is refused before
            # the conservation trigger is reached, so this is also the positive
            # control for the recomputation guard.
            lawful = _solver_allocation(
                request["channels"], request["total_budget_minor"]
            )
            cursor.execute(
                _RESULT_INSERT, _result_params(tenant_id, request, lawful)
            )

        with conn.cursor() as cursor:
            tenant_id2 = _seed_tenant(cursor)
            request2 = _insert_request(cursor, tenant_id2)
            # One minor unit short of the solver's own allocation. The
            # conservation trigger is the layer under test, so the guard above
            # it is severed for the measurement and restored immediately.
            short = _solver_allocation(
                request2["channels"], request2["total_budget_minor"]
            )
            short[0]["allocation_minor"] -= 1
            cursor.execute(
                "SELECT pg_get_triggerdef(oid) FROM pg_catalog.pg_trigger"
                " WHERE tgname = 'trg_b28_result_consequence' AND NOT tgisinternal"
            )
            consequence_trigger = cursor.fetchone()[0]
            cursor.execute(
                "DROP TRIGGER trg_b28_result_consequence"
                " ON public.b28_simulation_results"
            )
            try:
                with pytest.raises(psycopg2.Error) as excinfo:
                    cursor.execute(
                        _RESULT_INSERT,
                        _result_params(
                            tenant_id2,
                            request2,
                            short,
                            allocated_total=request2["total_budget_minor"],
                        ),
                    )
                assert "conserve the requested budget" in str(excinfo.value)
            finally:
                cursor.execute("ROLLBACK")
                cursor.execute(consequence_trigger)

        with conn.cursor() as cursor:
            tenant_id3 = _seed_tenant(cursor)
            request3 = _insert_request(cursor, tenant_id3)
            fractional = _solver_allocation(
                request3["channels"], request3["total_budget_minor"]
            )
            fractional[0]["allocation_minor"] = (
                fractional[0]["allocation_minor"] + 0.5
            )
            fractional[1]["allocation_minor"] = (
                fractional[1]["allocation_minor"] - 0.5
            )
            cursor.execute(
                "SELECT pg_get_triggerdef(oid) FROM pg_catalog.pg_trigger"
                " WHERE tgname = 'trg_b28_result_consequence' AND NOT tgisinternal"
            )
            consequence_trigger = cursor.fetchone()[0]
            cursor.execute(
                "DROP TRIGGER trg_b28_result_consequence"
                " ON public.b28_simulation_results"
            )
            try:
                with pytest.raises(psycopg2.Error) as excinfo:
                    cursor.execute(
                        _RESULT_INSERT,
                        _result_params(tenant_id3, request3, fractional),
                    )
                assert "fractional money" in str(excinfo.value)
            finally:
                cursor.execute("ROLLBACK")
                cursor.execute(consequence_trigger)
    finally:
        conn.close()


def test_p14_gate9_the_database_refuses_an_escalated_action_authority() -> None:
    """Two independent layers refuse an escalated authority, severed apart.

    The Corrective IV derivation guard computes the lawful authority from the
    source policy and refuses anything else; the pre-existing CHECK refuses
    ``approval_required`` outright. Proving both means severing the first, so a
    later change that quietly makes one of them the only fence is visible here.
    """

    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
            request = _insert_request(
                cursor, tenant_id, policy_state="approval_required"
            )
            # Layer 1: the derivation guard. An `approval_required` source
            # yields `proposal_required`, so the escalated value is refused for
            # not following from its source rather than for being on a list.
            with pytest.raises(psycopg2.Error) as excinfo:
                cursor.execute(
                    _RESULT_INSERT,
                    _result_params(
                        tenant_id,
                        request,
                        _solver_allocation(
                            request["channels"], request["total_budget_minor"]
                        ),
                        action_authority="approval_required",
                    ),
                )
            assert "b28_result_action_authority_not_derived" in str(excinfo.value)

        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT pg_get_triggerdef(oid) FROM pg_catalog.pg_trigger"
                " WHERE tgname = 'trg_b28_result_consequence' AND NOT tgisinternal"
            )
            triggerdef = cursor.fetchone()[0]
            assert triggerdef

        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DROP TRIGGER trg_b28_result_consequence"
                    " ON public.b28_simulation_results"
                )
            with conn.cursor() as cursor:
                tenant_id2 = _seed_tenant(cursor)
                request2 = _insert_request(
                    cursor,
                    tenant_id2,
                    policy_state="approval_required",
                )
                # Layer 2: the CHECK, alone.
                with pytest.raises(psycopg2.errors.CheckViolation):
                    cursor.execute(
                        _RESULT_INSERT,
                        _result_params(
                            tenant_id2,
                            request2,
                            _solver_allocation(
                                request2["channels"],
                                request2["total_budget_minor"],
                            ),
                            action_authority="approval_required",
                        ),
                    )
        finally:
            with conn.cursor() as cursor:
                cursor.execute(triggerdef)

        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT pg_get_triggerdef(oid) FROM pg_catalog.pg_trigger"
                " WHERE tgname = 'trg_b28_result_consequence' AND NOT tgisinternal"
            )
            assert cursor.fetchone()[0] == triggerdef
    finally:
        conn.close()


def test_p14_new_relations_force_row_level_security() -> None:
    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT relname, relrowsecurity, relforcerowsecurity"
                " FROM pg_catalog.pg_class AS c"
                " JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace"
                " WHERE n.nspname = 'public' AND c.relname = ANY(%s)",
                (list(P14_RELATIONS),),
            )
            rows = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
    finally:
        conn.close()

    assert set(rows) == set(P14_RELATIONS), rows
    for relation, (enabled, forced) in rows.items():
        assert enabled and forced, (relation, enabled, forced)


def test_p14_new_relations_are_least_privilege() -> None:
    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            observed = {
                relation: {
                    principal: sorted(ops)
                    for principal, ops in _effective_privileges(cursor, relation).items()
                }
                for relation in P14_RELATIONS
            }
    finally:
        conn.close()

    # B2.5-P14 Corrective V. Exactly one principal writes each relation, and
    # which one is a statement about causal responsibility rather than about
    # convenience: the API principal composed the B2.7 explanation, so it
    # appends that; the request-entry authority is the only thing that can
    # establish a caller, so it appends requests; the solver consequence
    # authority is the only thing that runs the solver, so it appends results
    # and the proposals derived from them. Before 202609061200 `app_user` wrote
    # all four, which is why one credential could author a cause and its own
    # consequence.
    expected_writer = {
        "b27_explanation_materializations": "app_user",
        "b28_simulation_requests": "app_b28_requester",
        "b28_simulation_results": "app_b28_solver",
        "b28_proposals": "app_b28_solver",
    }
    for relation, matrix in observed.items():
        writer = expected_writer[relation]
        assert matrix[writer] == ["INSERT", "SELECT"], (relation, matrix)
        assert matrix["app_ro"] == ["SELECT"], (relation, matrix)
        # app_worker is a member of app_ro, so it reads what the read-only role
        # reads. Reading a non-authoritative downstream materialization is not
        # authority over it; writing would be, and it holds no write anywhere.
        assert matrix["app_worker"] == ["SELECT"], (relation, matrix)
        assert matrix["app_rw"] == [], (relation, matrix)
        if writer != "app_user":
            assert matrix["app_user"] == ["SELECT"], (relation, matrix)
        for principal in (
            "app_dispatch_publisher",
            "app_celery_transport",
            "app_trust_issuer",
            "app_trust_signer",
        ):
            assert matrix[principal] == [], (relation, principal, matrix)
        # Exactly one principal may write, and nothing may mutate or remove.
        writers = [
            principal
            for principal, ops in matrix.items()
            if {"INSERT", "UPDATE", "DELETE"} & set(ops)
        ]
        assert writers == [writer], (relation, writers)
        for principal, ops in matrix.items():
            assert "UPDATE" not in ops, (relation, principal, ops)
            assert "DELETE" not in ops, (relation, principal, ops)
    _record_evidence({"p14_relation_authority_matrix": observed})
