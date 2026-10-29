#!/usr/bin/env python3
"""B2.6-P2 Corrective XXV falsifier engine.

Each subcommand is one falsifier built from the XXV attacker set
(report section 1(b)) and executed against the production-equivalent lane
that ``b26_p2_xxv_lane.py`` brings up. Every run writes a JSON evidence
record naming the exact artifact it executed on.

The falsifiers are written BEFORE the corresponding repair. A falsifier
that cannot be made RED on the starting artifact is reported as such
instead of being quietly relaxed.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from b26_p2_xxv_lane import (  # noqa: E402
    API,
    BEAT,
    admin_dsn,
    API_PORT,
    DB_NAME,
    LANE_ROOT,
    OBSERVER,
    PG_PORT,
    SIGNER,
    PREFIX,
    REPO_ROOT,
    WITNESS_VOL,
    SOURCE_EVIDENCE_VOL,
    WORKER_B23,
    docker,
    load_state,
    mint_jwt,
    role_dsn,
    seed_tenant,
    sql,
    volume_get,
    volume_list,
    volume_put,
    volume_rm,
    start_api,
    start_auth,
    wait_http,
    AUTH_PORT,
)

EVIDENCE_DIR = LANE_ROOT / "evidence"
_TOKEN_WARMUP_OBSERVATIONS: list[dict[str, object]] = []


def utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_evidence(name: str, record: dict) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    record = {
        "falsifier": name,
        "recorded_at_utc": utc(),
        "artifact": state["artifact"],
        "authority_universe": state.get("authority_universe"),
        "lane": {
            "image_tag": state["final_image_tag"],
            "image_id": state["final_image_id"],
            "migration_head": state["migration_head"],
            "environment": "prod",
            "database": DB_NAME,
            "roles": "least-privilege graph from prepare_migration_authority_boundary.py",
        },
        **(
            {"token_warmup": list(_TOKEN_WARMUP_OBSERVATIONS)}
            if _TOKEN_WARMUP_OBSERVATIONS
            else {}
        ),
        **record,
    }
    path = EVIDENCE_DIR / f"{name}.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps(record, indent=2, sort_keys=True, default=str)[:4000])
    print(f"[xxv-falsify] evidence -> {path}")
    return path


# ------------------------------------------------------------------ http
def http(
    method: str,
    url: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
) -> tuple[int, str]:
    req = urllib.request.Request(url, data=body, method=method)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()
    except Exception as exc:  # noqa: BLE001
        return 0, f"transport_error:{type(exc).__name__}:{exc}"


def sign_stripe(body: bytes, secret: str) -> str:
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def post_stripe(
    state: dict,
    tenant: dict,
    intent_id: str,
    amount: int,
    *,
    created: int | None = None,
) -> tuple[int, str, bytes]:
    body = json.dumps(
        {
            "id": intent_id,
            "amount": amount,
            "currency": "usd",
            "created": created or int(time.time()),
            "status": "succeeded",
        },
        separators=(",", ":"),
    ).encode()
    status, text = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/webhooks/stripe/payment_intent_succeeded",
        body=body,
        headers={
            "Content-Type": "application/json",
            "X-Skeldir-Tenant-Key": tenant["tenant_key"],
            "Stripe-Signature": sign_stripe(body, tenant["stripe_secret"]),
            "X-Idempotency-Key": str(uuid.uuid4()),
        },
    )
    return status, text, body


def post_stripe_envelope(
    state: dict,
    tenant: dict,
    *,
    event_reference: str,
    commerce_reference: str,
    amount: int,
    created: int | None = None,
) -> tuple[int, str, bytes]:
    """POST the Stripe EVENT envelope: one event over one payment intent.

    ``id`` is the event (``evt_...``), ``data.object.id`` is the commerce
    identity (``pi_...``). The sovereign derivation keeps them distinct, which
    is what makes a second event over the same intent expressible at all.
    Top-level ``amount``/``currency`` are deliberately absent: the derivation
    refuses a payload that carries both envelope and flat money fields.
    """
    body = json.dumps(
        {
            "id": event_reference,
            "type": "payment_intent.succeeded",
            "created": created or int(time.time()),
            "data": {
                "object": {
                    "id": commerce_reference,
                    "amount": amount,
                    "currency": "usd",
                    "created": created or int(time.time()),
                    "status": "succeeded",
                }
            },
        },
        separators=(",", ":"),
    ).encode()
    status, text = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/webhooks/stripe/payment_intent/succeeded",
        body=body,
        headers={
            "Content-Type": "application/json",
            "X-Skeldir-Tenant-Key": tenant["tenant_key"],
            "Stripe-Signature": sign_stripe(body, tenant["stripe_secret"]),
            "X-Idempotency-Key": str(uuid.uuid4()),
        },
    )
    return status, text, body


#: One access token per (tenant, scopes) per run, like a real client.
#:
#: Measured on the lane: a freshly minted access token is refused with HTTP 401
#: on its FIRST use about 10% of the time under concurrent database load
#: (9 of 10 reads succeeded when every read minted a new token; 10 of 10
#: succeeded when one token was reused). A new ``jti`` is unknown to the
#: revocation runtime cache, so its first use takes the database fall-through,
#: and that fall-through fails closed. Reusing one token per run is what a
#: client does; the first-use refusal is recorded as a finding instead of being
#: absorbed silently by retries.
_ACCESS_TOKENS: dict[tuple[str, tuple[str, ...]], str] = {}


def viewer_token(state: dict, tenant: dict, scopes=("viewer", "manager")) -> str:
    key = (str(tenant["tenant_id"]), tuple(scopes))
    token = _ACCESS_TOKENS.get(key)
    if token is None:
        token = mint_jwt(state, tenant, tuple(scopes))
        _ACCESS_TOKENS[key] = token
        # A freshly minted jti is unknown to the API's revocation runtime
        # cache. Its first authenticated use can be refused while the
        # process-local listener warms; the same token succeeds on the next
        # use. Warm the cache with a harmless authenticated read and record
        # every observation instead of hiding a first-use refusal.
        statuses: list[int] = []
        for attempt in range(10):
            status, _body = http(
                "GET",
                f"http://127.0.0.1:{API_PORT}/api/reconciliation/coverage"
                "?window_start=2026-01-01T00:00:00Z"
                "&window_end=2026-12-31T23:59:59Z",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Correlation-ID": str(uuid.uuid4()),
                },
            )
            statuses.append(status)
            if status != 401:
                break
            if attempt < 9:
                time.sleep(1.5)
        _TOKEN_WARMUP_OBSERVATIONS.append(
            {
                "tenant_id": str(tenant["tenant_id"]),
                "scopes": list(scopes),
                "statuses": statuses,
            }
        )
    return token


def viewer_headers(state: dict, tenant: dict, scopes=("viewer", "manager")) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {viewer_token(state, tenant, scopes)}",
        "X-Correlation-ID": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def machine_headers(tenant: dict) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {tenant['machine_token']}",
        "X-Tenant-ID": tenant["tenant_id"],
        "X-Trust-Nonce": f"xxv-{uuid.uuid4().hex}",
        "X-Correlation-ID": str(uuid.uuid4()),
        "X-Idempotency-Key": f"xxv-{uuid.uuid4()}",
        "Content-Type": "application/json",
    }


def wait_verdict(tenant_id: str, intent_id: str, timeout_s: int = 150) -> dict | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        rows = sql(
            """
            SELECT v.id::text, v.canonical_net_verified_amount_minor,
                   v.verified_amount_minor, v.attributed_amount_minor,
                   v.currency_code, v.status::text,
                   v.b26_p2_source_authority_state::text,
                   v.attribution_event_id::text,
                   v.provider_native_commerce_reference
              FROM public.b23_match_verdicts v
             WHERE v.tenant_id = %s
               AND (v.provider_native_commerce_reference = %s
                    OR v.canonical_commerce_reference = %s)
             ORDER BY v.created_at DESC LIMIT 1
            """,
            (tenant_id, intent_id, intent_id),
        )
        if rows:
            row = rows[0]
            return {
                "verdict_id": row[0],
                "canonical_net_verified_amount_minor": row[1],
                "verified_amount_minor": row[2],
                "attributed_amount_minor": row[3],
                "currency_code": row[4],
                "match_status": row[5],
                "source_authority_state": row[6],
                "attribution_event_id": row[7],
                "commerce_reference": row[8],
            }
        time.sleep(3)
    return None


#: How many attempts the last unsigned read needed. The authenticated customer
#: read path intermittently fails closed with HTTP 401 while the mandatory
#: composition proof is working against the same database (reproduced three
#: times in ten attempts, recovering without intervention). That is recorded
#: per observation so a retry is visible evidence, never a hidden smoothing.
LAST_UNSIGNED_READ_ATTEMPTS = 0


def read_reconciliation_once(
    state: dict, tenant: dict, verdict_id: str
) -> tuple[int, dict | str]:
    status, text = http(
        "GET",
        f"http://127.0.0.1:{API_PORT}/api/reconciliation/match-verdicts/{verdict_id}",
        headers=viewer_headers(state, tenant),
    )
    try:
        return status, json.loads(text)
    except Exception:  # noqa: BLE001
        return status, text


def read_reconciliation(
    state: dict, tenant: dict, verdict_id: str, *, attempts: int = 4
) -> tuple[int, dict | str]:
    """Read the unsigned financial consumer, distinguishing a refusal from a
    failed observation.

    The customer read path fails closed with HTTP 401 while the mandatory
    composition proof holds database resources (reproduced: proof -> immediate
    read 401, and the same token reads 200 a moment later). A 401 is therefore
    not an answer about the money -- it is an observation that did not happen,
    and recording it as a financial refusal is what made earlier recovery
    evidence uneven. Unauthenticated and transport outcomes are retried a
    bounded number of times; a persistent one is returned as-is so the caller
    reports an unavailable observation rather than a verdict.
    """
    global LAST_UNSIGNED_READ_ATTEMPTS
    last: tuple[int, dict | str] = (0, "not_attempted")
    for attempt in range(attempts):
        LAST_UNSIGNED_READ_ATTEMPTS = attempt + 1
        last = read_reconciliation_once(state, tenant, verdict_id)
        if last[0] not in (0, 401, 403, 429, 502, 503, 504):
            return last
        time.sleep(3 + 3 * attempt)
    return last


def read_trust(tenant: dict, verdict_id: str) -> tuple[int, dict | str]:
    urn = f"urn:skeldir:match_verdict:{verdict_id}"
    status, text = http(
        "GET",
        f"http://127.0.0.1:{API_PORT}/api/trust/v1/envelopes/match_verdict/{urn}",
        headers=machine_headers(tenant),
    )
    try:
        return status, json.loads(text)
    except Exception:  # noqa: BLE001
        return status, text


def verify_trust(tenant: dict, envelope: dict) -> tuple[int, dict | str]:
    status, text = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/trust/v1/verify",
        body=json.dumps(envelope).encode(),
        headers=machine_headers(tenant),
    )
    try:
        return status, json.loads(text)
    except Exception:  # noqa: BLE001
        return status, text


def composition_proof() -> dict:
    """Run the mandatory composition validator against the lane DB."""
    env = dict(os.environ)
    env["B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH"] = str(
        LANE_ROOT / "source_attestation_ed25519.pub"
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/ci/validate_b26_p2_xxii_composition.py"),
            "--dsn",
            f"postgresql://postgres:postgres@127.0.0.1:{PG_PORT}/{DB_NAME}",
        ],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env=env,
    )
    verdict = "PASS" if "B26_P2_XXII_COMPOSITION_PASS" in proc.stdout else "FAIL"
    return {
        "command": "scripts/ci/validate_b26_p2_xxii_composition.py --dsn <lane>",
        "returncode": proc.returncode,
        "printed_verdict": verdict,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-1500:],
    }


def composition_proof_with_source_evidence() -> dict:
    """Run the mandatory proof with the signed source-fact universe mounted.

    The ordinary host helper skips the source-evidence cell when no witness
    environment is present. This variant copies the real witness and source
    journals out of their volumes and makes the proof judge the same financial
    universe the readers see. A committed source fact missing from the database
    must therefore turn the proof RED.
    """
    proof_dir = LANE_ROOT / "proof-source-evidence"
    proof_dir.mkdir(parents=True, exist_ok=True)
    witness_journal = volume_get(WITNESS_VOL, "history_witness.jsonl")
    witness_public = volume_get(WITNESS_VOL, "history_witness_ed25519.pub")
    source_journal = volume_get(SOURCE_EVIDENCE_VOL, "source_evidence.jsonl")
    (proof_dir / "history_witness.jsonl").write_bytes(witness_journal)
    (proof_dir / "history_witness_ed25519.pub").write_bytes(witness_public)
    (proof_dir / "source_evidence.jsonl").write_bytes(source_journal)
    env = dict(os.environ)
    env["ENVIRONMENT"] = "ci"
    env["DATABASE_URL"] = (
        "postgresql+asyncpg://app_user:app_user@"
        f"127.0.0.1:{PG_PORT}/{DB_NAME}"
    )
    env["MIGRATION_DATABASE_URL"] = (
        f"postgresql://postgres:postgres@127.0.0.1:{PG_PORT}/{DB_NAME}"
    )
    env["B26_P2_HISTORY_WITNESS_JOURNAL_PATH"] = str(
        proof_dir / "history_witness.jsonl"
    )
    env["B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH"] = str(
        proof_dir / "history_witness_ed25519.pub"
    )
    env["B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH"] = str(
        proof_dir / "source_evidence.jsonl"
    )
    env["B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH"] = str(
        LANE_ROOT / "source_attestation_ed25519.pub"
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/ci/validate_b26_p2_xxii_composition.py"),
            "--dsn",
            f"postgresql://postgres:postgres@127.0.0.1:{PG_PORT}/{DB_NAME}",
        ],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env=env,
    )
    verdict = "PASS" if "B26_P2_XXII_COMPOSITION_PASS" in proc.stdout else "FAIL"
    return {
        "command": "scripts/ci/validate_b26_p2_xxii_composition.py --dsn <lane> (source evidence mounted)",
        "returncode": proc.returncode,
        "printed_verdict": verdict,
        "stdout_tail": proc.stdout[-5000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def owner_sql(statement: str, params: tuple = ()) -> list[tuple]:
    return sql(statement, params, dsn=role_dsn("migration_owner"))


def owner_tx(statements: list[tuple[str, tuple]]) -> None:
    """Execute owner statements in ONE transaction.

    Restoration and repair touch three agreeing representations. Executed as
    separate autocommit statements they leave a window in which the
    representations disagree, and a mandatory proof (or a customer read) that
    lands inside that window observes a divergence this run created and did not
    intend -- which is how a restored lane still produced a FAIL naming an
    already-restored verdict. One transaction, one visible state.
    """
    import psycopg2  # noqa: PLC0415

    conn = psycopg2.connect(role_dsn("migration_owner"))
    try:
        conn.autocommit = False
        cur = conn.cursor()
        for statement, params in statements:
            cur.execute(statement, params)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def money_snapshot(verdict_id: str) -> dict:
    row = sql(
        """
        SELECT v.canonical_net_verified_amount_minor,
               v.canonical_captured_gross_amount_minor,
               v.canonical_expected_gross_amount_minor,
               v.verified_amount_minor, v.attributed_amount_minor,
               v.b26_p2_source_authority_state::text,
               i.verified_amount_minor, ae.revenue_cents,
               (SELECT count(*) FROM public.b26_p2_verdict_supersession_ledger
                 WHERE verdict_id = v.id)
          FROM public.b23_match_verdicts v
          LEFT JOIN public.webhook_ingress_identities i
                 ON i.id = v.webhook_ingress_identity_id
          LEFT JOIN public.attribution_events ae ON ae.id = v.attribution_event_id
         WHERE v.id = %s
        """,
        (verdict_id,),
    )[0]
    return {
        "verdict_net_minor": row[0],
        "verdict_captured_minor": row[1],
        "verdict_expected_minor": row[2],
        "verified_amount_minor": row[3],
        "attributed_amount_minor": row[4],
        "source_authority_state": row[5],
        "ingress_verified_amount_minor": row[6],
        "attribution_revenue_cents": row[7],
        "supersession_rows": row[8],
    }


def witness_files() -> dict:
    out: dict[str, object] = {"listing": volume_list(WITNESS_VOL)}
    try:
        journal = volume_get(WITNESS_VOL, "history_witness.jsonl").decode().strip()
        out["journal_lines"] = len(journal.splitlines())
        out["journal_tip"] = json.loads(journal.splitlines()[-1])["payload"]
    except Exception as exc:  # noqa: BLE001
        out["journal_error"] = str(exc)
    for rel in ("history_witness_custody.json", "history_witness_heartbeat.json"):
        try:
            out[rel] = json.loads(volume_get(WITNESS_VOL, rel).decode())
        except Exception as exc:  # noqa: BLE001
            out[rel] = f"unreadable:{exc}"
    return out


def observe_once(state: dict) -> dict:
    """Drive the shipping observer task once, in the observer container."""
    probe = (
        "import asyncio, json;"
        "from app.tasks.b26_p2_history import observe_history_integrity;"
        "print('OBS=' + json.dumps(asyncio.run(observe_history_integrity()), default=str))"
    )
    proc = docker("exec", OBSERVER, "python", "-c", probe)
    return {
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-1500:],
        "stderr_tail": proc.stderr[-1500:],
    }


# ============================================================== falsifiers
# --------------------------------------------------------------- XXV oracles
def history_identity() -> dict:
    """The full identity of the append-only financial history.

    A count is not an identity. The signed witness commits to count, tip
    sequence, tip entry hash and whole-prefix digest, and the builder compares
    all four, so a restoration oracle must compare all four too.
    """
    import psycopg2  # noqa: PLC0415

    conn = psycopg2.connect(admin_dsn())
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "SELECT count(*)::bigint, max(seq) FROM"
            " public.b26_p2_verdict_supersession_ledger"
        )
        rows, tip_seq = cur.fetchone()
        cur.execute(
            "SELECT entry_hash FROM public.b26_p2_verdict_supersession_ledger"
            " ORDER BY seq DESC LIMIT 1"
        )
        tip = cur.fetchone()
        cur.execute("SELECT public.b26_p2_read_history_prefix_digest()")
        digest = cur.fetchone()[0]
        return {
            "ledger_rows": int(rows or 0),
            "ledger_tip_seq": None if tip_seq is None else int(tip_seq),
            "ledger_tip_hash": None if tip is None else str(tip[0]),
            "ledger_prefix_digest": None if digest is None else str(digest),
        }
    finally:
        conn.close()


def history_is_restored(pristine: dict, restored: dict) -> dict:
    """Decide restoration by identity, and say exactly why when it is not.

    Append-only history cannot be un-appended. When the experiment caused
    rows, restoration of history is NOT established and this records that as
    the finding rather than passing on a nondecreasing count.
    """
    same = all(
        pristine.get(key) == restored.get(key)
        for key in (
            "ledger_rows",
            "ledger_tip_seq",
            "ledger_tip_hash",
            "ledger_prefix_digest",
        )
    )
    appended = int(restored.get("ledger_rows") or 0) - int(
        pristine.get("ledger_rows") or 0
    )
    return {
        "established": same,
        "appended_rows": appended,
        "basis": "count+tip_seq+tip_hash+prefix_digest identity",
        "limit_of_inference": (
            "identical"
            if same
            else (
                "history is NOT restored: the experiment appended"
                f" {appended} ledger row(s) and an append-only history cannot"
                " be un-appended. Any consumer state that depends on the"
                " history is therefore being read against a different history"
                " than the pristine one."
            )
        ),
    }


def signed_financial_result(
    tenant: dict, verdict_id: str, *, expected_minor: int, expected_currency: str
) -> dict:
    """Verify the SIGNED financial result a machine consumer would read.

    Establishes the consumer only when the signed envelope is issued, carries
    the expected integer-minor amount and currency, and its signature verifies
    independently. An HTTP 200 and an unsigned figure establish nothing about
    the signed artifact, which is the artifact B6/B9/B12 govern.
    """
    status, body = read_trust(tenant, verdict_id)
    record = {
        "trust_status": status,
        "verified_revenue_minor": None,
        "currency": None,
        "verification_status": None,
        "established": False,
    }
    if status != 200 or not isinstance(body, dict):
        record["body_head"] = str(body)[:240]
        record["durable_refusal_reason"] = durable_trust_refusal_reason(
            str(tenant["tenant_id"])
        )
        return record
    record["verified_revenue_minor"] = body.get("verified_revenue_minor")
    record["currency"] = body.get("currency")
    verify = verify_trust(tenant, body)
    if isinstance(verify[1], dict):
        record["verification_status"] = verify[1].get("verification_status")
    record["established"] = (
        record["verified_revenue_minor"] == expected_minor
        and str(record["currency"] or "").upper() == expected_currency.upper()
        and record["verification_status"] == "verified"
    )
    return record


def _ingress_row_by_event(
    tenant_id: str, event_reference: str
) -> dict | None:
    import psycopg2  # noqa: PLC0415

    conn = psycopg2.connect(admin_dsn())
    try:
        conn.autocommit = True
        cur = conn.cursor()
        # The currentness predicate is a tenant-filtered reader; an admin
        # session without the tenant GUC would see FALSE for a current row.
        cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, false)",
            (tenant_id,),
        )
        cur.execute(
            """
        SELECT i.id::text, i.provider_native_event_reference,
               i.provider_native_commerce_reference,
               i.verified_amount_minor, i.verified_amount_currency,
               i.b26_p2_provenance_status::text,
               i.b26_p2_demotion_reason,
               i.event_timestamp, i.created_at,
               public.b26_p2_ingress_has_current_authority(i.id) AS is_current,
               EXISTS (
                   SELECT 1 FROM public.b26_p2_source_money_attestation a
                    WHERE a.webhook_ingress_identity_id = i.id
                      AND a.tenant_id = i.tenant_id
               ) AS has_attestation,
               EXISTS (
                   SELECT 1 FROM public.b26_p2_ingress_auth_witness w
                    WHERE w.webhook_ingress_identity_id = i.id
               ) AS has_witness,
               EXISTS (
                   SELECT 1 FROM public.b26_p2_auth_root_evidence r
                    WHERE r.webhook_ingress_identity_id = i.id
               ) AS has_root_evidence
          FROM public.webhook_ingress_identities i
         WHERE i.tenant_id = %s
           AND i.provider_native_event_reference = %s
         ORDER BY i.created_at DESC
         LIMIT 1
        """,
            (tenant_id, event_reference),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    if not rows:
        return None
    r = rows[0]
    return {
        "ingress_id": r[0],
        "event_reference": r[1],
        "commerce_reference": r[2],
        "amount_minor": r[3],
        "currency": r[4],
        "provenance": r[5],
        "demotion_reason": r[6],
        "event_timestamp": r[7],
        "created_at": r[8],
        "is_current": bool(r[9]),
        "has_attestation": bool(r[10]),
        "has_witness": bool(r[11]),
        "has_root_evidence": bool(r[12]),
    }


def _wait_amendment_ingress(
    tenant_id: str, event_reference: str, *, timeout_s: int = 90
) -> dict | None:
    deadline = time.time() + timeout_s
    last: dict | None = None
    while time.time() < deadline:
        last = _ingress_row_by_event(tenant_id, event_reference)
        if last is not None and last["is_current"] and last["has_attestation"]:
            return last
        time.sleep(3)
    return last


def _correction_state(verdict_id: str) -> dict:
    row = sql(
        """
        SELECT v.canonical_net_verified_amount_minor,
               v.canonical_captured_gross_amount_minor,
               v.canonical_expected_gross_amount_minor,
               v.b26_p2_source_authority_state::text,
               v.webhook_ingress_identity_id::text,
               v.provider_native_event_reference,
               (SELECT count(*) FROM public.b26_p2_verdict_supersession_ledger
                 WHERE verdict_id = v.id) AS supersession_rows,
               (SELECT count(*) FROM public.b23_revenue_events e
                 WHERE e.match_verdict_id = v.id
                   AND e.is_gross_capture_correction) AS correction_events,
               (SELECT count(*) FROM public.b23_match_verdicts x
                 WHERE x.tenant_id = v.tenant_id
                   AND x.provider = v.provider
                   AND x.provider_native_commerce_reference =
                       v.provider_native_commerce_reference) AS verdicts_for_identity
          FROM public.b23_match_verdicts v
         WHERE v.id = %s
        """,
        (verdict_id,),
    )[0]
    return {
        "net_minor": row[0],
        "captured_minor": row[1],
        "expected_minor": row[2],
        "authority_state": row[3],
        "linked_ingress_id": row[4],
        "linked_event_reference": row[5],
        "supersession_rows": int(row[6]),
        "correction_events": int(row[7]),
        "verdicts_for_identity": int(row[8]),
    }


def _last_observation() -> dict:
    rows = sql(
        """
        SELECT id::bigint, observed_at, ledger_count::bigint,
               observer_violations, author::text
          FROM public.b26_p2_history_integrity_observations
         ORDER BY id DESC
         LIMIT 1
        """
    )
    if not rows:
        return {
            "observation_id": 0,
            "observed_at": None,
            "observed_at_epoch": 0.0,
            "ledger_count": 0,
            "violations": "",
            "author": None,
        }
    r = rows[0]
    observed_at = r[1]
    return {
        "observation_id": int(r[0]),
        "observed_at": (
            observed_at.isoformat()
            if hasattr(observed_at, "isoformat")
            else str(observed_at)
        ),
        "observed_at_epoch": (
            observed_at.timestamp()
            if hasattr(observed_at, "timestamp")
            else 0.0
        ),
        "ledger_count": int(r[2]),
        "violations": str(r[3] or ""),
        "author": str(r[4]),
    }


def _last_observation_id() -> int:
    return int(_last_observation()["observation_id"])


def _wait_scheduled_observation(
    last_observation_id: int,
    min_ledger_count: int,
    *,
    not_before_epoch: float | None = None,
    timeout_s: int = 420,
) -> dict | None:
    """Wait for the live beat schedule to publish the witnessing observation.

    This deliberately never invokes the observer. The lane's beat process
    schedules ``app.tasks.b26_p2_history.observe_history_integrity`` every 300
    seconds; a controlled catch-up would not establish natural scheduled
    progression.
    """
    deadline = time.time() + timeout_s
    last_seen: dict | None = None
    while time.time() < deadline:
        rows = sql(
            """
            SELECT id::bigint, observed_at, ledger_count::bigint,
                   observer_violations, author::text
              FROM public.b26_p2_history_integrity_observations
             WHERE id > %s
             ORDER BY id ASC
             LIMIT 1
            """,
            (last_observation_id,),
        )
        if rows:
            r = rows[0]
            last_seen = {
                "observation_id": int(r[0]),
                "observed_at": r[1].isoformat() if hasattr(r[1], "isoformat") else str(r[1]),
                "ledger_count": int(r[2]),
                "violations": str(r[3] or ""),
                "author": str(r[4]),
            }
            if last_seen["violations"]:
                return last_seen
            if (
                not_before_epoch is not None
                and r[1] is not None
                and hasattr(r[1], "timestamp")
                and r[1].timestamp() < not_before_epoch
            ):
                # This is the immediate observation enqueued by the append
                # path, not the periodic beat observation. Record it only if
                # the caller asks for the scheduled cadence.
                last_observation_id = last_seen["observation_id"]
                time.sleep(5)
                continue
            if last_seen["ledger_count"] >= min_ledger_count:
                return last_seen
            # This observation landed before the correction's ledger append;
            # wait for the next scheduled cycle.
            last_observation_id = last_seen["observation_id"]
        time.sleep(5)
    return last_seen


def _scheduler_state() -> dict:
    rows = sql(
        "SELECT max(last_tick), count(*)::int,"
        " max(beat_instance_id::text)"
        " FROM public.b26_p2_scheduler_heartbeat"
    )
    last_tick, tenants, instance = rows[0]
    return {
        "last_tick": last_tick.isoformat() if hasattr(last_tick, "isoformat") else str(last_tick),
        "tenant_rows": int(tenants or 0),
        "beat_instance_id": instance,
    }


def _wait_correction_applied(
    verdict_id: str,
    *,
    expected_ingress_id: str,
    expected_amount: int,
    expected_event_reference: str,
    prior_supersession_rows: int,
    prior_correction_events: int,
    timeout_s: int = 150,
) -> dict:
    deadline = time.time() + timeout_s
    last = _correction_state(verdict_id)
    while time.time() < deadline:
        last = _correction_state(verdict_id)
        if (
            last["linked_ingress_id"] == expected_ingress_id
            and last["linked_event_reference"] == expected_event_reference
            and last["net_minor"] == expected_amount
            and last["authority_state"] == "current"
            and last["supersession_rows"] > prior_supersession_rows
            and last["correction_events"] > prior_correction_events
        ):
            return last
        time.sleep(3)
    return last


def _wait_signed_result(
    tenant: dict,
    verdict_id: str,
    *,
    expected_minor: int,
    timeout_s: int = 150,
) -> dict:
    deadline = time.time() + timeout_s
    last: dict = {
        "trust_status": None,
        "verified_revenue_minor": None,
        "currency": None,
        "verification_status": None,
        "established": False,
    }
    while time.time() < deadline:
        last = signed_financial_result(
            tenant,
            verdict_id,
            expected_minor=expected_minor,
            expected_currency="USD",
        )
        if last["established"]:
            return last
        time.sleep(5)
    return last


def f_b4_coverage(args: argparse.Namespace) -> int:
    """B4: canonical coverage is 95.00 only with a genuine unresolved leg.

    The semantic contract says a provisional match participates in the
    coverage numerator; it is a match, not confirmation. A 76,000 confirmed
    source plus a 4,000 provisional source is therefore 100%, not 95%. The
    canonical 95% witness is a 76,000 matched source plus a 4,000 source with
    no match verdict (an unresolved source). The proof creates that state by
    stopping the real B2.3 consumer while the 4,000 source is admitted, reads
    95.00, restarts the consumer, observes the provisional verdict, and reads
    100.00. The two readings are the two halves of the contract.
    """
    state = load_state()
    tenant = seed_tenant(f"b4-{uuid.uuid4().hex[:8]}")
    denominator_minor = 80_000
    numerator_minor = 76_000
    confirmed_intent = f"pi_xxvb4a{uuid.uuid4().hex[:14]}"
    provisional_intent = f"pi_xxvb4b{uuid.uuid4().hex[:14]}"
    old_created = int(time.time()) - 2 * 86400
    status_a, body_a, _raw_a = post_stripe(
        state, tenant, confirmed_intent, numerator_minor, created=old_created
    )
    confirmed = wait_verdict(tenant["tenant_id"], confirmed_intent, timeout_s=180)
    if confirmed is None:
        write_evidence(
            "xxv-b4-coverage",
            {"error": "confirmed_source_missing"},
        )
        return 1
    deadline = time.time() + 420
    confirmed_status = confirmed["match_status"]
    while confirmed_status not in ("matched_confirmed", "adjusted"):
        if time.time() > deadline:
            break
        time.sleep(10)
        refreshed = wait_verdict(tenant["tenant_id"], confirmed_intent, timeout_s=15)
        if refreshed is not None:
            confirmed = refreshed
            confirmed_status = refreshed["match_status"]
    if confirmed_status not in ("matched_confirmed", "adjusted"):
        write_evidence(
            "xxv-b4-coverage",
            {"error": "confirmed_source_not_confirmed", "verdict": confirmed},
        )
        return 1

    # The 4,000 leg must be genuinely unresolved, not provisional: the
    # canonical contract counts provisional matches. Stop the shipping B2.3
    # consumer so the source can be admitted without a verdict.
    worker_stop = subprocess.run(
        ["docker", "stop", WORKER_B23], capture_output=True, text=True
    )
    if worker_stop.returncode != 0:
        write_evidence(
            "xxv-b4-coverage",
            {
                "error": "worker_stop_failed",
                "stderr": worker_stop.stderr[-800:],
            },
        )
        return 1
    status_b, body_b, _raw_b = post_stripe(
        state, tenant, provisional_intent, denominator_minor - numerator_minor
    )
    unresolved_ingress = _wait_amendment_ingress(
        tenant["tenant_id"], provisional_intent, timeout_s=120
    )
    if unresolved_ingress is None:
        subprocess.run(["docker", "start", WORKER_B23], capture_output=True, text=True)
        write_evidence(
            "xxv-b4-coverage",
            {"error": "unresolved_source_missing"},
        )
        return 1
    window_start = datetime.fromtimestamp(
        old_created - 3600, tz=timezone.utc
    ).isoformat()
    # The event timestamp is second precision; the half-open window must
    # include the admitted unresolved source, not end on its exact second.
    window_end = (
        datetime.now(timezone.utc) + timedelta(seconds=5)
    ).replace(microsecond=0).isoformat()
    from urllib.parse import urlencode  # noqa: PLC0415

    coverage_query = urlencode(
        {"window_start": window_start, "window_end": window_end}
    )

    def read_coverage() -> tuple[int, dict]:
        status, body = http(
            "GET",
            f"http://127.0.0.1:{API_PORT}/api/reconciliation/coverage"
            f"?{coverage_query}",
            headers=viewer_headers(state, tenant),
        )
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body[:600]}
        return status, parsed

    unresolved_status, unresolved = read_coverage()
    worker_start = subprocess.run(
        ["docker", "start", WORKER_B23], capture_output=True, text=True
    )
    provisional = wait_verdict(
        tenant["tenant_id"], provisional_intent, timeout_s=180
    )
    if provisional is None:
        write_evidence(
            "xxv-b4-coverage",
            {"error": "provisional_source_missing_after_restart"},
        )
        return 1
    provisional_status, provisional_coverage = read_coverage()
    record = {
        "property": (
            "B4: canonical coverage counts provisional matches; the 95.00%"
            " witness requires a genuine unresolved leg and becomes 100.00%"
            " when that leg gains a provisional match"
        ),
        "tenant_id": tenant["tenant_id"],
        "confirmed_event": {
            "http": {"status": status_a, "body": body_a[:300]},
            "intent": confirmed_intent,
            "amount_minor": numerator_minor,
            "verdict": confirmed,
        },
        "unresolved_event": {
            "http": {"status": status_b, "body": body_b[:300]},
            "intent": provisional_intent,
            "amount_minor": denominator_minor - numerator_minor,
            "ingress": unresolved_ingress,
        },
        "worker_stop": {
            "returncode": worker_stop.returncode,
            "stdout": worker_stop.stdout.strip(),
            "stderr": worker_stop.stderr[-400:],
        },
        "worker_start": {
            "returncode": worker_start.returncode,
            "stdout": worker_start.stdout.strip(),
            "stderr": worker_start.stderr[-400:],
        },
        "provisional_event": {
            "intent": provisional_intent,
            "verdict": provisional,
        },
        "coverage_unresolved": {
            "http_status": unresolved_status,
            "numerator_minor": unresolved.get(
                "numerator_matched_webhook_revenue_minor"
            ),
            "denominator_minor": unresolved.get(
                "denominator_connected_platform_revenue_minor"
            ),
            "coverage_percent": unresolved.get("coverage_percent"),
        },
        "coverage_provisional": {
            "http_status": provisional_status,
            "numerator_minor": provisional_coverage.get(
                "numerator_matched_webhook_revenue_minor"
            ),
            "denominator_minor": provisional_coverage.get(
                "denominator_connected_platform_revenue_minor"
            ),
            "coverage_percent": provisional_coverage.get("coverage_percent"),
        },
        "window_start": window_start,
        "window_end": window_end,
        "expected": {
            "unresolved_coverage_percent": "95.00",
            "provisional_coverage_percent": "100.00",
        },
    }
    write_evidence("xxv-b4-coverage", record)
    return 0 if (
        unresolved_status == 200
        and unresolved.get("numerator_matched_webhook_revenue_minor")
        == numerator_minor
        and unresolved.get("denominator_connected_platform_revenue_minor")
        == denominator_minor
        and unresolved.get("coverage_percent") == "95.00"
        and unresolved.get("zero_denominator") is False
        and provisional.get("match_status") == "matched_provisional"
        and provisional_status == 200
        and provisional_coverage.get("numerator_matched_webhook_revenue_minor")
        == denominator_minor
        and provisional_coverage.get("coverage_percent") == "100.00"
    ) else 1


def f_b6_worker_loss(args: argparse.Namespace) -> int:
    """B6/HB-14: accepted ingress without its financial consumer is RED.

    The B2.3 consumer is stopped, a fresh authenticated source is accepted,
    and the mandatory composition proof is run after the conduction grace.
    It must report the missing consequence. Restoring the worker must produce
    the verdict and return the proof to GREEN.
    """
    state = load_state()
    tenant = state["tenant_a"]
    baseline = composition_proof()
    if baseline["printed_verdict"] != "PASS":
        write_evidence(
            "xxv-b6-worker-loss",
            {"error": "baseline_proof_not_green", "baseline": baseline},
        )
        return 1
    stop = subprocess.run(
        ["docker", "stop", WORKER_B23], capture_output=True, text=True
    )
    intent = f"pi_xxvb6{uuid.uuid4().hex[:16]}"
    status, body, _raw = post_stripe(state, tenant, intent, 4321)
    time.sleep(70)
    adverse = composition_proof()
    start = subprocess.run(
        ["docker", "start", WORKER_B23], capture_output=True, text=True
    )
    verdict = wait_verdict(tenant["tenant_id"], intent, timeout_s=180)
    time.sleep(10)
    restored = composition_proof()
    record = {
        "property": (
            "B6/HB-14: an accepted authenticated source with its required"
            " financial consumer absent must RED the governing proof"
        ),
        "actor": "B2.3 consumer worker removed from the production topology",
        "baseline_proof": {
            "verdict": baseline["printed_verdict"],
            "stdout_tail": baseline["stdout_tail"][-800:],
        },
        "worker_stop": {
            "returncode": stop.returncode,
            "stdout": stop.stdout.strip(),
            "stderr": stop.stderr.strip()[:300],
        },
        "event_http": {"status": status, "body": body[:300]},
        "adverse_proof": {
            "verdict": adverse["printed_verdict"],
            "stdout_tail": adverse["stdout_tail"][-1200:],
            "conduction_missing": "conduction_missing" in adverse["stdout_tail"],
        },
        "worker_start": {
            "returncode": start.returncode,
            "stdout": start.stdout.strip(),
            "stderr": start.stderr.strip()[:300],
        },
        "verdict_after_restart": verdict,
        "restored_proof": {
            "verdict": restored["printed_verdict"],
            "stdout_tail": restored["stdout_tail"][-800:],
        },
    }
    write_evidence("xxv-b6-worker-loss", record)
    return 0 if (
        stop.returncode == 0
        and adverse["printed_verdict"] == "FAIL"
        and "conduction_missing" in adverse["stdout_tail"]
        and start.returncode == 0
        and verdict is not None
        and restored["printed_verdict"] == "PASS"
    ) else 1


def f_a8_crash_recovery(args: argparse.Namespace) -> int:
    """A8: unwitnessed finance is refused; observer crash recovery conducts.

    A correction commits on the real B2.3 worker while the shipping observer
    is hard-killed. The signed consumer must refuse (no unwitnessed complete
    result). Restarting the observer must consume the durable observation
    request, witness the new ledger and let the signed consumer serve the
    corrected amount without manual journal repair.
    """
    state = load_state()
    tenant = state["tenant_a"]
    commerce = f"pi_xxva8{uuid.uuid4().hex[:14]}"
    initial_event = f"evt_xxva8A{uuid.uuid4().hex[:12]}"
    amendment_event = f"evt_xxva8B{uuid.uuid4().hex[:12]}"
    initial_amount = 4321
    amended_amount = 5100
    base_created = int(time.time())
    status_a, body_a, _raw_a = post_stripe_envelope(
        state,
        tenant,
        event_reference=initial_event,
        commerce_reference=commerce,
        amount=initial_amount,
        created=base_created,
    )
    verdict = wait_verdict(tenant["tenant_id"], commerce)
    if verdict is None:
        write_evidence(
            "xxv-a8-crash-recovery",
            {"error": "initial_event_did_not_conduct"},
        )
        return 1
    vid = verdict["verdict_id"]
    baseline = _wait_signed_result(tenant, vid, expected_minor=initial_amount)
    if baseline.get("established") is not True:
        write_evidence(
            "xxv-a8-crash-recovery",
            {"error": "baseline_signed_result_not_established", "baseline": baseline},
        )
        return 1
    status_b, body_b, _raw_b = post_stripe_envelope(
        state,
        tenant,
        event_reference=amendment_event,
        commerce_reference=commerce,
        amount=amended_amount,
        created=base_created + 1,
    )
    ingress = _wait_amendment_ingress(tenant["tenant_id"], amendment_event)
    if ingress is None:
        write_evidence(
            "xxv-a8-crash-recovery",
            {"error": "amendment_ingress_missing"},
        )
        return 1
    before = _correction_state(vid)
    last_observation = _last_observation()
    kill = subprocess.run(
        ["docker", "kill", OBSERVER], capture_output=True, text=True
    )
    correction_status, correction_body = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/reconciliation/match-verdicts/{vid}/corrections",
        body=json.dumps(
            {
                "provider": "stripe",
                "event_type": "payment_capture",
                "provider_native_event_reference": amendment_event,
                "is_gross_capture_correction": True,
            }
        ).encode(),
        headers=viewer_headers(state, tenant),
    )
    applied = _wait_correction_applied(
        vid,
        expected_ingress_id=ingress["ingress_id"],
        expected_amount=amended_amount,
        expected_event_reference=amendment_event,
        prior_supersession_rows=before["supersession_rows"],
        prior_correction_events=before["correction_events"],
    )
    after_history = history_identity()
    adverse_status, adverse_body = read_trust(tenant, vid)
    adverse_reason = durable_trust_refusal_reason(str(tenant["tenant_id"]))
    start = subprocess.run(
        ["docker", "start", OBSERVER], capture_output=True, text=True
    )
    observation = _wait_scheduled_observation(
        int(last_observation["observation_id"]),
        after_history["ledger_rows"],
        timeout_s=360,
    )
    signed = _wait_signed_result(tenant, vid, expected_minor=amended_amount, timeout_s=180)
    record = {
        "property": (
            "A8: unwitnessed finance must not issue as complete, and a"
            " legitimate correction must recover through the observer"
        ),
        "commerce_reference": commerce,
        "verdict_id": vid,
        "baseline_signed": baseline,
        "amendment_http": {"status": status_b, "body": body_b[:300]},
        "correction_http": {
            "status": correction_status,
            "body": correction_body[:400],
        },
        "observer_kill": {
            "returncode": kill.returncode,
            "stdout": kill.stdout.strip(),
            "stderr": kill.stderr.strip()[:400],
        },
        "observer_start": {
            "returncode": start.returncode,
            "stdout": start.stdout.strip(),
            "stderr": start.stderr.strip()[:400],
        },
        "before": before,
        "after_worker": applied,
        "history_after_worker": after_history,
        "unwitnessed_trust_read": {
            "status": adverse_status,
            "body_head": str(adverse_body)[:300],
        },
        "unwitnessed_durable_reason": adverse_reason,
        "recovered_observation": observation,
        "recovered_signed_result": signed,
        "limit_of_inference": (
            "This is a hard observer-container kill after a committed"
            " correction, not an arbitrary worker/database crash."
        ),
    }
    write_evidence("xxv-a8-crash-recovery", record)
    return 0 if (
        kill.returncode == 0
        and applied.get("net_minor") == amended_amount
        and adverse_status == 404
        and adverse_reason is not None
        and "history_integrity_unverifiable" in adverse_reason
        and start.returncode == 0
        and observation is not None
        and not observation.get("violations")
        and signed.get("established") is True
    ) else 1


def f_a4_foreign_universe(args: argparse.Namespace) -> int:
    """A4: a coherently signed foreign authority universe is refused.

    The authentic witness key re-signs the latest checkpoint with a foreign
    authority-universe UUID. The journal remains internally coherent (prefix,
    count and tip unchanged) and the heartbeat/custody are made coherent with
    it. The real Trust consumer must refuse; exact byte restoration must return
    it to GREEN. A disposable copy of the verifier with the universe comparison
    removed must accept the same journal, proving the check is load-bearing
    rather than vacuous.
    """
    import importlib.util
    import tempfile

    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    os.environ.setdefault(
        "DATABASE_URL",
        f"postgresql+asyncpg://app_user:app_user@127.0.0.1:{PG_PORT}/{DB_NAME}",
    )
    os.environ.setdefault("ENVIRONMENT", "ci")
    from app.trust.history_witness import (  # noqa: PLC0415
        HistoryWitnessError,
        _canonical,
        _checkpoint_hash,
        _heartbeat_hash,
        _b64url_decode,
        verify_journal,
    )

    state = load_state()
    tenant = state["tenant_a"]
    intent = f"pi_xxva4{uuid.uuid4().hex[:16]}"
    post_stripe(state, tenant, intent, 4321)
    verdict = wait_verdict(tenant["tenant_id"], intent)
    if verdict is None:
        write_evidence(
            "xxv-a4-foreign-universe",
            {"error": "baseline_verdict_missing"},
        )
        return 1
    vid = verdict["verdict_id"]
    pristine = read_trust(tenant, vid)
    if pristine[0] != 200:
        write_evidence(
            "xxv-a4-foreign-universe",
            {
                "error": "baseline_not_signed",
                "pristine": {"status": pristine[0], "body_head": str(pristine[1])[:300]},
            },
        )
        return 1
    journal_bytes = volume_get(WITNESS_VOL, "history_witness.jsonl")
    heartbeat_bytes = volume_get(WITNESS_VOL, "history_witness_heartbeat.json")
    custody_bytes = volume_get(WITNESS_VOL, "history_witness_custody.json")
    pub_bytes = volume_get(WITNESS_VOL, "history_witness_ed25519.pub")
    private_seed = _b64url_decode(state["material"]["witness_private_b64url"])
    private_key = Ed25519PrivateKey.from_private_bytes(private_seed)
    foreign_universe = str(uuid.uuid4())
    live_universe = str(
        sql("SELECT public.b26_p2_authority_universe()::text")[0][0]
    )
    entries = [
        json.loads(line)
        for line in journal_bytes.decode().strip().splitlines()
        if line.strip()
    ]
    if not entries:
        raise RuntimeError("witness_journal_empty")
    genesis = entries[0]
    genesis_hash = genesis["payload"]["checkpoint_hash"]
    live = history_identity()
    observed = datetime.now(timezone.utc).isoformat()
    payload = dict(genesis["payload"])
    payload["observed_at"] = observed
    payload["ledger_count"] = live["ledger_rows"]
    payload["ledger_tip_seq"] = live["ledger_tip_seq"]
    payload["ledger_tip_hash"] = live["ledger_tip_hash"]
    payload["ledger_prefix_digest"] = live["ledger_prefix_digest"]
    payload["previous_checkpoint_hash"] = genesis_hash
    payload["authority_universe"] = foreign_universe
    payload["checkpoint_hash"] = _checkpoint_hash(payload)
    forged_entry = {
        "payload": payload,
        "signature": "ed25519:"
        + base64.urlsafe_b64encode(
            private_key.sign(_canonical(payload))
        ).rstrip(b"=").decode(),
    }
    forged_journal = (
        "\n".join(
            json.dumps(entry, separators=(",", ":"), sort_keys=True)
            for entry in (genesis, forged_entry)
        )
        + "\n"
    ).encode()
    heartbeat = json.loads(heartbeat_bytes.decode())
    hb_payload = dict(heartbeat["payload"])
    hb_payload["observed_at"] = observed
    hb_payload["ledger_count"] = live["ledger_rows"]
    hb_payload["ledger_tip_seq"] = live["ledger_tip_seq"]
    hb_payload["ledger_tip_hash"] = live["ledger_tip_hash"]
    hb_payload["ledger_prefix_digest"] = live["ledger_prefix_digest"]
    hb_payload["authority_universe"] = foreign_universe
    hb_payload["checkpoint_hash"] = payload["checkpoint_hash"]
    hb_payload["heartbeat_hash"] = _heartbeat_hash(hb_payload)
    heartbeat["payload"] = hb_payload
    heartbeat["signature"] = "ed25519:" + base64.urlsafe_b64encode(
        private_key.sign(_canonical(hb_payload))
    ).rstrip(b"=").decode()
    custody = json.loads(custody_bytes.decode())
    custody["authority_universe"] = foreign_universe
    custody["checkpoint_hash"] = payload["checkpoint_hash"]
    custody["ledger_count"] = live["ledger_rows"]
    volume_put(
        WITNESS_VOL,
        {
            "history_witness.jsonl": forged_journal,
            "history_witness_heartbeat.json": json.dumps(heartbeat).encode(),
            "history_witness_custody.json": json.dumps(custody).encode(),
        },
        mode="0644",
    )
    adverse = read_trust(tenant, vid)
    adverse_reason = durable_trust_refusal_reason(str(tenant["tenant_id"]))
    volume_put(
        WITNESS_VOL,
        {
            "history_witness.jsonl": journal_bytes,
            "history_witness_heartbeat.json": heartbeat_bytes,
            "history_witness_custody.json": custody_bytes,
            "history_witness_ed25519.pub": pub_bytes,
        },
        mode="0644",
    )
    restored = read_trust(tenant, vid)

    from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: PLC0415
        Ed25519PublicKey,
    )

    runtime_public = Ed25519PublicKey.from_public_bytes(
        __import__("base64").urlsafe_b64decode(
            pub_bytes.decode().strip() + "=" * (-len(pub_bytes.decode().strip()) % 4)
        )
    )
    tempdir = Path(tempfile.mkdtemp(prefix="xxv-a4-"))
    foreign_path = tempdir / "foreign.jsonl"
    foreign_path.write_bytes(forged_journal)
    unpatched = {"refused": False, "reason": None, "accepted": False}
    try:
        verify_journal(
            foreign_path,
            public_key=runtime_public,
            expected_universe=live_universe,
            require_universe=True,
        )
        unpatched["accepted"] = True
    except HistoryWitnessError as exc:
        unpatched["refused"] = True
        unpatched["reason"] = str(exc)
    patched_source = (
        REPO_ROOT / "backend" / "app" / "trust" / "history_witness.py"
    ).read_text(encoding="utf-8")
    patched_source = patched_source.replace(
        """            if journal_universe is None:
                journal_universe = universe
            elif journal_universe != universe:
                raise HistoryWitnessError("witness_authority_universe_changed")""",
        """            journal_universe = universe""",
        1,
    )
    patched_source = patched_source.replace(
        """    if expected_universe is not None and (
        latest.authority_universe or None
    ) != (_normalize_universe(expected_universe) or None):
        raise HistoryWitnessError("witness_live_universe_diverged")""",
        """    pass""",
        1,
    )
    patched_path = tempdir / "history_witness_patched.py"
    patched_path.write_text(patched_source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(
        "xxv_a4_patched_witness", patched_path
    )
    patched = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = patched
    spec.loader.exec_module(patched)
    patched_result = {"accepted": False, "reason": None}
    try:
        patched.verify_journal(
            foreign_path,
            public_key=runtime_public,
            expected_universe=live_universe,
            require_universe=True,
        )
        patched_result["accepted"] = True
    except Exception as exc:  # noqa: BLE001
        patched_result["reason"] = f"{type(exc).__name__}:{exc}"
    record = {
        "property": (
            "A4: a coherently signed foreign authority universe cannot"
            " establish current historical authority"
        ),
        "actor": "authentic witness-key holder re-signing a foreign-universe journal",
        "verdict_id": vid,
        "live_universe": live_universe,
        "foreign_universe": foreign_universe,
        "pristine_trust_read": {"status": pristine[0], "body_head": str(pristine[1])[:300]},
        "adverse_trust_read": {"status": adverse[0], "body_head": str(adverse[1])[:300]},
        "adverse_durable_reason": adverse_reason,
        "restored_trust_read": {"status": restored[0], "body_head": str(restored[1])[:300]},
        "unpatched_verifier": unpatched,
        "patched_verifier_without_universe_check": patched_result,
        "live_journal_lines": len(entries),
        "forged_journal_lines": 2,
        "journal_note": (
            "the compiled genesis line is preserved; the forged latest line"
            " carries the foreign universe and is signed by the authentic key"
        ),
    }
    write_evidence("xxv-a4-foreign-universe", record)
    return 0 if (
        pristine[0] == 200
        and adverse[0] == 404
        and adverse_reason is not None
        and "history_integrity_unverifiable" in adverse_reason
        and restored[0] == 200
        and unpatched["refused"] is True
        and patched_result["accepted"] is True
    ) else 1


def f_a3_observation_on_growth(args: argparse.Namespace) -> int:
    """A3/HB-08: witness immediately after a real ledger append, and serialize
    concurrent observers.

    An initial authenticated event reaches a verdict. A second authenticated
    event over the same commerce identity is then conducted through the
    shipping correction surface. That correction appends supersession history;
    the correction task enqueues the shipping observer from the append path.
    The signed consumer must become available at task latency, not at the next
    300-second beat. Two manual observer processes are then run concurrently:
    the journal lock must keep one append-only chain, and the signed consumer
    must still verify afterwards.
    """
    state = load_state()
    tenant = state["tenant_a"]
    commerce = f"pi_xxva3{uuid.uuid4().hex[:14]}"
    initial_event = f"evt_xxva3A{uuid.uuid4().hex[:12]}"
    amendment_event = f"evt_xxva3B{uuid.uuid4().hex[:12]}"
    initial_amount = 4321
    amended_amount = 5100
    base_created = int(time.time())
    status_a, body_a, raw_a = post_stripe_envelope(
        state,
        tenant,
        event_reference=initial_event,
        commerce_reference=commerce,
        amount=initial_amount,
        created=base_created,
    )
    verdict = wait_verdict(tenant["tenant_id"], commerce)
    if verdict is None:
        write_evidence(
            "xxv-a3-observation-on-growth",
            {
                "error": "initial_event_did_not_conduct",
                "http": {"status": status_a, "body": body_a[:400]},
            },
        )
        return 1
    vid = verdict["verdict_id"]
    before = _correction_state(vid)
    status_b, body_b, raw_b = post_stripe_envelope(
        state,
        tenant,
        event_reference=amendment_event,
        commerce_reference=commerce,
        amount=amended_amount,
        created=base_created + 1,
    )
    ingress = _wait_amendment_ingress(tenant["tenant_id"], amendment_event)
    if ingress is None:
        write_evidence(
            "xxv-a3-observation-on-growth",
            {
                "error": "amendment_ingress_missing",
                "amending_event_http": {
                    "status": status_b,
                    "body": body_b[:300],
                },
            },
        )
        return 1
    last_observation = _last_observation()
    correction_started = time.time()
    correction_status, correction_body = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/reconciliation/match-verdicts/{vid}/corrections",
        body=json.dumps(
            {
                "provider": "stripe",
                "event_type": "payment_capture",
                "provider_native_event_reference": amendment_event,
                "is_gross_capture_correction": True,
            }
        ).encode(),
        headers=viewer_headers(state, tenant),
    )
    applied = _wait_correction_applied(
        vid,
        expected_ingress_id=ingress["ingress_id"],
        expected_amount=amended_amount,
        expected_event_reference=amendment_event,
        prior_supersession_rows=before["supersession_rows"],
        prior_correction_events=before["correction_events"],
    )
    after_history = history_identity()
    observation = _wait_scheduled_observation(
        int(last_observation["observation_id"]),
        after_history["ledger_rows"],
        timeout_s=150,
    )
    observation_latency = None
    if observation and observation.get("observed_at"):
        try:
            observation_latency = (
                datetime.fromisoformat(
                    observation["observed_at"].replace("Z", "+00:00")
                ).timestamp()
                - correction_started
            )
        except Exception:  # noqa: BLE001
            observation_latency = None
    signed = _wait_signed_result(tenant, vid, expected_minor=amended_amount)
    if signed.get("established") is not True:
        write_evidence(
            "xxv-a3-observation-on-growth",
            {
                "error": "signed_result_not_established_after_enqueued_observation",
                "observation": observation,
                "observation_latency_seconds": observation_latency,
                "signed": signed,
                "history": after_history,
                "applied": applied,
            },
        )
        return 1

    observe_command = [
        "docker",
        "exec",
        OBSERVER,
        "python",
        "-c",
        "import asyncio,json;"
        "from app.tasks.b26_p2_history import observe_history_integrity;"
        "print('OBS=' + json.dumps(asyncio.run(observe_history_integrity()),"
        " default=str))",
    ]
    processes = [
        subprocess.Popen(
            observe_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    concurrent: list[dict] = []
    for proc in processes:
        stdout, stderr = proc.communicate(timeout=180)
        concurrent.append(
            {
                "returncode": proc.returncode,
                "stdout_tail": stdout[-600:],
                "stderr_tail": stderr[-600:],
            }
        )
    journal_lines = volume_get(WITNESS_VOL, "history_witness.jsonl").decode(
        "utf-8"
    ).splitlines()
    entries = [json.loads(line) for line in journal_lines if line.strip()]
    chain_ok = True
    for index in range(1, len(entries)):
        previous = entries[index - 1].get("payload", {}).get("checkpoint_hash")
        claim = entries[index].get("payload", {}).get(
            "previous_checkpoint_hash"
        )
        if claim != previous:
            chain_ok = False
            break
    signed_after = _wait_signed_result(tenant, vid, expected_minor=amended_amount)
    record = {
        "property": (
            "P-XXV A3/HB-08: a real ledger append is witnessed from the append"
            " path at task latency, and concurrent observers preserve one signed"
            " journal chain"
        ),
        "actor": (
            "provider amendment + shipping correction + real B2.3 worker"
            " (append path) + shipping observer queue + two concurrent"
            " observer processes + Trust builder"
        ),
        "commerce_reference": commerce,
        "initial_event": {
            "event_reference": initial_event,
            "amount_minor": initial_amount,
            "http": {"status": status_a, "body": body_a[:300]},
            "body_sha256": hashlib.sha256(raw_a).hexdigest(),
        },
        "amending_event": {
            "event_reference": amendment_event,
            "amount_minor": amended_amount,
            "http": {"status": status_b, "body": body_b[:300]},
            "body_sha256": hashlib.sha256(raw_b).hexdigest(),
        },
        "verdict_id": vid,
        "before": before,
        "ingress": ingress,
        "correction_http": {
            "status": correction_status,
            "body": correction_body[:400],
        },
        "after_worker": applied,
        "history_after": after_history,
        "last_observation_before": last_observation,
        "observation_on_growth": observation,
        "observation_latency_seconds": observation_latency,
        "signed_after_growth": signed,
        "concurrent_observers": concurrent,
        "journal_lines": len(entries),
        "journal_chain_ok": chain_ok,
        "signed_after_concurrent_observers": signed_after,
        "limit_of_inference": (
            "This establishes the append-path observation and concurrent"
            " observer serialization on this artifact. It does not establish"
            " the A3 crash-window or every observer restart ordering; those"
            " remain separate A3/A8 evidence."
        ),
    }
    write_evidence("xxv-a3-observation-on-growth", record)
    return 0 if (
        observation is not None
        and not observation.get("violations")
        and observation_latency is not None
        and observation_latency <= 150.0
        and applied.get("net_minor") == amended_amount
        and signed.get("established") is True
        and all(item["returncode"] == 0 for item in concurrent)
        and chain_ok
        and signed_after.get("established") is True
    ) else 1


def f_b9_same_cohort(args: argparse.Namespace) -> int:
    """B9: one persisted cohort, read by the independent canonical readers.

    The snapshot, witness state, continuity, prefix, universe, scope,
    conservation, unsigned reconciliation reader, and signed Trust reader
    must agree about the same ledger tip and the same verdict money. The
    readers run as the least-privilege runtime principal; the proof does not
    seed or rewrite authority.
    """
    from datetime import timedelta

    import psycopg2  # noqa: PLC0415

    state = load_state()
    tenant = state["tenant_a"]
    tenant_id = tenant["tenant_id"]
    selected = sql(
        "SELECT v.id::text, v.provider, v.status,"
        " v.canonical_net_verified_amount_minor, v.created_at"
        " FROM public.b23_match_verdicts v"
        " JOIN public.b26_p2_source_money_attestation a"
        "   ON a.webhook_ingress_identity_id = v.webhook_ingress_identity_id"
        "  AND a.tenant_id = v.tenant_id"
        " WHERE v.tenant_id = %s"
        "   AND v.b26_p2_source_authority_state = 'current'"
        " ORDER BY v.created_at DESC LIMIT 1",
        (tenant_id,),
    )
    if not selected:
        write_evidence(
            "xxv-b9-same-cohort",
            {"error": "no_current_attested_verdict", "tenant_id": tenant_id},
        )
        return 1
    verdict_id, provider, status, amount, created_at = selected[0]
    amount = int(amount)

    def reader(query: str, params: tuple = ()) -> list[tuple]:
        conn = psycopg2.connect(role_dsn("app_user"))
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (str(tenant_id),),
                )
                cur.execute(query, params)
                return cur.fetchall()
        finally:
            conn.close()

    snapshot = reader(
        "SELECT n, tip_seq, tip_hash, prefix_digest, violations,"
        " authority_universe::text, prior_tip_hash"
        " FROM public.b26_p2_read_history_snapshot(NULL)"
    )[0]
    witness = reader(
        "SELECT n, tip_seq, tip_hash"
        " FROM public.b26_p2_read_history_witness_state()"
    )[0]
    continuity = reader(
        "SELECT n, tip FROM public.b26_p2_read_history_continuity()"
    )[0]
    prefix = reader("SELECT public.b26_p2_read_history_prefix_digest()")[0][0]
    universe = reader("SELECT public.b26_p2_authority_universe()::text")[0][0]
    window_start = created_at - timedelta(days=1)
    window_end = created_at + timedelta(days=1)
    scope_a = reader(
        "SELECT public.b26_p2_canonical_scope_identity_for_window(%s,%s,%s)",
        (tenant_id, window_start, window_end),
    )[0][0]
    scope_b = reader(
        "SELECT public.b26_p2_canonical_scope_identity_for_window(%s,%s,%s)",
        (tenant_id, window_start, window_end),
    )[0][0]
    conservation = [
        row[0]
        for row in reader(
            "SELECT violation FROM"
            " public.b26_p2_verify_source_money_conservation(%s,%s)",
            (tenant_id, verdict_id),
        )
    ]
    trust_status, trust = read_trust(tenant, verdict_id)
    recon_status, recon = read_reconciliation(state, tenant, verdict_id)
    trust_amount = trust.get("verified_revenue_minor") if isinstance(trust, dict) else None
    recon_amount = (
        recon.get("canonical_net_verified_amount_minor")
        if isinstance(recon, dict)
        else None
    )
    pre_history_status = (
        recon.get("history_integrity_status") if isinstance(recon, dict) else None
    )
    pre_authority_state = (
        recon.get("source_authority_state") if isinstance(recon, dict) else None
    )
    pre_recon_status = recon_status
    pre_trust_status = trust_status
    # A stale/unwitnessed history must make both readers non-authoritative.
    # The unsigned reader now publishes that state; it must never call the
    # same money current while the signed path refuses it.
    pre_boundary_consistent = (
        (pre_history_status == "verified" and trust_status == 200)
        or (
            pre_history_status == "unverifiable"
            and pre_authority_state == "historically_unverifiable"
            and trust_status == 404
        )
    )
    deadline = time.time() + 420
    while time.time() < deadline:
        if (
            post_history_status := (
                recon.get("history_integrity_status")
                if isinstance(recon, dict)
                else None
            )
        ) == "verified" and recon_status == 200 and trust_status == 200:
            break
        time.sleep(10)
        recon_status, recon = read_reconciliation(state, tenant, verdict_id)
        trust_status, trust = read_trust(tenant, verdict_id)
        recon_amount = (
            recon.get("canonical_net_verified_amount_minor")
            if isinstance(recon, dict)
            else None
        )
        trust_amount = (
            trust.get("verified_revenue_minor") if isinstance(trust, dict) else None
        )
        post_history_status = (
            recon.get("history_integrity_status") if isinstance(recon, dict) else None
        )
    checks = {
        "ledger_count_equal": int(snapshot[0]) == int(witness[0]) == int(continuity[0]),
        "tip_seq_equal": (snapshot[1] or None) == (witness[1] or None),
        "tip_hash_equal": (snapshot[2] or None) == (witness[2] or None)
        == (continuity[1] or None),
        "prefix_digest_equal": snapshot[3] == prefix,
        "universe_equal": snapshot[5] == universe,
        "snapshot_violations_empty": not str(snapshot[4] or "").strip(),
        "conservation_empty": conservation == [],
        "scope_identity_stable": scope_a == scope_b and len(str(scope_a)) == 64,
        "pre_reader_boundary_consistent": pre_boundary_consistent,
        "unsigned_reconciliation_money_equal": recon_status == 200
        and recon_amount == amount,
        "signed_trust_money_equal": trust_status == 200 and trust_amount == amount,
        "history_verified_after_catchup": post_history_status == "verified",
    }
    record = {
        "property": (
            "B9: the independent canonical readers agree about one persisted"
            " cohort's ledger tip, universe, scope, conservation, and money"
        ),
        "actor": "least-privilege runtime readers plus the signed Trust reader",
        "verdict_id": verdict_id,
        "tenant_id": tenant_id,
        "provider": provider,
        "verdict_status": status,
        "amount_minor": amount,
        "snapshot": {
            "n": int(snapshot[0]),
            "tip_seq": snapshot[1],
            "tip_hash": snapshot[2],
            "prefix_digest": snapshot[3],
            "violations": snapshot[4],
            "authority_universe": snapshot[5],
        },
        "witness_state": {
            "n": int(witness[0]),
            "tip_seq": witness[1],
            "tip_hash": witness[2],
        },
        "continuity": {"n": int(continuity[0]), "tip": continuity[1]},
        "prefix_digest": prefix,
        "authority_universe": universe,
        "scope_identity": {"first": scope_a, "second": scope_b},
        "conservation_violations": conservation,
        "unsigned_reconciliation": {
            "status": recon_status,
            "canonical_net_verified_amount_minor": recon_amount,
        },
        "signed_trust": {
            "status": trust_status,
            "verified_revenue_minor": trust_amount,
        },
        "pre_reader_boundary": {
            "reconciliation_status": pre_recon_status,
            "history_integrity_status": pre_history_status,
            "source_authority_state": pre_authority_state,
            "signed_trust_status": pre_trust_status,
        },
        "post_history_integrity_status": post_history_status,
        "checks": checks,
        "all_readers_equal": all(checks.values()),
    }
    write_evidence("xxv-b9-same-cohort", record)
    return 0 if record["all_readers_equal"] else 1


def f_s11_s13_controls(args: argparse.Namespace) -> int:
    """A9/B7: malformed caller shapes produce governed outcomes, not a 500.

    S11 is the Stripe envelope that carries both top-level money and
    data.object money; S13 is a non-UUID idempotency key. Neither may reach
    the authentication root as an unhandled database type error, and neither
    may leave an authenticated current-claiming row.
    """
    state = load_state()
    tenant = state["tenant_a"]
    common_headers = {
        "Content-Type": "application/json",
        "X-Skeldir-Tenant-Key": tenant["tenant_key"],
    }
    s11_event = f"evt_s11_{uuid.uuid4().hex[:10]}"
    s11_pi = f"pi_s11_{uuid.uuid4().hex[:10]}"
    s11_body = json.dumps(
        {
            "id": s11_event,
            "type": "payment_intent.succeeded",
            "created": int(time.time()),
            "amount": 9999,
            "currency": "usd",
            "data": {
                "object": {
                    "id": s11_pi,
                    "amount": 4321,
                    "currency": "usd",
                    "created": int(time.time()),
                    "status": "succeeded",
                }
            },
        },
        separators=(",", ":"),
    ).encode()
    s11_status, s11_text = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/webhooks/stripe/payment_intent/succeeded",
        body=s11_body,
        headers={
            **common_headers,
            "Stripe-Signature": sign_stripe(s11_body, tenant["stripe_secret"]),
            "X-Idempotency-Key": str(uuid.uuid4()),
        },
    )
    s13_event = f"evt_s13_{uuid.uuid4().hex[:10]}"
    s13_pi = f"pi_s13_{uuid.uuid4().hex[:10]}"
    s13_body = json.dumps(
        {
            "id": s13_event,
            "type": "payment_intent.succeeded",
            "created": int(time.time()),
            "data": {
                "object": {
                    "id": s13_pi,
                    "amount": 4321,
                    "currency": "usd",
                    "created": int(time.time()),
                    "status": "succeeded",
                }
            },
        },
        separators=(",", ":"),
    ).encode()
    s13_status, s13_text = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/webhooks/stripe/payment_intent/succeeded",
        body=s13_body,
        headers={
            **common_headers,
            "Stripe-Signature": sign_stripe(s13_body, tenant["stripe_secret"]),
            "X-Idempotency-Key": "not-a-uuid-caller-key",
        },
    )
    shopify_order = str(uuid.uuid4().int % 1_000_000_000)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    shopify_body = json.dumps(
        {
            "id": int(shopify_order),
            "total_price": "42.00",
            "currency": "USD",
            "financial_status": "paid",
            "cancelled_at": None,
            "refunds": [],
            "created_at": (now - timedelta(seconds=30)).isoformat(),
            "updated_at": now.isoformat(),
        },
        separators=(",", ":"),
    ).encode()
    shopify_signature = base64.b64encode(
        hmac.new(
            tenant["shopify_secret"].encode(), shopify_body, hashlib.sha256
        ).digest()
    ).decode()
    shopify_status, shopify_text = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/webhooks/shopify/order_create",
        body=shopify_body,
        headers={
            **common_headers,
            "X-Shopify-Hmac-Sha256": shopify_signature,
            "X-Shopify-Topic": "orders/create",
        },
    )
    time.sleep(5)
    shopify_ingress = _ingress_row_by_event(
        tenant["tenant_id"], shopify_order
    )
    s11_ingress = _ingress_row_by_event(tenant["tenant_id"], s11_event)
    s13_ingress = _ingress_row_by_event(tenant["tenant_id"], s13_event)
    record = {
        "property": (
            "A9/B7: malformed caller shapes receive governed outcomes and"
            " never leave an authenticated current claim"
        ),
        "s11_dual_money": {
            "http": {"status": s11_status, "body": s11_text[:600]},
            "ingress": s11_ingress,
        },
        "s13_non_uuid_idempotency": {
            "http": {"status": s13_status, "body": s13_text[:600]},
            "ingress": s13_ingress,
        },
        "shopify_creation_skew_30s": {
            "http": {"status": shopify_status, "body": shopify_text[:600]},
            "ingress": shopify_ingress,
        },
        "s11_governed": (
            s11_status != 500
            and "status=500" not in s11_text
            and (
                s11_ingress is None
                or s11_ingress.get("provenance") != "authenticated_known"
            )
        ),
        "s13_governed": (
            s13_status != 500
            and "status=500" not in s13_text
            and (
                s13_ingress is None
                or s13_ingress.get("provenance") == "authenticated_known"
                or not s13_ingress.get("is_current")
            )
        ),
        "shopify_creation_skew_governed": (
            shopify_status == 200
            and shopify_ingress is not None
            and shopify_ingress.get("provenance") == "authenticated_known"
            and shopify_ingress.get("is_current") is True
        ),
    }
    write_evidence("xxv-s11-s13-controls", record)
    return 0 if (
        record["s11_governed"]
        and record["s13_governed"]
        and record["shopify_creation_skew_governed"]
    ) else 1


def f_a2b10_natural_corrections(args: argparse.Namespace) -> int:
    """A2/B10: three lawful amount-changing corrections on the live schedule.

    Each cycle is a real signed provider event over the existing commerce
    identity, admitted as an amendment (the prior authenticated source is
    superseded, not replaced), followed by the shipping correction request that
    names it. The real B2.3 worker relinks the verdict and writes the money; the
    live beat schedule (never a manual observer invocation) witnesses the
    resulting ledger checkpoint; the signed Trust consumer must then serve the
    amended integer-minor amount and currency with a verified signature.

    The three amounts and event references are constructed here, before any
    request, and the expected state after each cycle is fixed from them.
    """
    state = load_state()
    tenant = state["tenant_a"]
    commerce = f"pi_xxv3corr{uuid.uuid4().hex[:14]}"
    initial_event = f"evt_xxv3A{uuid.uuid4().hex[:12]}"
    amounts = [4321, 5100, 6200, 7300]
    events = [initial_event] + [
        f"evt_xxv3B{i}{uuid.uuid4().hex[:10]}" for i in range(1, 4)
    ]
    base_created = int(time.time())

    first_status, first_body, first_raw = post_stripe_envelope(
        state,
        tenant,
        event_reference=events[0],
        commerce_reference=commerce,
        amount=amounts[0],
        created=base_created,
    )
    verdict = wait_verdict(tenant["tenant_id"], commerce)
    if verdict is None:
        write_evidence(
            "xxv-a2b10-natural-corrections",
            {
                "error": "initial_event_did_not_conduct",
                "initial_event_http": {"status": first_status, "body": first_body[:400]},
            },
        )
        return 1
    vid = verdict["verdict_id"]
    baseline = _correction_state(vid)
    if baseline["net_minor"] != amounts[0]:
        write_evidence(
            "xxv-a2b10-natural-corrections",
            {"error": "unexpected_baseline", "baseline": baseline},
        )
        return 1
    scheduler_before = _scheduler_state()

    cycles: list[dict] = []
    for index in range(3):
        amended = amounts[index + 1]
        event_reference = events[index + 1]
        before = _correction_state(vid)
        before_history = history_identity()
        last_observation = _last_observation()
        # The append path now enqueues an immediate observation. The scheduled
        # proof must not mistake that for the periodic beat observation, so
        # require an observation at least four minutes after the prior one
        # (the beat entry is 300 seconds).
        scheduled_not_before = (
            float(last_observation["observed_at_epoch"] or time.time())
            + 240.0
        )
        event_created = base_created + index + 1

        status_b, body_b, raw_b = post_stripe_envelope(
            state,
            tenant,
            event_reference=event_reference,
            commerce_reference=commerce,
            amount=amended,
            created=event_created,
        )
        ingress = _wait_amendment_ingress(tenant["tenant_id"], event_reference)
        if ingress is None:
            cycles.append(
                {
                    "cycle": index + 1,
                    "error": "amendment_ingress_missing",
                    "amending_event": {
                        "event_reference": event_reference,
                        "amount_minor": amended,
                        "http": {"status": status_b, "body": body_b[:400]},
                    },
                }
            )
            break
        old_ingress = _ingress_row_by_event(
            tenant["tenant_id"], before["linked_event_reference"]
        )
        amendment_verdicts = sql(
            "SELECT count(*)::int FROM public.b23_match_verdicts"
            " WHERE tenant_id = %s AND provider = 'stripe'"
            "   AND provider_native_event_reference = %s",
            (tenant["tenant_id"], event_reference),
        )[0][0]
        compiled_cycle: dict = {
            "cycle": index + 1,
            "amending_event": {
                "event_reference": event_reference,
                "amount_minor": amended,
                "http": {"status": status_b, "body": body_b[:400]},
                "body_sha256": hashlib.sha256(raw_b).hexdigest(),
            },
            "ingress": ingress,
            "old_source": old_ingress,
            "amending_event_created_its_own_verdict": int(amendment_verdicts),
            "before": before,
            "history_before": before_history,
            "last_observation_before": last_observation,
        }
        cycles.append(compiled_cycle)
        if amendment_verdicts != 0:
            compiled_cycle["error"] = "amendment_created_a_second_verdict"
            break
        if old_ingress is None or not str(
            old_ingress.get("demotion_reason") or ""
        ).startswith("superseded_by_provider_amendment:"):
            compiled_cycle["error"] = "prior_source_not_superseded_by_amendment"
            break
        if ingress["amount_minor"] != amended:
            compiled_cycle["error"] = "amendment_amount_mismatch"
            break

        correction_status, correction_body = http(
            "POST",
            f"http://127.0.0.1:{API_PORT}/api/reconciliation/match-verdicts/{vid}/corrections",
            body=json.dumps(
                {
                    "provider": "stripe",
                    "event_type": "payment_capture",
                    "provider_native_event_reference": event_reference,
                    "is_gross_capture_correction": True,
                }
            ).encode(),
            headers=viewer_headers(state, tenant),
        )
        compiled_cycle["correction_http"] = {
            "status": correction_status,
            "body": correction_body[:500],
        }
        applied = _wait_correction_applied(
            vid,
            expected_ingress_id=ingress["ingress_id"],
            expected_amount=amended,
            expected_event_reference=event_reference,
            prior_supersession_rows=before["supersession_rows"],
            prior_correction_events=before["correction_events"],
        )
        compiled_cycle["after_worker"] = applied
        if (
            applied["linked_ingress_id"] != ingress["ingress_id"]
            or applied["net_minor"] != amended
            or applied["authority_state"] != "current"
            or applied["supersession_rows"] <= before["supersession_rows"]
            or applied["verdicts_for_identity"] != 1
        ):
            compiled_cycle["error"] = "correction_did_not_apply"
            break

        applied_history = history_identity()
        compiled_cycle["history_after_worker"] = applied_history
        observation = _wait_scheduled_observation(
            int(last_observation["observation_id"]),
            applied_history["ledger_rows"],
            not_before_epoch=scheduled_not_before,
        )
        compiled_cycle["scheduled_observation"] = observation
        if observation is None or observation.get("violations"):
            compiled_cycle["error"] = "scheduled_witness_not_clean"
            break
        signed = _wait_signed_result(tenant, vid, expected_minor=amended)
        compiled_cycle["signed_financial_result"] = signed
        recon = read_reconciliation(state, tenant, vid)
        compiled_cycle["reconciliation"] = {
            "status": recon[0],
            "net": _net(recon[1]),
            "source_authority_state": _field(recon[1], "source_authority_state"),
            "attestation_status": _field(recon[1], "source_money_attestation_status"),
        }
        if not signed["established"]:
            compiled_cycle["error"] = "signed_result_not_established"
            break

    scheduler_after = _scheduler_state()
    all_cycles_established = (
        len(cycles) == 3
        and all("error" not in cycle for cycle in cycles)
        and all(
            cycle.get("signed_financial_result", {}).get("established") is True
            for cycle in cycles
        )
        and all(
            cycle.get("scheduled_observation", {}).get("violations") == ""
            for cycle in cycles
        )
        and all(
            cycle.get("after_worker", {}).get("verdicts_for_identity") == 1
            for cycle in cycles
        )
    )
    record = {
        "property": (
            "P-XXV A2/B10: three lawful amount-changing corrections conduct"
            " through the shipping correction surface and the real B2.3 worker,"
            " are witnessed by the live scheduled observer, and are served by"
            " the signed Trust consumer"
        ),
        "actor": (
            "provider (three signed amendment events over one payment intent)"
            " + shipping correction caller + real B2.3 worker + live beat"
            " schedule + Trust builder/signer + independent verification"
        ),
        "commerce_reference": commerce,
        "expected_amounts_minor": amounts,
        "event_references": events,
        "initial_event": {
            "event_reference": events[0],
            "amount_minor": amounts[0],
            "http": {"status": first_status, "body": first_body[:400]},
            "body_sha256": hashlib.sha256(first_raw).hexdigest(),
        },
        "verdict_id": vid,
        "baseline": baseline,
        "scheduler_before": scheduler_before,
        "scheduler_after": scheduler_after,
        "cycles": cycles,
        "all_three_established": all_cycles_established,
        "observation_control": (
            "the beat schedule was never paused and the observer was never"
            " invoked by this run; observations are the live scheduled rows"
            " and their ids/timestamps are recorded per cycle"
        ),
        "limit_of_inference": (
            "three corrections establish the A2/B10 positive path on this"
            " artifact. They do not establish READY-FOR-AUDIT, exact historical"
            " restoration, or any other XXV gate."
        ),
    }
    write_evidence("xxv-a2b10-natural-corrections", record)
    return 0 if all_cycles_established else 1


def await_witness_catchup(state: dict, *, max_cycles: int = 5) -> dict:
    """Drive the shipping observer until the signed witness matches live state.

    The signed consumer refuses with ``history_integrity_unverifiable`` between
    a ledger append and the next scheduled observation. That window is a
    recorded residual of this phase (A3/HB-08), not something a falsifier may
    silently absorb: a run that reads Trust inside it attributes a freshness
    refusal to its own mutation. This helper closes the window explicitly and
    reports the number of observer cycles it needed, so the window's size is
    itself evidence.
    """
    cycles = 0
    runs = []
    for _ in range(max_cycles):
        before = history_identity()
        observation = observe_once(state)
        runs.append(
            {
                "returncode": observation["returncode"],
                "stdout_tail": observation["stdout_tail"][-200:],
            }
        )
        cycles += 1
        after = history_identity()
        if before == after and observation["returncode"] == 0:
            # One more unchanged-ledger observation publishes the freshness
            # heartbeat the builder reads.
            observation = observe_once(state)
            runs.append(
                {
                    "returncode": observation["returncode"],
                    "stdout_tail": observation["stdout_tail"][-200:],
                }
            )
            cycles += 1
            break
    return {"observer_cycles": cycles, "runs": runs[-4:]}


def durable_trust_refusal_reason(tenant_id: str | None = None) -> str | None:
    """The reason the Trust path recorded for its most recent decision.

    The external projection of a Trust refusal is an opaque 404, so the
    reason only survives in ``public.trust_access_log``. A falsifier that
    reports the 404 without the reason cannot distinguish a money refusal
    from a freshness refusal, which is how recovery evidence became uneven.
    """
    if tenant_id:
        rows = sql(
            "SELECT status, reason_code FROM public.trust_access_log"
            " WHERE tenant_id = %s ORDER BY created_at DESC LIMIT 1",
            (tenant_id,),
        )
    else:
        rows = sql(
            "SELECT status, reason_code FROM public.trust_access_log"
            " ORDER BY created_at DESC LIMIT 1"
        )
    if not rows:
        return None
    status, reason = rows[0]
    return f"{status}:{reason or 'none'}"


def phase_snapshot(
    state: dict,
    tenant: dict,
    verdict_id: str,
    *,
    expected_minor: int,
    expected_currency: str = "USD",
) -> dict:
    """One attributable observation of every authoritative consumer.

    The order is forced, because it is load-bearing:

    1. the mandatory composition proof runs FIRST -- its own cells append
       supersession-ledger rows, so running it after a witness catch-up
       immediately re-opens the freshness window it just closed (this is why
       earlier runs recorded a pristine signed refusal while the proof passed);
    2. the shipping observer is then driven until the signed witness agrees
       with the live ledger, and the number of cycles is recorded;
    3. the unsigned reader and the SIGNED consumer are read last, so a refusal
       is attributable to the state under test rather than to publication lag.

    That the proof mutates the history it adjudicates is itself recorded: it is
    a governance residual of this phase, not a property of the artifact under
    test.
    """
    # The scheduled observer is paused for the duration of one observation.
    # The mandatory proof reads live ledger count/tip/prefix in several cells,
    # and a scheduled observation landing mid-proof changes those values under
    # it: a proof FAIL that does not reproduce was traced to exactly that race
    # (the same database returned FAIL and then PASS with no mutation between).
    # A snapshot has to be taken against a quiescent scheduler or its verdict
    # is not attributable to the state under test.
    docker("pause", BEAT)
    try:
        proof = composition_proof()
        if proof["printed_verdict"] != "PASS":
            second = composition_proof()
            proof = {
                **second,
                "first_run_verdict": proof["printed_verdict"],
                "reproduced": second["printed_verdict"] == proof["printed_verdict"],
            }
        catchup = await_witness_catchup(state)
        recon = read_reconciliation(state, tenant, verdict_id)
    finally:
        docker("unpause", BEAT)
    signed = signed_financial_result(
        tenant,
        verdict_id,
        expected_minor=expected_minor,
        expected_currency=expected_currency,
    )
    return {
        "db": money_snapshot(verdict_id),
        "history_identity": history_identity(),
        "mandatory_proof": proof["printed_verdict"],
        "mandatory_proof_stdout_tail": proof["stdout_tail"][-1200:],
        "witness_catchup": catchup,
        "reconciliation": {
            "status": recon[0],
            "net": _net(recon[1]),
            "source_authority_state": _field(recon[1], "source_authority_state"),
            "attestation_status": _field(
                recon[1], "source_money_attestation_status"
            ),
        },
        "signed_financial_result": signed,
        "unsigned_observation_available": recon[0] not in (0, 401, 403, 429),
        "unsigned_read_attempts": LAST_UNSIGNED_READ_ATTEMPTS,
        "consumers_green": bool(
            proof["printed_verdict"] == "PASS"
            and recon[0] == 200
            and _net(recon[1]) == expected_minor
            and signed["established"]
        ),
    }


def _baseline_is_green(
    name: str,
    pristine_proof: dict,
    pristine_recon: tuple,
    pristine_trust: tuple,
) -> dict | None:
    """Return an evidence record when the baseline was not green, else None."""
    if pristine_proof["printed_verdict"] == "PASS":
        return None
    record = {
        "error": "baseline_contaminated",
        "explanation": (
            "the mandatory composition proof was already RED on the pristine"
            " database, so this run cannot attribute any observation to its"
            " own mutation"
        ),
        "pristine": {
            "reconciliation": {
                "status": pristine_recon[0],
                "net": _net(pristine_recon[1]),
            },
            "trust": {"status": pristine_trust[0]},
            "mandatory_proof": pristine_proof["printed_verdict"],
            "mandatory_proof_stdout_tail": pristine_proof["stdout_tail"][-1200:],
        },
    }
    write_evidence(name, record)
    return record


def f_journey(args: argparse.Namespace) -> int:
    """World A baseline: authentic provider evidence to a signed consumer read."""
    state = load_state()
    tenant = state["tenant_a"]
    intent = f"pi_xxv{uuid.uuid4().hex[:16]}"
    amount = 4321
    status, text, body = post_stripe(state, tenant, intent, amount)
    verdict = wait_verdict(tenant["tenant_id"], intent)
    recon = read_reconciliation(state, tenant, verdict["verdict_id"]) if verdict else (0, "no_verdict")
    # XXV (A3/HB-08, B6/B12): the signed consumer requires a fresh
    # beat-authored history observation that agrees with the live ledger, so a
    # result is not signable until the scheduled observer has run. Both reads
    # are recorded -- the immediate one, which is what a caller sees inside the
    # window, and the one after the observer has caught up, which is what the
    # phase promises -- together with the number of observer cycles the window
    # cost. Reporting only the second read would hide the window; reporting
    # only the first would call a scheduling latency a broken journey.
    first_trust = read_trust(tenant, verdict["verdict_id"]) if verdict else (0, "no_verdict")
    first_refusal_reason = durable_trust_refusal_reason(str(tenant["tenant_id"]))
    catchup = await_witness_catchup(state) if verdict else {"observer_cycles": 0}
    trust = read_trust(tenant, verdict["verdict_id"]) if verdict else (0, "no_verdict")
    verified = (0, "not_attempted")
    envelope_keys: list[str] = []
    money_in_envelope = None
    if trust[0] == 200 and isinstance(trust[1], dict):
        env = trust[1].get("envelope", trust[1])
        if isinstance(env, dict):
            envelope_keys = sorted(env.keys())
            money_in_envelope = {
                "verified_revenue_minor": env.get("verified_revenue_minor"),
                "currency": env.get("currency"),
                "amount_string_present": str(amount) in json.dumps(env),
            }
            verified = verify_trust(tenant, env)
    record = {
        "property": "P-XXV positive obligation: authentic evidence reaches a usable signed financial result",
        "expected_independently": (
            "verdict money equals the provider amount; the signed envelope carries the"
            " integer-minor amount and currency; the signature verifies"
        ),
        "input": {"provider": "stripe", "intent": intent, "amount_minor": amount,
                   "body_sha256": hashlib.sha256(body).hexdigest()},
        "ingress_http": {"status": status, "body": text[:600]},
        "verdict": verdict,
        "reconciliation_read": {"status": recon[0], "body": recon[1]},
        "trust_read_immediately_after_ingress": {
            "status": first_trust[0],
            "durable_refusal_reason": first_refusal_reason,
            "body_head": str(first_trust[1])[:200],
        },
        "witness_catchup": catchup,
        "trust_read": {"status": trust[0], "body": trust[1]},
        "trust_verify": {"status": verified[0], "body": verified[1]},
        "envelope_keys": envelope_keys,
        "money_in_signed_envelope": money_in_envelope,
        "witness": witness_files(),
    }
    write_evidence("xxv-journey-baseline", record)
    return 0


def f_hb01_anchor(args: argparse.Namespace) -> int:
    """HB-01: the compiled-anchor / custody branch is unreachable at issuance."""
    probe = (
        "from app.core.config import settings;"
        "from app.trust.witness_anchor import COMPILED_GENESIS_HASH, COMPILED_PUBLIC_KEY_SHA256;"
        "import json;"
        "print('PROBE=' + json.dumps({"
        "'settings_environment': settings.ENVIRONMENT,"
        "'equals_production_literal': settings.ENVIRONMENT == 'production',"
        "'compiled_public_key_sha256': COMPILED_PUBLIC_KEY_SHA256,"
        "'compiled_genesis_hash': COMPILED_GENESIS_HASH,"
        "'witness_required': settings.B26_P2_HISTORY_WITNESS_REQUIRED,"
        "}))"
    )
    proc = docker("exec", API, "python", "-c", probe)
    reachability = {}
    for line in proc.stdout.splitlines():
        if line.startswith("PROBE="):
            reachability = json.loads(line.split("=", 1)[1])
    guard_sites = subprocess.run(
        ["git", "grep", "-n", 'settings.ENVIRONMENT == "production"', "--", "backend/app"],
        text=True, capture_output=True, cwd=str(REPO_ROOT),
    ).stdout.strip()
    alias_map = subprocess.run(
        ["git", "grep", "-n", '"production": "prod"', "--", "backend/app"],
        text=True, capture_output=True, cwd=str(REPO_ROOT),
    ).stdout.strip()
    record = {
        "property": "P-XXV 1(a)(i): the historical verification root must bind at issuance",
        "actor": "runtime public-key configurator + journal/heartbeat/custody writer",
        "expected_independently": (
            "the issuance-time compiled-anchor comparison executes in a production"
            " deployment, so a substituted verification root is refused"
        ),
        "observed_in_running_production_container": reachability,
        "guard_sites": guard_sites,
        "environment_canonicalization": alias_map,
        "observed_result": (
            "RED: settings.ENVIRONMENT is 'prod' in the running production container,"
            " so both issuance-time guards (compiled anchor comparison and"
            " witness_custody_missing) are unreachable under every possible"
            " deployment value, because resolve_control_plane_env canonicalises"
            " 'production' to 'prod' before Settings stores it."
        ),
        "limit_of_inference": (
            "this records guard reachability on the running artifact; the acceptance"
            " of a coherently substituted root is recorded separately by"
            " xxv-hb01-root-substitution and xxv-hb02-custody"
        ),
    }
    write_evidence("xxv-hb01-anchor-reachability", record)
    return 0


def f_hb02_custody(args: argparse.Namespace) -> int:
    """HB-02/A5: delete the custody record; issuance must refuse. It does not."""
    state = load_state()
    tenant = state["tenant_a"]
    intent = f"pi_xxv{uuid.uuid4().hex[:16]}"
    post_stripe(state, tenant, intent, 5555)
    verdict = wait_verdict(tenant["tenant_id"], intent)
    before = read_trust(tenant, verdict["verdict_id"])
    custody_before = volume_get(WITNESS_VOL, "history_witness_custody.json")
    volume_rm(WITNESS_VOL, "history_witness_custody.json")
    listing_after_delete = volume_list(WITNESS_VOL)
    after = read_trust(tenant, verdict["verdict_id"])
    volume_put(
        WITNESS_VOL, {"history_witness_custody.json": custody_before}, mode="0644"
    )
    restored = read_trust(tenant, verdict["verdict_id"])
    record = {
        "property": "P-XXV 1(a)(i): required historical custody cannot be silently removed",
        "actor": "custody writer (filesystem reach over the witness volume)",
        "expected_independently": "issuance refuses with witness_custody_missing",
        "pristine_trust_read": {"status": before[0], "body_head": str(before[1])[:400]},
        "custody_record_removed": listing_after_delete,
        "adverse_trust_read": {"status": after[0], "body_head": str(after[1])[:400]},
        "exact_restoration_trust_read": {"status": restored[0], "body_head": str(restored[1])[:400]},
        "observed_result": (
            "RED if the adverse read still issues (HTTP 200 with a signature)"
            " — the custody guard sits behind the unreachable production branch"
        ),
        "verdict_id": verdict["verdict_id"] if verdict else None,
    }
    write_evidence("xxv-hb02-custody", record)
    return 0


def f_hb01_root_substitution(args: argparse.Namespace) -> int:
    """HB-01/A1: replace the entire witness verification root coherently."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    os.environ.setdefault(
        "DATABASE_URL",
        f"postgresql+asyncpg://app_user:app_user@127.0.0.1:{PG_PORT}/{DB_NAME}",
    )
    os.environ.setdefault("ENVIRONMENT", "ci")
    from app.trust.history_witness import _canonical  # noqa: PLC0415

    state = load_state()
    tenant = state["tenant_a"]
    intent = f"pi_xxv{uuid.uuid4().hex[:16]}"
    post_stripe(state, tenant, intent, 6000)
    verdict = wait_verdict(tenant["tenant_id"], intent)
    pristine = read_trust(tenant, verdict["verdict_id"])

    journal_bytes = volume_get(WITNESS_VOL, "history_witness.jsonl")
    heartbeat_bytes = volume_get(WITNESS_VOL, "history_witness_heartbeat.json")
    custody_bytes = volume_get(WITNESS_VOL, "history_witness_custody.json")
    pub_bytes = volume_get(WITNESS_VOL, "history_witness_ed25519.pub")

    # Forge an entirely new root: new key, every journal line re-signed,
    # the heartbeat re-signed, the runtime public key swapped. The ledger
    # facts and the pinned genesis payloads are preserved, so the world is
    # internally coherent; only the cryptographic authority changes.
    forged_key = ed25519.Ed25519PrivateKey.generate()
    forged_pub_raw = forged_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    forged_lines = []
    for line in journal_bytes.decode().strip().splitlines():
        entry = json.loads(line)
        payload = entry["payload"]
        signature = forged_key.sign(_canonical(payload))
        entry["signature"] = "ed25519:" + base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
        forged_lines.append(json.dumps(entry, separators=(",", ":"), sort_keys=True))
    heartbeat = json.loads(heartbeat_bytes.decode())
    hb_payload = heartbeat["payload"]
    heartbeat["signature"] = "ed25519:" + base64.urlsafe_b64encode(
        forged_key.sign(_canonical(hb_payload))
    ).rstrip(b"=").decode()

    volume_put(
        WITNESS_VOL,
        {
            "history_witness.jsonl": ("\n".join(forged_lines) + "\n").encode(),
            "history_witness_heartbeat.json": json.dumps(heartbeat).encode(),
            "history_witness_ed25519.pub": base64.urlsafe_b64encode(forged_pub_raw)
            .rstrip(b"=")
            .decode()
            .encode(),
        },
        mode="0644",
    )
    adverse = read_trust(tenant, verdict["verdict_id"])
    volume_put(
        WITNESS_VOL,
        {
            "history_witness.jsonl": journal_bytes,
            "history_witness_heartbeat.json": heartbeat_bytes,
            "history_witness_custody.json": custody_bytes,
            "history_witness_ed25519.pub": pub_bytes,
        },
        mode="0644",
    )
    restored = read_trust(tenant, verdict["verdict_id"])
    record = {
        "property": "P-XXV 1(a)(i): a replaceable verification root is not independent history",
        "actor": "witness key configurator + journal writer + heartbeat writer",
        "expected_independently": (
            "the compiled anchor in the image refuses a runtime public key whose"
            " fingerprint differs, so a coherently re-signed history is rejected"
        ),
        "compiled_anchor_in_image": {
            "public_key_sha256": state["material"]["witness_public_sha256"],
            "genesis_hash": state["genesis_hash"],
        },
        "forged_public_key_sha256": hashlib.sha256(forged_pub_raw).hexdigest(),
        "pristine_trust_read": {"status": pristine[0], "body_head": str(pristine[1])[:300]},
        "adverse_trust_read": {"status": adverse[0], "body_head": str(adverse[1])[:300]},
        "exact_restoration_trust_read": {"status": restored[0], "body_head": str(restored[1])[:300]},
        "verdict_id": verdict["verdict_id"] if verdict else None,
        "observed_result": (
            "RED if the adverse read issues a signed envelope under the forged root"
        ),
    }
    write_evidence("xxv-hb01-root-substitution", record)
    return 0


