#!/usr/bin/env python3
"""B2.6-P2 Corrective VIII in-image proof (artifact closure, Gates 25/26).

Builds the exact candidate production image from the candidate tree and
executes the load-bearing VIII proof with the IMAGE's interpreter against
a database the IMAGE migrated:

  1. alembic upgrade head            (migration path in-image)
  2. VIII battery pytest             (adoption/temporal/policy/heartbeat law)
  3. VIII equivalence                (harness mounted read-only; every P2
                                     byte and every gate evaluation comes
                                     from the image)
  4. authority-universe assertion    (meaning-closed denominator in-image)
  5. image-identity self-report      (image file SHAs vs candidate checkout;
                                     a stale image REDs here)
   6. stale falsifier                 (optional --base-sha: build the base
                                      tree image, prove caller-assertion
                                      attestation PROMOTES there while the
                                      candidate refuses without a witness
                                      (restoring only through ingress): the
                                      proof distinguishes the artifacts)

Usage (CI):
  python scripts/ci/prove_b26_p2_in_image.py \
    --image-tag skeldir-b26-p2-viii:$SHA --candidate-sha $SHA \
    [--base-sha $BASE_SHA] [--evidence-out artifacts/.../in-image.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

NETWORK = "b26p2-viii-proof-net"
PG_CONTAINER = "b26p2-viii-proof-pg"
PG_PASSWORD = "viii-proof-pw"
PG_PORT = "15444"
DB_NAME = "skeldir_b26_p2_inimage"

IDENTITY_FILES = [
    "backend/app/finance_reconciliation/scope_authority.py",
    "backend/app/finance_reconciliation/candidate_conduction.py",
    "backend/app/ingestion/event_service.py",
    "backend/app/finance_reconciliation/conduction_state.py",
    "backend/app/tasks/b26_p2_health.py",
    "backend/app/core/construction_authority.py",
    "contracts/reconciliation/b2.6/scope-policy.v2.yaml",
    "alembic/versions/007_skeldir_foundation/202609220001_b26_p2_corrective_viii_context_robust.py",
    "alembic/versions/007_skeldir_foundation/202609230001_b26_p2_corrective_ix_consequence_authority.py",
    "alembic/versions/007_skeldir_foundation/202609240001_b26_p2_corrective_x_assurance_sovereignty.py",
    "alembic/versions/007_skeldir_foundation/202609240002_b26_p2_corrective_xi_p2_core_closure.py",
    "alembic/versions/007_skeldir_foundation/202609250001_b26_p2_corrective_xii_fact_anchored_closure.py",
]

# Corrective XII stale falsifier probe (attestation delta): the base
# (pre-XII) tree promotes unknown_legacy -> authenticated_known on a bare
# caller assertion through the app_user attester (XI) or mints a witness
# without a provider consequence (XI ingress-only mint); the candidate
# (XII) tree refuses the same assertion (no EXECUTE / witness_missing /
# no_auth_consequence / governed_admin_only) and restores authority only
# through the provider-bound chain (consequence via app_user, bound
# witness + signed attestation via ingress). MODE=base expects
# XI_BASE_ATTESTED; MODE=candidate expects XI_CAND_DENIED then
# XI_CAND_RESTORED. A base that refuses (already strict) or a candidate
# that promotes (still assertable) fails the falsifier as vacuous.
PROBE_XI_ATTEST_DELTA = '''
import os
import sys
import uuid
import psycopg2
DAY_NOON = __import__("datetime").datetime(2026, 1, 15, 12, 0, tzinfo=__import__("datetime").timezone.utc)
mode = os.environ.get("PROBE_MODE", "candidate")
admin = psycopg2.connect(os.environ["PROBE_ADMIN_DSN"])
admin.autocommit = True
ac = admin.cursor()
t = str(uuid.uuid4())
tag = uuid.uuid4().hex[:8]
ac.execute("INSERT INTO public.tenants (id, name, api_key_hash, notification_email) VALUES (%s, %s, %s, %s)", (t, "attdelta-" + tag, uuid.uuid4().hex, tag + "@x.invalid"))
ac.execute("SELECT set_config('app.current_tenant_id', %s, false)", (t,))
ac.execute("INSERT INTO public.channel_taxonomy (code, family, is_paid, display_name, state) VALUES ('attdelta_ch', 'attdelta', true, 'ATTDELTA', 'active') ON CONFLICT (code) DO NOTHING")
e = str(uuid.uuid4())
ing = str(uuid.uuid4())
idem = "attdelta:" + tag
ac.execute("INSERT INTO public.attribution_events (id, tenant_id, occurred_at, correlation_id, session_id, revenue_cents, raw_payload, idempotency_key, event_type, channel, campaign_id, conversion_value_cents, currency, event_timestamp, processed_at, processing_status) VALUES (%s, %s, %s, %s, %s, 38000, '{}'::jsonb, %s, 'conversion', 'attdelta_ch', 'c', 38000, 'USD', %s, %s, 'processed')", (e, t, DAY_NOON, str(uuid.uuid4()), str(uuid.uuid4()), idem, DAY_NOON, DAY_NOON))
ac.execute("INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id, provider, provider_native_event_reference, provider_native_commerce_reference, normalized_commerce_reference_kind, normalized_commerce_reference_value, verified_amount_minor, verified_amount_currency, event_timestamp, idempotency_key, verified_commerce_ingress_state) VALUES (%s, %s, %s, 'stripe', %s, %s, 'order_reference', %s, 38000, 'USD', %s, %s, 'authenticity_verified')", (ing, t, e, "evt-" + tag, "ord-" + tag, "ord-" + tag, DAY_NOON, idem))
ac.execute("ALTER TABLE public.webhook_ingress_identities DISABLE TRIGGER trg_b26_p2_ingress_provenance")
ac.execute("UPDATE public.webhook_ingress_identities SET b26_p2_provenance_status = 'unknown_legacy' WHERE id = %s", (ing,))
ac.execute("ALTER TABLE public.webhook_ingress_identities ENABLE TRIGGER trg_b26_p2_ingress_provenance")
user = psycopg2.connect(os.environ["PROBE_USER_DSN"])
user.autocommit = True
uc = user.cursor()
uc.execute("SELECT set_config('app.current_tenant_id', %s, false)", (t,))
try:
    uc.execute("SELECT public.b26_p2_attest_provenance_evidence(%s, 'governed_attestation', %s)", (ing, idem))
    outcome = str(uc.fetchone()[0])
except Exception as exc:
    outcome = "REFUSED:" + str(exc).split("\\n")[0][:120]
user.close()
ingress0 = psycopg2.connect(os.environ["PROBE_INGRESS_DSN"])
ingress0.autocommit = True
ic0 = ingress0.cursor()
ic0.execute("SELECT set_config('app.current_tenant_id', %s, false)", (t,))
try:
    ic0.execute("SELECT public.b26_p2_record_ingress_auth_witness(%s)", (ing,))
    mint_outcome = str(ic0.fetchone()[0])
except Exception as exc:
    mint_outcome = "REFUSED:" + str(exc).split("\\n")[0][:120]
ingress0.close()
if mode == "base":
    if outcome == "authenticated_known" or (mint_outcome and not mint_outcome.startswith("REFUSED")):
        print("XI_BASE_ATTESTED")
    else:
        print("XI_BASE_VACUOUS:" + outcome + "|" + mint_outcome)
        raise SystemExit(0)
else:
    if outcome == "authenticated_known":
        print("XI_CAND_PROMOTED_BY_ASSERTION")
        raise SystemExit(1)
    if not mint_outcome.startswith("REFUSED"):
        print("XI_CAND_MINTED_WITHOUT_CONSEQUENCE")
        raise SystemExit(1)
    print("XI_CAND_DENIED:" + outcome + "|" + mint_outcome)
    user2 = psycopg2.connect(os.environ["PROBE_USER_DSN"])
    user2.autocommit = True
    uc2 = user2.cursor()
    uc2.execute("SELECT set_config('app.current_tenant_id', %s, false)", (t,))
    uc2.execute("SELECT public.b26_p2_record_provider_auth_consequence(%s, 'stripe', %s, %s, %s, 'hmac-sha256-timestamped-hex', 'v1')", (ing, "evt-" + tag, "c" * 64, "d" * 64))
    user2.close()
    ingress = psycopg2.connect(os.environ["PROBE_INGRESS_DSN"])
    ingress.autocommit = True
    ic = ingress.cursor()
    ic.execute("SELECT set_config('app.current_tenant_id', %s, false)", (t,))
    ic.execute("SELECT public.b26_p2_record_ingress_auth_witness(%s, 'stripe', %s, %s)", (ing, "evt-" + tag, "c" * 64))
    ic.execute("SELECT public.b26_p2_attest_provenance_evidence(%s, 'signed_provider_reingestion', %s)", (ing, idem))
    restored = str(ic.fetchone()[0])
    ingress.close()
    if restored == "authenticated_known":
        print("XI_CAND_RESTORED")
    else:
        print("XI_CAND_RESTORE_FAILED:" + restored)
        raise SystemExit(1)
admin.close()
'''

PROBE_X_TAB_CONDUCTION = '''
import asyncio
import os
import sys
import uuid
import psycopg2
from datetime import datetime, timezone
DAY_START = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)
DAY_END = datetime(2026, 1, 16, 0, 0, tzinfo=timezone.utc)
DAY_NOON = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
POLICY_SHA = "fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99"
TAB = chr(9)
RAW_PROVIDER = TAB + "stripe"
admin = psycopg2.connect(os.environ["PROBE_ADMIN_DSN"])
admin.autocommit = True
ac = admin.cursor()
t = str(uuid.uuid4())
tag = uuid.uuid4().hex[:8]
ac.execute("INSERT INTO public.tenants (id, name, api_key_hash, notification_email) VALUES (%s, %s, %s, %s)", (t, "probe-" + tag, uuid.uuid4().hex, tag + "@x.invalid"))
ac.execute("SELECT set_config('app.current_tenant_id', %s, false)", (t,))
ac.execute("INSERT INTO public.channel_taxonomy (code, family, is_paid, display_name, state) VALUES ('probe_ch', 'p', true, 'P', 'active') ON CONFLICT (code) DO NOTHING")
e = str(uuid.uuid4())
ing = str(uuid.uuid4())
ac.execute("INSERT INTO public.attribution_events (id, tenant_id, occurred_at, correlation_id, session_id, revenue_cents, raw_payload, idempotency_key, event_type, channel, campaign_id, conversion_value_cents, currency, event_timestamp, processed_at, processing_status) VALUES (%s, %s, %s, %s, %s, 38000, '{}'::jsonb, %s, 'conversion', 'probe_ch', 'c', 38000, 'USD', %s, %s, 'processed')", (e, t, DAY_NOON, str(uuid.uuid4()), str(uuid.uuid4()), "probe:" + tag, DAY_NOON, DAY_NOON))
ac.execute("INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id, provider, provider_native_event_reference, provider_native_commerce_reference, normalized_commerce_reference_kind, normalized_commerce_reference_value, verified_amount_minor, verified_amount_currency, event_timestamp, idempotency_key, verified_commerce_ingress_state) VALUES (%s, %s, %s, %s, %s, %s, 'order_reference', %s, 38000, 'USD', %s, %s, 'authenticity_verified')", (ing, t, e, RAW_PROVIDER, "evt-" + tag, "ord-" + tag, "ord-" + tag, DAY_NOON, "probe:" + tag))
task = "probe-tab-" + tag
ac.execute("INSERT INTO public.b23_match_task_dispatches (tenant_id, webhook_ingress_identity_id, task_id, task_name, queue, routing_key, correlation_id, provider, provider_native_event_reference, provider_native_commerce_reference, normalized_commerce_reference_value, status, delivery_state, publish_attempts, window_start, window_end) VALUES (%s, %s, %s, 'app.tasks.revenue_verification.execute_b23_batch_match_engine', 'b23_match_engine', 'b23_match_engine.task', %s, %s, 'evt', 'ord', 'ord', 'dispatched', 'pending_publish', 0, %s, %s)", (t, ing, task, str(uuid.uuid4()), RAW_PROVIDER, DAY_START, DAY_END))
ac.execute("INSERT INTO public.b26_p2_execution_outbox (tenant_id, dispatch_task_id, webhook_ingress_identity_id) VALUES (%s, %s, %s)", (t, task, ing))
ac.execute("INSERT INTO public.b26_p2_task_authority_directory (task_id, tenant_id, webhook_ingress_identity_id, window_start, window_end) VALUES (%s, %s, %s, %s, %s)", (task, t, ing, DAY_START, DAY_END))
ac.execute("UPDATE public.b23_match_task_dispatches SET delivery_state='published', first_published_at=now() WHERE task_id=%s", (task,))
ac.execute("UPDATE public.b26_p2_execution_outbox SET state='published' WHERE dispatch_task_id=%s", (task,))
ac.execute("INSERT INTO public.b23_match_verdicts (tenant_id, attribution_event_id, webhook_ingress_identity_id, provider, canonical_commerce_reference, provider_native_event_reference, provider_native_commerce_reference, status, match_quality, attributed_amount_minor, verified_amount_minor, currency_code, canonical_expected_gross_amount_minor, canonical_captured_gross_amount_minor, canonical_net_verified_amount_minor, discrepancy_amount_minor, discrepancy_ratio_bps, discrepancy_band) VALUES (%s, %s, %s, 'stripe', 'ord', 'evt', 'ord', 'matched_confirmed', 'high', 38000, 38000, 'USD', 38000, 38000, 38000, 0, 0, 'exact')", (t, e, ing))
admin.close()
sys.path.insert(0, "/app/backend")
from app.finance_reconciliation.tenant_authority import open_governed_b23_snapshot_session
from app.finance_reconciliation.candidate_conduction import derive_governed_scope
async def _derive():
    async with open_governed_b23_snapshot_session(t) as session:
        return await derive_governed_scope(session, tenant_id=t, window_start=DAY_START, window_end=DAY_END)
try:
    scope = asyncio.run(_derive())
except Exception as exc:
    print("X_TAB_DERIVE_REFUSED:" + str(exc).splitlines()[0][:120])
    raise SystemExit(0)
print("X_TAB_DISPOSITION:" + scope.candidates[0].classification.disposition)
w = psycopg2.connect(os.environ["PROBE_WORKER_DSN"])
w.autocommit = True
wc = w.cursor()
try:
    wc.execute("SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)", (task, scope.scope_identity, 1, POLICY_SHA))
    wc.execute("SELECT public.b26_p2_mark_conducted(%s)", (task,))
    print("X_TAB_" + str(wc.fetchone()[0]).upper())
except Exception as exc:
    print("X_TAB_REFUSED:" + str(exc).splitlines()[0][:120])
'''



def _docker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True)


def _fail(details: dict, message: str) -> int:
    details["status"] = "FAIL"
    details["failure"] = message
    print(f"B26_P2_IN_IMAGE_FAIL {message}")
    return 1


def _base_migration_head(worktree) -> str | None:
    """Resolve the single migration head of the base worktree.

    Asks the base tree's own Alembic (host interpreter, base working
    copy) rather than re-parsing revision graphs by hand: merges with
    tuple down_revisions and multi-branch layouts resolve exactly as
    the migrator sees them. The stale lane must run base-head physics.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "alembic", "heads"],
            cwd=str(worktree), capture_output=True, text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    heads = []
    for line in proc.stdout.splitlines():
        match = re.match(r"^([0-9a-f]+)\b", line.strip())
        if match:
            heads.append(match.group(1))
    if len(heads) != 1:
        return None
    return heads[0]


