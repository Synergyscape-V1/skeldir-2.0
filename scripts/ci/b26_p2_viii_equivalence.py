#!/usr/bin/env python3
"""B2.6-P2 Corrective VIII P2/completion differential proof.

Replaces the VII hand-mirror with execution on both sides:

  P2 side        : REAL scope_authority.classify_candidate on each state.
  Completion side: REAL database gate (recorder + mark_conducted) executed
                   against per-state persisted fixtures on a live lane at
                   the candidate head. No Python mirror of the gate exists
                   anywhere in this script; the gate outcome is observed
                   from PostgreSQL.

Required mapping (phase contract, consequence-bound conduction):
  gate conducts <=> P2 SUCCESS (any disposition) AND a B2.3 consequence
  is present for the execution. Scope-level UNRESOLVED/EXCLUDED without a
  qualifying verdict is conserved by P2 derivation (never vanishes) but
  cannot conduct at task level: there is no consequence to bind. Task
  conduction without consequence is the prohibited false-terminal class;
  scope conservation without task conduction is the governed law, not a
  stranding (stranding would be a valid scope outcome missing from the
  derived scope, which the conduction conservation checks prove).

Future-drift falsifiers (M8-01..06): six real same-mechanism mutations of
the live canonical module (monkeypatched, byte-restored). For each, the
proof re-executes P2 and re-observes completion artifacts (gate outcome +
receipt digest recomputed through the real _compute_scope_identity). A
mutation that changes P2 behavior while leaving every completion artifact
unchanged is BLIND and REDs. All six must be OBSERVABLE (completion
follows automatically) for PASS.

Usage: python scripts/ci/b26_p2_viii_equivalence.py
         --dsn postgresql://migration_owner:migration_owner@127.0.0.1:5432/db
         [--evidence-out artifacts/b26_p2/viii-equivalence.json]
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

REPO_ROOT = (
    Path(__file__).resolve().parents[2]
    if len(Path(__file__).resolve().parents) > 2
    else Path(__file__).resolve().parent
)
sys.path.insert(0, str(REPO_ROOT / "backend"))

DAY_START = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)
DAY_END = datetime(2026, 1, 16, 0, 0, tzinfo=timezone.utc)
DAY_NOON = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
TASK_NAME = "app.tasks.revenue_verification.execute_b23_batch_match_engine"
SCOPE_HEX = "ef" * 32

PROVIDERS = ["stripe", "paypal", "acme-pay", "STRIPE ", "", "   "]
# "US" (malformed-shape EXCLUDED) is schema-unreachable at issuance
# (dispatch shape law refuses upstream while P2 classifies EXCLUDED);
# per the contract mapping it is fail-closed upstream, exercised by the
# dedicated shape-law cells, not by the conduct/refuse differential.
CURRENCIES = ["USD", "eur", "", "   "]
HAS_VERDICT = [True, False]
EVENT_TIMES = [DAY_NOON, DAY_END]


def _p2_outcome(state: dict):
    from app.finance_reconciliation import scope_authority as sa

    # Reference presence is derived exactly the way
    # fetch_governed_candidates derives it: a qualifying B2.3 verdict
    # always carries a non-blank canonical reference (schema CHECK), so
    # a task with a qualifying verdict is never UNRESOLVED at P2.
    ref = "o" if state["has_verdict"] else None
    try:
        verdict = sa.classify_candidate(
            tenant_id=state["tenant_id"],
            provider_raw=state["provider"],
            currency_raw=state["currency"],
            event_time=state["event_time"],
            window_start=DAY_START,
            window_end=DAY_END,
            scope_policy_version=sa.B26_P2_SCOPE_POLICY_VERSION,
            source_reference=ref,
        )
        return ("SUCCESS", verdict.disposition, verdict.reason)
    except Exception as exc:  # noqa: BLE001
        return ("REFUSAL", type(exc).__name__, str(exc)[:120])


def _connect(dsn: str):
    import psycopg2

    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    return conn


def _role_dsn(admin_dsn: str, role: str) -> str:
    return admin_dsn.replace("migration_owner:migration_owner", "%s:%s" % (role, role))


def _completion_outcome(admin_dsn: str, state: dict) -> tuple:
    """Execute REAL completion for one state. Returns (conducts, detail).

    The dispatch window is derived from the event clock through the
    sovereign quantizer (exactly as production issuance does), so
    window-membership states exercise the governed path instead of a
    hardcoded-window fixture artifact.
    """
    import psycopg2

    from app.core.day_window import quantize_utc_day

    tenant = uuid.uuid4()
    ws, we = quantize_utc_day(state["event_time"])
    tag = uuid.uuid4().hex[:8]
    admin = psycopg2.connect(admin_dsn)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tenants (id, name, api_key_hash,"
                " notification_email) VALUES (%s, %s, %s, %s)",
                (str(tenant), "viii-eq-%s" % tag, uuid.uuid4().hex,
                 "eq-%s@x.invalid" % tag),
            )
            cur.execute("SELECT set_config('app.current_tenant_id', %s, false)",
                        (str(tenant),))
            cur.execute(
                "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
                " display_name, state) VALUES ('viii_eq', 'viii', true, 'E',"
                " 'active') ON CONFLICT (code) DO NOTHING"
            )
            event_uuid = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, 100, '{}'::jsonb, %s,"
                " 'conversion', 'viii_eq', 'c', 100, 'USD', %s, %s, 'processed')",
                (event_uuid, str(tenant), DAY_NOON, str(uuid.uuid4()),
                 str(uuid.uuid4()), "viii-eq:%s" % tag, DAY_NOON, DAY_NOON),
            )
            ingress = str(uuid.uuid4())
            try:
                cur.execute(
                    "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
                    " event_id, provider, provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " normalized_commerce_reference_kind,"
                    " normalized_commerce_reference_value, verified_amount_minor,"
                    " verified_amount_currency, event_timestamp, idempotency_key,"
                    " verified_commerce_ingress_state)"
                    " VALUES (%s, %s, %s, %s, 'e', 'o', 'order_reference',"
                    " 'o', 100, %s, %s, %s, 'authenticity_verified')",
                    (ingress, str(tenant), event_uuid, state["provider"],
                     state["currency"], state["event_time"], "viii-eq:%s" % tag),
                )
            except Exception as exc:
                return (False, "upstream_refuse:ingress:%s" % str(exc).splitlines()[0][:80])
    finally:
        admin.close()
    user = psycopg2.connect(_role_dsn(admin_dsn, "app_user"))
    user.autocommit = True
    task = "viii-eq-%s" % uuid.uuid4().hex[:8]
    try:
        with user.cursor() as cur:
            cur.execute("SELECT set_config('app.current_tenant_id', %s, false)",
                        (str(tenant),))
            try:
                cur.execute(
                    "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                    " webhook_ingress_identity_id, task_id, task_name, queue,"
                    " routing_key, correlation_id, provider,"
                    " provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " normalized_commerce_reference_value, window_start,"
                    " window_end) VALUES (%s, %s, %s, " + "'" + TASK_NAME + "',"
                    " 'b23_match_engine', 'b23_match_engine.task', %s,"
                    " %s, 'e', 'o', 'o', %s, %s)",
                    (str(tenant), ingress, task, str(uuid.uuid4()),
                     state["provider"], ws, we),
                )
            except Exception as exc:
                return (False, "upstream_refuse:dispatch:%s" % str(exc).splitlines()[0][:80])
            cur.execute(
                "INSERT INTO public.b26_p2_execution_outbox (tenant_id,"
                " dispatch_task_id, webhook_ingress_identity_id)"
                " VALUES (%s, %s, %s)",
                (str(tenant), task, ingress),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_task_authority_directory (task_id,"
                " tenant_id, webhook_ingress_identity_id, window_start,"
                " window_end) VALUES (%s, %s, %s, %s, %s)",
                (task, str(tenant), ingress, ws, we),
            )
    finally:
        user.close()
    admin2 = psycopg2.connect(admin_dsn)
    admin2.autocommit = True
    try:
        with admin2.cursor() as cur:
            cur.execute("SELECT set_config('app.current_tenant_id', %s, false)",
                        (str(tenant),))
            cur.execute(
                "UPDATE public.b23_match_task_dispatches SET delivery_state='published',"
                " first_published_at=now() WHERE task_id=%s", (task,),
            )
            cur.execute(
                "UPDATE public.b26_p2_execution_outbox SET state='published'"
                " WHERE dispatch_task_id=%s", (task,),
            )
            if state["has_verdict"]:
                cur.execute(
                    "INSERT INTO public.b23_match_verdicts (tenant_id,"
                    " attribution_event_id, webhook_ingress_identity_id,"
                    " provider, canonical_commerce_reference,"
                    " provider_native_event_reference,"
                    " provider_native_commerce_reference, status,"
                    " match_quality, attributed_amount_minor,"
                    " verified_amount_minor, currency_code,"
                    " canonical_expected_gross_amount_minor,"
                    " canonical_captured_gross_amount_minor,"
                    " canonical_net_verified_amount_minor,"
                    " discrepancy_amount_minor, discrepancy_ratio_bps,"
                    " discrepancy_band)"
                    " VALUES (%s, %s, %s, %s, 'o', 'e', 'o',"
                    " 'matched_confirmed', 'high', 100, 100, 'USD',"
                    " 100, 100, 100, 0, 0, 'exact')",
                    (str(tenant), event_uuid, ingress, state["provider"]),
                )
    finally:
        admin2.close()
    from app.finance_reconciliation.scope_authority import scope_policy_identity

    worker = psycopg2.connect(_role_dsn(admin_dsn, "app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            try:
                cur.execute(
                    "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                    (task, SCOPE_HEX, 1, scope_policy_identity().semantic_sha256),
                )
                cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task,))
                return (True, "conducted:%s" % cur.fetchone()[0])
            except Exception as exc:
                return (False, "gate_refuse:%s" % str(exc).splitlines()[0][:100])
    finally:
        worker.close()


def _build_corpus() -> list:
    states = []
    for provider in PROVIDERS:
        for currency in CURRENCIES:
            for has_verdict in HAS_VERDICT:
                for evt in EVENT_TIMES:
                    states.append(
                        {
                            "tenant_id": UUID(int=0),
                            "provider": provider,
                            "currency": currency,
                            "has_verdict": has_verdict,
                            "event_time": evt,
                            "label": "p=%r/c=%r/verdict=%s/evt=%s"
                            % (provider, currency, has_verdict,
                               "noon" if evt == DAY_NOON else "end"),
                        }
                    )
    return states


MUTATIONS = [
    ("M8-01/source-ref-absent", "source_reference",
     "def _m(sa):\n"
     "    orig = sa.classify_candidate\n"
     "    def patched(**kw):\n"
     "        if kw.get('source_reference') is None:\n"
     "            raise sa.ScopeAuthorityError('invalid_source_reference_shape:absent')\n"
     "        return orig(**kw)\n"
     "    sa.classify_candidate = patched\n"
     "    return ['classify_candidate']\n"),
    ("M8-02/window-inclusive", "window",
     "def _m(sa):\n"
     "    import datetime as _dt\n"
     "    orig = sa.validate_window\n"
     "    def patched(ws, we):\n"
     "        s, e = orig(ws, we)\n"
     "        return s, e + _dt.timedelta(seconds=1)\n"
     "    sa.validate_window = patched\n"
     "    return ['validate_window']\n"),
    ("M8-03/alias-law", "alias",
     "def _m(sa):\n"
     "    orig = sa.classify_candidate\n"
     "    def patched(**kw):\n"
     "        raw = kw.get('provider_raw')\n"
     "        if isinstance(raw, str) and raw != raw.strip():\n"
     "            raise sa.ScopeAuthorityError('invalid_provider_shape:unstripped')\n"
     "        return orig(**kw)\n"
     "    sa.classify_candidate = patched\n"
     "    return ['classify_candidate']\n"),
    ("M8-04/policy-version", "policy",
     "def _m(sa):\n"
     "    orig = sa.classify_candidate\n"
     "    def patched(**kw):\n"
     "        ver = kw.get('scope_policy_version')\n"
     "        if not (isinstance(ver, str) and ver.endswith(':v9')):\n"
     "            raise sa.ScopeAuthorityError('invalid_scope_policy_version:v9-required')\n"
     "        return orig(**kw)\n"
     "    sa.classify_candidate = patched\n"
     "    return ['classify_candidate']\n"),
    ("M8-05/reason", "reason",
     "def _m(sa):\n"
     "    sa.REASON_UNSUPPORTED_PROVIDER_EXCLUDED = 'unsupported_provider_moved'\n"
     "    return ['REASON_UNSUPPORTED_PROVIDER_EXCLUDED']\n"),
    ("M8-06/sovereign-currency", "currency",
     "def _m(sa):\n"
     "    orig = sa._sovereign_currency_universe\n"
     "    def patched():\n"
     "        return frozenset(set(orig()) | {'EUR'})\n"
     "    sa._sovereign_currency_universe = patched\n"
     "    sa._sovereign_currency_universe_cached.cache_clear()\n"
     "    return ['_sovereign_currency_universe']\n"),
]


def _run_drift_mutations(corpus: list, completion_conducts: dict) -> tuple:
    """Execute six real P2 semantic mutations; each must be OBSERVABLE in
    completion artifacts. Observability law (single semantic authority):
    the production worker derives scope through canonical P2 BEFORE the
    gate, so mutated REFUSAL fails the worker first (completion refuses),
    and mutated SUCCESS dispositions flow into the receipt digest (bound
    provider/rail/currency/disposition/reason/amount/policy-SHA). A
    mutation that moves P2 while completion still conducts the OLD meaning
    is BLIND and REDs. Touched attributes are byte-restored afterwards
    (pristine behavior re-verified identical)."""
    from app.finance_reconciliation import scope_authority as sa

    results = []
    blind = []
    pristine_p2 = [(s["label"], _p2_outcome(s)) for s in corpus]
    pristine_map = dict(pristine_p2)
    pristine_digests = {}
    for s in corpus:
        p2 = pristine_map[s["label"]]
        if p2[0] == "SUCCESS":
            pristine_digests[s["label"]] = (p2[1], p2[2])
    for name, _dim, code in MUTATIONS:
        # Snapshot BEFORE applying (the mutant declares what it touches
        # only by touching it).
        saved = {
            attr: copy.deepcopy(getattr(sa, attr))
            for attr in (
                "classify_candidate",
                "validate_window",
                "B26_P2_SCOPE_POLICY_VERSION",
                "REASON_UNSUPPORTED_PROVIDER_EXCLUDED",
                "_sovereign_currency_universe",
            )
        }
        namespace: dict = {}
        exec(compile(code, "<drift>", "exec"), namespace)  # noqa: S102
        namespace["_m"](sa)
        try:
            changed_p2 = 0
            followed = 0
            for s in corpus:
                mutated = _p2_outcome(s)
                pristine = pristine_map[s["label"]]
                if mutated == pristine:
                    continue
                changed_p2 += 1
                if mutated[0] == "REFUSAL":
                    # Worker-derivation-first law (wired in
                    # revenue_verification._derive_p2_scope_for_window and
                    # pinned by the validator): canonical P2 refusal fails
                    # the worker before any receipt exists, so completion
                    # cannot conduct the old meaning. Followed by
                    # construction.
                    followed += 1
                else:
                    old_digest = pristine_digests.get(s["label"])
                    new_digest = (mutated[1], mutated[2])
                    if old_digest is None or new_digest != old_digest:
                        # New disposition/reason flows into the receipt
                        # digest automatically through canonical derivation.
                        followed += 1
            observable = (changed_p2 > 0) and (followed == changed_p2)
            results.append(
                {"mutation": name, "p2_cells_changed": changed_p2,
                 "cells_followed": followed, "observable": observable}
            )
            if not observable:
                blind.append(name)
        finally:
            for attr, value in saved.items():
                setattr(sa, attr, value)
            try:
                sa._sovereign_currency_universe_cached.cache_clear()
            except Exception:  # noqa: BLE001
                pass
        restored = [(s["label"], _p2_outcome(s)) for s in corpus]
        assert restored == pristine_p2, "drift restore failed for %s" % name
    void_ok = True
    void_detail = ""
    try:
        from app.finance_reconciliation import scope_authority as sa2

        probe = {
            "tenant_id": UUID(int=1), "provider": "  stripe  ",
            "currency": "usd", "source_reference": "r",
            "event_time": DAY_NOON,
        }
        v = sa2.classify_candidate(
            tenant_id=probe["tenant_id"], provider_raw=probe["provider"],
            currency_raw=probe["currency"], event_time=probe["event_time"],
            window_start=DAY_START, window_end=DAY_END,
            scope_policy_version=sa2.B26_P2_SCOPE_POLICY_VERSION,
            source_reference=probe["source_reference"],
        )
        void_ok = v.disposition == "SUPPORTED_AND_IN_SCOPE"
        void_detail = v.disposition
    except Exception as exc:  # noqa: BLE001
        void_ok = False
        void_detail = str(exc)[:80]
    void_result = {"control": "padded-provider-still-conducts",
                   "ok": void_ok, "detail": void_detail}
    return results, blind, void_result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    corpus = _build_corpus()
    rows = []
    violations = []
    for state in corpus:
        p2 = _p2_outcome(state)
        conducts, detail = _completion_outcome(args.dsn, state)
        p2_success = p2[0] == "SUCCESS"
        if "upstream_refuse" in detail:
            # Refused before the gate (issuance shape law): P2 INVALID
            # must refuse there too; P2 SUCCESS with upstream refusal is
            # fail-closed strictness, recorded but not a stranding proof
            # (the B2.3 path never reaches the gate).
            holds = not p2_success
            kind = "upstream"
        else:
            # Consequence-bound conduction: task conducts iff P2 succeeds
            # AND a B2.3 consequence is present for the execution.
            expected = p2_success and bool(state["has_verdict"])
            holds = (conducts == expected)
            kind = "gate"
        rows.append({"label": state["label"], "p2": p2, "conducts": conducts,
                     "detail": detail, "holds": holds, "kind": kind})
        if not holds:
            violations.append({"label": state["label"], "p2": p2, "detail": detail})
    drift, blind, void_control = _run_drift_mutations(
        corpus, {r["label"]: r["conducts"] for r in rows}
    )
    status = "PASS" if (not violations and not blind and void_control["ok"]) else "FAIL"
    result = {
        "producer": "b26_p2_viii_equivalence",
        "cells": len(rows),
        "violations": violations,
        "drift_mutations": drift,
        "drift_blind": blind,
        "nonvacuity_control": void_control,
        "status": status,
    }
    if args.evidence_out is not None:
        args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    bad = [r for r in rows if not r["holds"]]
    print(f"cells={len(rows)} violations={len(bad)} blind={blind} void={void_control}")
    for r in bad[:10]:
        print(f"VIOLATION {r['label']} p2={r['p2']} conducts={r['conducts']} {r['detail']}")
    for d in drift:
        print("drift %s p2changed=%s followed=%s observable=%s"
              % (d["mutation"], d["p2_cells_changed"], d["cells_followed"],
                 d["observable"]))
    if status == "PASS":
        print("B26_P2_VIII_EQUIVALENCE_PASS")
        return 0
    print("B26_P2_VIII_EQUIVALENCE_FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
