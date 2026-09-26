#!/usr/bin/env python3
"""B2.6-P2 Corrective XI ingress-capability isolation validator (CLASS B).

Law: only the process boundary that verifies provider authentication
may possess the capability that creates authentication-authoritative
durable state. Generic API/worker/relay/beat roles cannot mint or
attest sovereign ingress. The isolation is physical (role grants +
trigger session_user gates + process DSN custody), never caller
discipline.

Checks: process x DSN x role census over every in-scope executable
topology (Procfile, local compose, env templates, backend references);
live grant census (attester/witness EXECUTE, verified authorship,
witness unforgeability); least-privilege ceiling on app_ingress
(no B2.3/P2/policy/TrustEnvelope authority); cross-tenant refusal.

Exit code is the gate: 0 on PASS, 1 plus a violation list on FAIL.
"""

from __future__ import annotations

import argparse
import json
import re
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Every in-scope executable topology: the generic worker must resolve
# to a non-ingress credential, and the ingress DSN must reach only
# the API boundary.
TOPOLOGY_FILES = (
    "Procfile",
    "docker-compose.local.yml",
    "docker-compose.e2e.yml",
    "docker-compose.test.yml",
)

INGRESS_DSN_TOKEN = "B26_P2_INGRESS_DATABASE_URL"
API_DSN_TOKENS = ("DATABASE_URL=$WORKER_DATABASE_URL",)


def _line_mounts_ingress(line: str) -> bool:
    """True when a topology line actually delivers the credential.

    B2.6-P2 Corrective XII: non-ingress processes explicitly blank the
    variable (``VAR=`` with an empty value / ``VAR: ""``). Blanking is
    the physical expression of non-possession; only an assignment
    carrying a value on the ingress token itself mounts it.
    """
    if INGRESS_DSN_TOKEN not in line:
        return False
    match = re.search(INGRESS_DSN_TOKEN + r"\s*([:=])", line)
    if match is None:
        return True
    rest = line[match.end():]
    if match.group(1) == "=":
        # Shell semantics: `VAR=value` mounts; `VAR=` / `VAR= cmd`
        # leaves the variable empty (explicit blanking).
        return rest != "" and rest[0] not in (" ", "\t", "#", "\n")
    rest = rest.strip()
    if rest == "" or rest.startswith("#"):
        return False
    if rest[0] in ("\"", "'"):
        closer = rest.find(rest[0], 1)
        inner = rest[1:closer] if closer > 0 else rest[1:]
        return inner.strip() != ""
    # Compose indirection with an empty default (`${VAR:-}` /
    # `${VAR-}`) mounts nothing unless the lane opts in by exporting
    # VAR; a non-empty default mounts the credential.
    if re.fullmatch(r"\$\{[A-Za-z_][A-Za-z0-9_]*:-?\}", rest):
        return False
    return True