_AM8_BODY_FN = "b24_mark_fit_dispatch_running"


def _am8_cycle(image: str, harness: str, out_mount: str,
               covered: list[str], host_admin_dsn: str) -> dict:
    """Mutate known-authority meaning in-image; universe must RED then GREEN.

    Mutations execute against the proof database over the host-reachable
    admin DSN (same cluster the image migrated); the universe assertion
    itself executes inside the image. Unknown-meaning fails closed.
    """
    import psycopg2

    result: dict = {"mutations": []}
    admin = psycopg2.connect(host_admin_dsn)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname=%s"
                        " AND pronamespace='public'::regnamespace", (_AM8_BODY_FN,))
            original_body = cur.fetchone()[0]
    finally:
        admin.close()

    def universe() -> tuple[int, str, str]:
        cmd = ["run", "--rm", "--network", NETWORK, "-v", harness, "-v", out_mount,
               "-e", "PYTHONPATH=/proof:/app/backend",
               image, "python", "/proof/assert_b26_p2_authority_universe.py",
               "--dsn", f"postgresql://postgres:{PG_PASSWORD}@pg:5432/{DB_NAME}",
                "--pin", "/app/contracts-internal/governance/b26_p2_authority_universe.pin.json",
                "--migration-head", "202609240002",
                "--covered"] + covered
        proc = _docker(*cmd)
        full = proc.stdout + proc.stderr
        # The drift marker lives at the head of the output, ahead of the
        # JSON details; match against the FULL output (a tail window would
        # be at the mercy of JSON length).
        return proc.returncode, full, full[-600:]

    def sql(statement: str) -> None:
        conn = psycopg2.connect(host_admin_dsn)
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute(statement)
        finally:
            conn.close()

    mutations = [
        ("AM8-01/body", "body mutation of allowlisted definer",
         original_body.replace("BEGIN", "BEGIN\n-- am8 probe", 1),
         "authority_universe_drift"),
        ("AM8-03/overload", "same-name overload with new signature",
         "CREATE OR REPLACE FUNCTION public.%s(t text, n integer) RETURNS text"
         " LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'pg_catalog','public'"
         " AS $$ BEGIN RETURN 'am8'; END $$;" % _AM8_BODY_FN
         + "GRANT EXECUTE ON FUNCTION public.%s(text, integer) TO app_worker;" % _AM8_BODY_FN,
         "authority_universe_drift"),
        ("AM8-05/trigger", "trigger-mediated writer behind lawful write",
         "CREATE OR REPLACE FUNCTION public.am8_trigger_writer() RETURNS trigger"
         " LANGUAGE plpgsql SET search_path TO 'pg_catalog','public'"
         " AS $$ BEGIN RETURN NEW; END $$;"
         " CREATE TRIGGER am8_probe_trigger BEFORE UPDATE ON"
         " public.webhook_ingress_identities FOR EACH ROW EXECUTE FUNCTION"
         " public.am8_trigger_writer();",
         "authority_universe_drift"),
        ("AM8-08/schema-create", "schema CREATE granted to runtime",
         "GRANT CREATE ON SCHEMA public TO app_worker;",
         "authority_universe_drift"),
    ]
    try:
        for name, _desc, statement, expect in mutations:
            sql(statement)
            code, full, tail = universe()
            ok = code != 0 and expect in full
            result["mutations"].append({"name": name, "red": ok})
            if not ok:
                result["status"] = "FAIL"
                result["failure"] = f"{name}_did_not_red:{tail[-200:]}"
                return result
        # Exact restore GREEN.
        sql("DROP TRIGGER IF EXISTS am8_probe_trigger"
            " ON public.webhook_ingress_identities;")
        sql("DROP FUNCTION IF EXISTS public.am8_trigger_writer();")
        sql("DROP FUNCTION IF EXISTS public.%s(text, integer);" % _AM8_BODY_FN)
        sql("REVOKE CREATE ON SCHEMA public FROM app_worker;")
        admin2 = psycopg2.connect(host_admin_dsn)
        admin2.autocommit = True
        try:
            with admin2.cursor() as cur:
                cur.execute(original_body)
        finally:
            admin2.close()
        code, full, tail = universe()
        # Restore check compares the pinned hash AND requires the known
        # overload/trigger/probe objects to be gone (hash equality proves it).
        if code != 0:
            result["status"] = "FAIL"
            result["failure"] = f"am8_restore_not_green:{tail[-200:]}"
            return result
        result["status"] = "PASS"
        return result
    except Exception as exc:  # noqa: BLE001
        result["status"] = "FAIL"
        result["failure"] = f"am8_cycle_crash:{exc}"
        try:
            sql("DROP TRIGGER IF EXISTS am8_probe_trigger"
                " ON public.webhook_ingress_identities;")
            sql("DROP FUNCTION IF EXISTS public.am8_trigger_writer();")
            sql("DROP FUNCTION IF EXISTS public.%s(text, integer);" % _AM8_BODY_FN)
            sql("REVOKE CREATE ON SCHEMA public FROM app_worker;")
        except Exception:  # noqa: BLE001
            pass
        return result


