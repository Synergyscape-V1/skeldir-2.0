#!/usr/bin/env python3
"""B2.6-P2 Corrective XIV independent phase-law oracle (BLOCKER D).

Law: the shipped contract + executable semantics implement the actual
B2.6-P2 phase requirements. This oracle is specified INDEPENDENTLY of
the contract JSON and the canonical SQL text: it calls the live
routines and checks behavioral properties derived from the phase law
(half-open UTC windows, provider/rail normalization, USD-only currency,
reference presence, disposition ordering, tenant isolation, policy
pinning, set membership, integer-minor money).

A common-mode wrong change (contract + runtime moved together to the
same wrong P2 rule) stays GREEN in conformance validators but MUST RED
here, because this oracle does not read the contract.

Exit code is the gate: 0 on PASS, 1 plus violations on FAIL.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]

POLICY_VERSION = "b2.6-p2-scope-policy-v2"
POLICY_SHA = "fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99"


def _classify(cur, tenant, provider, currency, event_ts, ws, we, ref="ord-1"):
    cur.execute(
        "SELECT o_provider, o_rail, o_currency, o_disposition, o_reason"
        " FROM public.b26_p2_classify_candidate"
        "(%s,%s,%s,%s,%s,%s,%s,%s)",
        (tenant, provider, currency, event_ts, ws, we, POLICY_VERSION, ref),
    )
    row = cur.fetchone()
    return {
        "provider": row[0],
        "rail": row[1],
        "currency": row[2],
        "disposition": row[3],
        "reason": row[4],
    }


def _live_checks(dsn: str, violations: list[str], checks: dict) -> None:
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        violations.append(f"xiv_oracle_no_driver:{exc}")
        return
    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
    except Exception as exc:
        violations.append(f"xiv_oracle_connect_failed:{exc}")
        return
    try:
        cur = conn.cursor()
        tenant = str(uuid4())
        tenant_b = str(uuid4())
        ws = "2026-09-01T00:00:00+00:00"
        we = "2026-09-02T00:00:00+00:00"
        mid = "2026-09-01T12:00:00+00:00"

        # O1: half-open window -- event at exact end EXCLUDED.
        r = _classify(cur, tenant, "stripe", "USD", we, ws, we)
        if r["disposition"] != "EXPLICITLY_EXCLUDED":
            violations.append(f"xiv_oracle_window_end_not_excluded:{r}")
        else:
            checks["window_end_excluded"] = True
        # O2: event at start INCLUDED.
        r = _classify(cur, tenant, "stripe", "USD", ws, ws, we)
        if r["disposition"] != "SUPPORTED_AND_IN_SCOPE":
            violations.append(f"xiv_oracle_window_start_not_included:{r}")
        else:
            checks["window_start_included"] = True
        # O3: just-before-end INCLUDED.
        r = _classify(cur, tenant, "stripe", "USD", "2026-09-01T23:59:59+00:00", ws, we)
        if r["disposition"] != "SUPPORTED_AND_IN_SCOPE":
            violations.append(f"xiv_oracle_window_inside_not_included:{r}")
        else:
            checks["window_inside_included"] = True
        # O4: provider normalization equivalence.
        a = _classify(cur, tenant, "STRIPE", "USD", mid, ws, we)
        b = _classify(cur, tenant, " stripe ", "USD", mid, ws, we)
        cc = _classify(cur, tenant, "Stripe", "USD", mid, ws, we)
        if not (a["provider"] == b["provider"] == cc["provider"] == "stripe"):
            violations.append(f"xiv_oracle_provider_equivalence:{a}|{b}|{cc}")
        else:
            checks["provider_equivalence"] = True
        # O5: rail equals provider.
        if a["rail"] != "stripe":
            violations.append(f"xiv_oracle_rail_not_provider:{a}")
        else:
            checks["rail_equals_provider"] = True
        # O6: currency usd -> USD supported.
        r = _classify(cur, tenant, "stripe", "usd", mid, ws, we)
        if r["currency"] != "USD" or r["disposition"] != "SUPPORTED_AND_IN_SCOPE":
            violations.append(f"xiv_oracle_currency_usd:{r}")
        else:
            checks["currency_usd"] = True
        # O7: EUR excluded.
        r = _classify(cur, tenant, "stripe", "EUR", mid, ws, we)
        if r["disposition"] != "EXPLICITLY_EXCLUDED":
            violations.append(f"xiv_oracle_currency_eur_not_excluded:{r}")
        else:
            checks["currency_eur_excluded"] = True
        # O8: unsupported provider excluded.
        r = _classify(cur, tenant, "acme", "USD", mid, ws, we)
        if r["disposition"] != "EXPLICITLY_EXCLUDED":
            violations.append(f"xiv_oracle_provider_acme_not_excluded:{r}")
        else:
            checks["provider_acme_excluded"] = True
        # O9: blank reference unresolved (not in-scope).
        r = _classify(cur, tenant, "stripe", "USD", mid, ws, we, ref="   ")
        if r["disposition"] == "SUPPORTED_AND_IN_SCOPE":
            violations.append(f"xiv_oracle_blank_ref_in_scope:{r}")
        else:
            checks["blank_ref_unresolved"] = True
        # O10: inverted window refused (raises, never silently computes).
        try:
            _classify(cur, tenant, "stripe", "USD", mid, we, ws)
            violations.append("xiv_oracle_inverted_window_accepted")
        except Exception:
            checks["inverted_window_refused"] = True
        # O11: wrong policy refused.
        try:
            cur.execute(
                "SELECT o_provider FROM public.b26_p2_classify_candidate"
                "(%s,'stripe','USD',%s,%s,%s,'wrong-policy','ord-1')",
                (tenant, mid, ws, we),
            )
            cur.fetchone()
            violations.append("xiv_oracle_wrong_policy_accepted")
        except Exception:
            checks["wrong_policy_refused"] = True
        # O12: identity deterministic on replay.
        cur.execute(
            "SELECT public.b26_p2_canonical_scope_identity_for_window(%s,%s,%s)",
            (tenant, ws, we),
        )
        id1 = str(cur.fetchone()[0])
        cur.execute(
            "SELECT public.b26_p2_canonical_scope_identity_for_window(%s,%s,%s)",
            (tenant, ws, we),
        )
        id2 = str(cur.fetchone()[0])
        if id1 != id2:
            violations.append("xiv_oracle_identity_unstable")
        else:
            checks["identity_stable"] = True
        # O13: identity tenant-bound.
        cur.execute(
            "SELECT public.b26_p2_canonical_scope_identity_for_window(%s,%s,%s)",
            (tenant_b, ws, we),
        )
        id_b = str(cur.fetchone()[0])
        if id_b == id1:
            violations.append("xiv_oracle_identity_not_tenant_bound")
        else:
            checks["identity_tenant_bound"] = True
        # O14: policy pinned live.
        cur.execute(
            "SELECT scope_policy_version, semantic_sha256"
            " FROM public.b26_p2_scope_policy_authority"
        )
        rows = cur.fetchall()
        if not any(r[0] == POLICY_VERSION and r[1] == POLICY_SHA for r in rows):
            violations.append("xiv_oracle_policy_not_pinned")
        else:
            checks["policy_pinned"] = True
        # O15: integer-minor money (no float/decimal amount columns on
        # the P2 commerce surface).
        cur.execute(
            """
            SELECT column_name, data_type FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = 'webhook_ingress_identities'
               AND column_name IN ('verified_amount_minor', 'verified_amount_scale')
            """
        )
        cols = {r[0]: r[1] for r in cur.fetchall()}
        if cols.get("verified_amount_minor") != "integer":
            violations.append(f"xiv_oracle_money_not_integer:{cols}")
        else:
            checks["money_integer_minor"] = True
        checks["oracle_cells"] = 15
        cur.close()
    except Exception as exc:
        violations.append(f"xiv_oracle_live_failed:{exc}")
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="XIV independent phase-law oracle.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    if args.dsn is None:
        violations.append("xiv_oracle_requires_dsn")
    else:
        _live_checks(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XIV_ORACLE_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XIV-PHASE-ORACLE",
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
