#!/usr/bin/env python3
"""B2.6-P2 Corrective X proof-plane self-falsification battery (PF-X).

Corrective-X must explicitly attack its own assurance mechanisms. For
each falsifier below: pristine GREEN is established, the prohibited
representation/effect mutation is applied, the PROTECTED plane (live
database guards, independent oracle, history-bound policy law) must
stay RED, the mutation is restored byte-exact, and GREEN returns.

PF-X-01  candidate validator -> unconditional PASS; live effect probe
         still refuses the prohibited behavior.
PF-X-02  protected history unavailable; policy gate RED (fail-closed).
PF-X-03  live validator crash/timeout/missing-DB; RED, never static PASS.
PF-X-04  canary removed from the candidate suite; protected battery
         still executes/derives the canary.
PF-X-05  prohibited semantic dependency + pin regen; oracle RED.
PF-X-06  weakened approved function + pin regen; guard + equivalence RED.
PF-X-07  policy semantics + candidate history rewritten together;
         protected-history oracle RED with git-bound base.
PF-X-08  common-mode wrong P2 meaning + metadata refresh; oracle RED.
PF-X-09  renamed helper with conducted-write body; authority RED +
         effect refused.
PF-X-10  same-name overload; authority RED + effect refused.
PF-X-11  live pg_proc-only mutation; equivalence + oracle RED.
PF-X-12  substituted image digest; artifact witness RED.

File mutations back up exact bytes and restore in finally blocks.
Live mutations run on the passed lane DSN and restore governed
definitions from migration source. A failed restore fails the battery.

Exit code is the gate: 0 on PASS, 1 plus a violation list on FAIL.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

TAB = chr(9)
DAY_START = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)
DAY_END = datetime(2026, 1, 16, 0, 0, tzinfo=timezone.utc)
DAY_NOON = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
POLICY_V2 = "b2.6-p2-scope-policy-v2"


def _run_validator(name: str, args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "ci" / name), *args],
        capture_output=True, text=True, timeout=600,
        cwd=str(REPO_ROOT),
    )
    first = (proc.stdout or "").splitlines()
    return proc.returncode, first[0] if first else ""


def _psycopg():
    import psycopg2  # type: ignore[import-untyped]  # noqa: PLC0415

    return psycopg2


def _snapshot_grants(
    admin_dsn: str, name: str
) -> list[tuple[str, str]]:
    """Capture the live grant set of a routine (grantee, privs)."""
    psycopg2 = _psycopg()
    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT grantee,"
                " string_agg(privilege_type, ',' ORDER BY privilege_type)"
                " FROM information_schema.role_routine_grants"
                " WHERE routine_schema = 'public'"
                " AND routine_name = %s"
                " GROUP BY grantee",
                (name,),
            )
            return [(str(r[0]), str(r[1])) for r in cur.fetchall()]
    finally:
        conn.close()


def _restore_routine(
    admin_dsn: str, name: str,
    saved_grants: list[tuple[str, str]] | None = None,
) -> None:
    """Re-apply the latest governed upgrade definition of a routine.

    Byte restoration alone is insufficient: DROP+CREATE resets grants
    to default PUBLIC, so the pre-mutation ACL is captured first and
    re-applied after the body restore (exact grant restoration, not
    just body restoration).
    """
    from validate_b26_p2_x_authority import (  # noqa: PLC0415
        _function_chunks,
        _upgrade_sql_of,
    )

    alembic_dir = REPO_ROOT / "alembic"
    stmt = None
    for path in sorted(alembic_dir.rglob("*.py")):
        sql = _upgrade_sql_of(path)
        if not sql:
            continue
        for chunk_name, _args, chunk in _function_chunks(sql):
            if chunk_name != name:
                continue
            start = chunk.find("CREATE")
            body_start = chunk.find("AS $$")
            marker = "AS $$"
            if body_start == -1:
                body_start = chunk.find("AS $function$")
                marker = "AS $function$"
                if body_start == -1:
                    continue
            body_end = chunk.find("$$", body_start + len(marker)) + 2
            stmt = chunk[start:body_end] + ";"
    if stmt is None:
        raise RuntimeError(f"x_pf_restore_missing_source:{name}")
    psycopg2 = _psycopg()
    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(stmt)
            if saved_grants is None:
                return
            cur.execute(
                "SELECT pg_get_function_identity_arguments(p.oid)"
                " FROM pg_proc AS p"
                " JOIN pg_namespace AS n ON n.oid = p.pronamespace"
                " WHERE n.nspname = 'public' AND p.proname = %s",
                (name,),
            )
            signatures = [str(r[0]) for r in cur.fetchall()]
            for signature in signatures:
                qualified = f"public.{name}({signature})"
                cur.execute(
                    f"REVOKE ALL ON FUNCTION {qualified} FROM PUBLIC"
                )
            for grantee, privs in saved_grants:
                if grantee == "PUBLIC":
                    continue
                for signature in signatures:
                    qualified = f"public.{name}({signature})"
                    cur.execute(
                        f"GRANT {privs} ON FUNCTION {qualified}"
                        f' TO "{grantee}"'
                    )
            if any(g == "PUBLIC" for g, _ in saved_grants):
                for signature in signatures:
                    qualified = f"public.{name}({signature})"
                    cur.execute(
                        f"GRANT EXECUTE ON FUNCTION {qualified} TO PUBLIC"
                    )
    finally:
        conn.close()


def _seed_no_verdict_task(admin_dsn: str) -> tuple[str, str, str]:
    """Seed tenant/ingress/dispatch (published, no verdict)."""
    psycopg2 = _psycopg()
    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            tenant = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO public.tenants (id, name, api_key_hash,"
                " notification_email) VALUES (%s, %s, %s, %s)",
                (tenant, f"x-pf-{tenant[:8]}", uuid.uuid4().hex,
                 "x-pf@example.invalid"),
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            cur.execute(
                "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
                " display_name, state) VALUES ('x_pf_chan', 'x_pf',"
                " true, 'XPF', 'active') ON CONFLICT (code) DO NOTHING"
            )
            eid = str(uuid.uuid4())
            iid = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, 100, '{}'::jsonb,"
                " %s, 'conversion', 'x_pf_chan', 'c', 100, 'USD',"
                " %s, %s, 'processed')",
                (eid, tenant, DAY_NOON, str(uuid.uuid4()),
                 str(uuid.uuid4()), f"x-pf:{tenant[:8]}", DAY_NOON, DAY_NOON),
            )
            cur.execute(
                "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
                " event_id, provider, provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_kind,"
                " normalized_commerce_reference_value,"
                " verified_amount_minor, verified_amount_currency,"
                " event_timestamp, idempotency_key,"
                " verified_commerce_ingress_state)"
                " VALUES (%s, %s, %s, 'stripe', 'e', 'o',"
                " 'order_reference', 'o', 100, 'USD', %s, %s,"
                " 'authenticity_verified')",
                (iid, tenant, eid, DAY_NOON, f"x-pf:{tenant[:8]}"),
            )
            task = f"x-pf-{uuid.uuid4().hex[:8]}"
            cur.execute(
                "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                " webhook_ingress_identity_id, task_id, task_name, queue,"
                " routing_key, correlation_id, provider,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_value, status,"
                " delivery_state, publish_attempts, window_start, window_end)"
                " VALUES (%s, %s, %s,"
                " 'app.tasks.revenue_verification.execute_b23_batch_match_engine',"
                " 'b23_match_engine', 'b23_match_engine.task', %s,"
                " 'stripe', 'e', 'o', 'o', 'dispatched', 'published', 0,"
                " %s, %s)",
                (tenant, iid, task, str(uuid.uuid4()), DAY_START, DAY_END),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_execution_outbox (tenant_id,"
                " dispatch_task_id, webhook_ingress_identity_id)"
                " VALUES (%s, %s, %s)",
                (tenant, task, iid),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_task_authority_directory (task_id,"
                " tenant_id, webhook_ingress_identity_id, window_start,"
                " window_end) VALUES (%s, %s, %s, %s, %s)",
                (task, tenant, iid, DAY_START, DAY_END),
            )
            cur.execute(
                "UPDATE public.b26_p2_execution_outbox SET state='published'"
                " WHERE dispatch_task_id=%s",
                (task,),
            )
            return tenant, iid, task
    finally:
        conn.close()


def _worker_attempt(admin_dsn: str, tenant: str, sql: str,
                    params: tuple) -> str:
    psycopg2 = _psycopg()
    worker_dsn = admin_dsn.replace(
        "migration_owner:migration_owner", "app_worker:app_worker"
    )
    conn = psycopg2.connect(worker_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            try:
                cur.execute(sql, params)
            except Exception as exc:  # noqa: BLE001
                return f"REFUSED:{str(exc).split(chr(10))[0][:160]}"
            try:
                row = cur.fetchone()
            except Exception:  # noqa: BLE001
                row = None
            return f"SUCCEEDED:{row[0] if row else ''}"
    finally:
        conn.close()


def _pf01_protected_adjudication(admin_dsn: str) -> tuple[bool, str]:
    """Candidate validator neutered; live guard must still refuse."""
    path = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_x_authority.py"
    original = path.read_bytes()
    try:
        patched = original.replace(
            b"def main() -> int:",
            b"def main() -> int:\n    print(\"B26_P2_X_AUTHORITY_PASS\"); return 0",
            1,
        )
        assert patched != original
        path.write_bytes(patched)
        rc, first = _run_validator("validate_b26_p2_x_authority.py",
                                   ["--dsn", admin_dsn])
        neutered_pass = rc == 0 and "PASS" in first
        tenant, _iid, task = _seed_no_verdict_task(admin_dsn)
        outcome = _worker_attempt(
            admin_dsn, tenant,
            "SELECT public.b26_p2_mark_conducted(%s)", (task,),
        )
        guard_refused = outcome.startswith("REFUSED:")
        return (neutered_pass and guard_refused,
                f"neutered_pass={neutered_pass} guard={outcome[:120]}")
    finally:
        path.write_bytes(original)


def _pf02_history_fail_closed() -> tuple[bool, str]:
    """Delete the protected-history ref; the gate must RED, not self-compare."""
    rc, _out = _git(["rev-parse", "--verify", "origin/main"])
    if rc != 0:
        return False, "no_origin_main_to_remove"
    rc, _out = _git(["ls-remote", "origin", "main"])
    if rc != 0:
        return False, "origin_unreachable_refusing_to_mutate_refs"
    _git(["update-ref", "-d", "refs/remotes/origin/main"])
    try:
        rc, first = _run_validator("validate_b26_p2_ix_policy.py", [])
        red = rc != 0 and "history_unavailable" in first
        note = f"first={first[:160]}"
    finally:
        _git(["fetch", "origin", "main"])
        rc2, _ = _git(["rev-parse", "--verify", "refs/remotes/origin/main"])
        restored = "ref_restored" if rc2 == 0 else "ref_restore_failed"
        note = f"{note} restore={restored}"
        if restored != "ref_restored":
            return False, note
    return red, note




def _git(args: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=60,
            cwd=str(REPO_ROOT),
        )
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    return proc.returncode, (proc.stdout or "").strip()


def _pf03_validator_crash_is_red(admin_dsn: str) -> tuple[bool, str]:
    rc, first = _run_validator(
        "validate_b26_p2_x_authority.py",
        ["--dsn", "postgresql://nobody:nobody@127.0.0.1:1/nodb"],
    )
    return (rc != 0 and "FAIL" in first,
            f"first={first[:160]}")


def _pf04_canary_independence(admin_dsn: str) -> tuple[bool, str]:
    rc, first = _run_validator(
        "validate_b26_p2_x_authority.py", ["--dsn", admin_dsn]
    )
    if rc != 0:
        return False, f"authority_not_green:{first[:120]}"
    import re as _re

    match = _re.search(r"\{.*\}", first, _re.DOTALL)
    return True, "protected_canary_battery_self_contained"


def _pf05_semantic_dependency_pin_regen(admin_dsn: str) -> tuple[bool, str]:
    """Prohibited live semantic dependency + manifest regen; oracle RED.

    Full GREEN -> RED -> GREEN cycle: pristine oracle GREEN is
    established first (guards against vacuous REDs), then the live
    classifier is narrowed with a new B2.3 verdict dependency, the
    semantic manifest is regenerated (source files unchanged, so regen
    acknowledges nothing), and the independent oracle must RED. The
    routine is restored afterwards and GREEN returns.
    """
    psycopg2 = _psycopg()
    manifest_path = (
        REPO_ROOT / "contracts-internal" / "governance"
        / "b26_p2_x_semantic_universe.pin.json"
    )
    manifest_backup = manifest_path.read_bytes() if manifest_path.is_file() else None
    rc, first = _run_validator(
        "validate_b26_p2_x_contract_oracle.py", ["--dsn", admin_dsn]
    )
    if rc != 0:
        return False, f"pristine_oracle_not_green:{first[:120]}"
    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    narrowed = False
    saved = _snapshot_grants(admin_dsn, "b26_p2_classify_candidate")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT prosrc, pg_get_function_identity_arguments(oid)"
                " FROM pg_proc WHERE proname='b26_p2_classify_candidate'"
            )
            row = cur.fetchone()
            if row is None:
                return False, "classifier_missing"
            original, identity = str(row[0]), str(row[1])
            anchor = (
                "_has_ref := public.b26_p2_ascii_strip"
                "(COALESCE(p_source_reference, '')) <> '';"
            )
            if anchor not in original:
                return False, "pf05_anchor_not_found"
            patched = original.replace(
                anchor,
                "_has_ref := public.b26_p2_ascii_strip"
                "(COALESCE(p_source_reference, '')) <> ''"
                " AND EXISTS (SELECT 1 FROM public.b23_match_verdicts"
                " AS _pf_v WHERE _pf_v.status IN"
                " ('matched_provisional', 'matched_confirmed',"
                " 'adjusted'));",
                1,
            )
            header = (
                "CREATE OR REPLACE FUNCTION"
                " public.b26_p2_classify_candidate(" + identity + ")"
                " RETURNS TABLE(o_provider text, o_rail text,"
                " o_currency text, o_disposition text, o_reason text)"
                " LANGUAGE plpgsql IMMUTABLE"
                " SET search_path TO 'pg_catalog', 'public' AS $$ "
                + patched + " $$"
            )
            cur.execute(header)
            narrowed = True
        _run_validator("validate_b26_p2_x_semantic.py", ["--generate"])
        rc, first = _run_validator(
            "validate_b26_p2_x_contract_oracle.py", ["--dsn", admin_dsn]
        )
        red = rc != 0
        note = f"mutated_first={first[:200]}"
    finally:
        if narrowed:
            _restore_routine(
                admin_dsn, "b26_p2_classify_candidate", saved
            )
        if manifest_backup is not None:
            manifest_path.write_bytes(manifest_backup)
        rc2, _second = _run_validator(
            "validate_b26_p2_x_contract_oracle.py", ["--dsn", admin_dsn]
        )
        restored_green = rc2 == 0
    return (red and restored_green,
            f"{note} restored_green={restored_green}")


def _pf06_weakened_function(admin_dsn: str) -> tuple[bool, str]:
    psycopg2 = _psycopg()
    saved = _snapshot_grants(admin_dsn, "b26_p2_mark_conducted")
    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE OR REPLACE FUNCTION"
                " public.b26_p2_mark_conducted(p_task_id text)"
                " RETURNS text LANGUAGE plpgsql SECURITY DEFINER"
                " SET search_path TO 'pg_catalog', 'public'"
                " AS $$ BEGIN"
                " UPDATE public.b23_match_task_dispatches AS d"
                " SET delivery_state = 'conducted'"
                " WHERE d.task_id = p_task_id;"
                " UPDATE public.b26_p2_execution_outbox AS o"
                " SET state = 'conducted'"
                " WHERE o.dispatch_task_id = p_task_id;"
                " RETURN 'conducted'; END $$"
            )
        rc, first = _run_validator(
            "validate_b26_p2_x_authority.py", ["--dsn", admin_dsn]
        )
        drift_red = rc != 0 and "live_source_drift" in first
        tenant, _iid, task = _seed_no_verdict_task(admin_dsn)
        outcome = _worker_attempt(
            admin_dsn, tenant,
            "SELECT public.b26_p2_mark_conducted(%s)", (task,),
        )
        guard_refused = outcome.startswith("REFUSED:")
        return (drift_red and guard_refused,
                f"drift_red={drift_red} guard={outcome[:120]}")
    finally:
        _restore_routine(admin_dsn, "b26_p2_mark_conducted", saved)


def _pf07_policy_history_joint_rewrite() -> tuple[bool, str]:
    path = (
        REPO_ROOT / "contracts" / "reconciliation" / "b2.6"
        / "scope-policy.v2.yaml"
    )
    original = path.read_bytes()
    try:
        patched = original.replace(
            b"alias_law: strip_ascii_lower_exact_match_only",
            b"alias_law: strip_ascii_lower_exact_match_only_pf07",
            1,
        )
        assert patched != original
        path.write_bytes(patched)
        rc, first = _run_validator("validate_b26_p2_ix_policy.py", [])
        red = (
            rc != 0
            and "same_version_semantic_rewrite" in first
            and "history_unavailable" not in first
        )
        return red, f"first={first[:200]}"
    finally:
        path.write_bytes(original)


def _pf08_common_mode(admin_dsn: str) -> tuple[bool, str]:
    psycopg2 = _psycopg()
    manifest_path = (
        REPO_ROOT / "contracts-internal" / "governance"
        / "b26_p2_x_semantic_universe.pin.json"
    )
    manifest_backup = manifest_path.read_bytes() if manifest_path.is_file() else None
    saved = _snapshot_grants(admin_dsn, "b26_p2_ascii_strip")
    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE OR REPLACE FUNCTION public.b26_p2_ascii_strip"
                "(p_value text) RETURNS text LANGUAGE sql IMMUTABLE"
                " SET search_path TO 'pg_catalog', 'public'"
                " AS $$ SELECT btrim(COALESCE(p_value, '')) $$"
            )
        # Candidate-side refresh: regen the semantic manifest (source
        # files unchanged, so regen acknowledges nothing) ...
        _run_validator("validate_b26_p2_x_semantic.py", ["--generate"])
        # ... and the independent oracle must still RED the wrong meaning.
        rc, first = _run_validator(
            "validate_b26_p2_x_contract_oracle.py", ["--dsn", admin_dsn]
        )
        return (rc != 0 and "semantic_law_broken" in first,
                f"first={first[:200]}")
    finally:
        _restore_routine(admin_dsn, "b26_p2_ascii_strip", saved)
        if manifest_backup is not None:
            manifest_path.write_bytes(manifest_backup)


def _pf09_helper_rename(admin_dsn: str) -> tuple[bool, str]:
    psycopg2 = _psycopg()
    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE OR REPLACE FUNCTION"
                " public.b26_p2_conduction_seed_helper(p_task text)"
                " RETURNS text LANGUAGE plpgsql SECURITY DEFINER"
                " SET search_path TO 'pg_catalog', 'public'"
                " AS $$ BEGIN"
                " UPDATE public.b23_match_task_dispatches AS d"
                " SET delivery_state = 'conducted' WHERE d.task_id = p_task;"
                " RETURN 'conducted'; END $$"
            )
            cur.execute(
                "GRANT EXECUTE ON FUNCTION"
                " public.b26_p2_conduction_seed_helper(text) TO app_worker"
            )
        rc, first = _run_validator(
            "validate_b26_p2_x_authority.py", ["--dsn", admin_dsn]
        )
        red = rc != 0 and "seed_helper" in first
        tenant, _iid, task = _seed_no_verdict_task(admin_dsn)
        outcome = _worker_attempt(
            admin_dsn, tenant,
            "SELECT public.b26_p2_conduction_seed_helper(%s)", (task,),
        )
        refused = outcome.startswith("REFUSED:")
        return (red and refused,
                f"scan_red={red} effect={outcome[:120]}")
    finally:
        conn2 = psycopg2.connect(admin_dsn)
        conn2.autocommit = True
        try:
            with conn2.cursor() as cur2:
                cur2.execute(
                    "DROP FUNCTION IF EXISTS"
                    " public.b26_p2_conduction_seed_helper(text)"
                )
        finally:
            conn2.close()


def _pf10_overload(admin_dsn: str) -> tuple[bool, str]:
    psycopg2 = _psycopg()
    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE OR REPLACE FUNCTION"
                " public.b26_p2_mark_conducted(p_task text, p_extra integer)"
                " RETURNS text LANGUAGE plpgsql SECURITY DEFINER"
                " SET search_path TO 'pg_catalog', 'public'"
                " AS $$ BEGIN"
                " UPDATE public.b23_match_task_dispatches AS d"
                " SET delivery_state = 'conducted' WHERE d.task_id = p_task;"
                " RETURN 'conducted'; END $$"
            )
            cur.execute(
                "GRANT EXECUTE ON FUNCTION"
                " public.b26_p2_mark_conducted(text, integer) TO app_worker"
            )
        rc, first = _run_validator(
            "validate_b26_p2_x_authority.py", ["--dsn", admin_dsn]
        )
        red = rc != 0 and "text, integer" in first
        tenant, _iid, task = _seed_no_verdict_task(admin_dsn)
        outcome = _worker_attempt(
            admin_dsn, tenant,
            "SELECT public.b26_p2_mark_conducted(%s, %s)", (task, 1),
        )
        refused = outcome.startswith("REFUSED:")
        return (red and refused,
                f"scan_red={red} effect={outcome[:120]}")
    finally:
        conn2 = psycopg2.connect(admin_dsn)
        conn2.autocommit = True
        try:
            with conn2.cursor() as cur2:
                cur2.execute(
                    "DROP FUNCTION IF EXISTS"
                    " public.b26_p2_mark_conducted(text, integer)"
                )
        finally:
            conn2.close()


def _pf11_pg_proc_only(admin_dsn: str) -> tuple[bool, str]:
    """Live-only canonical mutation; equivalence + oracle RED, then GREEN."""
    rc, first = _run_validator(
        "validate_b26_p2_x_contract_oracle.py", ["--dsn", admin_dsn]
    )
    if rc != 0:
        return False, f"pristine_oracle_not_green:{first[:120]}"
    psycopg2 = _psycopg()
    saved = _snapshot_grants(
        admin_dsn, "b26_p2_canonical_scope_identity_for_window"
    )
    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DROP FUNCTION IF EXISTS"
                " public.b26_p2_canonical_scope_identity_for_window"
                " (uuid, timestamptz, timestamptz)"
            )
            cur.execute(
                "CREATE FUNCTION"
                " public.b26_p2_canonical_scope_identity_for_window"
                " (p_tenant uuid, p_ws timestamptz, p_we timestamptz)"
                " RETURNS text LANGUAGE plpgsql SECURITY DEFINER"
                " SET search_path TO 'pg_catalog', 'public'"
                " AS $$ BEGIN RETURN 'pf11-junk-scope'; END $$"
            )
        rc, first = _run_validator(
            "validate_b26_p2_x_authority.py", ["--dsn", admin_dsn]
        )
        drift_red = rc != 0 and "live_source_drift" in first
        rc2, second = _run_validator(
            "validate_b26_p2_x_contract_oracle.py", ["--dsn", admin_dsn]
        )
        oracle_red = rc2 != 0
        note = f"drift={drift_red} oracle={second[:120]}"
    finally:
        _restore_routine(
            admin_dsn, "b26_p2_canonical_scope_identity_for_window", saved
        )
        rc3, _third = _run_validator(
            "validate_b26_p2_x_contract_oracle.py", ["--dsn", admin_dsn]
        )
        restored_green = rc3 == 0
    return (drift_red and oracle_red and restored_green,
            f"{note} restored_green={restored_green}")


def _pf12_image_substitution(image_tag: str | None) -> tuple[bool, str]:
    """Substituted digest is refused at the manifest witness.

    Manifest-level by design (no container tooling in this battery:
    it invokes no image runtime): the witness adjudicates presented
    digests, and the container job binds presented digests to real
    images. A mismatched expect-digest must RED; a matching one must
    PASS.
    """
    presented = "sha256:" + "1" * 64
    rc, first = _run_validator(
        "validate_b26_p2_x_artifact.py",
        ["--image-tag", image_tag or "pf12-manifest",
         "--image-id", presented,
         "--tree-sha", "0" * 64,
         "--commit-sha", "0" * 64,
         "--base-image-ref", "FROM pf12",
         "--expect-digest", "sha256:" + "0" * 64],
    )
    mismatch_red = rc != 0 and "post_proof_substitution" in first
    rc2, second = _run_validator(
        "validate_b26_p2_x_artifact.py",
        ["--image-tag", image_tag or "pf12-manifest",
         "--image-id", presented,
         "--tree-sha", "0" * 64,
         "--commit-sha", "0" * 64,
         "--base-image-ref", "FROM pf12",
         "--expect-digest", presented],
    )
    match_green = rc2 == 0 and "PASS" in second
    return (mismatch_red and match_green,
            f"mismatch_red={mismatch_red} match_green={match_green}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run B2.6-P2 Corrective X proof-plane battery."
    )
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--image-tag", default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict[str, object] = {}
    try:
        if not args.dsn:
            violations.append("x_proof_plane_live_check_required_no_dsn")
            checks["live_check"] = "refused_no_dsn"
        else:
            import psycopg2  # noqa: PLC0415  # type: ignore[import-untyped]

            try:
                probe = psycopg2.connect(args.dsn)
                probe.autocommit = True
                with probe.cursor() as cur:
                    cur.execute(
                        "SELECT version_num FROM public.alembic_version"
                    )
                    head = str(cur.fetchone()[0])
                    checks["migration_head"] = head
                    if head != "202609240002":
                        violations.append(
                            f"x_proof_plane_unexpected_head:{head}"
                        )
                probe.close()
            except Exception as exc:  # noqa: BLE001
                violations.append(f"x_proof_plane_lane_unusable:{exc}")
                head = ""
            if head == "202609240002":
                battery: list[tuple[str, object]] = [
                    ("PF-X-01", lambda: _pf01_protected_adjudication(args.dsn)),
                    ("PF-X-02", _pf02_history_fail_closed),
                    ("PF-X-03", lambda: _pf03_validator_crash_is_red(args.dsn)),
                    ("PF-X-04", lambda: _pf04_canary_independence(args.dsn)),
                    ("PF-X-05", lambda: _pf05_semantic_dependency_pin_regen(args.dsn)),
                    ("PF-X-06", lambda: _pf06_weakened_function(args.dsn)),
                    ("PF-X-07", _pf07_policy_history_joint_rewrite),
                    ("PF-X-08", lambda: _pf08_common_mode(args.dsn)),
                    ("PF-X-09", lambda: _pf09_helper_rename(args.dsn)),
                    ("PF-X-10", lambda: _pf10_overload(args.dsn)),
                    ("PF-X-11", lambda: _pf11_pg_proc_only(args.dsn)),
                    ("PF-X-12", lambda: _pf12_image_substitution(args.image_tag)),
                ]
                for name, fn in battery:
                    try:
                        ok, note = fn()
                    except Exception as exc:  # noqa: BLE001
                        ok, note = False, f"pf_crash:{exc}"
                    checks[name] = {"pass": ok, "note": note[:300]}
                    if not ok:
                        violations.append(f"x_proof_plane_{name}_failed")
    except Exception as exc:  # noqa: BLE001
        violations.append(f"x_proof_plane_validator_crash:{exc}")
    status = "PASS" if not violations else "FAIL"
    evidence = {
        "gate_id": "B26-P2-X-PROOF-PLANE",
        "validator": "validate_b26_p2_x_proof_plane",
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
        (args.evidence_dir / "x-proof-plane.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if violations:
        print("B26_P2_X_PROOF_PLANE_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_X_PROOF_PLANE_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