def _host_sha(rel: str) -> str:
    return hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-tag", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--base-sha", default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    details: dict = {
        "producer": "b26-p2-in-image-proof",
        # Declared gate identity for the proof-plane capsule census. The
        # B2.6-P2 adjudicator loads every JSON under the evidence root and
        # rejects gateless documents; this cell is additive (no required
        # census entry collides with it) and is skipped by required-cell
        # adjudication — merge gating for this job flows through the
        # aggregate `needs` dependency, not the capsule.
        "gate_id": "B26-P2-IN-IMAGE-PROOF",
        "candidate_sha": args.candidate_sha,
        "image_tag": args.image_tag,
    }

    def run_img(image: str, inner: list[str], env: dict | None = None,
                mounts: list[str] | None = None,
                workdir: str | None = None) -> subprocess.CompletedProcess:
        cmd = ["run", "--rm", "--network", NETWORK]
        if workdir:
            cmd += ["-w", workdir]
        for m in mounts or []:
            cmd += ["-v", m]
        base_env = {
            "MIGRATION_DATABASE_URL":
                f"postgresql://migration_owner:migration_owner@pg:5432/{DB_NAME}",
            "DATABASE_URL":
                f"postgresql://app_user:app_user@pg:5432/{DB_NAME}",
        }
        if env:
            base_env.update(env)
        for k, v in base_env.items():
            cmd += ["-e", f"{k}={v}"]
        cmd += [image] + inner
        return _docker(*cmd)

    try:
        if not args.no_build:
            proc = _docker("build", "-f", "backend/Dockerfile", "-t", args.image_tag, ".")
            if proc.returncode != 0:
                return _fail(details, f"image_build_failed:{proc.stderr[-1500:]}")
        proc = _docker("image", "inspect", args.image_tag, "--format", "{{.Id}}")
        if proc.returncode != 0:
            return _fail(details, "image_missing")
        details["image_digest"] = proc.stdout.strip()
        print(f"image_digest={details['image_digest']}", flush=True)

        _docker("rm", "-f", PG_CONTAINER)
        _docker("network", "rm", NETWORK)
        _docker("network", "create", NETWORK)
        proc = _docker(
            "run", "-d", "--name", PG_CONTAINER, "--network", NETWORK,
            "--network-alias", "pg", "-e", f"POSTGRES_PASSWORD={PG_PASSWORD}",
            "-p", f"{PG_PORT}:5432", "postgres:15-alpine",
        )
        if proc.returncode != 0:
            return _fail(details, f"pg_start_failed:{proc.stderr[-500:]}")
        deadline = time.time() + 90
        while time.time() < deadline:
            if _docker("exec", PG_CONTAINER, "pg_isready", "-U", "postgres").returncode == 0:
                break
            time.sleep(2)
        else:
            return _fail(details, "pg_not_ready")

        import psycopg2

        admin_dsn = f"postgresql://postgres:{PG_PASSWORD}@127.0.0.1:{PG_PORT}/postgres"
        conn = psycopg2.connect(admin_dsn)
        conn.autocommit = True
        try:
            cur = conn.cursor()
            cur.execute(f'DROP DATABASE IF EXISTS "{DB_NAME}"')
            cur.execute(f'CREATE DATABASE "{DB_NAME}"')
        finally:
            conn.close()
        proc = subprocess.run(
            [sys.executable, "scripts/database/prepare_migration_authority_boundary.py",
             "--admin-dsn", admin_dsn, "--database-name", DB_NAME],
            cwd=str(REPO_ROOT), capture_output=True, text=True,
        )
        if proc.returncode != 0:
            return _fail(details, f"provision_failed:{proc.stderr[-1000:]}")

        # 1. Migration path inside the candidate image (from /app: the
        # ini's relative script_location and sys-path prelude resolve
        # there; the image WORKDIR is /app/backend).
        proc = run_img(args.image_tag, ["alembic", "upgrade", "head"],
                       workdir="/app")
        if proc.returncode != 0:
            return _fail(details, f"in_image_migrate_failed:{proc.stderr[-1500:]}")
        details["in_image_migrate"] = "PASS"

        # 2. VIII + IX batteries with the image's interpreter. The
        # production image deliberately excludes backend/tests (TCB
        # hygiene); the battery files are mounted read-only at their
        # canonical paths. The mount adds only test harness bytes (no
        # image path is shadowed); every app byte under test resolves
        # inside the image. The OB8 wiring cells read deployment
        # artifacts (compose/monitoring) that likewise ship outside the
        # image; they are mounted read-only for the same reason. The IX
        # battery proves the candidate refuses invented scope digests on
        # these exact bytes (the counterpart of the stale falsifier).
        tests_mounts = [
            f"{REPO_ROOT / 'backend' / 'tests'}:/app/backend/tests:ro",
            f"{REPO_ROOT / 'monitoring'}:/app/monitoring:ro",
            f"{REPO_ROOT / 'scripts' / 'ops'}:/app/scripts/ops:ro",
        ]
        proc = run_img(
            args.image_tag,
            ["python", "-m", "pytest",
             "tests/finance_reconciliation/test_b26_p2_corrective_viii_context_robust.py",
             "tests/finance_reconciliation/test_b26_p2_corrective_ix_consequence.py",
             "-q", "-o", "asyncio_mode=auto", "-p", "no:cacheprovider"],
            env={"DATABASE_URL":
                 f"postgresql+asyncpg://app_user:app_user@pg:5432/{DB_NAME}",
                 "B26_P2_SUPERUSER_DSN":
                 f"postgresql://postgres:{PG_PASSWORD}@pg:5432/{DB_NAME}"},
            mounts=tests_mounts,
        )
        details["in_image_battery_tail"] = (proc.stdout + proc.stderr)[-2000:]
        if proc.returncode != 0 or "passed" not in proc.stdout:
            return _fail(details, "in_image_battery_fail")
        details["in_image_battery"] = "PASS"

        # 3. Image-identity self-report: the image hashes its own bytes;
        # the job compares against the candidate checkout. A stale image
        # REDs here before any behavioral proof runs.
        proc = run_img(
            args.image_tag,
            ["python", "-c",
             "import hashlib,json;"
             "files=%s;"
             "print(json.dumps({f:hashlib.sha256(open('/app/'+f,'rb').read()).hexdigest() for f in files}))"
             % json.dumps(IDENTITY_FILES)],
        )
        if proc.returncode != 0:
            return _fail(details, "identity_self_report_failed")
        image_files = json.loads(proc.stdout.strip().splitlines()[-1])
        mismatched = [f for f in IDENTITY_FILES if image_files.get(f) != _host_sha(f)]
        details["identity_mismatches"] = mismatched
        if mismatched:
            return _fail(details, f"image_identity_mismatch:{mismatched}")
        details["image_identity"] = "PASS"

        harness = f"{REPO_ROOT / 'scripts' / 'ci'}:/proof:ro"
        outdir = REPO_ROOT / "artifacts" / "b26_p2" / "in-image"
        outdir.mkdir(parents=True, exist_ok=True)
        out_mount = f"{outdir}:/out"
        mig_dsn = ("postgresql://migration_owner:migration_owner"
                   f"@pg:5432/{DB_NAME}")

        # 4. VIII equivalence with image bytes (harness mounted read-only;
        # every P2 byte and gate evaluation resolves inside the image).
        harness_env = {"PYTHONPATH": "/proof:/app/backend"}
        proc = run_img(
            args.image_tag,
            ["python", "/proof/b26_p2_viii_equivalence.py", "--dsn", mig_dsn,
             "--evidence-out", "/out/viii-equivalence.json"],
            mounts=[harness, out_mount],
            env=harness_env,
        )
        details["equivalence_tail"] = (proc.stdout + proc.stderr)[-1500:]
        if proc.returncode != 0 or "B26_P2_VIII_EQUIVALENCE_PASS" not in proc.stdout:
            return _fail(details, "in_image_equivalence_fail")
        details["in_image_equivalence"] = "PASS"

        # 5. Authority-universe assertion with image bytes.
        import importlib.util as _ilu

        xii_spec = _ilu.spec_from_file_location(
            "b26_p2_xii_coverage",
            str(REPO_ROOT / "scripts" / "ci" / "b26_p2_xii_coverage.py"))
        if xii_spec is not None and xii_spec.loader is not None:
            coverage_mod = _ilu.module_from_spec(xii_spec)
            sys.modules["b26_p2_xii_coverage"] = coverage_mod
            xii_spec.loader.exec_module(coverage_mod)
            covered = sorted(coverage_mod.XII_COVERED_SURFACES)
        else:
            xi_spec = _ilu.spec_from_file_location(
                "b26_p2_xi_coverage",
                str(REPO_ROOT / "scripts" / "ci" / "b26_p2_xi_coverage.py"))
            if xi_spec is not None and xi_spec.loader is not None:
                coverage_mod = _ilu.module_from_spec(xi_spec)
                sys.modules["b26_p2_xi_coverage"] = coverage_mod
                xi_spec.loader.exec_module(coverage_mod)
                covered = sorted(coverage_mod.XI_COVERED_SURFACES)
            else:
                x_spec = _ilu.spec_from_file_location(
                    "b26_p2_x_coverage",
                    str(REPO_ROOT / "scripts" / "ci" / "b26_p2_x_coverage.py"))
                if x_spec is not None and x_spec.loader is not None:
                    coverage_mod = _ilu.module_from_spec(x_spec)
                    sys.modules["b26_p2_x_coverage"] = coverage_mod
                    x_spec.loader.exec_module(coverage_mod)
                    covered = sorted(coverage_mod.X_COVERED_SURFACES)
                else:
                    ix_spec = _ilu.spec_from_file_location(
                        "b26_p2_ix_coverage",
                        str(REPO_ROOT / "scripts" / "ci" / "b26_p2_ix_coverage.py"))
                    if ix_spec is not None and ix_spec.loader is not None:
                        coverage_mod = _ilu.module_from_spec(ix_spec)
                        sys.modules["b26_p2_ix_coverage"] = coverage_mod
                        ix_spec.loader.exec_module(coverage_mod)
                        covered = sorted(coverage_mod.IX_COVERED_SURFACES)
                    else:
                        spec = _ilu.spec_from_file_location(
                            "b26_p2_viii_coverage",
                            str(REPO_ROOT / "scripts" / "ci" / "b26_p2_viii_coverage.py"))
                        assert spec is not None and spec.loader is not None
                        coverage_mod = _ilu.module_from_spec(spec)
                        sys.modules["b26_p2_viii_coverage"] = coverage_mod
                    spec.loader.exec_module(coverage_mod)
                    covered = sorted(coverage_mod.VIII_COVERED_SURFACES)
        proc = run_img(
            args.image_tag,
            ["python", "/proof/assert_b26_p2_authority_universe.py", "--dsn",
             f"postgresql://postgres:{PG_PASSWORD}@pg:5432/{DB_NAME}",
              "--pin", "/app/contracts-internal/governance/b26_p2_authority_universe.pin.json",
               "--migration-head", "202609250001",
               "--evidence-out", "/out/authority-universe.json",
             "--covered"] + covered,
            mounts=[harness, out_mount],
            env=harness_env,
        )
        details["universe_tail"] = (proc.stdout + proc.stderr)[-800:]
        if proc.returncode != 0 or "B26_P2_AUTHORITY_UNIVERSE_PASS" not in proc.stdout:
            return _fail(details, "in_image_universe_fail")
        details["in_image_universe"] = "PASS"

        # 5b. AM8 meaning-drift cycle (authority meaning, not names): each
        # mutation must RED the universe assertion for the predicted cause;
        # exact restore must return GREEN. Unknown-meaning fails closed.
        am8 = _am8_cycle(args.image_tag, harness, out_mount, covered,
                         f"postgresql://postgres:{PG_PASSWORD}@127.0.0.1:{PG_PORT}/{DB_NAME}")
        details["am8_cycle"] = am8
        if am8.get("status") != "PASS":
            return _fail(details, f"am8_cycle_fail:{am8.get('failure')}")

        # 6. Stale falsifier: base-tree image must ACCEPT the invented
        # scope digest the candidate refuses (the proof distinguishes the
        # artifacts on the IX consequence-authority delta).
        if args.base_sha:
            base_tag = f"{args.image_tag}-base"
            worktree = REPO_ROOT / ".viii-base-tree"
            subprocess.run(["git", "worktree", "remove", "--force", str(worktree)],
                           cwd=str(REPO_ROOT), capture_output=True)
            # The CI checkout pins the candidate commit only; the base
            # object must be fetched before the worktree can materialize
            # it. Fail closed when the base is unreachable: a skipped
            # stale falsifier would silently weaken artifact closure.
            fetch = subprocess.run(
                ["git", "fetch", "origin", args.base_sha, "--depth", "1"],
                cwd=str(REPO_ROOT), capture_output=True, text=True)
            if fetch.returncode != 0:
                return _fail(details, f"base_fetch_failed:{fetch.stderr[-500:]}")
            proc = subprocess.run(
                ["git", "worktree", "add", "--detach", str(worktree), args.base_sha],
                cwd=str(REPO_ROOT), capture_output=True, text=True)
            if proc.returncode != 0:
                return _fail(details, f"base_worktree_failed:{proc.stderr[-500:]}")
            try:
                proc = _docker("build", "-f", str(worktree / "backend" / "Dockerfile"),
                               "-t", base_tag, str(worktree))
                if proc.returncode != 0:
                    return _fail(details, f"base_build_failed:{proc.stderr[-800:]}")
                stale_db = f"{DB_NAME}_stale"
                conn = psycopg2.connect(admin_dsn)
                conn.autocommit = True
                try:
                    cur = conn.cursor()
                    cur.execute(f'DROP DATABASE IF EXISTS "{stale_db}"')
                    cur.execute(f'CREATE DATABASE "{stale_db}"')
                finally:
                    conn.close()
                subprocess.run(
                    [sys.executable,
                     "scripts/database/prepare_migration_authority_boundary.py",
                     "--admin-dsn", admin_dsn, "--database-name", stale_db],
                    cwd=str(REPO_ROOT), capture_output=True)
                stale_env = {
                    "MIGRATION_DATABASE_URL":
                        f"postgresql://migration_owner:migration_owner@pg:5432/{stale_db}",
                    "DATABASE_URL":
                        f"postgresql://app_user:app_user@pg:5432/{stale_db}",
                    "B23_WORKER_DATABASE_URL":
                        f"postgresql+asyncpg://app_worker:app_worker@pg:5432/{stale_db}",
                }
                # The stale lane migrates with the HOST candidate
                # alembic (pinned dependencies), not the base image's
                # alembic: base-tree images predate dependency pins and
                # their in-image migrate is an environment lottery.
                # Migrating the stale lane to the BASE head with
                # candidate bytes is faithful (linear history: the base
                # head is an ancestor of the candidate head); the probe
                # itself still executes inside the base image.
                base_head = _base_migration_head(worktree)
                if base_head is None:
                    return _fail(details, "stale_base_head_unresolvable")
                proc = subprocess.run(
                    [sys.executable, "-m", "alembic", "upgrade", base_head],
                    cwd=str(REPO_ROOT), capture_output=True, text=True,
                    env={**os.environ,
                         "MIGRATION_DATABASE_URL":
                             f"postgresql://migration_owner:migration_owner"
                             f"@127.0.0.1:{PG_PORT}/{stale_db}",
                         "DATABASE_URL":
                             f"postgresql://migration_owner:migration_owner"
                             f"@127.0.0.1:{PG_PORT}/{stale_db}"},
                )
                if proc.returncode != 0:
                    return _fail(details, "stale_migrate_failed:"
                                 + (proc.stdout + proc.stderr)[-800:])
                # XI attestation delta: the base (pre-XI) tree promotes
                # by caller assertion through the app_user attester;
                # the candidate must refuse the same assertion. (The X
                # tab-strand expectation is obsolete: X already conducts
                # TAB under one SQL law, so both trees conduct it.)
                probe = PROBE_XI_ATTEST_DELTA
                cmd = ["run", "--rm", "--network", NETWORK]
                for k, v in stale_env.items():
                    cmd += ["-e", f"{k}={v}"]
                cmd += [
                    "-e", "PROBE_MODE=base",
                    "-e",
                    "PROBE_ADMIN_DSN=postgresql://postgres:%s@pg:5432/%s"
                    % (PG_PASSWORD, stale_db),
                    "-e",
                    "PROBE_USER_DSN=postgresql://app_user:app_user@pg:5432/%s"
                    % stale_db,
                    "-e",
                    "PROBE_INGRESS_DSN=postgresql://app_ingress:app_ingress@pg:5432/%s"
                    % stale_db,
                    "-e",
                    "PROBE_WORKER_DSN=postgresql://app_worker:app_worker@pg:5432/%s"
                    % stale_db,
                    base_tag, "python", "-c", probe,
                ]
                proc = _docker(*cmd)
                base_out = proc.stdout + proc.stderr
                if "XI_BASE_ATTESTED" not in proc.stdout:
                    return _fail(
                        details,
                        "stale_falsifier_vacuous:base_did_not_promote:"
                        + base_out[-500:])
                details["stale_falsifier_base"] = "PASS_promoted_as_required"
                # The candidate image must conduct the same lawful task:
                # its thin adapter observes the SQL meaning, so receipt
                # and gate agree and the terminal conducts.
                xdelta_db = f"{DB_NAME}_xdelta"
                conn = psycopg2.connect(admin_dsn)
                conn.autocommit = True
                try:
                    cur = conn.cursor()
                    cur.execute(f'DROP DATABASE IF EXISTS "{xdelta_db}"')
                    cur.execute(f'CREATE DATABASE "{xdelta_db}"')
                finally:
                    conn.close()
                subprocess.run(
                    [sys.executable,
                     "scripts/database/prepare_migration_authority_boundary.py",
                     "--admin-dsn", admin_dsn, "--database-name", xdelta_db],
                    cwd=str(REPO_ROOT), capture_output=True)
                xdelta_env = {
                    "MIGRATION_DATABASE_URL":
                        f"postgresql://migration_owner:migration_owner@pg:5432/{xdelta_db}",
                    "DATABASE_URL":
                        f"postgresql://app_user:app_user@pg:5432/{xdelta_db}",
                    "B23_WORKER_DATABASE_URL":
                        f"postgresql+asyncpg://app_worker:app_worker@pg:5432/{xdelta_db}",
                }
                cmd = ["run", "--rm", "--network", NETWORK, "-w", "/app"]
                for k, v in xdelta_env.items():
                    cmd += ["-e", f"{k}={v}"]
                cmd += [args.image_tag, "alembic", "upgrade", "head"]
                proc = _docker(*cmd)
                if proc.returncode != 0:
                    return _fail(details, "xdelta_migrate_failed:"
                                 + (proc.stdout + proc.stderr)[-800:])
                cmd = ["run", "--rm", "--network", NETWORK]
                for k, v in xdelta_env.items():
                    cmd += ["-e", f"{k}={v}"]
                cmd += [
                    "-e", "PROBE_MODE=candidate",
                    "-e",
                    "PROBE_ADMIN_DSN=postgresql://postgres:%s@pg:5432/%s"
                    % (PG_PASSWORD, xdelta_db),
                    "-e",
                    "PROBE_USER_DSN=postgresql://app_user:app_user@pg:5432/%s"
                    % xdelta_db,
                    "-e",
                    "PROBE_INGRESS_DSN=postgresql://app_ingress:app_ingress@pg:5432/%s"
                    % xdelta_db,
                    "-e",
                    "PROBE_WORKER_DSN=postgresql://app_worker:app_worker@pg:5432/%s"
                    % xdelta_db,
                    args.image_tag, "python", "-c", probe,
                ]
                proc = _docker(*cmd)
                cand_out = proc.stdout + proc.stderr
                if ("XI_CAND_DENIED" not in proc.stdout
                        or "XI_CAND_RESTORED" not in proc.stdout):
                    return _fail(
                        details,
                        "xdelta_falsifier_candidate_assertable:"
                        + cand_out[-500:])
                details["stale_falsifier"] = "PASS"
            finally:
                subprocess.run(["git", "worktree", "remove", "--force", str(worktree)],
                               cwd=str(REPO_ROOT), capture_output=True)
                _docker("rmi", "-f", base_tag)
        else:
            details["stale_falsifier"] = "SKIPPED:no_base_sha"

        details["status"] = "PASS"
        print("B26_P2_IN_IMAGE_PASS")
        return 0
    finally:
        if args.evidence_out is not None:
            args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
            args.evidence_out.write_text(json.dumps(details, indent=2), encoding="utf-8")
        _docker("rm", "-f", PG_CONTAINER)
        _docker("network", "rm", NETWORK)


if __name__ == "__main__":
    raise SystemExit(main())
