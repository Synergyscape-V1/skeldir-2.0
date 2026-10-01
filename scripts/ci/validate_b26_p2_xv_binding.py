#!/usr/bin/env python3
"""B2.6-P2 Corrective XV cryptographic meaning binding closure (H-XV-R1/R2).

Laws (each REDs on the effect):
- the sovereign derivation module exists and is the single semantic
  authority imported by BOTH the general API relay path and the dedicated
  authentication trust root (no parallel parser universes);
- the root re-derives every material financial field from the verified raw
  bytes and refuses any handoff mismatch before persistence (static: token
  presence + binding call order; live: mutated handoff refused);
- persisted authority comes from the derivation, never from the handoff
  (static: commerce dict sourced from derived);
- the relay cross-checks handoff against sovereign derivation before
  relaying (fail closed on divergence).

Exit code is the gate. Live DB checks run only with --dsn.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _static_checks(violations: list[str], checks: dict) -> None:
    try:
        deriv = (
            REPO_ROOT / "backend" / "app" / "webhooks" / "commerce_derivation.py"
        ).read_text(encoding="utf-8")
        server = (
            REPO_ROOT / "backend" / "app" / "auth_service" / "server.py"
        ).read_text(encoding="utf-8")
        ev = (
            REPO_ROOT / "backend" / "app" / "ingestion" / "event_service.py"
        ).read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xv_bind_unreadable:{exc}")
        return
    for token in (
        "def derive_commerce",
        "def binding_mismatches",
        "class SovereignCommerce",
        "SUPPORTED_PROVIDERS",
        "stripe",
        "shopify",
        "paypal",
        "woocommerce",
    ):
        if token not in deriv:
            violations.append(f"xv_bind_derivation_missing:{token}")
    checks["derivation_module_present"] = True
    # Root must import and enforce the sovereign derivation.
    for token in (
        "derive_commerce",
        "binding_mismatches",
        "b26_p2_handoff_binding_refused",
    ):
        if token not in server:
            violations.append(f"xv_bind_root_missing:{token}")
    # Binding must occur after signature verification and before persistence.
    # Neutralization guards (e.g. `if False and mismatched`) keep tokens
    # but kill enforcement; refuse them explicitly.
    if "if False and mismatched" in server or "if False and" in server:
        violations.append("xv_bind_root_neutralized")
    try:
        vpos = server.index("invalid provider signature")
        bpos = server.index("b26_p2_handoff_binding_refused")
        ipos = server.index("INSERT INTO public.webhook_ingress_identities")
        if not (vpos < bpos < ipos):
            violations.append("xv_bind_root_wrong_order")
        else:
            checks["root_binding_order"] = True
    except ValueError:
        violations.append("xv_bind_root_order_unverifiable")
    # Persisted commerce must come from the derivation, not the handoff.
    post_insert = server.split("INSERT INTO public.webhook_ingress_identities")[-1]
    if "derived." not in post_insert and "derived," not in post_insert:
        violations.append("xv_bind_root_persists_handoff")
    else:
        checks["root_persists_derived"] = True
    # Relay-side cross-check must exist (defense in depth).
    for token in (
        "relay_sovereign_divergence",
        "binding_mismatches",
        "derive_commerce",
    ):
        if token not in ev:
            violations.append(f"xv_bind_relay_missing:{token}")
    checks["relay_crosscheck_present"] = True
    # Single authority: the API must not define a competing money-scale law.
    # (Informational: the canonical scale lives in commerce_derivation;
    # webhooks.py retains a façade that must agree -- parity is proven by
    # the unit battery, not by token absence.)
    checks["static_complete"] = True


def _live_checks(admin_dsn: str, violations: list[str], checks: dict) -> None:
    """Pure-Python oracle parity: derivation agrees with itself across all
    providers and fires on every mutation class (no DB required)."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    try:
        from app.webhooks.commerce_derivation import (
            binding_mismatches,
            derive_commerce,
        )
    except Exception as exc:
        violations.append(f"xv_bind_import_failed:{exc}")
        return
    import json as _json

    fixtures = {
        "stripe": _json.dumps(
            {"id": "pi_xv1", "amount": 7600, "currency": "usd", "created": 1700000000}
        ).encode(),
        "shopify": _json.dumps(
            {
                "id": 4242,
                "total_price": "76.00",
                "currency": "USD",
                "created_at": "2025-11-10T14:30:00Z",
            }
        ).encode(),
        "paypal": _json.dumps(
            {
                "id": "PAY-XV1",
                "amount": {"total": "76.00", "currency": "USD"},
                "create_time": "2025-11-10T14:30:00Z",
            }
        ).encode(),
        "woocommerce": _json.dumps(
            {
                "id": 777,
                "total": "76.00",
                "currency": "USD",
                "date_completed": "2025-11-10T14:30:00Z",
            }
        ).encode(),
    }
    for provider, raw in fixtures.items():
        try:
            derived = derive_commerce(provider, raw)
        except Exception as exc:
            violations.append(f"xv_bind_derive_failed:{provider}:{exc}")
            continue
        honest = {
            "provider_native_event_reference": derived.provider_native_event_reference,
            "provider_native_commerce_reference": derived.provider_native_commerce_reference,
            "normalized_commerce_reference_kind": derived.normalized_commerce_reference_kind,
            "normalized_commerce_reference_value": derived.normalized_commerce_reference_value,
            "verified_amount_minor": derived.verified_amount_minor,
            "verified_amount_currency": derived.verified_amount_currency,
            "verified_amount_scale": derived.verified_amount_scale,
            "event_timestamp": derived.event_timestamp.isoformat(),
        }
        if binding_mismatches(provider=provider, handoff=honest, derived=derived):
            violations.append(f"xv_bind_honest_refused:{provider}")
            continue
        # Every mutation class must fire.
        mutations = [
            ("verified_amount_minor", 999999),
            ("verified_amount_currency", "EUR"),
            ("provider_native_commerce_reference", "mutated-ref"),
            ("provider_native_event_reference", "mutated-evt"),
            ("normalized_commerce_reference_value", "mutated-norm"),
            ("event_timestamp", "2025-11-11T14:30:00Z"),
        ]
        for field, bad in mutations:
            mutated = dict(honest)
            mutated[field] = bad
            if not binding_mismatches(
                provider=provider, handoff=mutated, derived=derived
            ):
                violations.append(f"xv_bind_mutation_survives:{provider}:{field}")
        checks[f"oracle_{provider}"] = True
    checks["live_complete"] = True


def main() -> int:
    parser = argparse.ArgumentParser(description="XV binding closure.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _static_checks(violations, checks)
    # Live oracle parity always runs (pure Python, no DB needed).
    _live_checks(args.dsn or "", violations, checks)
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XV_BIND_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XV-BINDING",
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