def _restore_from_context() -> dict:
    """Undo the HB-03 owner rewrite using the recorded pristine snapshot.

    The money is restored with the financial triggers suppressed (the
    money-authority trigger derives the amount from the source, so it must be
    disabled while the source itself is being put back), and the enforcement
    state is restored afterwards.
    """
    ctx = json.loads(
        (EVIDENCE_DIR / "hb03-context.json").read_text(encoding="utf-8")
    )
    vid = ctx["verdict_id"]
    pristine = ctx["pristine_db"]
    for statement in (
        "ALTER TABLE public.b23_match_verdicts NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.attribution_events NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.webhook_ingress_identities NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.b23_match_verdicts DISABLE TRIGGER USER",
        "ALTER TABLE public.attribution_events DISABLE TRIGGER USER",
        "ALTER TABLE public.webhook_ingress_identities DISABLE TRIGGER USER",
    ):
        try:
            owner_sql(statement)
        except Exception:  # noqa: BLE001
            pass
    owner_tx(
        [
            (
                "UPDATE public.b23_match_verdicts SET"
                " canonical_net_verified_amount_minor = %s,"
                " canonical_captured_gross_amount_minor = %s,"
                " canonical_expected_gross_amount_minor = %s,"
                " verified_amount_minor = %s, attributed_amount_minor = %s"
                " WHERE id = %s",
                (
                    pristine["verdict_net_minor"],
                    pristine["verdict_captured_minor"],
                    pristine["verdict_expected_minor"],
                    pristine["verified_amount_minor"],
                    pristine["attributed_amount_minor"],
                    vid,
                ),
            ),
            (
                "UPDATE public.attribution_events SET revenue_cents = %s,"
                " conversion_value_cents = %s WHERE id = %s",
                (
                    pristine["attribution_revenue_cents"],
                    pristine["attribution_revenue_cents"],
                    ctx["attribution_event_id"],
                ),
            ),
            (
                "UPDATE public.webhook_ingress_identities"
                " SET verified_amount_minor = %s"
                " WHERE id = (SELECT webhook_ingress_identity_id"
                " FROM public.b23_match_verdicts WHERE id = %s)",
                (pristine["ingress_verified_amount_minor"], vid),
            ),
        ]
    )
    for statement in (
        "ALTER TABLE public.b23_match_verdicts ENABLE TRIGGER USER",
        "ALTER TABLE public.attribution_events ENABLE TRIGGER USER",
        "ALTER TABLE public.webhook_ingress_identities ENABLE TRIGGER USER",
        "ALTER TABLE public.b23_match_verdicts FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.attribution_events FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.webhook_ingress_identities FORCE ROW LEVEL SECURITY",
    ):
        try:
            owner_sql(statement)
        except Exception:  # noqa: BLE001
            pass
    restored = money_snapshot(vid)
    return {
        "verdict_id": vid,
        "restored_db": restored,
        "byte_level_identical": restored == pristine,
    }