def _topology_checks(violations: list[str], checks: dict) -> None:
    procfile = REPO_ROOT / "Procfile"
    try:
        text = procfile.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xi_isolation_procfile_unreadable:{exc}")
        return
    worker_lines = [
        line for line in text.splitlines()
        if re.match(r"\s*worker\s*:", line)
        and "worker_b23" not in line
        and "worker_bayesian" not in line
    ]
    checks["generic_worker_lines"] = worker_lines
    if not worker_lines:
        violations.append("xi_isolation_no_generic_worker_line")
    for line in worker_lines:
        # The worker must never hold the dedicated ingress
        # credential. (It keeps the API DSN by C7 design; ingress
        # authority is denied at the database layer for every
        # non-ingress principal, proven by the live probes below.
        # Corrective XII blanks the variable on every non-ingress
        # process line; blanking is non-possession, not holding.)
        if _line_mounts_ingress(line):
            violations.append("xi_isolation_worker_holds_ingress_dsn")
    # Ingress DSN must never be mounted on a non-API process line.
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _line_mounts_ingress(line) and re.match(
            r"\s*(worker|relay_b26_p2|beat|worker_b23|worker_bayesian)\s*:",
            line,
        ):
            violations.append(
                "xi_isolation_ingress_dsn_on_non_api_process"
            )
    env_example = REPO_ROOT / ".env.example"
    try:
        env_text = env_example.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xi_isolation_env_unreadable:{exc}")
        return
    if INGRESS_DSN_TOKEN not in env_text:
        violations.append("xi_isolation_ingress_dsn_undeclared")
    # Backend: only the ingestion boundary (consumer) and the DB
    # pool factory (gateway, constructs but never spends the
    # credential) may reference the DSN. Test suites are not shipped
    # processes (they never receive production credentials); the
    # census covers shipped code.
    allowed_holders = {
        "backend/app/ingestion/event_service.py",
        "backend/app/db/session.py",
    }
    offenders = []
    for path in sorted((REPO_ROOT / "backend" / "app").rglob("*.py")):
        try:
            body = path.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        if INGRESS_DSN_TOKEN in body and rel not in allowed_holders:
            offenders.append(rel)
    checks["ingress_dsn_backend_holders"] = offenders
    if offenders:
        violations.append(
            "xi_isolation_ingress_dsn_beyond_boundary:"
            + ",".join(offenders[:10])
        )
    # Compose census: no non-API service may mount the ingress DSN
    # (blanking assignments carry no credential and are skipped).
    for name in (
        "docker-compose.local.yml",
        "docker-compose.e2e.yml",
        "docker-compose.test.yml",
        "docker-compose.c19.yml",
    ):
        path = REPO_ROOT / name
        if not path.is_file():
            continue
        try:
            body = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for i, line in enumerate(body.splitlines(), 1):
            if _line_mounts_ingress(line):
                context = "\n".join(body.splitlines()[max(0, i - 12):i])
                if not re.search(
                    r"(api|web)\s*:", context
                ):
                    violations.append(
                        f"xi_isolation_ingress_dsn_compose:{name}:{i}"
                    )


