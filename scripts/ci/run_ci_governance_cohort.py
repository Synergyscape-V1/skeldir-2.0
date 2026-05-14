#!/usr/bin/env python3
"""Run registry-backed CI governance cohorts with per-gate summaries."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs/ci/enforcer_registry.yaml"


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    path: str
    protected_invariant: str
    status: str
    command: str
    local_reproduction_command: str
    first_diagnostic_command: str
    expected_failure_meaning: str
    returncode: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "path": self.path,
            "protected_invariant": self.protected_invariant,
            "status": self.status,
            "command": self.command,
            "local_reproduction_command": self.local_reproduction_command,
            "first_diagnostic_command": self.first_diagnostic_command,
            "expected_failure_meaning": self.expected_failure_meaning,
            "returncode": self.returncode,
        }


def _load_registry(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"Registry must be a YAML list: {path}")
    return data


def _select_gates(
    registry: list[dict[str, Any]],
    *,
    cohort: str,
    gate_ids: set[str],
    include_non_default: bool,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for gate in registry:
        if gate.get("execution_cohort") != cohort:
            continue
        if gate_ids and gate.get("id") not in gate_ids:
            continue
        if gate.get("registry_action") == "utility":
            continue
        if not include_non_default and not gate.get("default_execution", False):
            continue
        selected.append(gate)
    return selected


def _gate_env(gate: dict[str, Any]) -> dict[str, str]:
    env = os.environ.copy()
    for key, raw_value in dict(gate.get("env") or {}).items():
        value = str(raw_value)
        if value.startswith("${") and value.endswith("}"):
            value = env.get(value[2:-1], "")
        env[str(key)] = value
    return env


def _run_gate(gate: dict[str, Any], *, dry_run: bool) -> GateResult:
    gate_id = str(gate["id"])
    command = str(gate["command"])
    print(f"::group::gate_id={gate_id}")
    print(f"gate_id={gate_id}")
    print(f"script_path={gate['path']}")
    print(f"protected_invariant={gate['protected_invariant']}")
    print(f"command={command}")
    print(f"local_reproduction_command={gate['local_reproduction_command']}")
    print(f"first_diagnostic_command={gate['first_diagnostic_command']}")
    print(f"failure_meaning={gate['expected_failure_meaning']}")

    if dry_run:
        print("status=dry_run")
        print("::endgroup::")
        return GateResult(
            gate_id=gate_id,
            path=str(gate["path"]),
            protected_invariant=str(gate["protected_invariant"]),
            status="dry_run",
            command=command,
            local_reproduction_command=str(gate["local_reproduction_command"]),
            first_diagnostic_command=str(gate["first_diagnostic_command"]),
            expected_failure_meaning=str(gate["expected_failure_meaning"]),
            returncode=0,
        )

    completed = subprocess.run(command, cwd=ROOT, env=_gate_env(gate), shell=True, text=True)
    status = "passed" if completed.returncode == 0 else "failed"
    if completed.returncode != 0:
        print(
            f"::error title={gate_id} failed::"
            f"{gate['expected_failure_meaning']} | reproduce: "
            f"{gate['local_reproduction_command']}"
        )
    print(f"status={status}")
    print("::endgroup::")
    return GateResult(
        gate_id=gate_id,
        path=str(gate["path"]),
        protected_invariant=str(gate["protected_invariant"]),
        status=status,
        command=command,
        local_reproduction_command=str(gate["local_reproduction_command"]),
        first_diagnostic_command=str(gate["first_diagnostic_command"]),
        expected_failure_meaning=str(gate["expected_failure_meaning"]),
        returncode=completed.returncode,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default=str(REGISTRY))
    parser.add_argument("--cohort", required=True)
    parser.add_argument("--gate", action="append", default=[])
    parser.add_argument("--include-non-default", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--summary-path", default="artifacts/ci_governance_cohort_summary.json")
    args = parser.parse_args()

    registry = _load_registry(Path(args.registry))
    gates = _select_gates(
        registry,
        cohort=args.cohort,
        gate_ids=set(args.gate),
        include_non_default=args.include_non_default,
    )
    if not gates:
        raise SystemExit(f"No registry gates selected for cohort: {args.cohort}")

    results = [_run_gate(gate, dry_run=args.dry_run) for gate in gates]
    summary = {
        "cohort": args.cohort,
        "dry_run": args.dry_run,
        "gate_count": len(results),
        "failed_gate_ids": [result.gate_id for result in results if result.returncode != 0],
        "results": [result.as_dict() for result in results],
    }
    summary_path = ROOT / args.summary_path
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if summary["failed_gate_ids"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