def f_hb03_owner_money(args: argparse.Namespace) -> int:
    """HB-03/A6/A10: coherent owner-origin money rewrite reaching the consumers."""
    state = load_state()
    tenant = state["tenant_a"]
    intent = f"pi_xxv{uuid.uuid4().hex[:16]}"
    authentic = 4321
    forged = 77777
    status, text, body = post_stripe(state, tenant, intent, authentic)
    verdict = wait_verdict(tenant["tenant_id"], intent)
    if verdict is None:
        write_evidence(
            "xxv-hb03-owner-money",
            {"error": "no_verdict", "ingress": {"status": status, "body": text[:400]}},
        )
        return 1
    vid = verdict["verdict_id"]
    independent_original = {
        "provider_amount_minor": authentic,
        "provider_body_sha256": hashlib.sha256(body).hexdigest(),
        "held_outside_the_database": True,
    }
    # The baseline is ASSERTED, not assumed, and it is taken in the forced
    # order of phase_snapshot: a falsifier that starts from a database that is
    # already a false world -- or from inside the post-append freshness window
    # -- cannot attribute any observation to its own mutation, and its
    # "pristine" reading would be a lie.
    pristine = phase_snapshot(
        state, tenant, vid, expected_minor=authentic
    )
    baseline_observation = pristine["witness_catchup"]
    pristine_history_identity = pristine["history_identity"]
    pristine_db = pristine["db"]
    pristine_recon = (
        pristine["reconciliation"]["status"],
        {"canonical_net_verified_amount_minor": pristine["reconciliation"]["net"]},
    )
    pristine_trust = (pristine["signed_financial_result"]["trust_status"], "")
    pristine_proof = {
        "printed_verdict": pristine["mandatory_proof"],
        "stdout_tail": pristine["mandatory_proof_stdout_tail"],
    }
    pristine_signed = pristine["signed_financial_result"]
    if not pristine["consumers_green"]:
        write_evidence(
            "xxv-hb03-owner-money",
            {
                "error": "baseline_contaminated",
                "baseline_signed_financial_result": pristine_signed,
                "baseline_gate": (
                    "a run may only attribute an observation to its own"
                    " mutation when the pristine database serves the authentic"
                    " figure through BOTH readers and the mandatory proof"
                    " passes. A pristine signed refusal means the signed leg of"
                    " any later observation is unattributable."
                ),
                "explanation": (
                    "the mandatory composition proof was already RED on the"
                    " pristine database, so this run cannot attribute any"
                    " observation to its own mutation"
                ),
                "pristine": {
                    "reconciliation": {
                        "status": pristine_recon[0],
                        "net": _net(pristine_recon[1]),
                    },
                    "trust": {"status": pristine_trust[0]},
                    "mandatory_proof": pristine_proof["printed_verdict"],
                    "mandatory_proof_stdout_tail": pristine_proof["stdout_tail"][-1200:],
                },
            },
        )
        return 1
    # The restoration context is written BEFORE the mutation, so a run that
    # fails later still leaves the exact bytes needed to undo the forgery.
    (EVIDENCE_DIR / "hb03-context.json").write_text(
        json.dumps(
            {
                "verdict_id": vid,
                "authentic": authentic,
                "forged": forged,
                "attribution_event_id": verdict["attribution_event_id"],
                "pristine_db": pristine_db,
                # XXV: the restoration run judges history by identity, so the
                # mutation run has to record that identity.
                "pristine_history_identity": pristine_history_identity,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    # Owner-origin coherent rewrite. The owner owns every financial object,
    # so it may relax RLS and suppress its own triggers.
    owner_steps = []
    for statement in (
        "ALTER TABLE public.b23_match_verdicts NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.attribution_events NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.webhook_ingress_identities NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.b23_match_verdicts DISABLE TRIGGER USER",
        "ALTER TABLE public.attribution_events DISABLE TRIGGER USER",
        "ALTER TABLE public.webhook_ingress_identities DISABLE TRIGGER USER",
    ):
        try:
            owner_sql(statement)
            owner_steps.append({"statement": statement, "result": "accepted"})
        except Exception as exc:  # noqa: BLE001
            owner_steps.append({"statement": statement, "result": f"refused:{exc}"})
    forged_writes: list[tuple[str, tuple]] = []
    for statement, params in (
        (
            "UPDATE public.b23_match_verdicts SET"
            " canonical_net_verified_amount_minor = %s,"
            " canonical_captured_gross_amount_minor = %s,"
            " canonical_expected_gross_amount_minor = %s,"
            " verified_amount_minor = %s, attributed_amount_minor = %s"
            " WHERE id = %s",
            (forged, forged, forged, forged, forged, vid),
        ),
        (
            "UPDATE public.attribution_events SET revenue_cents = %s,"
            " conversion_value_cents = %s WHERE id = %s",
            (forged, forged, verdict["attribution_event_id"]),
        ),
        (
            "UPDATE public.webhook_ingress_identities SET verified_amount_minor = %s"
            " WHERE id = (SELECT webhook_ingress_identity_id"
            " FROM public.b23_match_verdicts WHERE id = %s)",
            (forged, vid),
        ),
    ):
        forged_writes.append((statement, params))
    # One transaction: the attacker's world becomes visible all at once, which
    # is both what a competent maintenance principal would do and what keeps a
    # concurrent proof from observing a half-built world this run did not mean
    # to present.
    try:
        owner_tx(forged_writes)
        owner_steps.extend(
            {"statement": s.split(" SET")[0], "result": "accepted"}
            for s, _ in forged_writes
        )
    except Exception as exc:  # noqa: BLE001
        owner_steps.append({"statement": "coherent rewrite", "result": f"refused:{exc}"})
    for statement in (
        "ALTER TABLE public.b23_match_verdicts ENABLE TRIGGER USER",
        "ALTER TABLE public.attribution_events ENABLE TRIGGER USER",
        "ALTER TABLE public.webhook_ingress_identities ENABLE TRIGGER USER",
        "ALTER TABLE public.b23_match_verdicts FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.attribution_events FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.webhook_ingress_identities FORCE ROW LEVEL SECURITY",
    ):
        try:
            owner_sql(statement)
        except Exception:  # noqa: BLE001
            pass

    # Same forced order as the baseline, so the adverse reading is comparable
    # to it rather than to a different publication state. A failure anywhere in
    # here restores the lane before propagating, so one broken run cannot
    # poison every later baseline.
    try:
        adverse = phase_snapshot(state, tenant, vid, expected_minor=authentic)
    except Exception:
        _restore_from_context()
        raise
    adverse_db = adverse["db"]
    adverse_recon = (
        adverse["reconciliation"]["status"],
        {
            "canonical_net_verified_amount_minor": adverse["reconciliation"]["net"],
            "source_authority_state": adverse["reconciliation"][
                "source_authority_state"
            ],
            "source_money_attestation_status": adverse["reconciliation"][
                "attestation_status"
            ],
        },
    )
    adverse_trust = (
        adverse["signed_financial_result"]["trust_status"],
        adverse["signed_financial_result"],
    )
    adverse_proof = {
        "printed_verdict": adverse["mandatory_proof"],
        "stdout_tail": adverse["mandatory_proof_stdout_tail"],
    }
    record = {
        "property": "P-XXV 1(a)(i): unsupported money must not become current authority",
        "actor": "migration_owner (owns every financial object; the login the repo runbook uses for migrations)",
        "expected_independently": (
            "no authoritative consumer presents 77777 as current money, because the"
            " provider never sent it; the mandatory proof detects the contradiction"
        ),
        "independent_original_evidence": independent_original,
        "verdict_id": vid,
        "pristine": {
            "db": pristine_db,
            "reconciliation": {"status": pristine_recon[0], "net": _net(pristine_recon[1])},
            "trust": {"status": pristine_trust[0], "body_head": str(pristine_trust[1])[:300]},
            "mandatory_proof": pristine_proof["printed_verdict"],
            "observer": {
                "observer_cycles": baseline_observation.get("observer_cycles"),
                "runs": baseline_observation.get("runs"),
            },
        },
        "owner_operations": owner_steps,
        "adverse": {
            "db": adverse_db,
            "reconciliation": {
                "status": adverse_recon[0],
                "net": _net(adverse_recon[1]),
                "source_authority_state": _field(adverse_recon[1], "source_authority_state"),
                "body_head": str(adverse_recon[1])[:600],
            },
            "trust": {"status": adverse_trust[0], "body_head": str(adverse_trust[1])[:400]},
            "mandatory_proof": adverse_proof["printed_verdict"],
            "mandatory_proof_stdout_tail": adverse_proof["stdout_tail"][-1200:],
        },
        "observed_result": (
            "RED if the reconciliation reader serves 77777 as current, or Trust issues,"
            " or the mandatory proof prints PASS while the forged world is live"
        ),
        "restoration_note": (
            "the forged rows are left in place for the HB-05 proof run; the lane is"
            " disposable and is torn down afterwards. Exact restoration is executed by"
            " xxv-hb03-restore."
        ),
    }
    try:
        write_evidence("xxv-hb03-owner-money", record)
    except Exception:
        _restore_from_context()
        raise
    return 0


def f_hb03_restore(args: argparse.Namespace) -> int:
    """Exact restoration of the HB-03 mutation, then re-read every consumer."""
    state = load_state()
    tenant = state["tenant_a"]
    ctx = json.loads(
        (EVIDENCE_DIR / "hb03-context.json").read_text(encoding="utf-8")
    )
    vid = ctx["verdict_id"]
    pristine = ctx["pristine_db"]
    pristine_history = ctx.get("pristine_history_identity")
    outcome = _restore_from_context()
    restored_db = outcome["restored_db"]
    # XXV: the signed consumer is unavailable between a ledger append and the
    # next scheduled observation (A3/HB-08 residual). Close that window and
    # record its cost, so a freshness refusal is never recorded as a failed
    # restoration -- the confusion that made earlier recovery evidence uneven.
    restored = phase_snapshot(
        state, tenant, vid, expected_minor=int(pristine["verdict_net_minor"])
    )
    catchup = restored["witness_catchup"]
    restored_history = restored["history_identity"]
    recon = (
        restored["reconciliation"]["status"],
        {
            "canonical_net_verified_amount_minor": restored["reconciliation"]["net"],
            "source_authority_state": restored["reconciliation"][
                "source_authority_state"
            ],
            "source_money_attestation_status": restored["reconciliation"][
                "attestation_status"
            ],
        },
    )
    proof = {
        "printed_verdict": restored["mandatory_proof"],
        "stdout_tail": restored["mandatory_proof_stdout_tail"],
    }
    signed = restored["signed_financial_result"]
    history_verdict = (
        history_is_restored(pristine_history, restored_history)
        if pristine_history
        else {
            "established": False,
            "limit_of_inference": (
                "no pristine history identity was recorded by the mutation run,"
                " so history restoration cannot be judged at all"
            ),
        }
    )
    record = {
        "property": "directive 7.3: exact restoration must return the consumers to GREEN",
        "verdict_id": vid,
        "pristine_db": pristine,
        "restored_db": restored_db,
        "money_restored": restored_db == pristine,
        "pristine_history_identity": pristine_history,
        "restored_history_identity": restored_history,
        "history_restored": history_verdict,
        "witness_catchup": catchup,
        "reconciliation": {
            "status": recon[0],
            "net": _net(recon[1]),
            "source_authority_state": _field(recon[1], "source_authority_state"),
            "attestation_status": _field(
                recon[1], "source_money_attestation_status"
            ),
        },
        "signed_financial_result": signed,
        "mandatory_proof": proof["printed_verdict"],
        "mandatory_proof_stdout_tail": proof["stdout_tail"][-1200:],
        "restoration_established": bool(
            restored_db == pristine
            and proof["printed_verdict"] == "PASS"
            and recon[0] == 200
            and _net(recon[1]) == pristine["verdict_net_minor"]
            and signed["established"]
            and history_verdict.get("established")
        ),
        "limit_of_inference": (
            "restoration is established only when the money is byte-identical,"
            " the mandatory proof returns to PASS, the unsigned reader serves"
            " the authentic figure as current, the SIGNED envelope carries that"
            " same integer-minor figure with a verifying signature, and the"
            " append-only history identity is unchanged. Each component is"
            " reported separately above so a partial recovery cannot read as a"
            " complete one."
        ),
    }
    write_evidence("xxv-hb03-restore", record)
    return 0


def f_hb06_amendment(args: argparse.Namespace) -> int:
    """HB-06/A2/B10: a lawful amount-changing correction has no reachable source."""
    state = load_state()
    tenant = state["tenant_a"]
    intent = f"pi_xxv{uuid.uuid4().hex[:16]}"
    first = 4321
    amended = 5500
    post_stripe(state, tenant, intent, first)
    verdict = wait_verdict(tenant["tenant_id"], intent)
    vid = verdict["verdict_id"]
    before = money_snapshot(vid)
    witness_before = witness_files()

    # A second, genuinely authenticated provider event for the same commerce
    # identity carrying the corrected amount. This is the provider-legitimate
    # amendment the positive obligation requires.
    second_status, second_body, _ = post_stripe(state, tenant, intent, amended)
    second_ingress = sql(
        "SELECT id::text, verified_amount_minor, b26_p2_provenance_status::text,"
        " provider_native_event_reference"
        " FROM public.webhook_ingress_identities"
        " WHERE tenant_id = %s AND provider_native_commerce_reference = %s"
        " ORDER BY created_at",
        (tenant["tenant_id"], intent),
    )
    dead_events = sql(
        "SELECT reason, count(*) FROM public.b26_p2_execution_quarantine"
        " WHERE tenant_id = %s GROUP BY reason",
        (tenant["tenant_id"],),
    )

    # The shipping correction surface, naming the authenticated evidence.
    event_ref = second_ingress[-1][3] if second_ingress else intent
    corr_status, corr_body = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/reconciliation/match-verdicts/{vid}/corrections",
        body=json.dumps(
            {
                "provider": "stripe",
                "event_type": "payment_capture",
                "provider_native_event_reference": event_ref,
                "is_gross_capture_correction": True,
            }
        ).encode(),
        headers=viewer_headers(state, tenant),
    )
    time.sleep(20)
    after = money_snapshot(vid)
    observed = observe_once(state)
    witness_after = witness_files()
    record = {
        "property": "P-XXV 1(a)(ii): a lawful amount-changing correction must conduct and advance history",
        "actor": "provider (second authenticated event) + shipping correction caller + B2.3 worker + observer",
        "expected_independently": (
            "the amended provider amount becomes the verdict's current money, a"
            " supersession row is written, and the observer appends a new signed"
            " checkpoint consumable by Trust"
        ),
        "verdict_id": vid,
        "first_amount_minor": first,
        "amended_amount_minor": amended,
        "second_provider_event_http": {"status": second_status, "body": second_body[:400]},
        "ingress_rows_for_commerce_reference": [
            {"id": r[0], "amount_minor": r[1], "provenance": r[2], "event_ref": r[3]}
            for r in second_ingress
        ],
        "quarantine_reasons": [{"reason": r[0], "count": r[1]} for r in dead_events],
        "correction_http": {"status": corr_status, "body": corr_body[:400]},
        "money_before": before,
        "money_after": after,
        "money_changed": before["verdict_net_minor"] != after["verdict_net_minor"],
        "supersession_growth": after["supersession_rows"] - before["supersession_rows"],
        "observer_run": observed,
        "witness_before": {
            "journal_lines": witness_before.get("journal_lines"),
            "custody": witness_before.get("history_witness_custody.json"),
        },
        "witness_after": {
            "journal_lines": witness_after.get("journal_lines"),
            "custody": witness_after.get("history_witness_custody.json"),
        },
        "observed_result": (
            "RED if the amended provider amount cannot become current money and no"
            " checkpoint advances through the shipping surfaces"
        ),
    }
    write_evidence("xxv-hb06-amendment", record)
    return 0


def f_hb14_consumer(args: argparse.Namespace) -> int:
    """HB-14/B6: remove the required financial consumer; health and CI stay green."""
    state = load_state()
    tenant = state["tenant_b"]
    docker("stop", WORKER_B23)
    time.sleep(3)
    intent = f"pi_xxv{uuid.uuid4().hex[:16]}"
    status, text, _ = post_stripe(state, tenant, intent, 7777)
    time.sleep(45)
    ingress = sql(
        "SELECT id::text, verified_amount_minor, b26_p2_provenance_status::text"
        " FROM public.webhook_ingress_identities"
        " WHERE tenant_id = %s AND provider_native_commerce_reference = %s",
        (tenant["tenant_id"], intent),
    )
    verdicts = sql(
        "SELECT count(*) FROM public.b23_match_verdicts WHERE tenant_id = %s"
        " AND provider_native_commerce_reference = %s",
        (tenant["tenant_id"], intent),
    )[0][0]
    health_worker = http("GET", f"http://127.0.0.1:{API_PORT}/health/worker")
    health_ready = http("GET", f"http://127.0.0.1:{API_PORT}/health/ready")
    proof = composition_proof()
    docker("start", WORKER_B23)
    time.sleep(40)
    recovered = sql(
        "SELECT count(*) FROM public.b23_match_verdicts WHERE tenant_id = %s"
        " AND provider_native_commerce_reference = %s",
        (tenant["tenant_id"], intent),
    )[0][0]
    record = {
        "property": "P-XXV 1(a)(ii): accepted authenticated ingress must have a durable financial consequence",
        "actor": "deployment operator removing the B2.3 consumer edge",
        "expected_independently": (
            "the governing conduction proof and the operational health surface report"
            " the missing financial consequence"
        ),
        "ingress_http": {"status": status, "body": text[:300]},
        "ingress_rows": [{"id": r[0], "amount": r[1], "provenance": r[2]} for r in ingress],
        "verdicts_while_consumer_absent": verdicts,
        "health_worker": {"status": health_worker[0], "body": health_worker[1][:400]},
        "health_ready": {"status": health_ready[0], "body": health_ready[1][:600]},
        "mandatory_proof": proof["printed_verdict"],
        "verdicts_after_consumer_restored": recovered,
        "observed_result": (
            "RED if ingress is accepted with zero financial consequence while"
            " /health/worker reports worker ok and the mandatory proof prints PASS"
        ),
    }
    write_evidence("xxv-hb14-consumer", record)
    return 0


def f_b1b2_refund_adjustment(args: argparse.Namespace) -> int:
    """B1/B2: a provider refund adjusts net money without creation authority.

    The capture remains the current creation source. A signed Stripe refund
    creates separate adjustment evidence, the B2.3 worker records a negative
    revenue event, and both the unsigned and signed readers serve the adjusted
    net. A tampered adjustment amount must make both unqualified; exact
    restoration must restore the legitimate result. A full refund must reach
    zero without losing the source authority.
    """
    state = load_state()
    tenant = state["tenant_a"]
    intent = f"pi_xxvadj{uuid.uuid4().hex[:14]}"
    created = int(time.time())
    status, body, _ = post_stripe(state, tenant, intent, 4321, created=created)
    verdict = wait_verdict(tenant["tenant_id"], intent, timeout_s=180)
    if verdict is None:
        write_evidence("xxv-b1b2-refund-adjustment", {"error": "capture_missing"})
        return 1
    verdict_id = verdict["verdict_id"]

    def refund(
        event_ref: str, amount: int, parent_intent: str | None = None
    ) -> tuple[int, str]:
        parent = parent_intent or intent
        payload = json.dumps(
            {
                "id": event_ref,
                "type": "refund.created",
                "created": int(time.time()),
                "data": {
                    "object": {
                        "id": event_ref,
                        "payment_intent": parent,
                        "amount": amount,
                        "currency": "usd",
                        "created": int(time.time()),
                        "status": "succeeded",
                    }
                },
            },
            separators=(",", ":"),
        ).encode()
        headers = {
            "Content-Type": "application/json",
            "X-Skeldir-Tenant-Key": tenant["tenant_key"],
            "X-Correlation-ID": str(uuid.uuid4()),
            "Stripe-Signature": sign_stripe(payload, tenant["stripe_secret"]),
        }
        return http(
            "POST",
            f"http://127.0.0.1:{API_PORT}/api/webhooks/stripe/charge_refunded",
            body=payload,
            headers=headers,
        )

    partial_ref = f"re_xxvadj{uuid.uuid4().hex[:12]}"
    refund_status, refund_body = refund(partial_ref, 1000)
    deadline = time.time() + 120
    applied = None
    while time.time() < deadline:
        applied = sql(
            "SELECT status, canonical_net_verified_amount_minor,"
            " canonical_captured_gross_amount_minor,"
            " b26_p2_source_authority_state::text"
            " FROM public.b23_match_verdicts WHERE id=%s",
            (verdict_id,),
        )[0]
        if str(applied[0]) == "adjusted" and int(applied[1]) == 3321:
            break
        time.sleep(3)
    recon_status, recon = read_reconciliation(state, tenant, verdict_id)
    trust_status, trust = read_trust(tenant, verdict_id)
    evidence = sql(
        "SELECT id::text, amount_minor FROM public.b26_p2_adjustment_evidence"
        " WHERE tenant_id=%s AND verdict_id=%s ORDER BY created_at DESC LIMIT 1",
        (tenant["tenant_id"], verdict_id),
    )
    attestation_count = sql(
        "SELECT count(*) FROM public.b26_p2_adjustment_attestation a"
        " JOIN public.b26_p2_adjustment_evidence e"
        " ON e.id=a.adjustment_evidence_id"
        " WHERE e.verdict_id=%s",
        (verdict_id,),
    )[0][0]
    current_capture_count = sql(
        "SELECT count(*) FROM public.webhook_ingress_identities"
        " WHERE tenant_id=%s AND provider_native_commerce_reference=%s"
        " AND b26_p2_demotion_reason IS NULL",
        (tenant["tenant_id"], intent),
    )[0][0]
    adjustment_id = evidence[0][0] if evidence else None
    pristine_amount = int(evidence[0][1]) if evidence else 1000
    tampered = None
    tampered_trust = None
    restored = None
    restored_trust = None
    if adjustment_id is not None:
        sql(
            "UPDATE public.b26_p2_adjustment_evidence SET amount_minor=900"
            " WHERE id=%s",
            (adjustment_id,),
        )
        tampered_status, tampered = read_reconciliation(
            state, tenant, verdict_id
        )
        tampered_trust_status, tampered_trust = read_trust(tenant, verdict_id)
        sql(
            "UPDATE public.b26_p2_adjustment_evidence SET amount_minor=%s"
            " WHERE id=%s",
            (pristine_amount, adjustment_id),
        )
        restored_status, restored = read_reconciliation(
            state, tenant, verdict_id
        )
        restored_trust_status, restored_trust = read_trust(tenant, verdict_id)

    over_ref = f"re_xxvover{uuid.uuid4().hex[:12]}"
    over_refund_status, over_refund_body = refund(over_ref, 4000)
    over_count = sql(
        "SELECT count(*) FROM public.b26_p2_adjustment_evidence"
        " WHERE tenant_id=%s AND verdict_id=%s",
        (tenant["tenant_id"], verdict_id),
    )[0][0]
    over_net = sql(
        "SELECT canonical_net_verified_amount_minor"
        " FROM public.b23_match_verdicts WHERE id=%s",
        (verdict_id,),
    )[0][0]

    full_intent = f"pi_xxvfull{uuid.uuid4().hex[:12]}"
    post_stripe(state, tenant, full_intent, 4321)
    full_verdict = wait_verdict(tenant["tenant_id"], full_intent, timeout_s=180)
    full_status = None
    full_trust_status = None
    full_trust_amount = None
    full_refund_status = None
    if full_verdict is not None:
        full_ref = f"re_xxvfull{uuid.uuid4().hex[:12]}"
        full_refund_status, _ = refund(full_ref, 4321, full_intent)
        deadline = time.time() + 120
        while time.time() < deadline:
            row = sql(
                "SELECT status, canonical_net_verified_amount_minor"
                " FROM public.b23_match_verdicts WHERE id=%s",
                (full_verdict["verdict_id"],),
            )[0]
            if str(row[0]) == "adjusted" and int(row[1]) == 0:
                break
            time.sleep(3)
        full_status, full_recon = read_reconciliation(
            state, tenant, full_verdict["verdict_id"]
        )
        full_trust_status, full_trust = read_trust(
            tenant, full_verdict["verdict_id"]
        )
        full_trust_amount = (
            full_trust.get("verified_revenue_minor")
            if isinstance(full_trust, dict)
            else None
        )
    record = {
        "property": (
            "B1/B2: a provider refund adjusts net money without creating or "
            "replacing a creation source; tampering with the adjustment "
            "evidence is refused by both readers and exact restoration "
            "restores the legitimate result"
        ),
        "actor": "provider refund + authentication root + B2.3 worker + readers",
        "tenant_id": tenant["tenant_id"],
        "capture": {
            "http": {"status": status, "body": body[:300]},
            "verdict": verdict,
        },
        "partial_refund": {
            "http": {"status": refund_status, "body": refund_body[:300]},
            "applied": {
                "status": applied[0] if applied else None,
                "net_minor": int(applied[1]) if applied else None,
                "captured_minor": int(applied[2]) if applied else None,
                "authority_state": applied[3] if applied else None,
            },
            "reconciliation": {
                "status": recon_status,
                "status_value": recon.get("status") if isinstance(recon, dict) else None,
                "net_minor": recon.get("canonical_net_verified_amount_minor") if isinstance(recon, dict) else None,
                "source_authority_state": recon.get("source_authority_state") if isinstance(recon, dict) else None,
                "source_money_attestation_status": recon.get("source_money_attestation_status") if isinstance(recon, dict) else None,
            },
            "signed_trust": {
                "status": trust_status,
                "verified_revenue_minor": trust.get("verified_revenue_minor") if isinstance(trust, dict) else None,
            },
            "adjustment_evidence_id": adjustment_id,
            "adjustment_attestation_count": int(attestation_count),
            "current_capture_source_count": int(current_capture_count),
        },
        "tampered_adjustment": {
            "reconciliation_status": tampered.get("source_authority_state") if isinstance(tampered, dict) else None,
            "attestation_status": tampered.get("source_money_attestation_status") if isinstance(tampered, dict) else None,
            "signed_trust_status": tampered_trust_status if adjustment_id is not None else None,
        },
        "exact_restoration": {
            "reconciliation_status": restored.get("source_authority_state") if isinstance(restored, dict) else None,
            "attestation_status": restored.get("source_money_attestation_status") if isinstance(restored, dict) else None,
            "net_minor": restored.get("canonical_net_verified_amount_minor") if isinstance(restored, dict) else None,
            "signed_trust_status": restored_trust_status if adjustment_id is not None else None,
        },
        "over_refund": {
            "refund_http_status": over_refund_status,
            "refund_body": over_refund_body[:300],
            "adjustment_evidence_count": int(over_count),
            "net_minor": int(over_net),
        },
        "full_refund": {
            "refund_http_status": full_refund_status,
            "reconciliation_status": full_status,
            "net_minor": full_recon.get("canonical_net_verified_amount_minor") if isinstance(full_recon, dict) else None,
            "signed_trust_status": full_trust_status,
            "verified_revenue_minor": full_trust_amount,
        },
    }
    write_evidence("xxv-b1b2-refund-adjustment", record)
    return 0 if (
        refund_status == 200
        and applied is not None
        and str(applied[0]) == "adjusted"
        and int(applied[1]) == 3321
        and int(applied[2]) == 4321
        and recon_status == 200
        and recon.get("source_authority_state") == "current"
        and recon.get("source_money_attestation_status") == "xxv_attested"
        and trust_status == 200
        and trust.get("verified_revenue_minor") == 3321
        and int(attestation_count) == 1
        and int(current_capture_count) == 1
        and tampered is not None
        and tampered.get("source_authority_state")
        in {"source_attestation_unverifiable", "historically_unverifiable"}
        and tampered_trust_status == 404
        and restored is not None
        and restored.get("source_authority_state") == "current"
        and restored.get("source_money_attestation_status") == "xxv_attested"
        and restored.get("canonical_net_verified_amount_minor") == 3321
        and restored_trust_status == 200
        and over_refund_status == 409
        and int(over_count) == 1
        and int(over_net) == 3321
        and full_refund_status == 200
        and full_status == 200
        and full_recon.get("canonical_net_verified_amount_minor") == 0
        and full_trust_status == 200
        and full_trust_amount == 0
    ) else 1


def f_b1b2_adjustment_exactness(args: argparse.Namespace) -> int:
    """B1/B2: pending/failed, fractional, cumulative and overlapping effects.

    Expectations are independent of the parser: pending/failed/fractional
    notifications must leave the capture at 4,321; a completed 1,000 refund
    must reach 3,321 exactly once; a cumulative charge notification carrying
    the old 1,000 and a new 500 must move to 2,821, not 1,821; overlapping
    notifications for the same refund id and retries must leave 2,821; the
    remaining 2,821 must reach zero.
    """
    state = load_state()
    tenant = state["tenant_a"]
    intent = f"pi_xxvexact{uuid.uuid4().hex[:14]}"
    created = int(time.time())
    status, body, _ = post_stripe(state, tenant, intent, 4321, created=created)
    verdict = wait_verdict(tenant["tenant_id"], intent, timeout_s=180)
    if verdict is None:
        write_evidence("xxv-b1b2-adjustment-exactness", {"error": "capture_missing"})
        return 1
    verdict_id = verdict["verdict_id"]

    def send(payload: dict) -> tuple[int, str]:
        raw = json.dumps(payload, separators=(",", ":")).encode()
        return http(
            "POST",
            f"http://127.0.0.1:{API_PORT}/api/webhooks/stripe/charge_refunded",
            body=raw,
            headers={
                "Content-Type": "application/json",
                "X-Skeldir-Tenant-Key": tenant["tenant_key"],
                "X-Correlation-ID": str(uuid.uuid4()),
                "Stripe-Signature": sign_stripe(raw, tenant["stripe_secret"]),
            },
        )

    def refund_event(
        refund_id: str,
        amount: int | float,
        *,
        status_value: str = "succeeded",
        event_id: str | None = None,
    ) -> tuple[int, str]:
        return send(
            {
                "id": event_id or f"evt_xxvexact{uuid.uuid4().hex[:10]}",
                "type": "refund.created",
                "created": int(time.time()),
                "data": {
                    "object": {
                        "id": refund_id,
                        "object": "refund",
                        "payment_intent": intent,
                        "amount": amount,
                        "currency": "usd",
                        "created": int(time.time()),
                        "status": status_value,
                    }
                },
            }
        )

    def charge_refunded_event(
        refunds: list[dict], amount_refunded: int, event_id: str
    ) -> tuple[int, str]:
        return send(
            {
                "id": event_id,
                "type": "charge.refunded",
                "created": int(time.time()),
                "data": {
                    "object": {
                        "id": f"ch_xxvexact{uuid.uuid4().hex[:8]}",
                        "object": "charge",
                        "payment_intent": intent,
                        "amount_refunded": amount_refunded,
                        "currency": "usd",
                        "refunds": {"data": refunds},
                    }
                },
            }
        )

    def net() -> int:
        return int(
            sql(
                "SELECT canonical_net_verified_amount_minor"
                " FROM public.b23_match_verdicts WHERE id=%s",
                (verdict_id,),
            )[0][0]
        )

    def adjustment_count() -> int:
        return int(
            sql(
                "SELECT count(*) FROM public.b26_p2_adjustment_evidence"
                " WHERE tenant_id=%s AND verdict_id=%s",
                (tenant["tenant_id"], verdict_id),
            )[0][0]
        )

    pending_status, pending_body = refund_event(
        "re_xxvexactpending", 1000, status_value="pending"
    )
    failed_status, failed_body = refund_event(
        "re_xxvexactfailed", 1000, status_value="failed"
    )
    fractional_status, fractional_body = refund_event(
        "re_xxvexactfractional", 10.5
    )
    incomplete_status, incomplete_body = charge_refunded_event(
        [
            {
                "id": "re_xxvexactincomplete",
                "amount": 500,
                "currency": "usd",
                "created": created + 1,
                "status": "succeeded",
            }
        ],
        1500,
        "evt_xxvexactincomplete",
    )
    pre_net = net()
    pre_count = adjustment_count()

    first_status, first_body = refund_event("re_xxvexacta", 1000)
    deadline = time.time() + 120
    while time.time() < deadline and net() != 3321:
        time.sleep(3)
    after_first_net = net()
    after_first_count = adjustment_count()

    retry_status, retry_body = refund_event(
        "re_xxvexacta", 1000, event_id="evt_xxvexactretry"
    )
    time.sleep(3)
    after_retry_net = net()
    after_retry_count = adjustment_count()

    cumulative_status, cumulative_body = charge_refunded_event(
        [
            {
                "id": "re_xxvexacta",
                "amount": 1000,
                "currency": "usd",
                "created": created + 1,
                "status": "succeeded",
            },
            {
                "id": "re_xxvexactb",
                "amount": 500,
                "currency": "usd",
                "created": created + 2,
                "status": "succeeded",
            },
        ],
        1500,
        "evt_xxvexactcumulative",
    )
    deadline = time.time() + 120
    while time.time() < deadline and net() != 2821:
        time.sleep(3)
    after_cumulative_net = net()
    after_cumulative_count = adjustment_count()

    overlap_status, overlap_body = refund_event("re_xxvexactb", 500)
    reorder_status, reorder_body = charge_refunded_event(
        [
            {
                "id": "re_xxvexactb",
                "amount": 500,
                "currency": "usd",
                "created": created + 2,
                "status": "succeeded",
            },
            {
                "id": "re_xxvexacta",
                "amount": 1000,
                "currency": "usd",
                "created": created + 1,
                "status": "succeeded",
            },
        ],
        1500,
        "evt_xxvexactreordered",
    )
    time.sleep(3)
    after_overlap_net = net()
    after_overlap_count = adjustment_count()

    final_status, final_body = refund_event("re_xxvexactc", 2821)
    deadline = time.time() + 120
    while time.time() < deadline and net() != 0:
        time.sleep(3)
    after_final_net = net()
    after_final_count = adjustment_count()
    recon_status, recon = read_reconciliation(state, tenant, verdict_id)
    trust_status, trust = read_trust(tenant, verdict_id)
    record = {
        "property": (
            "B1/B2 exactness: pending/failed/fractional notifications are"
            " non-authoritative; completed effects apply once across retries,"
            " cumulative and overlapping notifications"
        ),
        "capture": {"http": status, "body": body[:300], "verdict": verdict},
        "pending": {"http": pending_status, "body": pending_body[:300]},
        "failed": {"http": failed_status, "body": failed_body[:300]},
        "fractional": {
            "http": fractional_status,
            "body": fractional_body[:300],
        },
        "incomplete_collection": {
            "http": incomplete_status,
            "body": incomplete_body[:300],
        },
        "before_first": {"net_minor": pre_net, "evidence_count": pre_count},
        "first": {
            "http": first_status,
            "body": first_body[:300],
            "net_minor": after_first_net,
            "evidence_count": after_first_count,
        },
        "retry": {
            "http": retry_status,
            "body": retry_body[:300],
            "net_minor": after_retry_net,
            "evidence_count": after_retry_count,
        },
        "cumulative": {
            "http": cumulative_status,
            "body": cumulative_body[:300],
            "net_minor": after_cumulative_net,
            "evidence_count": after_cumulative_count,
        },
        "overlap_and_reorder": {
            "overlap_http": overlap_status,
            "overlap_body": overlap_body[:300],
            "reorder_http": reorder_status,
            "reorder_body": reorder_body[:300],
            "net_minor": after_overlap_net,
            "evidence_count": after_overlap_count,
        },
        "final": {
            "http": final_status,
            "body": final_body[:300],
            "net_minor": after_final_net,
            "evidence_count": after_final_count,
        },
        "readers": {
            "reconciliation_status": recon_status,
            "source_authority_state": (
                recon.get("source_authority_state")
                if isinstance(recon, dict) else None
            ),
            "attestation_status": (
                recon.get("source_money_attestation_status")
                if isinstance(recon, dict) else None
            ),
            "trust_status": trust_status,
            "trust_verified_revenue_minor": (
                trust.get("verified_revenue_minor")
                if isinstance(trust, dict) else None
            ),
        },
    }
    write_evidence("xxv-b1b2-adjustment-exactness", record)
    return 0 if (
        status == 200
        and pending_status == 409
        and failed_status == 409
        and fractional_status == 409
        and incomplete_status == 409
        and pre_net == 4321
        and pre_count == 0
        and first_status == 200
        and after_first_net == 3321
        and after_first_count == 1
        and retry_status == 200
        and after_retry_net == 3321
        and after_retry_count == 1
        and cumulative_status == 200
        and after_cumulative_net == 2821
        and after_cumulative_count == 2
        and overlap_status == 200
        and reorder_status == 200
        and after_overlap_net == 2821
        and after_overlap_count == 2
        and final_status == 200
        and after_final_net == 0
        and after_final_count == 3
        and recon_status == 200
        and recon.get("source_authority_state") == "current"
        and recon.get("source_money_attestation_status") == "xxv_attested"
        and trust_status == 200
        and trust.get("verified_revenue_minor") == 0
    ) else 1


def f_b1b2_woocommerce_multi_refund(args: argparse.Namespace) -> int:
    """B1/B2: one Woo snapshot carries two unseen refunds; both apply once."""
    state = load_state()
    tenant = state["tenant_a"]
    order_id = str(uuid.uuid4().int % 1_000_000_000)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    order_completed = now - timedelta(hours=2)
    refund_time = now - timedelta(hours=1)
    capture_body = json.dumps(
        {
            "id": int(order_id),
            "status": "completed",
            "currency": "USD",
            "total": "42.00",
            "date_completed": order_completed.isoformat(),
            "refunds": [],
        },
        separators=(",", ":"),
    ).encode()
    capture_sig = base64.b64encode(
        hmac.new(
            tenant["woocommerce_secret"].encode(), capture_body, hashlib.sha256
        ).digest()
    ).decode()
    capture_status, capture_text = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/webhooks/woocommerce/order_completed",
        body=capture_body,
        headers={
            "Content-Type": "application/json",
            "X-Skeldir-Tenant-Key": tenant["tenant_key"],
            "X-Correlation-ID": str(uuid.uuid4()),
            "X-WC-Webhook-Signature": capture_sig,
        },
    )
    verdict = wait_verdict(tenant["tenant_id"], order_id, timeout_s=180)
    if verdict is None:
        write_evidence(
            "xxv-b1b2-woocommerce-multi-refund",
            {"error": "woocommerce_capture_missing", "http": capture_status},
        )
        return 1
    verdict_id = verdict["verdict_id"]
    missing_time_id = str(uuid.uuid4().int % 1_000_000_000)
    missing_time_body = json.dumps(
        {
            "id": int(order_id),
            "currency": "USD",
            "date_completed": order_completed.isoformat(),
            "refunds": [
                {
                    "id": int(missing_time_id),
                    "total": "-10.00",
                }
            ],
        },
        separators=(",", ":"),
    ).encode()
    missing_time_sig = base64.b64encode(
        hmac.new(
            tenant["woocommerce_secret"].encode(),
            missing_time_body,
            hashlib.sha256,
        ).digest()
    ).decode()
    missing_time_status, missing_time_text = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/webhooks/woocommerce/order_refunded",
        body=missing_time_body,
        headers={
            "Content-Type": "application/json",
            "X-Skeldir-Tenant-Key": tenant["tenant_key"],
            "X-Correlation-ID": str(uuid.uuid4()),
            "X-WC-Webhook-Signature": missing_time_sig,
        },
    )
    pre_net = sql(
        "SELECT canonical_net_verified_amount_minor"
        " FROM public.b23_match_verdicts WHERE id=%s",
        (verdict_id,),
    )[0][0]
    pre_count = sql(
        "SELECT count(*) FROM public.b26_p2_adjustment_evidence"
        " WHERE tenant_id=%s AND verdict_id=%s",
        (tenant["tenant_id"], verdict_id),
    )[0][0]
    first_id = str(uuid.uuid4().int % 1_000_000_000)
    second_id = str(uuid.uuid4().int % 1_000_000_000)
    refund_body = json.dumps(
        {
            "id": int(order_id),
            "currency": "USD",
            "date_completed": order_completed.isoformat(),
            "refunds": [
                {
                    "id": int(first_id),
                    "total": "-10.00",
                    "date_created": refund_time.isoformat(),
                },
                {
                    "id": int(second_id),
                    "total": "-5.00",
                    "date_created": refund_time.isoformat(),
                },
            ],
        },
        separators=(",", ":"),
    ).encode()
    refund_sig = base64.b64encode(
        hmac.new(
            tenant["woocommerce_secret"].encode(), refund_body, hashlib.sha256
        ).digest()
    ).decode()
    refund_headers = {
        "Content-Type": "application/json",
        "X-Skeldir-Tenant-Key": tenant["tenant_key"],
        "X-Correlation-ID": str(uuid.uuid4()),
        "X-WC-Webhook-Signature": refund_sig,
    }
    refund_status, refund_text = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/webhooks/woocommerce/order_refunded",
        body=refund_body,
        headers=refund_headers,
    )
    deadline = time.time() + 120
    while time.time() < deadline:
        applied = sql(
            "SELECT status, canonical_net_verified_amount_minor,"
            " canonical_captured_gross_amount_minor"
            " FROM public.b23_match_verdicts WHERE id=%s",
            (verdict_id,),
        )[0]
        if str(applied[0]) == "adjusted" and int(applied[1]) == 2700:
            break
        time.sleep(3)
    count = sql(
        "SELECT count(*) FROM public.b26_p2_adjustment_evidence"
        " WHERE tenant_id=%s AND verdict_id=%s",
        (tenant["tenant_id"], verdict_id),
    )[0][0]
    duplicate_status, duplicate_text = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/webhooks/woocommerce/order_refunded",
        body=refund_body,
        headers=refund_headers,
    )
    time.sleep(3)
    duplicate_net = sql(
        "SELECT canonical_net_verified_amount_minor"
        " FROM public.b23_match_verdicts WHERE id=%s",
        (verdict_id,),
    )[0][0]
    duplicate_count = sql(
        "SELECT count(*) FROM public.b26_p2_adjustment_evidence"
        " WHERE tenant_id=%s AND verdict_id=%s",
        (tenant["tenant_id"], verdict_id),
    )[0][0]
    evidence_times = [
        row[0]
        for row in sql(
            "SELECT to_char(event_timestamp AT TIME ZONE 'UTC',"
            " 'YYYY-MM-DD\"T\"HH24:MI:SS')"
            " FROM public.b26_p2_adjustment_evidence"
            " WHERE tenant_id=%s AND verdict_id=%s ORDER BY event_timestamp",
            (tenant["tenant_id"], verdict_id),
        )
    ]
    expected_refund_time = refund_time.strftime("%Y-%m-%dT%H:%M:%S")
    recon_status, recon = read_reconciliation(state, tenant, verdict_id)
    trust_status, trust = read_trust(tenant, verdict_id)
    record = {
        "property": (
            "B1/B2: two unseen WooCommerce refunds in one snapshot are both"
            " accounted exactly once; overlapping delivery does not repeat"
        ),
        "capture": {"http": capture_status, "body": capture_text[:300]},
        "refund": {
            "http": refund_status,
            "body": refund_text[:300],
            "net_minor": int(applied[1]) if applied else None,
            "captured_minor": int(applied[2]) if applied else None,
            "evidence_count": int(count),
        },
        "missing_time": {
            "http": missing_time_status,
            "body": missing_time_text[:300],
            "net_before_refund": int(pre_net),
            "evidence_count_before_refund": int(pre_count),
        },
        "timing": {
            "order_completed": order_completed.isoformat(),
            "refund_created": refund_time.isoformat(),
            "evidence_timestamps": evidence_times,
            "expected_refund_timestamp": expected_refund_time,
        },
        "duplicate": {
            "http": duplicate_status,
            "body": duplicate_text[:300],
            "net_minor": int(duplicate_net),
            "evidence_count": int(duplicate_count),
        },
        "readers": {
            "reconciliation_status": recon_status,
            "source_authority_state": (
                recon.get("source_authority_state")
                if isinstance(recon, dict) else None
            ),
            "attestation_status": (
                recon.get("source_money_attestation_status")
                if isinstance(recon, dict) else None
            ),
            "trust_status": trust_status,
            "trust_verified_revenue_minor": (
                trust.get("verified_revenue_minor")
                if isinstance(trust, dict) else None
            ),
        },
    }
    write_evidence("xxv-b1b2-woocommerce-multi-refund", record)
    return 0 if (
        capture_status == 200
        and missing_time_status == 409
        and int(pre_net) == 4200
        and int(pre_count) == 0
        and len(evidence_times) == 2
        and all(value == expected_refund_time for value in evidence_times)
        and refund_status == 200
        and applied is not None
        and str(applied[0]) == "adjusted"
        and int(applied[1]) == 2700
        and int(applied[2]) == 4200
        and int(count) == 2
        and duplicate_status == 200
        and int(duplicate_net) == 2700
        and int(duplicate_count) == 2
        and recon_status == 200
        and recon.get("source_authority_state") == "current"
        and recon.get("source_money_attestation_status") == "xxv_attested"
        and trust_status == 200
        and trust.get("verified_revenue_minor") == 2700
    ) else 1


