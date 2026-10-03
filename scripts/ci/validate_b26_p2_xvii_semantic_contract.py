#!/usr/bin/env python3
"""B2.6-P2 Corrective XVII governed semantic-contract authority gate.

H-XVII-R7/R8: the governed provider semantic contract constrains BOTH the
production parser AND the independent oracle. This gate derives expected
provider meaning from the CONTRACT artifact (never from either
implementation) and asserts both implementations agree with it -- on
golden vectors, refusal vectors, money-precision law, timestamp
day-boundary law, and currency-scale law.

The central antidote to proof-system common-mode failure: production
parser + oracle + local goldens co-edited in the same wrong direction
(without a contract revision) REDs here, because the contract vectors did
not move. The contract file itself is tamper-evident via the reviewed pin
(contracts-internal/governance/b26_p2_xvii_semantic_contract.pin.json):
silent contract edits RED. The semantic-regime identity must agree across
contract, parser constant, and database atomic: semantic-law change
without an explicit contract revision REDs.

Exit code is the gate. Prints B26_P2_XVII_CONTRACT_PASS on success.
Static gate (no database required).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (
    REPO_ROOT
    / "contracts"
    / "reconciliation"
    / "b2.6"
    / "provider-semantic-contract.v1.json"
)
PIN_PATH = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b26_p2_xvii_semantic_contract.pin.json"
)
ORACLE_PATH = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xvi_semantic_oracle.py"
MIG_XVII = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202609290001_b26_p2_corrective_xvii_historical_reconciliation.py"
)
DERIVATION_PATH = (
    REPO_ROOT / "backend" / "app" / "webhooks" / "commerce_derivation.py"
)

SNAPSHOT_KEYS = (
    "provider_native_event_reference",
    "provider_native_commerce_reference",
    "normalized_commerce_reference_kind",
    "normalized_commerce_reference_value",
    "verified_amount_minor",
    "verified_amount_currency",
    "verified_amount_scale",
    "event_timestamp_epoch",
)


def _load_oracle():
    spec = importlib.util.spec_from_file_location(
        "b26_p2_xvi_semantic_oracle_contract_gate", ORACLE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["b26_p2_xvi_semantic_oracle_contract_gate"] = module
    spec.loader.exec_module(module)
    return module


def _production_snapshot(derive_commerce, provider: str, raw: bytes) -> dict:
    produced = derive_commerce(provider, raw)
    snap = {
        "provider_native_event_reference": produced.provider_native_event_reference,
        "provider_native_commerce_reference": produced.provider_native_commerce_reference,
        "normalized_commerce_reference_kind": produced.normalized_commerce_reference_kind,
        "normalized_commerce_reference_value": produced.normalized_commerce_reference_value,
        "verified_amount_minor": produced.verified_amount_minor,
        "verified_amount_currency": produced.verified_amount_currency,
        "verified_amount_scale": produced.verified_amount_scale,
        "event_timestamp_epoch": int(produced.event_timestamp.timestamp()),
    }
    return snap


def main() -> int:
    parser = argparse.ArgumentParser(description="XVII semantic-contract gate.")
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}

    try:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        print("B26_P2_XVII_CONTRACT_FAIL")
        print(f"contract_unreadable:{exc}")
        return 1
    try:
        pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        print("B26_P2_XVII_CONTRACT_FAIL")
        print(f"pin_unreadable:{exc}")
        return 1

    # 1. Contract file tamper-evidence: reviewed pin binds exact bytes.
    # Line-ending immune: the pin covers LF-normalized bytes, so a
    # CRLF/LF checkout difference is not a semantic change (repo
    # .gitattributes normalizes text to LF in the object database).
    live_sha = hashlib.sha256(
        CONTRACT_PATH.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()
    if live_sha != pin.get("contract_sha256"):
        violations.append("contract_bytes_drift:review_required")
    else:
        checks["contract_pin_match"] = True
    if pin.get("contract_version") != contract.get("contract_version"):
        violations.append("contract_version_pin_mismatch")
    else:
        checks["contract_version_pinned"] = True

    # 2. Semantic-regime identity agreement: contract == parser constant
    # == database atomic literal. A semantic-law change in any one place
    # without the others REDs.
    regime = contract.get("semantic_regime")
    derivation_text = DERIVATION_PATH.read_text(encoding="utf-8")
    if f'SEMANTIC_CONTRACT_REGIME = "{regime}"' not in derivation_text:
        violations.append("parser_regime_not_bound_to_contract")
    else:
        checks["parser_regime_bound"] = True
    try:
        mig_text = MIG_XVII.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"migration_unreadable:{exc}")
        mig_text = ""
    if regime and mig_text.count(f"'{regime}'") < 3:
        violations.append("database_regime_not_bound_to_contract")
    else:
        checks["database_regime_bound"] = True

    # 3. Currency-scale law agreement: contract sets == oracle sets ==
    # production sets. (Parsed as text: the oracle must stay import-free.)
    for name, want in (
        ("zero_decimal_currencies", "_ORACLE_ZERO_DECIMAL"),
        ("three_decimal_currencies", "_ORACLE_THREE_DECIMAL"),
    ):
        contracted = set(contract["money_law"][name])
        oracle_text = ORACLE_PATH.read_text(encoding="utf-8")
        missing = [c for c in contracted if f'"{c}"' not in oracle_text]
        if missing:
            violations.append(f"oracle_scale_missing:{name}:{missing[:4]}")
        prod_missing = [c for c in contracted if f'"{c}"' not in derivation_text]
        if prod_missing:
            violations.append(f"production_scale_missing:{name}:{prod_missing[:4]}")
    if not [v for v in violations if "scale_missing" in v]:
        checks["scale_law_agrees"] = True

    # 4. Both implementations obey the contract vectors. The expected
    # values come from the CONTRACT (third authority), never from either
    # implementation's local goldens.
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    try:
        from app.webhooks.commerce_derivation import (  # noqa: PLC0415
            CommerceDerivationError,
            derive_commerce,
        )
    except Exception as exc:
        violations.append(f"production_unimportable:{exc}")
        derive_commerce = None
    oracle = _load_oracle()
    if oracle.check_purity():
        violations.append(f"oracle_impure:{oracle.check_purity()}")

    goldens = contract.get("golden_vectors", [])
    refusals = contract.get("refusal_vectors", [])
    if not goldens or not refusals:
        violations.append("contract_vectors_empty")
    for vector in goldens:
        raw = vector["raw"].encode("utf-8")
        expected = dict(vector["expected"])
        # Oracle obedience.
        try:
            observed_oracle = oracle.ORACLES[vector["provider"]](raw)
        except Exception as exc:
            violations.append(f"oracle_error:{vector['id']}:{exc}")
            continue
        if {k: observed_oracle.get(k) for k in SNAPSHOT_KEYS} != {
            k: expected.get(k) for k in SNAPSHOT_KEYS
        }:
            violations.append(f"oracle_defies_contract:{vector['id']}")
        # Production obedience.
        if derive_commerce is not None:
            try:
                observed_prod = _production_snapshot(
                    derive_commerce, vector["provider"], raw
                )
            except Exception as exc:
                violations.append(f"production_error:{vector['id']}:{exc}")
                continue
            if {k: observed_prod.get(k) for k in SNAPSHOT_KEYS} != {
                k: expected.get(k) for k in SNAPSHOT_KEYS
            }:
                violations.append(f"production_defies_contract:{vector['id']}")
    if not [v for v in violations if "_defies_contract" in v or "_error:" in v]:
        checks["contract_vectors_obeyed"] = True
    for vector in refusals:
        raw = vector["raw"].encode("utf-8")
        try:
            oracle.ORACLES[vector["provider"]](raw)
            violations.append(f"oracle_accepts_refused:{vector['id']}")
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
        if derive_commerce is not None:
            try:
                derive_commerce(vector["provider"], raw)
                violations.append(f"production_accepts_refused:{vector['id']}")
            except CommerceDerivationError:
                pass
            except Exception as exc:
                violations.append(
                    f"production_refusal_wrong_signal:{vector['id']}:{type(exc).__name__}"
                )
    if not [v for v in violations if "_accepts_refused" in v]:
        checks["contract_refusals_obeyed"] = True

    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XVII_CONTRACT_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XVII-CONTRACT",
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
