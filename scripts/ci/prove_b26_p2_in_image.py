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
                                     tree image, prove the worker-verified
                                     mint is ACCEPTED there while the
                                     candidate refuses: the proof
                                     distinguishes the artifacts)

Usage (CI):
  python scripts/ci/prove_b26_p2_in_image.py \
    --image-tag skeldir-b26-p2-viii:$SHA --candidate-sha $SHA \
    [--base-sha $BASE_SHA] [--evidence-out artifacts/.../in-image.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
    "contracts/reconciliation/b2.6/scope-policy.v2.yaml",
    "alembic/versions/007_skeldir_foundation/202609220001_b26_p2_corrective_viii_context_robust.py",
]

PROBE_WORKER_VERIFIED = '''
import os, psycopg2, uuid
admin = psycopg2.connect(os.environ["PROBE_ADMIN_DSN"])
admin.autocommit = True
ac = admin.cursor()
t = str(uuid.uuid4())
ac.execute("INSERT INTO public.tenants (id, name, api_key_hash, notification_email) VALUES (%s, %s, %s, %s)", (t, "probe", t, "p@x.invalid"))
ac.execute("SELECT set_config('app.current_tenant_id', %s, false)", (t,))
ac.execute("INSERT INTO public.channel_taxonomy (code, family, is_paid, display_name, state) VALUES ('probe_ch', 'p', true, 'P', 'active') ON CONFLICT (code) DO NOTHING")
e = str(uuid.uuid4())
ac.execute("INSERT INTO public.attribution_events (id, tenant_id, occurred_at, correlation_id, session_id, revenue_cents, raw_payload, idempotency_key, event_type, channel, campaign_id, conversion_value_cents, currency, event_timestamp, processed_at, processing_status) VALUES (%s, %s, now(), %s, %s, 1, '{}', %s, 'conversion', 'probe_ch', 'c', 1, 'USD', now(), now(), 'processed')", (e, t, t, t, t))
admin.close()
w = psycopg2.connect(os.environ["PROBE_WORKER_DSN"])
w.autocommit = True
wc = w.cursor()
wc.execute("SELECT set_config('app.current_tenant_id', %s, false)", (t,))
try:
    wc.execute("INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id, provider, provider_native_event_reference, provider_native_commerce_reference, normalized_commerce_reference_kind, normalized_commerce_reference_value, verified_amount_minor, verified_amount_currency, event_timestamp, idempotency_key, verified_commerce_ingress_state) VALUES (%s, %s, %s, 'stripe', 'e', 'o', 'order_reference', 'o', 1, 'USD', now(), %s, 'authenticity_verified')", (str(uuid.uuid4()), t, e, t))
    print("WORKER_VERIFIED_ACCEPTED")
except Exception as exc:
    print("WORKER_VERIFIED_REFUSED:" + str(exc).splitlines()[0][:100])
'''


def _docker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True)


def _fail(details: dict, message: str) -> int:
    details["status"] = "FAIL"
    details["failure"] = message
    print(f"B26_P2_IN_IMAGE_FAIL {message}")
    return 1


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

    def universe() -> tuple[int, str]:
        cmd = ["run", "--rm", "--network", NETWORK, "-v", harness, "-v", out_mount,
               "-e", "PYTHONPATH=/proof:/app/backend",
               image, "python", "/proof/assert_b26_p2_authority_universe.py",
               "--dsn", f"postgresql://postgres:{PG_PASSWORD}@pg:5432/{DB_NAME}",
               "--pin", "/app/contracts-internal/governance/b26_p2_authority_universe.pin.json",
               "--migration-head", "202609220001",
               "--covered"] + covered
        proc = _docker(*cmd)
        return proc.returncode, (proc.stdout + proc.stderr)[-600:]

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
            code, tail = universe()
            ok = code != 0 and expect in tail
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
        code, tail = universe()
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

        # 2. VIII battery with the image's interpreter. The production
        # image deliberately excludes backend/tests (TCB hygiene); the
        # battery file is mounted read-only at its canonical path. The
        # mount adds only test harness bytes (no image path is shadowed);
        # every app byte under test resolves inside the image. The OB8
        # wiring cells read deployment artifacts (compose/monitoring)
        # that likewise ship outside the image; they are mounted
        # read-only for the same reason.
        tests_mounts = [
            f"{REPO_ROOT / 'backend' / 'tests'}:/app/backend/tests:ro",
            f"{REPO_ROOT / 'docker-compose.local.yml'}:/app/docker-compose.local.yml:ro",
            f"{REPO_ROOT / 'monitoring'}:/app/monitoring:ro",
        ]
        proc = run_img(
            args.image_tag,
            ["python", "-m", "pytest",
             "tests/finance_reconciliation/test_b26_p2_corrective_viii_context_robust.py",
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
             "--migration-head", "202609220001",
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

        # 6. Stale falsifier: base-tree image must ACCEPT the worker mint
        # the candidate refuses (the proof distinguishes the artifacts).
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
                }
                cmd = ["run", "--rm", "--network", NETWORK, "-w", "/app"]
                for k, v in stale_env.items():
                    cmd += ["-e", f"{k}={v}"]
                cmd += [base_tag, "alembic", "upgrade", "head"]
                proc = _docker(*cmd)
                if proc.returncode != 0:
                    return _fail(details, "stale_migrate_failed:"
                                 + (proc.stdout + proc.stderr)[-800:])
                probe = PROBE_WORKER_VERIFIED
                cmd = ["run", "--rm", "--network", NETWORK]
                for k, v in stale_env.items():
                    cmd += ["-e", f"{k}={v}"]
                cmd += [
                    "-e",
                    "PROBE_ADMIN_DSN=postgresql://postgres:%s@pg:5432/%s"
                    % (PG_PASSWORD, stale_db),
                    "-e",
                    "PROBE_WORKER_DSN=postgresql://app_worker:app_worker@pg:5432/%s"
                    % stale_db,
                    base_tag, "python", "-c", probe,
                ]
                proc = _docker(*cmd)
                # Base (VII) physics ACCEPTS the worker mint: the probe
                # printing ACCEPTED proves the falsifier is non-vacuous.
                if proc.returncode != 0 or "WORKER_VERIFIED_ACCEPTED" not in proc.stdout:
                    return _fail(
                        details,
                        "stale_falsifier_vacuous:base_did_not_accept:"
                        + (proc.stdout + proc.stderr)[-500:])
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