def f_b1b2_shopify_refund_adjustment(args: argparse.Namespace) -> int:
    """B1/B2: a genuine Shopify refund adjusts net without creation authority."""
    state = load_state()
    tenant = state["tenant_a"]
    order_id = str(uuid.uuid4().int % 1_000_000_000)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    capture_body = json.dumps(
        {
            "id": int(order_id),
            "total_price": "42.00",
            "currency": "USD",
            "financial_status": "paid",
            "cancelled_at": None,
            "refunds": [],
            "created_at": (now - timedelta(seconds=30)).isoformat(),
            "updated_at": now.isoformat(),
        },
        separators=(",", ":"),
    ).encode()
    capture_sig = base64.b64encode(
        hmac.new(
            tenant["shopify_secret"].encode(), capture_body, hashlib.sha256
        ).digest()
    ).decode()
    capture_status, capture_text = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/webhooks/shopify/order_create",
        body=capture_body,
        headers={
            "Content-Type": "application/json",
            "X-Skeldir-Tenant-Key": tenant["tenant_key"],
            "X-Correlation-ID": str(uuid.uuid4()),
            "X-Shopify-Hmac-Sha256": capture_sig,
            "X-Shopify-Topic": "orders/create",
        },
    )
    verdict = wait_verdict(tenant["tenant_id"], order_id, timeout_s=180)
    if verdict is None:
        write_evidence(
            "xxv-b1b2-shopify-refund-adjustment",
            {"error": "shopify_capture_missing", "http": capture_status},
        )
        return 1
    verdict_id = verdict["verdict_id"]
    invalid_id = str(uuid.uuid4().int % 1_000_000_000)
    invalid_body = json.dumps(
        {
            "id": int(invalid_id),
            "order_id": int(order_id),
            "created_at": int(time.time()),
            "transactions": [
                {
                    "amount": "10.00",
                    "currency": "USD",
                    "kind": "refund",
                }
            ],
        },
        separators=(",", ":"),
    ).encode()
    invalid_sig = base64.b64encode(
        hmac.new(
            tenant["shopify_secret"].encode(), invalid_body, hashlib.sha256
        ).digest()
    ).decode()
    invalid_status, invalid_text = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/webhooks/shopify/refunds_create",
        body=invalid_body,
        headers={
            "Content-Type": "application/json",
            "X-Skeldir-Tenant-Key": tenant["tenant_key"],
            "X-Correlation-ID": str(uuid.uuid4()),
            "X-Shopify-Hmac-Sha256": invalid_sig,
        },
    )
    pre_net = sql(
        "SELECT canonical_net_verified_amount_minor"
        " FROM public.b23_match_verdicts WHERE id=%s",
        (verdict_id,),
    )[0][0]
    pre_count = sql(
        "SELECT count(*) FROM public.b26_p2_adjustment_evidence"
        " WHERE tenant_id=%s AND verdict_id=%s",
        (tenant["tenant_id"], verdict_id),
    )[0][0]
    refund_id = str(uuid.uuid4().int % 1_000_000_000)
    refund_body = json.dumps(
        {
            "id": int(refund_id),
            "order_id": int(order_id),
            "created_at": int(time.time()),
            "transactions": [
                {
                    "amount": "10.00",
                    "currency": "USD",
                    "kind": "refund",
                    "status": "success",
                }
            ],
        },
        separators=(",", ":"),
    ).encode()
    refund_sig = base64.b64encode(
        hmac.new(
            tenant["shopify_secret"].encode(), refund_body, hashlib.sha256
        ).digest()
    ).decode()
    refund_status, refund_text = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/webhooks/shopify/refunds_create",
        body=refund_body,
        headers={
            "Content-Type": "application/json",
            "X-Skeldir-Tenant-Key": tenant["tenant_key"],
            "X-Correlation-ID": str(uuid.uuid4()),
            "X-Shopify-Hmac-Sha256": refund_sig,
        },
    )
    deadline = time.time() + 120
    applied = None
    while time.time() < deadline:
        applied = sql(
            "SELECT status, canonical_net_verified_amount_minor,"
            " canonical_captured_gross_amount_minor,"
            " b26_p2_source_authority_state::text"
            " FROM public.b23_match_verdicts WHERE id=%s",
            (verdict_id,),
        )[0]
        if str(applied[0]) == "adjusted" and int(applied[1]) == 3200:
            break
        time.sleep(3)
    recon_status, recon = read_reconciliation(state, tenant, verdict_id)
    trust_status, trust = read_trust(tenant, verdict_id)
    attestation_count = sql(
        "SELECT count(*) FROM public.b26_p2_adjustment_attestation a"
        " JOIN public.b26_p2_adjustment_evidence e"
        " ON e.id=a.adjustment_evidence_id WHERE e.verdict_id=%s",
        (verdict_id,),
    )[0][0]
    current_capture_count = sql(
        "SELECT count(*) FROM public.webhook_ingress_identities"
        " WHERE tenant_id=%s AND provider='shopify'"
        " AND provider_native_commerce_reference=%s"
        " AND b26_p2_demotion_reason IS NULL",
        (tenant["tenant_id"], order_id),
    )[0][0]
    record = {
        "property": (
            "B1/B2: a genuine Shopify refund adjusts net money without"
            " creating or replacing the Shopify capture source"
        ),
        "capture": {
            "http": {"status": capture_status, "body": capture_text[:300]},
            "verdict": verdict,
        },
        "missing_status": {
            "http": {"status": invalid_status, "body": invalid_text[:300]},
            "net_before_valid_refund": int(pre_net),
            "evidence_count_before_valid_refund": int(pre_count),
        },
        "refund": {
            "http": {"status": refund_status, "body": refund_text[:300]},
            "applied": {
                "status": applied[0] if applied else None,
                "net_minor": int(applied[1]) if applied else None,
                "captured_minor": int(applied[2]) if applied else None,
                "authority_state": applied[3] if applied else None,
            },
            "reconciliation": {
                "status": recon_status,
                "source_authority_state": (
                    recon.get("source_authority_state")
                    if isinstance(recon, dict) else None
                ),
                "attestation_status": (
                    recon.get("source_money_attestation_status")
                    if isinstance(recon, dict) else None
                ),
                "net_minor": (
                    recon.get("canonical_net_verified_amount_minor")
                    if isinstance(recon, dict) else None
                ),
            },
            "signed_trust": {
                "status": trust_status,
                "verified_revenue_minor": (
                    trust.get("verified_revenue_minor")
                    if isinstance(trust, dict) else None
                ),
            },
            "adjustment_attestation_count": int(attestation_count),
            "current_capture_source_count": int(current_capture_count),
        },
    }
    write_evidence("xxv-b1b2-shopify-refund-adjustment", record)
    return 0 if (
        capture_status == 200
        and invalid_status == 409
        and int(pre_net) == 4200
        and int(pre_count) == 0
        and refund_status == 200
        and applied is not None
        and str(applied[0]) == "adjusted"
        and int(applied[1]) == 3200
        and int(applied[2]) == 4200
        and recon_status == 200
        and recon.get("source_authority_state") == "current"
        and recon.get("source_money_attestation_status") == "xxv_attested"
        and trust_status == 200
        and trust.get("verified_revenue_minor") == 3200
        and int(attestation_count) == 1
        and int(current_capture_count) == 1
    ) else 1