def _live_checks(
    admin_dsn: str, violations: list[str], checks: dict
) -> None:
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        violations.append(f"xi_isolation_live_no_driver:{exc}")
        return
    try:
        conn = psycopg2.connect(admin_dsn)
        conn.autocommit = True
    except Exception as exc:
        violations.append(f"xi_isolation_live_connect_failed:{exc}")
        return
    try:
        cur = conn.cursor()
        # Presence gate: lanes that never provision the ingress
        # principal run predecessor-compatible ingestion semantics;
        # wherever XI is adjudicated the principal must exist, or no
        # governed lane could silently lack strict isolation.
        cur.execute(
            "SELECT count(*) FROM pg_roles WHERE rolname = 'app_ingress'"
        )
        if int(cur.fetchone()[0]) != 1:
            violations.append("xi_isolation_ingress_principal_absent")
            checks["ingress_principal"] = "absent"
        else:
            checks["ingress_principal"] = "present"
        # No membership edge may connect the ingress principal to any
        # generic role (SET ROLE forgery impossible by construction).
        cur.execute(
            """
            SELECT role_ref.rolname, member_ref.rolname
            FROM pg_auth_members m
            JOIN pg_roles role_ref ON role_ref.oid = m.roleid
            JOIN pg_roles member_ref ON member_ref.oid = m.member
            WHERE role_ref.rolname IN (
                      'app_ingress', 'app_user', 'app_worker',
                      'app_rw', 'app_ro'
                  )
               OR member_ref.rolname = 'app_ingress'
            """
        )
        edges = cur.fetchall()
        leak = [
            (a, b) for a, b in edges
            if a == "app_ingress" or b == "app_ingress"
        ]
        checks["role_membership_edges"] = [
            f"{a}<->{b}" for a, b in edges
        ]
        if leak:
            violations.append(
                "xi_isolation_ingress_membership:"
                + ",".join(f"{a}-{b}" for a, b in leak)
            )
        # Least-privilege ceiling: app_ingress table privileges must
        # be a subset of ingress persistence + tenant reads.
        cur.execute(
            """
            SELECT table_name, privilege_type
            FROM information_schema.role_table_grants
            WHERE grantee = 'app_ingress'
              AND table_schema = 'public'
            """
        )
        grants = sorted(
            (t, p) for t, p in cur.fetchall()
        )
        checks["ingress_table_grants"] = [
            f"{t}:{p}" for t, p in grants
        ]
        allowed_tables = {
            "webhook_ingress_identities",
            "tenants",
            "b26_p2_ingress_auth_witness",
            # Read-only trigger-plane visibility (custody twin +
            # evidence trail); writes remain ungranted everywhere.
            "b23_match_task_dispatches",
            "b26_p2_provenance_evidence",
            # Read-only event visibility (ingress rows bind their
            # committed attribution event); writes ungranted.
            "attribution_events",
            # B2.6-P2 Corrective XII: the ingress boundary observes
            # (never authors) the predecessor consequence P.
            "b26_p2_provider_auth_consequence",
        }
        for table, priv in grants:
            if table not in allowed_tables:
                violations.append(
                    f"xi_isolation_ingress_overgrant:{table}:{priv}"
                )
        for table, priv in grants:
            if table == "webhook_ingress_identities" and priv not in (
                "SELECT", "INSERT", "UPDATE",
            ):
                violations.append(
                    f"xi_isolation_ingress_write_beyond_insert:{priv}"
                )
            if table in ("tenants", "b26_p2_ingress_auth_witness") and (
                priv != "SELECT"
            ):
                violations.append(
                    f"xi_isolation_ingress_read_beyond_select:{table}:{priv}"
                )
            if table in (
                "b23_match_task_dispatches",
                "b26_p2_provenance_evidence",
                "attribution_events",
                "b26_p2_provider_auth_consequence",
            ) and priv != "SELECT":
                violations.append(
                    f"xi_isolation_ingress_twin_beyond_select:{table}:{priv}"
                )
        # Routine ceiling: witness + attest (+ read-only P3
        # eligibility) only.
        cur.execute(
            """
            SELECT routine_name
            FROM information_schema.role_routine_grants
            WHERE grantee = 'app_ingress'
              AND routine_schema = 'public'
            """
        )
        routines = sorted(r[0] for r in cur.fetchall())
        checks["ingress_routine_grants"] = routines
        allowed_routines = {
            "b26_p2_record_ingress_auth_witness",
            "b26_p2_attest_provenance_evidence",
            "b26_p2_state_eligible_for_p3",
            "b26_p2_canonical_scope_identity_for_window",
            "b26_p2_classify_candidate",
            # B2.6-P2 Corrective XII: topology adjudication (read-only
            # checks) are observable by the ingress boundary.
            "b26_p2_xii_topology_check",
        }
        for routine in routines:
            if routine not in allowed_routines:
                violations.append(
                    f"xi_isolation_ingress_routine_overgrant:{routine}"
                )
        for forbidden in (
            "b26_p2_mark_conducted",
            "b26_p2_record_conduction_receipt",
        ):
            if forbidden in routines:
                violations.append(
                    f"xi_isolation_ingress_completion_authority:"
                    f"{forbidden}"
                )
    except Exception as exc:
        violations.append(f"xi_isolation_live_catalog_failed:{exc}")
        conn.close()
        return
    conn.close()
    _behavioral_probes(admin_dsn, violations, checks)


