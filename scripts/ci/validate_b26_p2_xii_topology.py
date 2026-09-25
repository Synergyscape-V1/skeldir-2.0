#!/usr/bin/env python3
"""B2.6-P2 Corrective XII single authentication regime (BLOCKER C).

Law: one migration head plus the declared topology version uniquely
determines the authentication authority model. The XII migration
refuses when the required ingress principal is absent (fail-closed
deploy, never predecessor service); no authentication law branches on
role existence; late provisioning deterministically installs the exact
governed grants (contract B: no third regime).

Static: the XII migration contains the absent-topology refusal gate;
no auth law body consults role existence.

Live (--dsn REQUIRED): topology_check() is strict; app_user holds no
verified authorship and no attestation EXECUTE on the XII lane;
provisioning converges (idempotent re-provision keeps the lane
strict); the app startup guard exists in shipped code.

Exit code is the gate: 0 on PASS, 1 plus a violation list on FAIL.
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
XII_MIGRATION = (
    REPO_ROOT / "alembic" / "versions" / "007_skeldir_foundation"
    / "202609250001_b26_p2_corrective_xii_fact_anchored_closure.py"
)


def _static_checks(violations: list[str], checks: dict) -> None:
    try:
        source = XII_MIGRATION.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xii_topo_static_unreadable:{exc}")
        return
    checks["migration_present"] = True
    if "b26_p2_xii_ingress_topology_absent" not in source:
        violations.append("xii_topo_static_no_absent_gate")
    if "b26_p2_xii_provision_ingress_topology" not in source:
        violations.append("xii_topo_static_no_provision_fn")
    # No authentication law may branch on role existence anymore.
    # Scope the search to each redefined function body (AS $$ ... END
    # $$), so neighboring sections (gate, grants, comments) cannot
    # false-positive.
    import re as _re

    for fn in (
        "b26_p2_attest_provenance_evidence",
        "b26_p2_enforce_ingress_verified_authorship",
        "b26_p2_enforce_ingress_provenance",
    ):
        bodies = _re.findall(
            r"FUNCTION\s+public\.%s\(.*?AS\s*\$\$(.*?)\$\$;"
            % _re.escape(fn),
            source,
            _re.IGNORECASE | _re.DOTALL,
        )
        for body in bodies:
            if "pg_roles" in body and "rolname" in body:
                violations.append("xii_topo_static_role_branching:%s" % fn)
                break
    # The application must adjudicate topology at startup.
    main_src = (REPO_ROOT / "backend" / "app" / "main.py").read_text(
        encoding="utf-8"
    )
    if "b26_p2_xii_ingress_topology_absent" not in main_src:
        violations.append("xii_topo_static_no_startup_guard")
    checks["static_done"] = True


def _live_checks(admin_dsn: str, violations: list[str], checks: dict) -> None:
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        violations.append(f"xii_topo_live_no_driver:{exc}")
        return
    try:
        conn = psycopg2.connect(admin_dsn)
        conn.autocommit = True
    except Exception as exc:
        violations.append(f"xii_topo_live_connect_failed:{exc}")
        return
    try:
        cur = conn.cursor()
        cur.execute("SELECT public.b26_p2_xii_topology_check()")
        if str(cur.fetchone()[0]) != "xii_topology_strict":
            violations.append("xii_topo_live_not_strict")
        else:
            checks["topology_strict"] = True
        # Re-provisioning converges (contract B idempotence).
        cur.execute(
            "SELECT public.b26_p2_xii_provision_ingress_topology()"
        )
        if str(cur.fetchone()[0]) != "xii_topology_provisioned":
            violations.append("xii_topo_live_provision_failed")
        else:
            checks["provision_converges"] = True
        cur.execute("SELECT public.b26_p2_xii_topology_check()")
        if str(cur.fetchone()[0]) != "xii_topology_strict":
            violations.append("xii_topo_live_post_provision_not_strict")
        # Provisioning refuses non-admin callers.
        user_dsn = admin_dsn.replace(
            "migration_owner:migration_owner", "app_user:app_user"
        )
        user = psycopg2.connect(user_dsn)
        user.autocommit = True
        try:
            with user.cursor() as ucur:
                try:
                    ucur.execute(
                        "SELECT public.b26_p2_xii_provision_ingress_topology()"
                    )
                    violations.append("xii_topo_live_provision_unprivileged")
                except Exception as exc:
                    msg = str(exc).lower()
                    if (
                        "permission denied" not in msg
                        and "b26_p2_xii_provision_refused" not in msg
                    ):
                        violations.append(
                            "xii_topo_live_provision_wrong_refusal:"
                            + str(exc)[:100]
                        )
        finally:
            user.close()
        # No predecessor authority on the XII lane (ROLE-1 physics).
        tenant = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash,"
            " notification_email) VALUES (%s, %s, %s, %s)",
            (tenant, "xii-topo-%s" % tenant[:8], uuid.uuid4().hex,
             "xii-topo@example.invalid"),
        )
        cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, false)",
            (tenant,),
        )
        cur.execute(
            "INSERT INTO public.attribution_events (id, tenant_id,"
            " occurred_at, correlation_id, session_id, revenue_cents,"
            " raw_payload, idempotency_key, event_type, channel,"
            " campaign_id, conversion_value_cents, currency,"
            " event_timestamp, processed_at, processing_status)"
            " VALUES (%s, %s, now(), %s, %s, 100,"
            " '{}'::jsonb, %s, 'conversion', 'xii_auth_ch',"
            " 'c', 100, 'USD', now(), now(), 'processed')",
            (str(uuid.uuid4()), tenant, str(uuid.uuid4()),
             str(uuid.uuid4()), "xii-topo:%s" % tenant[:8]),
        )
        user = psycopg2.connect(user_dsn)
        user.autocommit = True
        try:
            with user.cursor() as ucur:
                ucur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,),
                )
                try:
                    ucur.execute(
                        "INSERT INTO public.webhook_ingress_identities (id,"
                        " tenant_id, event_id, provider,"
                        " verified_amount_minor, verified_amount_currency,"
                        " event_timestamp, idempotency_key,"
                        " verified_commerce_ingress_state)"
                        " VALUES (%s, %s, %s, 'stripe', 100, 'USD',"
                        " now(), %s, 'authenticity_verified')",
                        (str(uuid.uuid4()), tenant, str(uuid.uuid4()),
                         "xii-topo-v:%s" % tenant[:8]),
                    )
                    violations.append("xii_topo_live_predecessor_authorship")
                except Exception as exc:
                    if "b26_p2_verified_authorship_refused" not in str(exc):
                        violations.append(
                            "xii_topo_live_authorship_wrong_refusal:"
                            + str(exc)[:100]
                        )
                    else:
                        checks["no_predecessor_authorship"] = True
        finally:
            user.close()
    except Exception as exc:
        violations.append(f"xii_topo_live_failed:{exc}"[:160])
        conn.close()
        return
    conn.close()
    checks["behavioral_done"] = True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate B2.6-P2 XII single-regime topology law."
    )
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _static_checks(violations, checks)
    if args.dsn is None:
        violations.append("xii_topo_live_check_required_no_dsn")
    else:
        _live_checks(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    evidence = {
        "gate_id": "B26-P2-XII-SINGLE-REGIME",
        "validator": "validate_b26_p2_xii_topology",
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
        (args.evidence_dir / "xii-topology.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if violations:
        print("B26_P2_XII_TOPO_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_XII_TOPO_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
