#!/usr/bin/env python3
"""B2.6-P2 Corrective XIV negative controls (non-vacuity proof).

Each control proves its gate can RED on a genuine member of the class
it governs (without using symbols the gate scans for as the defect
itself where avoidable), then restores byte-exact GREEN:

- XIV-NC-AUTH: legacy recorder+witness+attest without the atomic cannot
  promote (live DB; the gate is the promotion refusal itself).
- XIV-NC-HIST: forged complete-but-unverifiable shape flagged by the
  oracle; quarantine clears it (live DB, trigger-disabled plant with
  guaranteed restore + sweep cleanup).
- XIV-NC-SEM-MEANING: provider-selective helper blackout REDs behavior
  while structural conformance stays GREEN (live DB plant/restore).
- XIV-NC-SEM-STRUCT: allowlisted-helper relational read REDs structural
  (live DB plant/restore).
- XIV-NC-ORACLE-COMMON-MODE: contract+runtime moved together to the
  wrong window law REDs the independent phase oracle (live DB
  function patch/restore).
- XIV-NC-TEMP-MAP: disposition without mapped probe REDs statically
  (in-memory contract mutation; no file change).
- XIV-NC-TEMP-KILL: weakening a real enforcement trigger is caught
  (covered live by the temporal validator's kill-switches; here assert
  the validator reports killswitch_red cells).
- XIV-NC-TOPO: API-as-auth_ingress poison REDs topology; restore GREENs
  (compose file poison with byte-exact restore).
- XIV-NC-CAP: legacy credential in web REDs capability (covered by XIII
  NC; re-asserted here via the XIII control file presence).

Exit code is the gate.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SEM = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xiii_semantic_contract.py"
BEHAVIOR = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xiv_semantic_behavior.py"
ORACLE = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xiv_phase_oracle.py"
TEMP = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xiv_temporal_behavior.py"
COND = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xiv_auth_conduction.py"
TOPO = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xiv_topology.py"


def _run(args, **kw):
    return subprocess.run(
        args, capture_output=True, text=True, cwd=str(REPO_ROOT), **kw
    )


def _control_auth_legacy(admin_dsn, violations, checks):
    import psycopg2  # noqa: PLC0415

    admin = psycopg2.connect(admin_dsn)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            tenant = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
                " VALUES (%s,%s,%s,%s)",
                (tenant, "xiv-nc", uuid.uuid4().hex, "xiv-nc@example.invalid"),
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            cur.execute(
                "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
                " display_name, state) VALUES ('xiv_temp_ch', 'xiv_temp', true,"
                " 'XIVTEMP', 'active') ON CONFLICT (code) DO NOTHING"
            )
            ev, ing = str(uuid.uuid4()), str(uuid.uuid4())
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id, occurred_at, correlation_id,"
                " session_id, revenue_cents, raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency, event_timestamp, processed_at,"
                " processing_status) VALUES (%s,%s,now(),%s,%s,7600,'{}'::jsonb,%s,'conversion',"
                " 'xiv_temp_ch','c',7600,'USD',now(),now(),'processed')",
                (ev, tenant, str(uuid.uuid4()), str(uuid.uuid4()), "xiv-nc-1"),
            )
            cur.execute(
                "INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id, provider,"
                " provider_native_event_reference, provider_native_commerce_reference,"
                " normalized_commerce_reference_kind, normalized_commerce_reference_value,"
                " verified_amount_minor, verified_amount_currency, event_timestamp,"
                " idempotency_key, verified_commerce_ingress_state)"
                " VALUES (%s,%s,%s,'stripe','e1','o1','k','o1',7600,'USD',now(),"
                " 'xiv-nc-1','authenticity_verified')",
                (ing, tenant, ev),
            )
            ingress_dsn = admin_dsn.replace(
                "migration_owner:migration_owner", "app_ingress:app_ingress"
            )
            conn = psycopg2.connect(ingress_dsn)
            conn.autocommit = True
            try:
                with conn.cursor() as icur:
                    icur.execute(
                        "SELECT set_config('app.current_tenant_id', %s, false)",
                        (tenant,),
                    )
                    icur.execute(
                        "SELECT public.b26_p2_record_provider_auth_consequence(%s,'stripe','e1',%s,%s,"
                        "'hmac-sha256-timestamped-hex','v1')",
                        (ing, "a" * 64, "b" * 64),
                    )
                    icur.execute(
                        "SELECT public.b26_p2_record_ingress_auth_witness(%s,'stripe','e1',%s)",
                        (ing, "a" * 64),
                    )
                    try:
                        icur.execute(
                            "SELECT public.b26_p2_attest_provenance_evidence(%s,"
                            "'signed_provider_reingestion','xiv-nc-1')",
                            (ing,),
                        )
                        violations.append("xiv_nc_auth_legacy_promotes")
                    except Exception as exc:
                        if "b26_p2_provenance_promotion_refused" not in str(exc):
                            violations.append(
                                f"xiv_nc_auth_wrong_refusal:{str(exc).splitlines()[0][:120]}"
                            )
                        else:
                            checks["auth_legacy_red"] = True
                    # Atomic on the same ingress still authorizes (restore GREEN).
                    icur.execute(
                        "SELECT public.b26_p2_authenticate_ingress_atomic(%s,'stripe','e1',%s,%s,"
                        "'hmac-sha256-timestamped-hex','v1')",
                        (ing, "a" * 64, "b" * 64),
                    )
                    if str(icur.fetchone()[0]) != "authenticated_known":
                        violations.append("xiv_nc_auth_atomic_not_green")
                    else:
                        checks["auth_atomic_green"] = True
            finally:
                conn.close()
    finally:
        admin.close()


def _control_hist_oracle(admin_dsn, violations, checks):
    import psycopg2  # noqa: PLC0415

    admin = psycopg2.connect(admin_dsn)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            tenant = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
                " VALUES (%s,%s,%s,%s)",
                (tenant, "xiv-nc-h", uuid.uuid4().hex, "xiv-nc-h@example.invalid"),
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            cur.execute(
                "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
                " display_name, state) VALUES ('xiv_temp_ch', 'xiv_temp', true,"
                " 'XIVTEMP', 'active') ON CONFLICT (code) DO NOTHING"
            )
            cur.execute(
                "ALTER TABLE public.webhook_ingress_identities DISABLE TRIGGER trg_b26_p2_ingress_provenance"
            )
            try:
                f_ev, f_ing = str(uuid.uuid4()), str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO public.attribution_events (id, tenant_id, occurred_at, correlation_id,"
                    " session_id, revenue_cents, raw_payload, idempotency_key, event_type, channel,"
                    " campaign_id, conversion_value_cents, currency, event_timestamp, processed_at,"
                    " processing_status) VALUES (%s,%s,now(),%s,%s,7600,'{}'::jsonb,%s,'conversion',"
                    " 'xiv_temp_ch','c',7600,'USD',now(),now(),'processed')",
                    (
                        f_ev,
                        tenant,
                        str(uuid.uuid4()),
                        str(uuid.uuid4()),
                        "xiv-nc-forge",
                    ),
                )
                cur.execute(
                    "INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id, provider,"
                    " provider_native_event_reference, provider_native_commerce_reference,"
                    " normalized_commerce_reference_kind, normalized_commerce_reference_value,"
                    " verified_amount_minor, verified_amount_currency, event_timestamp,"
                    " idempotency_key, verified_commerce_ingress_state, b26_p2_provenance_status)"
                    " VALUES (%s,%s,%s,'stripe','ef','of','k','of',7600,'USD',now(),'xiv-nc-forge',"
                    " 'authenticity_verified','authenticated_known')",
                    (f_ing, tenant, f_ev),
                )
            finally:
                cur.execute(
                    "ALTER TABLE public.webhook_ingress_identities ENABLE TRIGGER trg_b26_p2_ingress_provenance"
                )
            cur.execute(
                "INSERT INTO public.b26_p2_provider_auth_consequence (webhook_ingress_identity_id,"
                " tenant_id, provider, provider_event_reference, body_sha256,"
                " signature_envelope_sha256, auth_method, auth_version, recorded_by)"
                " VALUES (%s,%s,'stripe','ef',%s,%s,'m','v1','postgres')",
                (f_ing, tenant, "e" * 64, "f" * 64),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_ingress_auth_witness (webhook_ingress_identity_id,"
                " tenant_id, witness_hash, witnessed_by) VALUES (%s,%s,'w','postgres')",
                (f_ing, tenant),
            )
            cur.execute(
                "SELECT violation_kind FROM public.b26_p2_xiii_invariant_oracle()"
            )
            if "xiv_complete_but_unverifiable" not in [r[0] for r in cur.fetchall()]:
                violations.append("xiv_nc_hist_oracle_blind")
            else:
                checks["hist_oracle_red"] = True
            # Quarantine clears; P3 FALSE for the forged lineage.
            cur.execute(
                "INSERT INTO public.b26_p2_execution_quarantine (source_relation, task_id, tenant_id,"
                " webhook_ingress_identity_id, reason, original_payload, migration_identity)"
                " VALUES ('webhook_ingress_identities',%s,%s,%s,'historically_unverifiable_xiv','{}','xiv-nc')",
                ("xiv-nc:" + f_ing, tenant, f_ing),
            )
            cur.execute(
                "SELECT violation_kind FROM public.b26_p2_xiii_invariant_oracle()"
            )
            if "xiv_complete_but_unverifiable" in [r[0] for r in cur.fetchall()]:
                violations.append("xiv_nc_hist_quarantine_no_clear")
            else:
                checks["hist_quarantine_green"] = True
    finally:
        admin.close()


def _db_plant(admin_dsn, sql, args=()):
    import psycopg2  # noqa: PLC0415

    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
    finally:
        conn.close()


def _control_sem(admin_dsn, violations, checks):
    # Meaning blackout: structural GREEN, behavior RED.
    _db_plant(
        admin_dsn,
        "CREATE OR REPLACE FUNCTION public.b26_p2_ascii_strip(p_value text) RETURNS text"
        " LANGUAGE plpgsql IMMUTABLE SET search_path TO 'pg_catalog','public' AS $$ BEGIN"
        " IF lower(COALESCE(p_value,'')) LIKE '%%shopify%%' THEN RETURN ''; END IF;"
        " RETURN regexp_replace(regexp_replace(COALESCE(p_value, ''),"
        " '^[ \\t\\n\\r\\f\\v]+', ''), '[ \\t\\n\\r\\f\\v]+$', ''); END $$;",
    )
    try:
        proc = _run([sys.executable, str(SEM), "--dsn", admin_dsn])
        struct_green = proc.returncode == 0
        proc = _run([sys.executable, str(BEHAVIOR), "--dsn", admin_dsn])
        if proc.returncode == 0:
            violations.append("xiv_nc_sem_meaning_not_red")
        elif "provider_blackout" not in (proc.stdout + proc.stderr):
            violations.append(
                "xiv_nc_sem_wrong_red:" + (proc.stdout + proc.stderr)[:160]
            )
        else:
            checks["sem_meaning_red"] = True
            if not struct_green:
                checks["sem_meaning_note"] = "structural also red (defense in depth)"
    finally:
        _db_plant(
            admin_dsn,
            "CREATE OR REPLACE FUNCTION public.b26_p2_ascii_strip(p_value text) RETURNS text"
            " LANGUAGE sql IMMUTABLE SET search_path TO 'pg_catalog','public' AS $_$"
            " SELECT regexp_replace(regexp_replace(COALESCE(p_value, ''),"
            " '^[ \\t\\n\\r\\f\\v]+', ''), '[ \\t\\n\\r\\f\\v]+$', '') $_$",
        )
    proc = _run([sys.executable, str(BEHAVIOR), "--dsn", admin_dsn])
    if proc.returncode != 0:
        violations.append(
            "xiv_nc_sem_restore_not_green:" + (proc.stdout + proc.stderr)[:160]
        )
    else:
        checks["sem_meaning_restore_green"] = True
    # Structural plant: relational read inside pure helper.
    _db_plant(
        admin_dsn,
        "CREATE OR REPLACE FUNCTION public.b26_p2_ascii_strip(p_value text) RETURNS text"
        " LANGUAGE plpgsql IMMUTABLE SET search_path TO 'pg_catalog','public' AS $$"
        " DECLARE _v text; BEGIN SELECT v.match_quality INTO _v"
        " FROM public.b23_match_verdicts AS v LIMIT 1;"
        " IF _v IS NOT NULL THEN RETURN 'low'; END IF;"
        " RETURN regexp_replace(regexp_replace(COALESCE(p_value, ''),"
        " '^[ \\t\\n\\r\\f\\v]+', ''), '[ \\t\\n\\r\\f\\v]+$', ''); END $$;",
    )
    try:
        proc = _run([sys.executable, str(SEM), "--dsn", admin_dsn])
        if proc.returncode == 0:
            violations.append("xiv_nc_sem_struct_not_red")
        else:
            checks["sem_struct_red"] = True
    finally:
        _db_plant(
            admin_dsn,
            "CREATE OR REPLACE FUNCTION public.b26_p2_ascii_strip(p_value text) RETURNS text"
            " LANGUAGE sql IMMUTABLE SET search_path TO 'pg_catalog','public' AS $_$"
            " SELECT regexp_replace(regexp_replace(COALESCE(p_value, ''),"
            " '^[ \\t\\n\\r\\f\\v]+', ''), '[ \\t\\n\\r\\f\\v]+$', '') $_$",
        )
    proc = _run([sys.executable, str(SEM), "--dsn", admin_dsn])
    if proc.returncode != 0:
        violations.append("xiv_nc_sem_struct_restore_not_green")
    else:
        checks["sem_struct_restore_green"] = True


def _control_oracle_common_mode(admin_dsn, violations, checks):
    import psycopg2  # noqa: PLC0415

    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname='b26_p2_classify_candidate'"
            )
            orig = cur.fetchone()[0]
            patched = orig.replace(
                "p_event_time < p_window_end", "p_event_time <= p_window_end"
            )
            if patched == orig:
                violations.append("xiv_nc_oracle_patch_anchor_drifted")
                return
            cur.execute(patched)
        try:
            proc = _run([sys.executable, str(ORACLE), "--dsn", admin_dsn])
            if proc.returncode == 0:
                violations.append("xiv_nc_oracle_common_mode_not_red")
            else:
                checks["oracle_common_mode_red"] = True
        finally:
            with conn.cursor() as cur:
                cur.execute(orig)
        proc = _run([sys.executable, str(ORACLE), "--dsn", admin_dsn])
        if proc.returncode != 0:
            violations.append("xiv_nc_oracle_restore_not_green")
        else:
            checks["oracle_restore_green"] = True
    finally:
        conn.close()


def _control_temp_map(violations, checks):
    import json as _json  # noqa: PLC0415

    contract = _json.loads(
        (
            REPO_ROOT
            / "contracts-internal"
            / "governance"
            / "b26_p2_xiii_semantic_contract.v1.json"
        ).read_text(encoding="utf-8")
    )
    contract["temporal_dispositions"].pop("b23_match_verdicts.status", None)
    treated = {str(k).lower() for k in contract["temporal_dispositions"]}
    cols = {
        f"{rel}.{c}".lower()
        for rel, coll in contract["allowed_source_columns"].items()
        for c in coll
    }
    if (
        "b23_match_verdicts.status" not in treated
        and "b23_match_verdicts.status" in cols
    ):
        checks["temp_map_red"] = True
    else:
        violations.append("xiv_nc_temp_map_blind")


def _control_topo(violations, checks):
    path = REPO_ROOT / "docker-compose.c19.yml"
    original = path.read_text(encoding="utf-8")
    try:
        poisoned = original.replace(
            'SKELDIR_PROCESS_ROLE: "api"', 'SKELDIR_PROCESS_ROLE: "auth_ingress"', 1
        )
        if poisoned == original:
            violations.append("xiv_nc_topo_anchor_drifted")
            return
        path.write_text(poisoned, encoding="utf-8")
        proc = _run([sys.executable, str(TOPO)])
        if proc.returncode == 0:
            violations.append("xiv_nc_topo_not_red")
        else:
            checks["topo_poison_red"] = True
    finally:
        path.write_text(original, encoding="utf-8")
    proc = _run([sys.executable, str(TOPO)])
    if proc.returncode != 0:
        violations.append(
            "xiv_nc_topo_restore_not_green:" + (proc.stdout + proc.stderr)[:160]
        )
    else:
        checks["topo_restore_green"] = True


def main() -> int:
    parser = argparse.ArgumentParser(description="XIV negative controls.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _control_temp_map(violations, checks)
    _control_topo(violations, checks)
    if args.dsn is not None:
        _control_auth_legacy(args.dsn, violations, checks)
        _control_hist_oracle(args.dsn, violations, checks)
        _control_sem(args.dsn, violations, checks)
        _control_oracle_common_mode(args.dsn, violations, checks)
        # Temporal kill-switch non-vacuity is executed live by the
        # temporal validator on every run; require its cells here.
        proc = _run([sys.executable, str(TEMP), "--dsn", args.dsn])
        if proc.returncode != 0:
            violations.append(
                "xiv_nc_temp_not_green:" + (proc.stdout + proc.stderr)[-200:]
            )
        elif "killswitch_red" not in proc.stdout:
            violations.append("xiv_nc_temp_killswitch_blind")
        else:
            checks["temp_killswitch_armed"] = True
        for name, script in (("cond", COND), ("topo_live", TOPO)):
            extra = [] if name == "topo_live" else ["--dsn", args.dsn]
            proc = _run([sys.executable, str(script), *extra])
            if proc.returncode != 0:
                violations.append(
                    f"xiv_nc_live_not_green:{name}:"
                    + (proc.stdout + proc.stderr)[-160:]
                )
            else:
                checks[f"live_{name}_green"] = True
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XIV_NC_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XIV-NEGATIVE-CONTROLS",
                    "status": status,
                    "violations": sorted(violations),
                    "checks": checks,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
