"""B2.5-P13 C20 — verdict-authority conservation, proved against a real role graph.

Corrective XX, Exit Gates XX2-A (verdict authority conservation), XX2-B (lawful
deterministic conduction preservation) and XX2-C (sibling role closure).

Two independent audits of protected main `87836b60` physically executed

    app_user: matched_provisional -> matched_confirmed   =>  UPDATE 1

and watched the C19 projection trigger propagate ``verified = true`` onto the
allocation. The database derived verification from a verdict correctly; nothing
fenced *who may assert the verdict*.

This proof is deliberately not a privilege-catalogue reading. It connects as the
real PostgreSQL login each production process uses, attempts the real historical
transition, and requires the database itself to refuse. It then performs the
lawful worker-owned transition and requires verification to appear, because a
fence that also blocks the legitimate author is not a fix.

The remediation expresses authority twice — a privilege layer and a trigger
layer — so the negative control severs each independently and then both
together. Only the both-severed case may reproduce the historical RED; that is
what makes the two green layers non-vacuous rather than merely co-present.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import psycopg2
import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_C20_RUNTIME_AUTHORITY_PROOF") != "1",
    reason="C20 runtime authority proof requires a provisioned production role graph",
)


# The processes whose premises must stay their own. Each entry is
# relation -> {principal: allowed operations}. A principal absent from a
# relation's map must hold no privilege on it at all.
#
# This is the machine-readable form of "who is allowed to assert this fact?".
# It is asserted as an equality, not a subset: a future migration that widens
# any of these fails here rather than in an audit.
AUTHORITY_CONTRACT: dict[str, dict[str, set[str]]] = {
    # B2.3 deterministic verdict truth: authored by the B2.3 worker alone.
    "b23_match_verdicts": {
        "app_user": {"SELECT"},
        "app_ro": {"SELECT"},
        "app_rw": set(),
        "app_worker": {"SELECT", "INSERT", "UPDATE"},
    },
    # B2.4 fit truth: authored by the Bayesian worker alone; the API reads it.
    "bayesian_model_fits": {
        "app_user": {"SELECT"},
        "app_ro": {"SELECT"},
        "app_rw": {"SELECT"},
        "app_worker": {"SELECT", "INSERT", "UPDATE"},
    },
    "bayesian_artifacts": {
        "app_user": {"SELECT"},
        "app_ro": {"SELECT"},
        "app_rw": {"SELECT"},
        "app_worker": {"SELECT", "INSERT", "UPDATE"},
    },
    # Fit dispatch: planned by the worker, published by the dispatch publisher.
    "b24_fit_dispatch_outbox": {
        "app_user": {"SELECT"},
        "app_worker": {"SELECT", "INSERT", "UPDATE"},
        "app_dispatch_publisher": {"SELECT"},
    },
    # Planner wakeups are worker-owned; the API principal may not schedule fits.
    "b24_fit_planner_wakeups": {
        "app_worker": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    },
    # Execution leases are the worker's own concurrency authority.
    "b24_active_execution_leases": {
        "app_user": {"SELECT"},
        "app_worker": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    },
}

# Principals enumerated for every relation in the contract. A principal that
# appears here but not in a relation's map must hold nothing on that relation.
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

OPERATIONS = ("SELECT", "INSERT", "UPDATE", "DELETE")

_OCCURRED_AT = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)

_HISTORICAL_GRANT = (
    "GRANT SELECT, INSERT, UPDATE ON TABLE public.b23_match_verdicts TO app_user"
)
_FENCED_GRANT = (
    "REVOKE ALL ON TABLE public.b23_match_verdicts FROM app_user; "
    "GRANT SELECT ON TABLE public.b23_match_verdicts TO app_user"
)


def _admin_dsn() -> str:
    for name in (
        "C20_ADMIN_DATABASE_URL",
        "C19_ADMIN_DATABASE_URL",
        "MIGRATION_DATABASE_URL",
    ):
        value = os.getenv(name, "").strip()
        if value:
            return value
    raise RuntimeError(
        "C20 authority proof needs an owner/superuser DSN: set C20_ADMIN_DATABASE_URL"
    )


def _admin_connection():
    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    return conn


def _role_connection(role: str):
    """Connect as one production login against the same database."""

    parts = urlsplit(_admin_dsn().replace("postgresql+psycopg2://", "postgresql://"))
    return psycopg2.connect(
        dbname=parts.path.lstrip("/"),
        host=parts.hostname,
        port=parts.port or 5432,
        user=role,
        password=os.getenv(f"C20_{role.upper()}_PASSWORD", role),
    )


def _bind_tenant(cursor, tenant_id: uuid.UUID | str) -> None:
    cursor.execute(
        "SELECT set_config('app.current_tenant_id', %s, false)", (str(tenant_id),)
    )


# ---------------------------------------------------------------------------
# One legitimate settlement, seeded the way the C19 journey persists one.
# ---------------------------------------------------------------------------


def _seed_settlement(cursor) -> dict[str, Any]:
    tenant_id = uuid.uuid4()
    event_id = uuid.uuid4()
    verdict_id = uuid.uuid4()
    allocation_id = uuid.uuid4()
    amount = 31_337
    label = tenant_id.hex[:8]

    cursor.execute(
        "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
        " VALUES (%s, %s, %s, %s)",
        (str(tenant_id), f"c20-{label}", uuid.uuid4().hex, f"c20-{label}@example.invalid"),
    )
    _bind_tenant(cursor, tenant_id)
    cursor.execute(
        "INSERT INTO public.channel_taxonomy (code, family, is_paid, display_name, state)"
        " VALUES ('c20_channel', 'b25_p13_c20', true, 'C20', 'active')"
        " ON CONFLICT (code) DO NOTHING"
    )
    cursor.execute(
        "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
        " correlation_id, session_id, revenue_cents, raw_payload, idempotency_key,"
        " event_type, channel, campaign_id, conversion_value_cents, currency,"
        " event_timestamp, processed_at, processing_status)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, 'conversion', 'c20_channel',"
        " 'c20-campaign', %s, 'USD', %s, %s, 'processed')",
        (
            str(event_id),
            str(tenant_id),
            _OCCURRED_AT,
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            amount,
            json.dumps({"source": "b25_p13_c20"}),
            f"c20:{label}",
            amount,
            _OCCURRED_AT,
            _OCCURRED_AT,
        ),
    )
    cursor.execute(
        "INSERT INTO public.attribution_allocations (id, tenant_id, event_id,"
        " channel_code, allocated_revenue_cents, allocation_ratio, model_version,"
        " model_type, confidence_score, verified)"
        " VALUES (%s, %s, %s, 'c20_channel', %s, 1.0, 'b25-p13-c20-v1',"
        " 'last_touch', 1.0, false)",
        (str(allocation_id), str(tenant_id), str(event_id), amount),
    )
    cursor.execute(
        "INSERT INTO public.b23_match_verdicts (id, tenant_id, attribution_event_id,"
        " provider, canonical_commerce_reference, provider_native_event_reference,"
        " provider_native_commerce_reference, status, match_quality,"
        " attributed_amount_minor, verified_amount_minor, currency_code,"
        " last_transition_at, canonical_expected_gross_amount_minor,"
        " canonical_captured_gross_amount_minor, canonical_net_verified_amount_minor,"
        " discrepancy_amount_minor, discrepancy_ratio_bps, discrepancy_band)"
        " VALUES (%s, %s, %s, 'stripe', %s, %s, %s, 'matched_provisional', 'high',"
        " %s, %s, 'USD', %s, %s, %s, %s, 0, 0, 'exact')",
        (
            str(verdict_id),
            str(tenant_id),
            str(event_id),
            f"c20-order-{label}",
            f"c20-event-{label}",
            f"c20-order-{label}",
            amount,
            amount,
            _OCCURRED_AT,
            amount,
            amount,
            amount,
        ),
    )
    return {
        "tenant_id": tenant_id,
        "event_id": event_id,
        "verdict_id": verdict_id,
        "allocation_id": allocation_id,
        "amount": amount,
    }


def _allocation_state(cursor, allocation_id) -> tuple[bool, str | None]:
    cursor.execute(
        "SELECT verified, verification_source FROM public.attribution_allocations"
        " WHERE id = %s",
        (str(allocation_id),),
    )
    return tuple(cursor.fetchone())


def _verdict_status(cursor, verdict_id) -> str:
    cursor.execute(
        "SELECT status FROM public.b23_match_verdicts WHERE id = %s", (str(verdict_id),)
    )
    return cursor.fetchone()[0]


def _attempt_transition(role: str, settlement: dict[str, Any]) -> dict[str, Any]:
    """Run the historical provisional -> confirmed transition as one principal."""

    outcome: dict[str, Any] = {"principal": role}
    conn = _role_connection(role)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT session_user, current_user")
            outcome["session_user"], outcome["current_user"] = cursor.fetchone()
            _bind_tenant(cursor, settlement["tenant_id"])
            cursor.execute(
                "UPDATE public.b23_match_verdicts"
                " SET status = 'matched_confirmed', confirmed_at = now(),"
                "     last_transition_at = now()"
                " WHERE id = %s",
                (str(settlement["verdict_id"]),),
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


def _reset_settlement(cursor, settlement: dict[str, Any]) -> None:
    """Return the settlement to its provisional, unverified starting state."""

    cursor.execute(
        "UPDATE public.b23_match_verdicts"
        " SET status = 'matched_provisional', confirmed_at = NULL,"
        "     last_transition_at = %s"
        " WHERE id = %s",
        (_OCCURRED_AT, str(settlement["verdict_id"])),
    )
    cursor.execute(
        "UPDATE public.attribution_allocations"
        " SET verified = false, verification_source = NULL"
        " WHERE id = %s",
        (str(settlement["allocation_id"]),),
    )


def _effective_privileges(cursor, relation: str) -> dict[str, set[str]]:
    observed: dict[str, set[str]] = {}
    for principal in PRINCIPALS:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (principal,))
        if cursor.fetchone() is None:
            continue
        held = set()
        for operation in OPERATIONS:
            cursor.execute(
                "SELECT has_table_privilege(%s, %s, %s)",
                (principal, f"public.{relation}", operation),
            )
            if cursor.fetchone()[0]:
                held.add(operation)
        observed[principal] = held
    return observed


def _contract_violations(cursor) -> list[str]:
    violations: list[str] = []
    for relation, expected in AUTHORITY_CONTRACT.items():
        observed = _effective_privileges(cursor, relation)
        for principal, held in observed.items():
            allowed = expected.get(principal, set())
            excess = held - allowed
            if excess:
                violations.append(
                    f"{principal} holds {sorted(excess)} on {relation}"
                    f" (contract allows {sorted(allowed)})"
                )
            missing = allowed - held
            if missing:
                violations.append(
                    f"{principal} is missing {sorted(missing)} on {relation}"
                )
    return violations


def _record_evidence(payload: dict[str, Any]) -> None:
    target = os.getenv("C20_EVIDENCE_PATH", "").strip()
    if not target:
        evidence = os.getenv("C19_EVIDENCE_PATH", "").strip()
        if not evidence:
            return
        target = str(
            Path(evidence).with_name("b25_p13_c20_runtime_authority_evidence.json")
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
# XX2-A / XX2-B: the fence refuses the API principal and admits the worker.
# ---------------------------------------------------------------------------


def test_c20_verdict_authority_is_conserved_in_both_directions() -> None:
    evidence: dict[str, Any] = {"gate": "XX2-A/XX2-B"}
    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            settlement = _seed_settlement(cursor)
            evidence["tenant_id"] = str(settlement["tenant_id"])
            evidence["verdict_id"] = str(settlement["verdict_id"])
            assert _allocation_state(cursor, settlement["allocation_id"]) == (
                False,
                None,
            )

        # --- Forbidden direction: the API principal cannot author verdict truth.
        forbidden = _attempt_transition("app_user", settlement)
        evidence["app_user_transition"] = forbidden
        assert forbidden["result"] == "REFUSED", forbidden
        assert forbidden["session_user"] == "app_user"

        with conn.cursor() as cursor:
            assert _verdict_status(cursor, settlement["verdict_id"]) == (
                "matched_provisional"
            )
            # No downstream consequence may have occurred.
            assert _allocation_state(cursor, settlement["allocation_id"]) == (
                False,
                None,
            )

        # The API principal must not be able to manufacture a verdict either.
        insert_refused = _attempt_forbidden_insert(settlement)
        evidence["app_user_insert"] = insert_refused
        assert insert_refused["result"] == "REFUSED", insert_refused

        # Tenant-GUC substitution buys nothing: the write authority is gone
        # regardless of which tenant the caller claims.
        cross_tenant = _attempt_cross_tenant_transition(settlement)
        evidence["app_user_cross_tenant"] = cross_tenant
        assert cross_tenant["result"] == "REFUSED", cross_tenant

        # --- Lawful direction: the B2.3 worker still confirms, and the
        # database still projects verified allocation truth from that verdict.
        lawful = _attempt_transition("app_worker", settlement)
        evidence["app_worker_transition"] = lawful
        assert lawful["result"] == "ALLOWED", lawful
        assert lawful["rowcount"] == 1, lawful

        with conn.cursor() as cursor:
            assert _verdict_status(cursor, settlement["verdict_id"]) == (
                "matched_confirmed"
            )
            projected = _allocation_state(cursor, settlement["allocation_id"])
            evidence["allocation_after_lawful_transition"] = list(projected)
            assert projected == (True, "b23_match_verdict"), projected
    finally:
        conn.close()

    _record_evidence({"c20_authority_conservation": evidence})


def _attempt_forbidden_insert(settlement: dict[str, Any]) -> dict[str, Any]:
    outcome: dict[str, Any] = {"principal": "app_user", "op": "INSERT"}
    conn = _role_connection("app_user")
    try:
        with conn.cursor() as cursor:
            _bind_tenant(cursor, settlement["tenant_id"])
            marker = uuid.uuid4().hex[:8]
            cursor.execute(
                "INSERT INTO public.b23_match_verdicts (tenant_id, provider,"
                " canonical_commerce_reference, provider_native_event_reference,"
                " provider_native_commerce_reference, status, match_quality,"
                " attributed_amount_minor, verified_amount_minor, currency_code,"
                " canonical_expected_gross_amount_minor,"
                " canonical_captured_gross_amount_minor,"
                " canonical_net_verified_amount_minor, discrepancy_amount_minor,"
                " discrepancy_ratio_bps, discrepancy_band)"
                " VALUES (%s, 'stripe', %s, %s, %s, 'unmatched', 'high', 1, 1,"
                " 'USD', 1, 1, 1, 0, 0, 'exact')",
                (
                    str(settlement["tenant_id"]),
                    f"c20-forged-{marker}",
                    f"c20-forged-{marker}",
                    f"c20-forged-{marker}",
                ),
            )
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


def _attempt_cross_tenant_transition(settlement: dict[str, Any]) -> dict[str, Any]:
    """Claim a different tenant, then attempt the same worker-owned transition."""

    outcome: dict[str, Any] = {"principal": "app_user", "op": "CROSS_TENANT_UPDATE"}
    conn = _role_connection("app_user")
    try:
        with conn.cursor() as cursor:
            _bind_tenant(cursor, uuid.uuid4())
            cursor.execute(
                "UPDATE public.b23_match_verdicts SET status = 'matched_confirmed'"
                " WHERE id = %s",
                (str(settlement["verdict_id"]),),
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
# XX2-A active falsifier: each layer, severed on its own and then together.
# ---------------------------------------------------------------------------


def _triggerdefs(cursor) -> dict[str, str]:
    cursor.execute(
        "SELECT tgname, pg_get_triggerdef(oid) FROM pg_trigger"
        " WHERE tgrelid = 'public.b23_match_verdicts'::regclass"
        "   AND tgname LIKE 'trg_b23_verdict_authorship%'"
    )
    return {name: definition for name, definition in cursor.fetchall()}


def test_c20_each_authority_layer_is_independently_load_bearing() -> None:
    evidence: dict[str, Any] = {"gate": "XX2-A active falsifier"}
    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            settlement = _seed_settlement(cursor)
            saved_triggers = _triggerdefs(cursor)
            assert len(saved_triggers) == 2, saved_triggers
            evidence["guard_triggers"] = sorted(saved_triggers)

        # (1) Restore the historical grant. The trigger must still refuse.
        with conn.cursor() as cursor:
            cursor.execute(_HISTORICAL_GRANT)
        grant_only = _attempt_transition("app_user", settlement)
        evidence["historical_grant_restored"] = grant_only
        assert grant_only["result"] == "REFUSED", grant_only
        assert grant_only.get("sqlstate") == "42501", grant_only
        with conn.cursor() as cursor:
            cursor.execute(_FENCED_GRANT)
            assert _verdict_status(cursor, settlement["verdict_id"]) == (
                "matched_provisional"
            )

        # (2) Sever the trigger layer. The privilege layer must still refuse.
        with conn.cursor() as cursor:
            for name in saved_triggers:
                cursor.execute(f"DROP TRIGGER {name} ON public.b23_match_verdicts")
        trigger_severed = _attempt_transition("app_user", settlement)
        evidence["guard_trigger_severed"] = trigger_severed
        assert trigger_severed["result"] == "REFUSED", trigger_severed

        # (3) Sever both. The historical defect must reappear exactly — this is
        # what proves the two green layers above are not vacuously green.
        with conn.cursor() as cursor:
            cursor.execute(_HISTORICAL_GRANT)
        historical = _attempt_transition("app_user", settlement)
        evidence["both_layers_severed"] = historical
        assert historical["result"] == "ALLOWED", historical
        assert historical["rowcount"] == 1, historical
        with conn.cursor() as cursor:
            assert _verdict_status(cursor, settlement["verdict_id"]) == (
                "matched_confirmed"
            )
            reproduced = _allocation_state(cursor, settlement["allocation_id"])
            evidence["historical_downstream_consequence"] = list(reproduced)
            assert reproduced == (True, "b23_match_verdict"), reproduced

        # (4) Exact restoration of both layers, then the same attempt again.
        with conn.cursor() as cursor:
            cursor.execute(_FENCED_GRANT)
            for definition in saved_triggers.values():
                cursor.execute(definition)
            restored_triggers = _triggerdefs(cursor)
            assert restored_triggers == saved_triggers, restored_triggers
            _reset_settlement(cursor, settlement)
        restored = _attempt_transition("app_user", settlement)
        evidence["after_exact_restoration"] = restored
        assert restored["result"] == "REFUSED", restored
        with conn.cursor() as cursor:
            assert _allocation_state(cursor, settlement["allocation_id"]) == (
                False,
                None,
            )
    finally:
        conn.close()

    _record_evidence({"c20_layer_falsifier": evidence})


# ---------------------------------------------------------------------------
# XX2-C: no production principal may manufacture another process's premise.
# ---------------------------------------------------------------------------


def test_c20_process_role_authority_contract_holds() -> None:
    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            violations = _contract_violations(cursor)
            observed = {
                relation: {
                    principal: sorted(ops)
                    for principal, ops in _effective_privileges(cursor, relation).items()
                }
                for relation in AUTHORITY_CONTRACT
            }
    finally:
        conn.close()
    _record_evidence({"c20_authority_matrix": observed, "violations": violations})
    assert violations == [], violations


def test_c20_no_runtime_principal_inherits_the_relation_owner() -> None:
    """Ownership is the trigger layer's one remaining escape hatch.

    ``b23_enforce_verdict_authorship`` admits the relation's owner, because the
    owner can drop the trigger outright and every environment migrates as it.
    That is only sound while no runtime login can reach the owner's role: an
    ownership transfer to a runtime principal, or a membership grant into the
    migration role, would open the trigger layer silently and leave only the
    privilege layer standing. Nothing else in the repository asserts this, so it
    is asserted here, beside the fence that depends on it.
    """

    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT owner.rolname FROM pg_class AS relation"
                " JOIN pg_roles AS owner ON owner.oid = relation.relowner"
                " WHERE relation.oid = 'public.b23_match_verdicts'::regclass"
            )
            owner = cursor.fetchone()[0]
            reachable = []
            for principal in PRINCIPALS:
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (principal,))
                if cursor.fetchone() is None:
                    continue
                cursor.execute(
                    "SELECT pg_has_role(%s, %s, 'USAGE')", (principal, owner)
                )
                if cursor.fetchone()[0]:
                    reachable.append(principal)
    finally:
        conn.close()
    assert reachable == [], (
        f"{reachable} can act as {owner!r}, the owner of b23_match_verdicts, so"
        " the verdict guard trigger would admit them"
    )


def test_c20_sibling_overgrant_is_detected() -> None:
    """The contract assertion must actually fire when authority widens."""

    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            baseline = _contract_violations(cursor)
            assert baseline == [], baseline

            cursor.execute(
                "GRANT INSERT ON TABLE public.bayesian_model_fits TO app_user"
            )
            try:
                widened = _contract_violations(cursor)
            finally:
                cursor.execute(
                    "REVOKE INSERT ON TABLE public.bayesian_model_fits FROM app_user"
                )
            assert any(
                "app_user holds ['INSERT'] on bayesian_model_fits" in item
                for item in widened
            ), widened

            assert _contract_violations(cursor) == []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# The fence must not break the governed referential consequence of deletion.
# ---------------------------------------------------------------------------


def test_c20_referential_nullification_still_succeeds() -> None:
    """Deleting a referenced ingress identity nulls the verdict FK, lawfully.

    ``webhook_ingress_identities`` references this table ``ON DELETE SET NULL``.
    That write is a consequence of a governed deletion, not an assertion of
    verdict truth, so the guard is scoped to the authority-bearing columns
    rather than to every write. Retention would otherwise deadlock against its
    own fence.
    """

    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            settlement = _seed_settlement(cursor)
            identity_id = uuid.uuid4()
            label = settlement["tenant_id"].hex[:8]
            cursor.execute(
                "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
                " event_id, provider, provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_kind,"
                " normalized_commerce_reference_value, verified_amount_minor,"
                " verified_amount_currency, event_timestamp, idempotency_key,"
                " verified_commerce_ingress_state)"
                " VALUES (%s, %s, %s, 'stripe', %s, %s, 'order_reference', %s,"
                " %s, 'USD', %s, %s, 'authenticity_verified')",
                (
                    str(identity_id),
                    str(settlement["tenant_id"]),
                    str(settlement["event_id"]),
                    f"c20-ingress-{label}",
                    f"c20-order-{label}",
                    f"c20-order-{label}",
                    settlement["amount"],
                    _OCCURRED_AT,
                    f"c20-ingress:{label}",
                ),
            )
            cursor.execute(
                "UPDATE public.b23_match_verdicts"
                " SET webhook_ingress_identity_id = %s WHERE id = %s",
                (str(identity_id), str(settlement["verdict_id"])),
            )
            cursor.execute(
                "DELETE FROM public.webhook_ingress_identities WHERE id = %s",
                (str(identity_id),),
            )
            cursor.execute(
                "SELECT webhook_ingress_identity_id, status"
                " FROM public.b23_match_verdicts WHERE id = %s",
                (str(settlement["verdict_id"]),),
            )
            nulled, status = cursor.fetchone()
            assert nulled is None
            assert status == "matched_provisional"
    finally:
        conn.close()
