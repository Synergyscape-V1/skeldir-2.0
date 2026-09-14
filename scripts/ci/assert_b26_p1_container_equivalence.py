#!/usr/bin/env python3
"""Compare the candidate contract with the production image's loaded bytes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(REPO_ROOT))
FORBIDDEN_IMAGE_ENV = (
    "TRUST_SIGNING_SEED",
    "TRUST_SIGNING_PRIVATE_KEY",
    "MIGRATION_DATABASE_URL",
    "P14_ADMIN_DATABASE_URL",
    "B28_SOLVER_DATABASE_URL",
)


def _run(*command: str) -> str:
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


_XI_IN_IMAGE_PROBE = r'''
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

report = {}

# 1. The frozen transform contract loads and matches the shipped contract pin.
from app.finance_reconciliation.external_semantics import (
    EXTERNAL_SEMANTICS,
    external_semantics_ast_sha256,
    project_external_fields,
)
from app.finance_reconciliation.semantic_contract import load_b26_p1_semantic_contract

document = load_b26_p1_semantic_contract()
section = document["external_semantics_authority"]
report["semantics_pin_ok"] = (
    external_semantics_ast_sha256() == section["ast_sha256"]
)
report["semantics_census_ok"] = (
    set(section["governed_external_keys"]) == set(EXTERNAL_SEMANTICS)
    and len(EXTERNAL_SEMANTICS) == 14
)

# 2. The governed egress module loads under the pin (import IS the check).
import importlib

sink = importlib.import_module("app.finance_reconciliation.canonical_sink")
report["egress_loaded"] = (
    getattr(sink, "_XI_CONTRACT_PIN_AST_SHA256", None)
    == external_semantics_ast_sha256()
)
report["egress_registry"] = sorted(getattr(sink, "GOVERNED_EGRESS_SURFACES", {}))

# 3. Transform vectors execute inside the image.
instant = EXTERNAL_SEMANTICS["window_start"].transform
report["window_vector_ok"] = (
    instant(datetime(2026, 1, 1, tzinfo=timezone.utc))
    == "2026-01-01T00:00:00+00:00"
)
money = EXTERNAL_SEMANTICS["matched_minor"].transform
report["money_vector_ok"] = money(76000) == 76000 and type(money(76000)) is int
refusals = True
for key, bad in (
    ("window_start", datetime(2026, 1, 1)),
    ("matched_minor", True),
    ("matched_minor", -5),
    ("coverage_percent", Decimal("95.005")),
    ("supported_platforms", ["paypal"]),
):
    try:
        EXTERNAL_SEMANTICS[key].transform(bad)
    except ValueError:
        pass
    else:
        refusals = False
report["transform_refusals_ok"] = refusals

# 4. Projection equivalence against the pinned lawful mapping.
from types import SimpleNamespace

sovereign = SimpleNamespace(
    authority="canonical_B2.6_financial_truth",
    sink_id="future_finance_projection",
    contract_version=document["contract_version"],
    tenant_id_hash="sha256:" + "ab" * 32,
    currency_code="USD",
    window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
    window_end=datetime(
        2026, 2, 1, 12, 30, 5,
        tzinfo=timezone(timedelta(hours=2)),
    ),
    supported_platforms=("paypal", "stripe"),
    matched_minor=76000,
    connected_minor=80000,
    coverage_percent=Decimal("95.00"),
    zero_denominator=False,
    provenance_mode="RE_DERIVE_ON_READ",
    sovereign_producer=(
        "app.revenue_verification.verification_coverage."
        "fetch_verification_coverage_aggregate"
        "+app.revenue_verification.verification_coverage."
        "VERIFICATION_COVERAGE.compute"
    ),
)
report["projection_ok"] = project_external_fields(sovereign) == {
    "authority": "canonical_B2.6_financial_truth",
    "sink_id": "future_finance_projection",
    "contract_version": document["contract_version"],
    "tenant_id_hash": "sha256:" + "ab" * 32,
    "currency_code": "USD",
    "window_start": "2026-01-01T00:00:00+00:00",
    "window_end": "2026-02-01T12:30:05+02:00",
    "supported_platforms": ["paypal", "stripe"],
    "matched_minor": 76000,
    "connected_minor": 80000,
    "coverage_percent": "95.00",
    "zero_denominator": False,
    "provenance_mode": "RE_DERIVE_ON_READ",
    "sovereign_producer": sovereign.sovereign_producer,
}

# 5. Capability admission physics: lookalikes never gain authority.
from types import MappingProxyType

Capability = sink.CanonicalExternalTruth
admit = sink.admit_canonical_external
lawful = project_external_fields(sovereign)
capability = Capability(dict(lawful), sink._EGRESS_ISSUANCE)
report["admit_capability_ok"] = admit(capability) is capability
lookalike_refused = True
for lookalike in (
    dict(lawful),
    MappingProxyType(dict(lawful)),
    type("L", (dict,), {})(dict(lawful)),
):
    try:
        admit(lookalike)
    except ValueError:
        pass
    else:
        lookalike_refused = False
report["lookalikes_refused"] = lookalike_refused
try:
    admit(object.__new__(type("F", (Capability,), {})))
except ValueError:
    report["subclass_refused"] = True
else:
    report["subclass_refused"] = False
try:
    Capability(dict(lawful), object())
except ValueError:
    report["wrong_proof_refused"] = True
else:
    report["wrong_proof_refused"] = False
try:
    capability["matched_minor"] = 0
except TypeError:
    report["immutable"] = True
else:
    report["immutable"] = False

print("XI_IN_IMAGE_BATTERY " + json.dumps(report, sort_keys=True))
'''


def _in_image_xi_battery(image: str) -> dict[str, object]:
    """Corrective-XI semantic battery inside the unmodified image (no mounts)."""
    proc = subprocess.run(
        ["docker", "run", "--rm", "-i", image, "python", "-"],
        input=_XI_IN_IMAGE_PROBE,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"container_xi_battery_failed:{proc.stderr[-800:]}")
    line = next(
        (
            ln
            for ln in proc.stdout.splitlines()
            if ln.startswith("XI_IN_IMAGE_BATTERY ")
        ),
        None,
    )
    if line is None:
        raise RuntimeError(f"container_xi_battery_output_missing:{proc.stdout[-400:]}")
    report = json.loads(line[len("XI_IN_IMAGE_BATTERY ") :])
    failed = sorted(
        k for k, v in report.items() if k != "egress_registry" and v is not True
    )
    if failed or report.get("egress_registry") != ["render_governed_external"]:
        raise RuntimeError(f"container_xi_battery_red:{failed or report}")
    return report


def validate(image: str) -> dict[str, object]:
    sys.path.insert(0, str(BACKEND))
    from app.finance_reconciliation.semantic_contract import (  # noqa: PLC0415
        semantic_contract_identity,
    )

    host = semantic_contract_identity().__dict__
    probe = (
        "import json;"
        "from app.finance_reconciliation.semantic_contract import semantic_contract_identity;"
        "print(json.dumps(semantic_contract_identity().__dict__,sort_keys=True))"
    )
    output = _run("docker", "run", "--rm", image, "python", "-c", probe)
    try:
        container = json.loads(output.splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"container_contract_identity_malformed:{output}") from exc
    if container != host:
        raise RuntimeError(
            f"container_contract_identity_mismatch:host={host}:container={container}"
        )
    xi_battery = _in_image_xi_battery(image)
    inspect = json.loads(_run("docker", "image", "inspect", image))[0]
    environment = inspect.get("Config", {}).get("Env", []) or []
    exposed = [
        item for item in environment if item.split("=", 1)[0] in FORBIDDEN_IMAGE_ENV
    ]
    if exposed:
        raise RuntimeError(f"container_forbidden_authority_env:{exposed}")
    return {
        "image": image,
        "image_id": inspect["Id"],
        "repo_digests": inspect.get("RepoDigests", []),
        "host_contract_identity": host,
        "container_contract_identity": container,
        "container_xi_battery": xi_battery,
        "forbidden_authority_env_present": [],
        "boot_authority": "exact-SHA C19 topology attested by independent producer",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--evidence-out", type=Path)
    args = parser.parse_args()
    try:
        details = validate(args.image)
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"B26_P1_CONTAINER_EQUIVALENCE_FAIL {exc}")
        return 1
    if args.evidence_out:
        from scripts.ci.b26_p1_evidence import write_evidence_cell  # noqa: PLC0415

        write_evidence_cell(
            args.evidence_out,
            gate_id="B26-P1-G3-G10-CONTAINER-EQUIVALENCE",
            producer="b26-p1-container-equivalence",
            scenario_id="candidate-production-image",
            falsifier_id="B26-P1-NC-07",
            details=details,
        )
    print("B26_P1_CONTAINER_EQUIVALENCE_PASS")
    print(json.dumps(details, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
