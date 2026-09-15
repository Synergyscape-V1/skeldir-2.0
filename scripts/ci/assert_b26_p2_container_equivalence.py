#!/usr/bin/env python3
"""Compare the P2 candidate scope authority with the production image bytes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(REPO_ROOT))


def _run(*command: str) -> str:
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


_P2_IN_IMAGE_PROBE = r'''
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

report = {}

from app.finance_reconciliation.scope_authority import (
    B26_P2_SCOPE_POLICY_VERSION,
    classify_candidate,
    load_b26_p2_scope_policy,
    normalize_provider_set,
    scope_policy_identity,
)

identity = scope_policy_identity()
report["policy_version_ok"] = identity.scope_policy_version == B26_P2_SCOPE_POLICY_VERSION
report["policy_phase_ok"] = identity.phase == "B2.6-P2"
document = load_b26_p2_scope_policy()
report["contract_pin_ok"] = document.get("module_ast_sha256") is not None
report["dispositions_ok"] = set(document.get("dispositions", [])) == {
    "SUPPORTED_AND_IN_SCOPE",
    "SUPPORTED_BUT_UNRESOLVED",
    "EXPLICITLY_EXCLUDED",
    "INVALID_OR_REFUSED",
}

ws = datetime(2026, 1, 1, tzinfo=timezone.utc)
we = datetime(2026, 2, 1, tzinfo=timezone.utc)
occ = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
tenant = UUID("11111111-2222-3333-4444-555555555555")
ver = B26_P2_SCOPE_POLICY_VERSION

def classify(**over):
    base = {
        "tenant_id": tenant,
        "provider_raw": "stripe",
        "currency_raw": "USD",
        "event_time": occ,
        "window_start": ws,
        "window_end": we,
        "scope_policy_version": ver,
        "source_reference": "ord-1",
    }
    base.update(over)
    return classify_candidate(**base)

vectors_ok = True
if classify().disposition != "SUPPORTED_AND_IN_SCOPE":
    vectors_ok = False
if classify(provider_raw="square").disposition != "EXPLICITLY_EXCLUDED":
    vectors_ok = False
if classify(currency_raw="EUR").reason != "unsupported_currency_excluded":
    vectors_ok = False
if classify(event_time=we).reason != "outside_governed_window_excluded":
    vectors_ok = False
if classify(event_time=ws).disposition != "SUPPORTED_AND_IN_SCOPE":
    vectors_ok = False
if classify(event_time=we - timedelta(microseconds=1)).disposition != "SUPPORTED_AND_IN_SCOPE":
    vectors_ok = False
if classify(source_reference=None).disposition != "SUPPORTED_BUT_UNRESOLVED":
    vectors_ok = False
try:
    classify(tenant_id="bad")
except Exception:
    pass
else:
    vectors_ok = False
report["vectors_ok"] = vectors_ok
report["universe_ok"] = normalize_provider_set(None) == ("paypal", "shopify", "stripe", "woocommerce")

from app.finance_reconciliation.coverage_authority import _normalize_platforms
report["delegation_ok"] = _normalize_platforms(None) == normalize_provider_set(None)

sink_source = open("app/finance_reconciliation/canonical_sink.py", encoding="utf-8").read()
report["wiring_ok"] = "_p2_scope.assert_aggregate_scope_supported(" in sink_source

print("P2_IN_IMAGE_BATTERY " + json.dumps(report, sort_keys=True))
'''


def _in_image_p2_battery(image: str) -> dict[str, object]:
    proc = subprocess.run(
        ["docker", "run", "--rm", "-i", image, "python", "-"],
        input=_P2_IN_IMAGE_PROBE,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"container_p2_battery_failed:{proc.stderr[-800:]}")
    line = next(
        (ln for ln in proc.stdout.splitlines() if ln.startswith("P2_IN_IMAGE_BATTERY ")),
        None,
    )
    if line is None:
        raise RuntimeError(f"container_p2_battery_output_missing:{proc.stdout[-400:]}")
    report = json.loads(line[len("P2_IN_IMAGE_BATTERY ") :])
    failed = sorted(k for k, v in report.items() if v is not True)
    if failed:
        raise RuntimeError(f"container_p2_battery_red:{failed}")
    return report


def validate(image: str) -> dict[str, object]:
    sys.path.insert(0, str(BACKEND))
    from app.finance_reconciliation.scope_authority import (  # noqa: PLC0415
        scope_policy_identity,
    )

    host = scope_policy_identity().__dict__
    probe = (
        "import json;"
        "from app.finance_reconciliation.scope_authority import scope_policy_identity;"
        "print(json.dumps(scope_policy_identity().__dict__,sort_keys=True))"
    )
    output = _run("docker", "run", "--rm", image, "python", "-c", probe)
    try:
        container = json.loads(output.splitlines()[-1])
    except (IndexError, ValueError) as exc:
        raise RuntimeError(f"container_p2_identity_malformed:{output}") from exc
    if container != host:
        raise RuntimeError(
            f"container_p2_identity_mismatch:host={host}:container={container}"
        )
    battery = _in_image_p2_battery(image)
    inspect = json.loads(_run("docker", "image", "inspect", image))[0]
    return {
        "image": image,
        "image_id": inspect["Id"],
        "host_scope_policy_identity": host,
        "container_scope_policy_identity": container,
        "container_p2_battery": battery,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--evidence-out", type=Path)
    args = parser.parse_args()
    try:
        details = validate(args.image)
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"B26_P2_CONTAINER_EQUIVALENCE_FAIL {exc}")
        return 1
    if args.evidence_out:
        from scripts.ci.b26_p2_evidence import write_evidence_cell  # noqa: PLC0415

        write_evidence_cell(
            args.evidence_out,
            gate_id="B26-P2-G9-PRODUCTION-ARTIFACT-EQUIVALENCE",
            producer="b26-p2-container-equivalence",
            scenario_id="candidate-production-image",
            falsifier_id="p2-stale-artifact-substitution",
            details=details,
        )
    print("B26_P2_CONTAINER_EQUIVALENCE_PASS")
    print(json.dumps(details, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