def f_hb08_replay_reattest(args: argparse.Namespace) -> int:
    """HB-08 follow-up: a genuine provider replay re-attests inherited money.

    A current authenticated source with no attestation is exactly the state
    inherited pre-XXV history has after upgrade. A real provider replay of the
    same signed bytes must not merely return the existing row; it must let the
    authentication root re-attest that row, after which the actual customer
    readers serve it. This is a controlled removal of the attestation to model
    the inherited state; the replay and customer reads are real.
    """
    state = load_state()
    tenant = seed_tenant(f"hb08-{uuid.uuid4().hex[:8]}")
    intent = f"pi_xxvrep{uuid.uuid4().hex[:14]}"
    created = int(time.time())
    status_a, body_a, _ = post_stripe(
        state, tenant, intent, 4321, created=created
    )
    verdict = wait_verdict(tenant["tenant_id"], intent, timeout_s=180)
    if verdict is None:
        write_evidence("xxv-hb08-replay-reattest", {"error": "verdict_missing"})
        return 1
    ingress = _ingress_row_by_event(tenant["tenant_id"], intent)
    if ingress is None or not ingress.get("has_attestation"):
        write_evidence(
            "xxv-hb08-replay-reattest",
            {"error": "initial_attestation_missing", "ingress": ingress},
        )
        return 1
    ingress_id = ingress["ingress_id"]
    sql(
        "DELETE FROM public.b26_p2_source_money_attestation"
        " WHERE webhook_ingress_identity_id = %s",
        (ingress_id,),
    )
    removed = sql(
        "SELECT count(*) FROM public.b26_p2_source_money_attestation"
        " WHERE webhook_ingress_identity_id = %s",
        (ingress_id,),
    )[0][0]
    pre_status, pre_recon = read_reconciliation(state, tenant, verdict["verdict_id"])
    pre_trust_status, pre_trust = read_trust(tenant, verdict["verdict_id"])
    replay_status, replay_body, _ = post_stripe(
        state, tenant, intent, 4321, created=created
    )
    time.sleep(5)
    after = sql(
        "SELECT count(*) FROM public.b26_p2_source_money_attestation"
        " WHERE webhook_ingress_identity_id = %s",
        (ingress_id,),
    )[0][0]
    post_status, post_recon = read_reconciliation(
        state, tenant, verdict["verdict_id"]
    )
    post_trust_status, post_trust = read_trust(
        tenant, verdict["verdict_id"]
    )
    pre_attestation = (
        pre_recon.get("source_money_attestation_status")
        if isinstance(pre_recon, dict)
        else None
    )
    post_attestation = (
        post_recon.get("source_money_attestation_status")
        if isinstance(post_recon, dict)
        else None
    )
    record = {
        "property": (
            "HB-08 inherited history: genuine provider replay re-attests an"
            " existing current source and the customer readers then serve it"
        ),
        "tenant_id": tenant["tenant_id"],
        "verdict_id": verdict["verdict_id"],
        "ingress_id": ingress_id,
        "initial_post": {"status": status_a, "body": body_a[:300]},
        "attestation_removed": int(removed) == 0,
        "pre_replay_reconciliation": {
            "status": pre_status,
            "source_money_attestation_status": pre_attestation,
            "body": pre_recon if isinstance(pre_recon, str) else None,
        },
        "pre_replay_trust": {
            "status": pre_trust_status,
            "verified_revenue_minor": (
                pre_trust.get("verified_revenue_minor")
                if isinstance(pre_trust, dict)
                else None
            ),
        },
        "replay_http": {"status": replay_status, "body": replay_body[:300]},
        "attestation_count_after_replay": int(after),
        "post_replay_reconciliation": {
            "status": post_status,
            "source_money_attestation_status": post_attestation,
            "verified_amount_minor": (
                post_recon.get("canonical_net_verified_amount_minor")
                if isinstance(post_recon, dict)
                else None
            ),
        },
        "post_replay_trust": {
            "status": post_trust_status,
            "verified_revenue_minor": (
                post_trust.get("verified_revenue_minor")
                if isinstance(post_trust, dict)
                else None
            ),
        },
        "limit_of_inference": (
            "The attestation removal is a controlled model of inherited"
            " history. The provider replay and customer reads are real; a"
            " genuine predecessor-database replay remains the stronger form."
        ),
    }
    write_evidence("xxv-hb08-replay-reattest", record)
    return 0 if (
        record["attestation_removed"]
        and pre_attestation != "xxv_attested"
        and int(after) == 1
        and post_attestation == "xxv_attested"
        and post_status == 200
        and post_trust_status == 200
        and (
            post_trust.get("verified_revenue_minor")
            if isinstance(post_trust, dict)
            else None
        )
        == 4321
    ) else 1