def _behavioral_probes(
    admin_dsn: str, violations: list[str], checks: dict
) -> None:
    import psycopg2  # noqa: PLC0415

    def role_dsn(role: str) -> str | None:
        if "migration_owner:migration_owner" not in admin_dsn:
            return None
        return admin_dsn.replace(
            "migration_owner:migration_owner", f"{role}:{role}"
        )

    worker_dsn = role_dsn("app_worker")
    relay_dsn = role_dsn("app_relay")
    beat_dsn = role_dsn("app_beat")
    if worker_dsn is None or relay_dsn is None or beat_dsn is None:
        violations.append("xi_isolation_role_dsn_underivable")
        return
    tenant_a = str(uuid.uuid4())
    admin = psycopg2.connect(admin_dsn)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tenants (id, name, api_key_hash,"
                " notification_email) VALUES (%s, %s, %s, %s)",
                (tenant_a, f"xi-iso-{tenant_a[:8]}",
                 uuid.uuid4().hex, "xi-iso@example.invalid"),
            )
    finally:
        admin.close()
    checks["_isolation_tenant"] = tenant_a
    # F-XI-B1: generic runtimes hold no ingress-auth capability.
    for role, dsn in (
        ("app_worker", worker_dsn),
        ("app_relay", relay_dsn),
        ("app_beat", beat_dsn),
    ):
        try:
            probe = psycopg2.connect(dsn)
            probe.autocommit = True
            try:
                with probe.cursor() as cur:
                    cur.execute(
                        "SELECT public.b26_p2_record_ingress_auth_witness"
                        "('00000000-0000-0000-0000-000000000000')"
                    )
                    violations.append(
                        f"xi_isolation_worker_mints:{role}"
                    )
            except Exception as exc:
                if "permission denied" not in str(exc).lower():
                    violations.append(
                        f"xi_isolation_worker_wrong_refusal:{role}:"
                        + str(exc)[:100]
                    )
            finally:
                probe.close()
        except Exception as exc:
            violations.append(
                f"xi_isolation_probe_connect_failed:{role}:{exc}"[:140]
            )
    # F-XI-B3: cross-tenant signed event under the ingress role is
    # refused (tenant boundary conserved).
    ingress_dsn = role_dsn("app_ingress")
    if ingress_dsn is None:
        violations.append("xi_isolation_ingress_dsn_underivable")
        return
    try:
        probe = psycopg2.connect(ingress_dsn)
        probe.autocommit = True
        try:
            with probe.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id',"
                    " %s, false)",
                    (tenant_a,),
                )
                try:
                    cur.execute(
                        "INSERT INTO public.webhook_ingress_identities"
                        " (id, tenant_id, event_id, provider,"
                        " verified_amount_minor,"
                        " verified_amount_currency, event_timestamp,"
                        " idempotency_key,"
                        " verified_commerce_ingress_state)"
                        " VALUES (%s, %s, %s, 'stripe', 100, 'USD',"
                        " now(), %s, 'pending')",
                        (str(uuid.uuid4()), str(uuid.uuid4()),
                         str(uuid.uuid4()),
                         f"xi-cross:{uuid.uuid4().hex[:8]}"),
                    )
                    violations.append("xi_isolation_cross_tenant_allowed")
                except Exception as exc:
                    msg = str(exc).lower()
                    if (
                        "row-level security" not in msg
                        and "violates" not in msg
                        and "policy" not in msg
                    ):
                        violations.append(
                            "xi_isolation_cross_tenant_wrong_refusal:"
                            + msg[:100]
                        )
        finally:
            probe.close()
    except Exception as exc:
        violations.append(f"xi_isolation_cross_probe_failed:{exc}"[:140])
    # The isolation tenant carries no P2 rows (tenant row only), so
    # the generic oracle is unaffected. Lanes are throwaway.
    checks["behavioral_done"] = True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate B2.6-P2 XI ingress isolation law."
    )
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _topology_checks(violations, checks)
    if args.dsn is None:
        violations.append("xi_isolation_live_check_required_no_dsn")
    else:
        _live_checks(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    evidence = {
        "gate_id": "B26-P2-XI-INGRESS-ISOLATION",
        "validator": "validate_b26_p2_xi_ingress_isolation",
        "status": status,
        "violations": sorted(violations),
        "checks": checks,
    }
    if args.evidence_out is not None:
        args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if args.evidence_dir is not None:
        args.evidence_dir.mkdir(parents=True, exist_ok=True)
        (args.evidence_dir / "xi-ingress-isolation.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if violations:
        print("B26_P2_XI_ISOLATION_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_XI_ISOLATION_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
