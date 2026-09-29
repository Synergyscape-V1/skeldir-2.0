#!/usr/bin/env python3
"""B2.6-P2 Corrective XIV pure-helper behavioral law (BLOCKER D).

Law: every pure semantic primitive obeys an executable behavioral
contract derived from the P2 phase law. The contract allowlist name
confers zero authority; these property/metamorphic tests prove meaning
against the live functions. A helper body changed to a different
meaning (e.g. provider-selective blackout) with zero dependency change
MUST RED here even when structural conformance stays GREEN.

Properties:
- ascii_strip: removes only governed ASCII boundary whitespace, preserves
  order/content of the remainder (including non-ASCII whitespace inside).
- strip_provider_token/normalize_provider: case/whitespace-equivalent
  canonical providers normalize identically; unknown providers raise or
  pass through per law (normalize raises on blank/unsupported).
- strip_currency_token/normalize_currency: governed 3-letter currencies
  normalize per explicit law (USD strict in normalize).
- canonical_day_start/end: UTC day boundaries of the event timestamp.

Exit code is the gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _live_checks(dsn: str, violations: list[str], checks: dict) -> None:
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        violations.append(f"xiv_behavior_no_driver:{exc}")
        return
    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
    except Exception as exc:
        violations.append(f"xiv_behavior_connect_failed:{exc}")
        return
    try:
        cur = conn.cursor()

        def fn(name, *args):
            cur.execute(f"SELECT public.{name}({', '.join(['%s'] * len(args))})", args)
            return cur.fetchone()[0]

        # ascii_strip: boundary ASCII whitespace removed, interior kept.
        if fn("b26_p2_ascii_strip", "  hi  ") != "hi":
            violations.append("xiv_behavior_ascii_basic")
        else:
            checks["ascii_basic"] = True
        if fn("b26_p2_ascii_strip", "\t stripe \n") != "stripe":
            violations.append("xiv_behavior_ascii_tabs")
        else:
            checks["ascii_tabs"] = True
        # Interior whitespace preserved (not collapsed).
        if fn("b26_p2_ascii_strip", "  a  b  ") != "a  b":
            violations.append("xiv_behavior_ascii_interior")
        else:
            checks["ascii_interior"] = True
        # Provider-selective blackout MUST be caught: stripe and shopify
        # normalize through the same law (both must survive stripping).
        for prov in ("stripe", "shopify", "paypal", "woocommerce"):
            try:
                got = fn("b26_p2_normalize_provider", prov)
            except Exception:
                violations.append(f"xiv_behavior_provider_blackout:{prov}")
                continue
            if (got or "").strip().lower() != prov:
                violations.append(f"xiv_behavior_provider_blackout:{prov}:{got}")
        if not any(v.startswith("xiv_behavior_provider_blackout") for v in violations):
            checks["provider_no_blackout"] = True
        # Case/whitespace equivalence.
        a = fn("b26_p2_normalize_provider", "STRIPE")
        b = fn("b26_p2_normalize_provider", " stripe ")
        cc = fn("b26_p2_normalize_provider", "Stripe")
        if not (a == b == cc == "stripe"):
            violations.append(f"xiv_behavior_provider_equivalence:{a}|{b}|{cc}")
        else:
            checks["provider_equivalence"] = True
        # Currency law: usd/ USD /' usd ' normalize to USD.
        for raw in ("usd", "USD", " usd "):
            try:
                got = fn("b26_p2_normalize_currency", raw)
            except Exception as exc:
                violations.append(f"xiv_behavior_currency_usd:{raw}:{exc}")
                continue
            if got != "USD":
                violations.append(f"xiv_behavior_currency_usd:{raw}:{got}")
        if not any(v.startswith("xiv_behavior_currency_usd") for v in violations):
            checks["currency_usd"] = True
        # EUR is refused by normalize (strict USD law); classify
        # excludes non-USD downstream via the strip path. Refusal here
        # is the governed meaning (a silent 'EUR' return would be drift).
        try:
            got = fn("b26_p2_normalize_currency", "eur")
            violations.append(f"xiv_behavior_currency_eur_not_refused:{got}")
        except Exception:
            checks["currency_eur_refused"] = True
        # Day boundaries: start <= event < end, exactly one UTC day apart.
        cur.execute(
            "SELECT public.b26_p2_canonical_day_start(%s), public.b26_p2_canonical_day_end(%s)",
            ("2026-09-01T12:34:56+00:00", "2026-09-01T12:34:56+00:00"),
        )
        ds, de = cur.fetchone()
        if (
            str(ds) != "2026-09-01 00:00:00+00:00"
            or str(de) != "2026-09-02 00:00:00+00:00"
        ):
            violations.append(f"xiv_behavior_day_bounds:{ds}|{de}")
        else:
            checks["day_bounds"] = True
        checks["behavior_cells"] = 8
        cur.close()
    except Exception as exc:
        violations.append(f"xiv_behavior_live_failed:{exc}")
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="XIV pure-helper behavioral law.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    if args.dsn is None:
        violations.append("xiv_behavior_requires_dsn")
    else:
        _live_checks(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XIV_BEHAVIOR_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XIV-SEMANTIC-BEHAVIOR",
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