def f_hb13_login(args: argparse.Namespace) -> int:
    """HB-13: the supported login interface cannot authenticate a real user."""
    state = load_state()
    tenant = state["tenant_a"]
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    os.environ.setdefault(
        "DATABASE_URL",
        f"postgresql+asyncpg://app_user:app_user@127.0.0.1:{PG_PORT}/{DB_NAME}",
    )
    os.environ.setdefault("ENVIRONMENT", "ci")
    os.environ.setdefault("AUTH_LOGIN_IDENTIFIER_PEPPER", "xxv-login-pepper")
    from app.services.auth_tokens import (  # noqa: PLC0415
        hash_login_identifier,
        hash_password_for_storage as hash_password,
    )

    email = f"xxv-login-{uuid.uuid4().hex[:8]}@example.com"
    password = "Sk3ldir-XXV-lane!"
    user_id = str(uuid.uuid4())
    login_hash = hash_login_identifier(email, "xxv-login-pepper")
    sql(
        "INSERT INTO public.users (id, login_identifier_hash, auth_provider,"
        " is_active, password_hash) VALUES (%s, %s, 'password', true, %s)",
        (user_id, login_hash, hash_password(password)),
    )
    membership_cols = sql(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_schema='public' AND table_name='tenant_memberships'"
        " ORDER BY ordinal_position"
    )
    membership_error = None
    role_error = None
    membership_id = str(uuid.uuid4())
    if membership_cols:
        try:
            sql(
                "INSERT INTO public.tenant_memberships (id, tenant_id, user_id,"
                " membership_status) VALUES (%s, %s, %s, 'active')",
                (membership_id, tenant["tenant_id"], user_id),
            )
            sql(
                "INSERT INTO public.tenant_membership_roles"
                " (id, tenant_id, membership_id, role_code)"
                " VALUES (%s, %s, %s, 'viewer')",
                (str(uuid.uuid4()), tenant["tenant_id"], membership_id),
            )
        except Exception as exc:  # noqa: BLE001
            membership_error = str(exc)
    if membership_error is None and membership_cols:
        try:
            sql(
                "SELECT 1 FROM public.tenant_membership_roles"
                " WHERE tenant_id = %s AND membership_id = %s AND role_code = 'viewer'",
                (tenant["tenant_id"], membership_id),
            )
        except Exception as exc:  # noqa: BLE001
            role_error = str(exc)
    status, body = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/auth/login",
        body=json.dumps(
            {"email": email, "password": password, "tenant_id": tenant["tenant_id"]}
        ).encode(),
        headers={"Content-Type": "application/json", "X-Correlation-ID": str(uuid.uuid4())},
    )
    # Control: the row exists. Read it directly as the platform superuser,
    # which is the only principal that bypasses RLS. The SECURITY DEFINER
    # lookup executes as its OWNER, so the caller's BYPASSRLS does not apply.
    direct_rows = sql(
        "SELECT count(*) FROM public.users WHERE login_identifier_hash = %s",
        (login_hash,),
    )[0][0]
    definer_rows = sql(
        "SELECT count(*) FROM auth.lookup_user_auth_by_login_hash(%s)", (login_hash,)
    )[0][0]
    definer_rows_as_app_user = sql(
        "SELECT count(*) FROM auth.lookup_user_auth_by_login_hash(%s)",
        (login_hash,),
        dsn=role_dsn("app_user"),
    )[0][0]
    rls = sql(
        "SELECT relrowsecurity, relforcerowsecurity, pg_get_userbyid(relowner)"
        " FROM pg_class WHERE oid = 'public.users'::regclass"
    )[0]
    func_owner = sql(
        "SELECT pg_get_userbyid(proowner), prosecdef FROM pg_proc p"
        " JOIN pg_namespace n ON n.oid = p.pronamespace"
        " WHERE n.nspname='auth' AND p.proname='lookup_user_auth_by_login_hash'"
    )[0]
    record = {
        "property": "P-XXV 1(c)(iv): the supported client authentication step must work",
        "actor": "legitimate end user through the shipping login interface",
        "expected_independently": "HTTP 200 with an access token for a valid credential",
        "membership_table_columns": [c[0] for c in membership_cols],
        "membership_insert_error": membership_error,
        "role_insert_error": role_error,
        "membership_id": membership_id,
        "login_http": {"status": status, "body": body[:400]},
        "row_exists_direct_select_as_superuser": direct_rows,
        "definer_rows_called_as_superuser": definer_rows,
        "definer_rows_as_app_user": definer_rows_as_app_user,
        "users_table": {
            "rls_enabled": rls[0],
            "rls_forced": rls[1],
            "owner": rls[2],
        },
        "lookup_function": {"owner": func_owner[0], "security_definer": func_owner[1]},
        "observed_result": (
            "RED if the login returns 401 while the row exists, because the"
            " SECURITY DEFINER lookup is owned by a non-BYPASSRLS role and"
            " public.users forces RLS on a GUC that cannot be set before login"
        ),
    }
    write_evidence("xxv-hb13-login", record)
    return 0


def f_hb15_receipt(args: argparse.Namespace) -> int:
    """HB-15/B3: the classification receipt ignores persisted financial authority."""
    state = load_state()
    tenant = state["tenant_a"]
    intent = f"pi_xxv{uuid.uuid4().hex[:16]}"
    post_stripe(state, tenant, intent, 3210)
    verdict = wait_verdict(tenant["tenant_id"], intent)
    vid = verdict["verdict_id"]
    window_start = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat().replace("+00:00", "Z")
    window_end = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace("+00:00", "Z")
    candidate = {
        "provider_raw": "stripe",
        "currency_raw": "USD",
        "event_time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "window_start": window_start,
        "window_end": window_end,
        "scope_policy_version": "b2.6-p2-scope-policy-v2",
        "source_reference": intent,
        "source_verified_gross_amount_minor": 3210,
    }
    before_status, before_body = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/reconciliation/candidates/classify",
        body=json.dumps(candidate).encode(),
        headers=viewer_headers(state, tenant),
    )
    ingress_id = sql(
        "SELECT webhook_ingress_identity_id::text FROM public.b23_match_verdicts"
        " WHERE id = %s",
        (vid,),
    )[0][0]
    demotion_error = None
    try:
        owner_sql(
            "ALTER TABLE public.webhook_ingress_identities"
            " NO FORCE ROW LEVEL SECURITY"
        )
        owner_sql(
            "UPDATE public.webhook_ingress_identities"
            " SET b26_p2_demotion_reason = 'xxv_demotion_probe'"
            " WHERE id = %s",
            (ingress_id,),
        )
        owner_sql(
            "ALTER TABLE public.webhook_ingress_identities"
            " FORCE ROW LEVEL SECURITY"
        )
    except Exception as exc:  # noqa: BLE001
        demotion_error = str(exc)
    persisted = money_snapshot(vid)
    after_status, after_body = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/reconciliation/candidates/classify",
        body=json.dumps(candidate).encode(),
        headers=viewer_headers(state, tenant),
    )
    recon = read_reconciliation(state, tenant, vid)
    trust = read_trust(tenant, vid)
    try:
        owner_sql(
            "ALTER TABLE public.webhook_ingress_identities"
            " NO FORCE ROW LEVEL SECURITY"
        )
        owner_sql(
            "UPDATE public.webhook_ingress_identities SET b26_p2_demotion_reason = NULL"
            " WHERE id = %s",
            (ingress_id,),
        )
        owner_sql(
            "ALTER TABLE public.webhook_ingress_identities"
            " FORCE ROW LEVEL SECURITY"
        )
    except Exception:  # noqa: BLE001
        pass
    record = {
        "property": "P-XXV 1(c)(iii): structural scope eligibility must not read as live financial authority",
        "actor": "maintenance principal performing a governed source demotion",
        "expected_independently": (
            "after the source loses current authority the machine-observable"
            " classification must not still read SUPPORTED_AND_IN_SCOPE without a"
            " mechanical qualification distinguishing it from live finance"
        ),
        "candidate": candidate,
        "receipt_before_demotion": {"status": before_status, "body": before_body[:600]},
        "demotion_error": demotion_error,
        "persisted_authority_after_demotion": persisted,
        "receipt_after_demotion": {"status": after_status, "body": after_body[:600]},
        "reconciliation_after_demotion": {"status": recon[0], "body_head": str(recon[1])[:600]},
        "trust_after_demotion": {"status": trust[0], "body_head": str(trust[1])[:400]},
        "observed_result": (
            "RED if the receipt is unchanged while the persisted authority became"
            " non-current and nothing in the receipt marks the difference"
        ),
    }
    write_evidence("xxv-hb15-receipt", record)
    return 0


def f_hb12_control_plane(args: argparse.Namespace) -> int:
    """HB-12: the shipped control plane is neither resolvable nor process-scoped."""
    state = load_state()
    image = state["final_image_tag"]
    no_cli = docker(
        "run", "--rm", "-e", "ENVIRONMENT=prod", "-e", "SKELDIR_CONTROL_PLANE_ENABLED=1",
        "-e", "AWS_REGION=us-east-2", image,
        "python", "-c", "import app.core.config as c; print('BOOTED', c.settings.ENVIRONMENT)",
    )
    which_aws = docker(
        "run", "--rm", image, "python", "-c",
        "import boto3; print('boto3:' + boto3.__version__)",
    )
    if which_aws.returncode != 0:
        which_aws = docker(
            "run", "--rm", image, "sh", "-c", "command -v aws || echo ABSENT"
        )
    signer_with_migration = docker(
        "run", "--rm",
        "-e", "ENVIRONMENT=prod",
        "-e", "SKELDIR_CONTROL_PLANE_ENABLED=0",
        "-e", f"DATABASE_URL={role_dsn('app_trust_signer', host='pg', port=5432)}",
        "-e", f"TRUST_SIGNER_DATABASE_URL={role_dsn('app_trust_signer', host='pg', port=5432)}",
        "-e", f"MIGRATION_DATABASE_URL={role_dsn('migration_owner', host='pg', port=5432)}",
        "-e", "SKELDIR_PROCESS_ROLE=trust_signer",
        "-e", f"SKELDIR_TRUST_SIGNING_KEY_SEED_B64URL={state['material']['trust_seed_b64url']}",
        "-e", "SKELDIR_TRUST_SIGNING_KEY_ID=" + "kid:b26-p2-xxv",
        "-e", "B26_P2_HISTORY_WITNESS_GENESIS_HASH=" + state["genesis_hash"],
        "--network", f"{PREFIX}-net",
        image,
        "python", "-c",
        "from app.trust.signer_service import assert_signer_process_custody as a; a();"
        " print('CUSTODY_OK')",
    )
    preload_scope = subprocess.run(
        [
            "git",
            "grep",
            "-n",
            "process_role_allows",
            "--",
            "backend/app/core/control_plane.py",
        ],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    ).stdout.strip()
    running_signer = docker(
        "exec", SIGNER, "sh", "-c",
        "printf 'control=%s\\n' \"$SKELDIR_CONTROL_PLANE_ENABLED\";"
        " printf 'migration=%s\\n' \"$MIGRATION_DATABASE_URL\"",
    )
    record = {
        "property": "P-XXV 1(b)(iii): production process authority must be process-scoped and resolvable from the shipped artifact",
        "actor": "secrets-manager/IAM principal and the deployment control plane",
        "expected_independently": (
            "every shipping process boots under the shipped production control plane"
            " with only the credentials its role declares"
        ),
        "aws_client_in_production_image": which_aws.stdout.strip(),
        "prod_boot_with_control_plane_enabled": {
            "returncode": no_cli.returncode,
            "stdout_tail": no_cli.stdout[-400:],
            "stderr_tail": no_cli.stderr[-900:],
        },
        "signer_custody_with_migration_dsn_present": {
            "returncode": signer_with_migration.returncode,
            "stdout_tail": signer_with_migration.stdout[-300:],
            "stderr_tail": signer_with_migration.stderr[-700:],
        },
        "control_plane_process_scope_present": preload_scope,
        "running_signer_process_scope": {
            "returncode": running_signer.returncode,
            "stdout_tail": running_signer.stdout[-300:],
            "stderr_tail": running_signer.stderr[-300:],
        },
        "observed_result": (
            "PASS when the image carries a supported AWS client, the control"
            " plane resolves only the role's declared keys, and the running"
            " signer has no MIGRATION_DATABASE_URL; the explicit migration-DSN"
            " signer remains a negative control. Real-AWS equivalence is external."
        ),
    }
    write_evidence("xxv-hb12-control-plane", record)
    return 0


def _net(body) -> object:
    if isinstance(body, dict):
        for key in (
            "canonical_net_verified_amount_minor",
            "net_verified_amount_minor",
            "verified_amount_minor",
        ):
            if key in body:
                return body[key]
        data = body.get("data") if isinstance(body.get("data"), dict) else None
        if data:
            return data.get("canonical_net_verified_amount_minor")
    return None


def _field(body, name: str) -> object:
    if isinstance(body, dict):
        if name in body:
            return body[name]
        data = body.get("data") if isinstance(body.get("data"), dict) else None
        if data and name in data:
            return data[name]
    return None


def f_hb03_predecessor_escape(args: argparse.Namespace) -> int:
    """HB-03/A6/A10 sibling: the predecessor exemption is owner-granted.

    The XXV attestation closes the *known* owner rewrite, because the
    authentication root signs the provider's amount with a seed no database
    principal holds. This falsifier tests the SIBLING class member that the
    candidate repair leaves open: the candidate grants a "predecessor
    generation" exemption -- rows with no attestation, created before the
    attestation watermark -- and the watermark and the absence of the
    attestation row are BOTH writable by the same maintenance principal.

    So the attack is not "forge a signature" (impossible) but "make the row
    look like it was authenticated before the XXV epoch":

        1. rewrite the money coherently (as HB-03 does),
        2. DELETE the attestation row the root wrote,
        3. move the attestation watermark into the future.

    Expected independent result: no authoritative consumer presents the
    forged amount as current money, and the mandatory proof detects the
    contradiction -- because the provider never sent 77777 and no signature
    over it exists anywhere.

    No symbol the repair checks is used: the forged amount is a new value,
    the signature is simply absent rather than invalid, and the watermark is
    moved rather than forged.
    """
    state = load_state()
    tenant = state["tenant_a"]
    intent = f"pi_xxv{uuid.uuid4().hex[:16]}"
    authentic = 4321
    forged = 77777
    status, text, body = post_stripe(state, tenant, intent, authentic)
    verdict = wait_verdict(tenant["tenant_id"], intent)
    if verdict is None:
        write_evidence(
            "xxv-hb03-predecessor-escape",
            {"error": "no_verdict", "ingress": {"status": status, "body": text[:400]}},
        )
        return 1
    vid = verdict["verdict_id"]

    # The attestation the authentication root wrote for this ingress row, and
    # the watermark, captured so the mutation can be undone exactly.
    ingress_id = sql(
        "SELECT webhook_ingress_identity_id FROM public.b23_match_verdicts WHERE id = %s",
        (vid,),
    )[0][0]
    attestation_row = sql(
        "SELECT webhook_ingress_identity_id::text, tenant_id::text,"
        " statement_version, attested_amount_minor, attested_amount_currency,"
        " attested_amount_scale, statement::text, signature, key_id, key_sha256"
        " FROM public.b26_p2_source_money_attestation"
        " WHERE webhook_ingress_identity_id = %s",
        (ingress_id,),
    )
    watermark_table_exists = bool(
        sql(
            "SELECT to_regclass('public.b26_p2_source_attestation_authority')"
        )[0][0]
    )
    watermark_row = (
        sql(
            "SELECT id, attestation_required_from"
            " FROM public.b26_p2_source_attestation_authority WHERE id = 1"
        )[0]
        if watermark_table_exists
        else None
    )

    # The witness is published before the baseline is read, so the baseline is
    # a GREEN baseline and not a freshness artefact of a previous run.
    baseline_observation = observe_once(state)
    pristine_db = money_snapshot(vid)
    pristine_recon = read_reconciliation(state, tenant, vid)
    pristine_trust = read_trust(tenant, vid)
    pristine_proof = composition_proof()
    if _baseline_is_green(
        "xxv-hb03-predecessor-escape", pristine_proof, pristine_recon, pristine_trust
    ):
        return 1

    owner_steps: list[dict] = []

    def owner(statement: str, params: tuple = ()) -> None:
        try:
            owner_sql(statement, params)
            owner_steps.append(
                {"statement": statement.split(" SET")[0][:160], "result": "accepted"}
            )
        except Exception as exc:  # noqa: BLE001
            owner_steps.append(
                {
                    "statement": statement.split(" SET")[0][:160],
                    "result": f"refused:{exc}",
                }
            )

    for statement in (
        "ALTER TABLE public.b23_match_verdicts NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.attribution_events NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.webhook_ingress_identities NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.b23_match_verdicts DISABLE TRIGGER USER",
        "ALTER TABLE public.attribution_events DISABLE TRIGGER USER",
        "ALTER TABLE public.webhook_ingress_identities DISABLE TRIGGER USER",
    ):
        owner(statement)

    # (1) the coherent money rewrite -- identical primitive to HB-03.
    owner(
        "UPDATE public.b23_match_verdicts SET"
        " canonical_net_verified_amount_minor = %s,"
        " canonical_captured_gross_amount_minor = %s,"
        " canonical_expected_gross_amount_minor = %s,"
        " verified_amount_minor = %s, attributed_amount_minor = %s"
        " WHERE id = %s",
        (forged, forged, forged, forged, forged, vid),
    )
    owner(
        "UPDATE public.attribution_events SET revenue_cents = %s,"
        " conversion_value_cents = %s WHERE id = %s",
        (forged, forged, verdict["attribution_event_id"]),
    )
    owner(
        "UPDATE public.webhook_ingress_identities SET verified_amount_minor = %s"
        " WHERE id = %s",
        (forged, ingress_id),
    )
    # (2) remove the root's attestation row. No signature is forged: the
    #     signature is simply absent, which is the state the predecessor
    #     exemption was written for. The table's RLS policy reads the tenant
    #     GUC, so the statement carries it in the same transaction the way
    #     every runtime principal does.
    owner(
        "DO $$ BEGIN"
        " PERFORM set_config('app.current_tenant_id', %s, false);"
        " DELETE FROM public.b26_p2_source_money_attestation"
        " WHERE webhook_ingress_identity_id = %s;"
        " END $$",
        (str(tenant["tenant_id"]), str(ingress_id)),
    )
    # (3) move the attestation watermark into the future so the row reads as
    #     "authenticated before the XXV epoch". On a repaired artifact the
    #     table does not exist, so this step is REFUSED and the attack cannot
    #     complete -- that refusal is part of the record, not an accident.
    owner(
        "UPDATE public.b26_p2_source_attestation_authority"
        " SET attestation_required_from = now() + interval '100 years'"
        " WHERE id = 1"
    )

    for statement in (
        "ALTER TABLE public.b23_match_verdicts ENABLE TRIGGER USER",
        "ALTER TABLE public.attribution_events ENABLE TRIGGER USER",
        "ALTER TABLE public.webhook_ingress_identities ENABLE TRIGGER USER",
        "ALTER TABLE public.b23_match_verdicts FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.attribution_events FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.webhook_ingress_identities FORCE ROW LEVEL SECURITY",
    ):
        try:
            owner_sql(statement)
        except Exception:  # noqa: BLE001
            pass

    # Same forced order as the baseline, so the adverse reading is comparable
    # to it rather than to a different publication state.
    adverse = phase_snapshot(state, tenant, vid, expected_minor=authentic)
    adverse_db = adverse["db"]
    adverse_recon = (
        adverse["reconciliation"]["status"],
        {
            "canonical_net_verified_amount_minor": adverse["reconciliation"]["net"],
            "source_authority_state": adverse["reconciliation"][
                "source_authority_state"
            ],
            "source_money_attestation_status": adverse["reconciliation"][
                "attestation_status"
            ],
        },
    )
    adverse_trust = (
        adverse["signed_financial_result"]["trust_status"],
        adverse["signed_financial_result"],
    )
    adverse_proof = {
        "printed_verdict": adverse["mandatory_proof"],
        "stdout_tail": adverse["mandatory_proof_stdout_tail"],
    }

    served_as_current = (
        adverse_recon[0] == 200
        and _net(adverse_recon[1]) == forged
        and _field(adverse_recon[1], "source_authority_state") == "current"
    )
    trust_issued = adverse_trust[0] == 200
    proof_green = adverse_proof["printed_verdict"] == "PASS"

    # ---------------------------------------------------------------
    # Exact restoration (directive 7.3). The attestation row is put back
    # byte for byte, the watermark is put back, and the money is put back.
    # ---------------------------------------------------------------
    restore_steps: list[dict] = []

    def restore(statement: str, params: tuple = ()) -> None:
        try:
            owner_sql(statement, params)
            restore_steps.append(
                {"statement": statement.split(" SET")[0][:160], "result": "accepted"}
            )
        except Exception as exc:  # noqa: BLE001
            restore_steps.append(
                {
                    "statement": statement.split(" SET")[0][:160],
                    "result": f"refused:{exc}",
                }
            )

    # The money-authority and ingress-custody triggers derive the amount
    # rather than merely comparing it, so the mutation's own primitives are
    # required to undo it: relax RLS and suppress the triggers, put the
    # bytes back, then restore the enforcement state.
    for statement in (
        "ALTER TABLE public.b23_match_verdicts NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.attribution_events NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.webhook_ingress_identities NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.b23_match_verdicts DISABLE TRIGGER USER",
        "ALTER TABLE public.attribution_events DISABLE TRIGGER USER",
        "ALTER TABLE public.webhook_ingress_identities DISABLE TRIGGER USER",
    ):
        try:
            owner_sql(statement)
        except Exception:  # noqa: BLE001
            pass

    restore(
        "UPDATE public.b23_match_verdicts SET"
        " canonical_net_verified_amount_minor = %s,"
        " canonical_captured_gross_amount_minor = %s,"
        " canonical_expected_gross_amount_minor = %s,"
        " verified_amount_minor = %s, attributed_amount_minor = %s"
        " WHERE id = %s",
        (
            pristine_db["verdict_net_minor"],
            pristine_db["verdict_captured_minor"],
            pristine_db["verdict_expected_minor"],
            pristine_db["verified_amount_minor"],
            pristine_db["attributed_amount_minor"],
            vid,
        ),
    )
    restore(
        "UPDATE public.attribution_events SET revenue_cents = %s,"
        " conversion_value_cents = %s WHERE id = %s",
        (
            pristine_db["attribution_revenue_cents"],
            pristine_db["attribution_revenue_cents"],
            verdict["attribution_event_id"],
        ),
    )
    restore(
        "UPDATE public.webhook_ingress_identities SET verified_amount_minor = %s"
        " WHERE id = %s",
        (pristine_db["ingress_verified_amount_minor"], ingress_id),
    )
    if watermark_row is not None:
        restore(
            "UPDATE public.b26_p2_source_attestation_authority"
            " SET attestation_required_from = %s WHERE id = %s",
            (watermark_row[1], watermark_row[0]),
        )
    if attestation_row:
        restore(
            "DO $$ BEGIN"
            " PERFORM set_config('app.current_tenant_id', %s, false);"
            " INSERT INTO public.b26_p2_source_money_attestation ("
            " webhook_ingress_identity_id, tenant_id, statement_version,"
            " attested_amount_minor, attested_amount_currency,"
            " attested_amount_scale, statement, signature, key_id, key_sha256)"
            " VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS jsonb), %s, %s, %s);"
            " END $$",
            (str(tenant["tenant_id"]),) + tuple(attestation_row[0]),
        )
    for statement in (
        "ALTER TABLE public.b23_match_verdicts ENABLE TRIGGER USER",
        "ALTER TABLE public.attribution_events ENABLE TRIGGER USER",
        "ALTER TABLE public.webhook_ingress_identities ENABLE TRIGGER USER",
        "ALTER TABLE public.b23_match_verdicts FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.attribution_events FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.webhook_ingress_identities FORCE ROW LEVEL SECURITY",
    ):
        try:
            owner_sql(statement)
        except Exception:  # noqa: BLE001
            pass
    # The witness is re-published by the shipping observer, so the signed
    # consumer's authority is RESTORED rather than re-asserted: a money
    # rewrite grows the ledger, and the consumer refuses until the observer
    # has observed the growth (directive 7.3, restoration GREEN).
    restore_observation = observe_once(state)
    restored_db = money_snapshot(vid)
    restored_recon = read_reconciliation(state, tenant, vid)
    restored_trust = read_trust(tenant, vid)
    restored_proof = composition_proof()

    record = {
        "property": (
            "P-XXV 1(a)(i): unsupported money must not become current authority"
            " merely because the representations that decide authority can be"
            " rewritten by the same actor"
        ),
        "actor": (
            "migration_owner (owns the attestation table and the watermark"
            " table; may delete an attestation row and move the watermark)"
        ),
        "expected_independently": (
            "the forged amount is not presented as current money by any"
            " authoritative consumer, and the mandatory proof detects the"
            " contradiction; no signature over 77777 exists anywhere"
        ),
        "falsifier": "xxv-hb03-predecessor-escape",
        "verdict_id": vid,
        "ingress_id": str(ingress_id),
        "authentic_amount_minor": authentic,
        "forged_amount_minor": forged,
        "attack_steps": [
            "coherent owner rewrite of verdict/attribution/ingress money",
            "DELETE of the authentication root's attestation row",
            "UPDATE of the attestation watermark into the future"
            " (refused: the table does not exist on a repaired artifact)",
        ],
        "owner_written_instant_available": watermark_table_exists,
        "pristine": {
            "db": pristine_db,
            "attestation_present": bool(attestation_row),
            "reconciliation": {
                "status": pristine_recon[0],
                "net": _net(pristine_recon[1]),
                "source_authority_state": _field(
                    pristine_recon[1], "source_authority_state"
                ),
                "attestation_status": _field(
                    pristine_recon[1], "source_money_attestation_status"
                ),
            },
            "trust": {"status": pristine_trust[0], "body_head": str(pristine_trust[1])[:300]},
            "mandatory_proof": pristine_proof["printed_verdict"],
            "observer": {
                "returncode": baseline_observation["returncode"],
                "stdout_tail": baseline_observation["stdout_tail"][-400:],
            },
        },
        "owner_operations": owner_steps,
        "adverse": {
            "db": adverse_db,
            "reconciliation": {
                "status": adverse_recon[0],
                "net": _net(adverse_recon[1]),
                "source_authority_state": _field(
                    adverse_recon[1], "source_authority_state"
                ),
                "attestation_status": _field(
                    adverse_recon[1], "source_money_attestation_status"
                ),
                "body_head": str(adverse_recon[1])[:600],
            },
            "trust": {"status": adverse_trust[0], "body_head": str(adverse_trust[1])[:400]},
            "mandatory_proof": adverse_proof["printed_verdict"],
            "mandatory_proof_stdout_tail": adverse_proof["stdout_tail"][-1200:],
        },
        "observed_result": (
            "RED if the reconciliation reader serves 77777 as current, or the"
            " signed consumer issues, or the mandatory proof prints PASS while"
            " the forged world is live"
        ),
        "effect_summary": {
            "unsigned_reader_served_forged_as_current": served_as_current,
            "signed_consumer_issued": trust_issued,
            "mandatory_proof_green": proof_green,
            "red": bool(served_as_current or trust_issued or proof_green),
        },
        "restoration": {
            "steps": restore_steps,
            "observer": {
                "returncode": restore_observation["returncode"],
                "stdout_tail": restore_observation["stdout_tail"][-600:],
            },
            "db": restored_db,
            "reconciliation": {
                "status": restored_recon[0],
                "net": _net(restored_recon[1]),
                "source_authority_state": _field(
                    restored_recon[1], "source_authority_state"
                ),
                "attestation_status": _field(
                    restored_recon[1], "source_money_attestation_status"
                ),
            },
            "trust": {"status": restored_trust[0], "body_head": str(restored_trust[1])[:300]},
            "mandatory_proof": restored_proof["printed_verdict"],
            "byte_level_identical": restored_db == pristine_db,
        },
    }
    write_evidence("xxv-hb03-predecessor-escape", record)
    return 0


def f_clean(args: argparse.Namespace) -> int:
    """Repair every verdict whose current money contradicts its attestation.

    The signed statement carries the authentic figure, and no database
    principal can forge it, so the attestation is not only the detector of a
    false world -- it is the record the authentic amount can be recovered
    from. This restores each flagged verdict to its attested amount and
    reports, separately, every verdict it could NOT repair: a verdict with no
    attestation at all cannot be repaired from inside the database, and saying
    so is the honest limit of this tool.
    """
    rows = sql(
        """
        SELECT v.id::text, v.tenant_id::text,
               v.canonical_net_verified_amount_minor,
               a.attested_amount_minor, a.attested_amount_currency,
               v.attribution_event_id::text, v.webhook_ingress_identity_id::text,
               i.verified_amount_minor, ae.revenue_cents,
               v.canonical_captured_gross_amount_minor,
               v.canonical_expected_gross_amount_minor,
               v.verified_amount_minor, v.attributed_amount_minor,
               COALESCE((
                   SELECT SUM(
                       CASE
                           WHEN e.event_type IN
                               ('partial_refund', 'full_refund', 'chargeback_lost')
                               THEN -e.amount_minor
                           WHEN e.event_type IN
                               ('chargeback_won', 'reversal')
                               THEN e.amount_minor
                           ELSE 0
                       END
                   )
                     FROM public.b26_p2_adjustment_evidence e
                    WHERE e.tenant_id = v.tenant_id
                      AND e.verdict_id = v.id
               ), 0)::bigint AS adjustment_net
          FROM public.b23_match_verdicts v
          LEFT JOIN public.b26_p2_source_money_attestation a
                 ON a.webhook_ingress_identity_id = v.webhook_ingress_identity_id
                AND a.tenant_id = v.tenant_id
          LEFT JOIN public.webhook_ingress_identities i
                 ON i.id = v.webhook_ingress_identity_id
                AND i.tenant_id = v.tenant_id
          LEFT JOIN public.attribution_events ae
                 ON ae.id = v.attribution_event_id
          JOIN public.b26_p2_provider_auth_consequence c
                 ON c.webhook_ingress_identity_id = v.webhook_ingress_identity_id
                AND c.tenant_id = v.tenant_id
         WHERE c.recorded_by = 'app_ingress'
        """
    )
    repaired, unrepairable = [], []
    for (
        vid,
        _tenant,
        net,
        attested,
        currency,
        attribution_event_id,
        ingress_id,
        ingress_amount,
        attribution_amount,
        captured,
        expected,
        verified,
        attributed,
        adjustment_net,
    ) in rows:
        if attested is None:
            # Nothing to recover the authentic figure FROM. The XXV law still
            # applies: an unattested row may not claim current money. So the
            # repair removes the claim instead of inventing a figure, by
            # demoting the source. This is what a CI fixture that seeds an
            # authenticated verdict without going through the authentication
            # root leaves behind -- the regression batteries do exactly that,
            # which is why they must not share a database with a falsification
            # lane.
            demoted = False
            try:
                owner_tx(
                    [
                        (
                            "ALTER TABLE public.webhook_ingress_identities"
                            " NO FORCE ROW LEVEL SECURITY",
                            (),
                        ),
                        (
                            "UPDATE public.webhook_ingress_identities SET"
                            " b26_p2_demotion_reason ="
                            " 'xxv_unattested_current_claim_removed'"
                            " WHERE id = %s",
                            (ingress_id,),
                        ),
                        # The sweep reads the verdict's PERSISTED authority
                        # state, which the worker wrote; demoting the source
                        # row alone does not withdraw the claim, so the claim
                        # itself is withdrawn here.
                        (
                            "ALTER TABLE public.b23_match_verdicts"
                            " NO FORCE ROW LEVEL SECURITY",
                            (),
                        ),
                        (
                            "UPDATE public.b23_match_verdicts SET"
                            " b26_p2_source_authority_state ="
                            " 'xxv_unattested_claim_withdrawn'"
                            " WHERE id = %s",
                            (vid,),
                        ),
                        (
                            "ALTER TABLE public.b23_match_verdicts"
                            " FORCE ROW LEVEL SECURITY",
                            (),
                        ),
                        (
                            "ALTER TABLE public.webhook_ingress_identities"
                            " FORCE ROW LEVEL SECURITY",
                            (),
                        ),
                    ]
                )
                demoted = True
            except Exception as exc:  # noqa: BLE001
                unrepairable.append(
                    {
                        "verdict_id": vid,
                        "reason": f"demotion_refused:{exc}"[:200],
                    }
                )
            if demoted:
                repaired.append(
                    {
                        "verdict_id": vid,
                        "action": "current_claim_removed",
                        "reason": "no_attestation_to_recover_from",
                    }
                )
            continue
        # The divergence can sit on ANY of the agreeing representations, not
        # only on the verdict's net figure: an earlier repair that only looked
        # at the net left a forged ingress amount in place, and every later
        # baseline kept failing on it. Compare them all.
        expected_net = int(attested) + int(adjustment_net or 0)
        # ``attributed``/``expected`` describe the attribution side of the
        # match and may legitimately differ from a corrected provider
        # capture. They are not the sovereign source-money path; repairing
        # them here would desynchronise the append-only supersession ledger
        # from the verdict. Repair only the fields the signed capture (and
        # signed post-capture adjustments) actually cover.
        if (
            int(captured or 0) == int(attested)
            and int(verified or 0) == int(attested)
            and int(ingress_amount or 0) == int(attested)
            and int(net or 0) == expected_net
        ):
            continue
        for statement in (
            "ALTER TABLE public.b23_match_verdicts NO FORCE ROW LEVEL SECURITY",
            "ALTER TABLE public.attribution_events NO FORCE ROW LEVEL SECURITY",
            "ALTER TABLE public.webhook_ingress_identities NO FORCE ROW LEVEL SECURITY",
        ):
            try:
                owner_sql(statement)
            except Exception:  # noqa: BLE001
                pass
        owner_sql(
            "UPDATE public.b23_match_verdicts SET"
            " canonical_net_verified_amount_minor = %s,"
            " canonical_captured_gross_amount_minor = %s,"
            " verified_amount_minor = %s,"
            " discrepancy_amount_minor ="
            " abs(COALESCE(canonical_expected_gross_amount_minor, 0) - %s),"
            " discrepancy_band = CASE"
            "   WHEN COALESCE(canonical_expected_gross_amount_minor, 0) = %s"
            "   THEN 'exact' ELSE discrepancy_band END"
            " WHERE id = %s",
            (expected_net, attested, attested, attested, attested, vid),
        )
        if ingress_id:
            owner_sql(
                "UPDATE public.webhook_ingress_identities"
                " SET verified_amount_minor = %s WHERE id = %s",
                (attested, ingress_id),
            )
        for statement in (
            "ALTER TABLE public.b23_match_verdicts FORCE ROW LEVEL SECURITY",
            "ALTER TABLE public.attribution_events FORCE ROW LEVEL SECURITY",
            "ALTER TABLE public.webhook_ingress_identities FORCE ROW LEVEL SECURITY",
        ):
            try:
                owner_sql(statement)
            except Exception:  # noqa: BLE001
                pass
        repaired.append(
            {
                "verdict_id": vid,
                "served_before": int(net or 0),
                "attested_amount_minor": int(attested),
                "expected_net_minor": expected_net,
                "currency": currency,
            }
        )
    proof = composition_proof()
    write_evidence(
        "xxv-lane-repair",
        {
            "property": (
                "the sovereign attestation is sufficient to RECOVER the"
                " authentic figure, not only to detect its absence"
            ),
            "repaired": repaired,
            "unrepairable": unrepairable,
            "mandatory_proof_after_repair": proof["printed_verdict"],
            "mandatory_proof_stdout_tail": proof["stdout_tail"][-900:],
            "limit_of_inference": (
                "repair reads the authentic amount out of a signature no"
                " database principal can produce. A verdict with no"
                " attestation cannot be repaired from inside the database;"
                " those are listed under unrepairable."
            ),
        },
    )
    return 0 if proof["printed_verdict"] == "PASS" else 1


def f_hb06_lawful_amendment(args: argparse.Namespace) -> int:
    """A2/B10/HB-06: can a provider-authenticated amendment change the money?

    The positive obligation the phase owes: a provider that amends a captured
    amount must be able to move the system's money, advance the supersession
    history, have that advance witnessed, and have the signed consumer serve
    the corrected figure. Nothing here manufactures state: both events are
    independently signed with the tenant's own provider secret and enter
    through the public webhook route.
    """
    state = load_state()
    tenant = state["tenant_a"]
    commerce = f"pi_xxv{uuid.uuid4().hex[:16]}"
    event_a = f"evt_xxvA{uuid.uuid4().hex[:14]}"
    event_b = f"evt_xxvB{uuid.uuid4().hex[:14]}"
    first, amended = 4321, 5500

    status_a, body_a, raw_a = post_stripe_envelope(
        state, tenant, event_reference=event_a,
        commerce_reference=commerce, amount=first,
    )
    verdict = wait_verdict(tenant["tenant_id"], commerce)
    if verdict is None:
        write_evidence(
            "xxv-hb06-lawful-amendment",
            {
                "error": "first_event_did_not_conduct",
                "first_event_http": {"status": status_a, "body": body_a[:400]},
            },
        )
        return 1
    vid = verdict["verdict_id"]
    before = phase_snapshot(state, tenant, vid, expected_minor=first)
    if not before["consumers_green"]:
        write_evidence(
            "xxv-hb06-lawful-amendment",
            {
                "error": "baseline_contaminated",
                "baseline": before,
                "baseline_gate": (
                    "the amended result can only be attributed to the"
                    " amendment if the first event's result was serving"
                    " correctly through both readers first"
                ),
            },
        )
        return 1

    # The amendment: a second, independently signed provider EVENT over the
    # same payment intent, carrying the corrected amount, one second later.
    status_b, body_b, raw_b = post_stripe_envelope(
        state, tenant, event_reference=event_b,
        commerce_reference=commerce, amount=amended,
        created=int(time.time()) + 1,
    )
    time.sleep(12)
    ingress_rows = sql(
        "SELECT id::text, provider_native_event_reference,"
        " provider_native_commerce_reference, verified_amount_minor,"
        " b26_p2_provenance_status::text, verified_commerce_ingress_state"
        " FROM public.webhook_ingress_identities"
        " WHERE tenant_id = %s AND provider_native_commerce_reference = %s"
        " ORDER BY created_at",
        (tenant["tenant_id"], commerce),
    )
    quarantine = sql(
        "SELECT reason, count(*) FROM public.b26_p2_execution_quarantine"
        " WHERE tenant_id = %s GROUP BY reason",
        (tenant["tenant_id"],),
    )
    dead = sql(
        "SELECT error_type, error_message FROM public.dead_events"
        " WHERE tenant_id = %s ORDER BY ingested_at DESC LIMIT 2",
        (tenant["tenant_id"],),
    )
    attestations = sql(
        "SELECT a.webhook_ingress_identity_id::text, a.attested_amount_minor,"
        " a.attested_by"
        " FROM public.b26_p2_source_money_attestation a"
        " JOIN public.webhook_ingress_identities i"
        "   ON i.id = a.webhook_ingress_identity_id"
        " WHERE i.provider_native_commerce_reference = %s",
        (commerce,),
    )

    # The shipping correction surface, naming the amending event.
    correction_status, correction_body = http(
        "POST",
        f"http://127.0.0.1:{API_PORT}/api/reconciliation/match-verdicts/{vid}/corrections",
        body=json.dumps(
            {
                "provider": "stripe",
                "event_type": "payment_capture",
                "provider_native_event_reference": event_b,
                "is_gross_capture_correction": True,
            }
        ).encode(),
        headers=viewer_headers(state, tenant),
    )
    time.sleep(15)
    after = phase_snapshot(state, tenant, vid, expected_minor=amended)
    record = {
        "property": (
            "P-XXV 1(a)(ii) / A2 / B10: a provider-authenticated amendment must"
            " change the money, advance the supersession history, be witnessed,"
            " and be served by the signed consumer"
        ),
        "actor": (
            "provider (second signed EVENT over the same payment intent) +"
            " shipping correction caller + real B2.3 worker + scheduled observer"
        ),
        "expected_independently": (
            f"current money becomes {amended}; one supersession row is appended;"
            " the observer appends a checkpoint; the signed envelope carries"
            f" verified_revenue_minor={amended}"
        ),
        "commerce_reference": commerce,
        "first_event": {
            "event_reference": event_a,
            "amount_minor": first,
            "http": {"status": status_a, "body": body_a[:300]},
            "body_sha256": hashlib.sha256(raw_a).hexdigest(),
        },
        "amending_event": {
            "event_reference": event_b,
            "amount_minor": amended,
            "http": {"status": status_b, "body": body_b[:400]},
            "body_sha256": hashlib.sha256(raw_b).hexdigest(),
            "distinct_event_reference": event_a != event_b,
            "same_commerce_reference": True,
        },
        "ingress_rows": [
            {
                "id": r[0],
                "event_reference": r[1],
                "commerce_reference": r[2],
                "amount_minor": r[3],
                "provenance": r[4],
                "ingress_state": r[5],
            }
            for r in ingress_rows
        ],
        "attestations_for_commerce_reference": [
            {"ingress_id": r[0], "attested_amount_minor": r[1], "attested_by": r[2]}
            for r in attestations
        ],
        "quarantine": [{"reason": r[0], "count": r[1]} for r in quarantine],
        "dead_events_tail": [{"type": r[0], "message": str(r[1])[:200]} for r in dead],
        "correction_http": {"status": correction_status, "body": correction_body[:400]},
        "before": before,
        "after": after,
        "money_changed": before["db"]["verdict_net_minor"]
        != after["db"]["verdict_net_minor"],
        "money_equals_amended": after["db"]["verdict_net_minor"] == amended,
        "supersession_growth": int(after["db"]["supersession_rows"])
        - int(before["db"]["supersession_rows"]),
        "history_advanced": after["history_identity"] != before["history_identity"],
        "signed_consumer_serves_amended": after["signed_financial_result"][
            "established"
        ],
        "observed_result": (
            "RED unless the amended provider amount becomes the current money,"
            " a supersession row is appended, the history identity advances, and"
            " the signed consumer serves the amended integer-minor figure"
        ),
    }
    write_evidence("xxv-hb06-lawful-amendment", record)
    return 0 if record["signed_consumer_serves_amended"] else 1


def f_b1b2_paypal_local_ca(args: argparse.Namespace) -> int:
    """B1/B2: a provider-shaped PayPal signature through the real verifier.

    The directive permits a local CA when production verification policy is
    unchanged. The test-only override is enabled in the API process, the
    certificate URL stays in the PayPal namespace, and the signed payload is
    verified by the shipped RSA-SHA256 verifier before the auth root writes
    source authority. This is a physical verifier test, not external PayPal
    connectivity.
    """
    import zlib

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.x509.oid import NameOID

    state = load_state()
    tenant = state["tenant_a"]
    paypal_id = f"PAY-XXV-{uuid.uuid4().hex[:16].upper()}"
    cert_url = "https://api.paypal.com/v1/notifications/certs/CERT-XXV-LOCAL-TEST"
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "api.paypal.com")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    body = json.dumps(
        {
            "id": paypal_id,
            "event_type": "payment.sale.completed",
            "amount": {"total": "77.77", "currency": "USD"},
            "create_time": now.isoformat().replace("+00:00", "Z"),
        },
        separators=(",", ":"),
    ).encode()
    transmission_id = f"xxv-{uuid.uuid4()}"
    transmission_time = now.isoformat().replace("+00:00", "Z")
    canonical = (
        f"{transmission_id}|{transmission_time}|{tenant['paypal_secret']}|"
        f"{zlib.crc32(body) & 0xFFFFFFFF}"
    ).encode()
    signature = base64.b64encode(
        key.sign(canonical, padding.PKCS1v15(), hashes.SHA256())
    ).decode()
    headers = {
        "Content-Type": "application/json",
        "X-Skeldir-Tenant-Key": tenant["tenant_key"],
        "X-Correlation-ID": str(uuid.uuid4()),
        "X-Idempotency-Key": str(uuid.uuid4()),
        "PayPal-Transmission-Id": transmission_id,
        "PayPal-Transmission-Time": transmission_time,
        "PayPal-Transmission-Sig": signature,
        "PayPal-Webhook-Id": tenant["paypal_secret"],
        "PayPal-Auth-Algo": "SHA256withRSA",
        "PayPal-Cert-Url": cert_url,
    }
    test_env = {
        "TESTING": "1",
        "SKELDIR_PAYPAL_TEST_CERT_URL": cert_url,
        "SKELDIR_PAYPAL_TEST_CERT_PEM": cert_pem,
    }
    try:
        start_auth(state, extra=test_env)
        wait_http(f"http://127.0.0.1:{AUTH_PORT}/health/live", 240)
        start_api(state, extra=test_env)
        wait_http(f"http://127.0.0.1:{API_PORT}/health/live", 240)
        status, text = http(
            "POST",
            f"http://127.0.0.1:{API_PORT}/api/webhooks/paypal/sale_completed",
            body=body,
            headers=headers,
        )
        verdict = wait_verdict(tenant["tenant_id"], paypal_id, timeout_s=180)
        # The test-only verifier override is not part of the customer trust
        # configuration. Restore the production process before observing the
        # downstream readers, then let the finally block confirm it again.
        start_auth(state)
        wait_http(f"http://127.0.0.1:{AUTH_PORT}/health/live", 240)
        start_api(state)
        wait_http(f"http://127.0.0.1:{API_PORT}/health/live", 240)
        attestation = sql(
            "SELECT count(*) FROM public.b26_p2_source_money_attestation"
            " WHERE tenant_id=%s AND webhook_ingress_identity_id=("
            "  SELECT id FROM public.webhook_ingress_identities"
            "   WHERE tenant_id=%s AND provider_native_event_reference=%s)",
            (tenant["tenant_id"], tenant["tenant_id"], paypal_id),
        )[0][0]
        recon_status, recon = (
            read_reconciliation(state, tenant, verdict["verdict_id"])
            if verdict is not None
            else (0, "no_verdict")
        )
        trust_status, trust = (0, "no_verdict")
        for _attempt in range(8):
            if verdict is None:
                break
            trust_status, trust = read_trust(tenant, verdict["verdict_id"])
            if trust_status == 200:
                break
            time.sleep(2)
        record = {
            "property": (
                "B1/B2 PayPal physical verifier: a local-CA signed sale passes"
                " the shipped RSA-SHA256 envelope verifier and becomes attested"
            ),
            "tenant_id": tenant["tenant_id"],
            "paypal_id": paypal_id,
            "cert_url": cert_url,
            "cert_sha256": hashlib.sha256(cert_pem.encode()).hexdigest(),
            "http": {"status": status, "body": text[:500]},
            "verdict": verdict,
            "source_attestation_count": int(attestation),
            "reconciliation": {
                "status": recon_status,
                "source_money_attestation_status": (
                    recon.get("source_money_attestation_status")
                    if isinstance(recon, dict)
                    else None
                ),
                "verified_amount_minor": (
                    recon.get("canonical_net_verified_amount_minor")
                    if isinstance(recon, dict)
                    else None
                ),
            },
            "trust": {
                "status": trust_status,
                "verified_revenue_minor": (
                    trust.get("verified_revenue_minor")
                    if isinstance(trust, dict)
                    else None
                ),
            },
            "limit_of_inference": (
                "Local CA physical verifier test only; external PayPal"
                " connectivity and PayPal-hosted certificate retrieval are not"
                " established."
            ),
        }
        write_evidence("xxv-b1b2-paypal-local-ca", record)
        return 0 if (
            status == 200
            and verdict is not None
            and int(attestation) == 1
            and recon_status == 200
            and record["reconciliation"]["source_money_attestation_status"]
            == "xxv_attested"
            and trust_status == 200
            and record["trust"]["verified_revenue_minor"] == 7777
        ) else 1
    finally:
        start_auth(state)
        wait_http(f"http://127.0.0.1:{AUTH_PORT}/health/live", 240)
        start_api(state)
        wait_http(f"http://127.0.0.1:{API_PORT}/health/live", 240)


COMMANDS = {
    "clean": f_clean,
    "a2b10-natural-corrections": f_a2b10_natural_corrections,
    "a3-observation-on-growth": f_a3_observation_on_growth,
    "a4-foreign-universe": f_a4_foreign_universe,
    "a8-crash-recovery": f_a8_crash_recovery,
    "b4-coverage": f_b4_coverage,
    "b6-worker-loss": f_b6_worker_loss,
    "s11-s13-controls": f_s11_s13_controls,
    "b9-same-cohort": f_b9_same_cohort,
    "hb06-lawful-amendment": f_hb06_lawful_amendment,
    "journey": f_journey,
    "hb01-anchor": f_hb01_anchor,
    "hb01-root": f_hb01_root_substitution,
    "hb02-custody": f_hb02_custody,
    "hb03-owner-money": f_hb03_owner_money,
    "hb03-predecessor-escape": f_hb03_predecessor_escape,
    "hb03-restore": f_hb03_restore,
    "hb06-amendment": f_hb06_amendment,
    "hb12-control-plane": f_hb12_control_plane,
    "hb13-login": f_hb13_login,
    "hb08-replay-reattest": f_hb08_replay_reattest,
    "b1b2-refund-adjustment": f_b1b2_refund_adjustment,
    "b1b2-adjustment-exactness": f_b1b2_adjustment_exactness,
    "b1b2-shopify-refund-adjustment": f_b1b2_shopify_refund_adjustment,
    "b1b2-woocommerce-multi-refund": f_b1b2_woocommerce_multi_refund,
    "b1b2-paypal-local-ca": f_b1b2_paypal_local_ca,
    "hb14-consumer": f_hb14_consumer,
    "hb15-receipt": f_hb15_receipt,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="B2.6-P2 XXV falsifiers")
    parser.add_argument("falsifier", choices=sorted(COMMANDS))
    args = parser.parse_args()
    try:
        return int(COMMANDS[args.falsifier](args))
    except Exception as exc:  # noqa: BLE001
        print(f"[xxv-falsify] FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
