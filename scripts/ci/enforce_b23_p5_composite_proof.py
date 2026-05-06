#!/usr/bin/env python3
"""Composite B2.3-P5 proof harness for P0-P4 merge-blocking adjudication."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_FILE = "contracts-internal/governance/b23_p5_composite_proof.main.json"
PYTEST_SUITE_FILE = "contracts-internal/governance/b23_p5_pytest_suite.main.json"


@dataclass
class GateResult:
    gate_id: str
    phase: str
    proof_class: str
    status: str
    details: list[str]


def _resolve(repo_root: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (repo_root / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json_payload_not_object:{path}")
    return payload


def _extract_job_block(workflow_text: str, job_id: str) -> str:
    pattern = re.compile(rf"^  {re.escape(job_id)}:\s*$", re.MULTILINE)
    match = pattern.search(workflow_text)
    if match is None:
        return ""
    next_job = re.search(r"^  [A-Za-z0-9_-]+:\s*$", workflow_text[match.end() :], re.MULTILINE)
    if next_job is None:
        return workflow_text[match.start() :]
    return workflow_text[match.start() : match.end() + next_job.start()]


def _expand_env(value: str, env: dict[str, str]) -> str:
    if value.startswith("${") and value.endswith("}"):
        key = value[2:-1]
        return env.get(key, "")
    return value


def _run_command(
    *,
    repo_root: Path,
    command: list[str],
    env_overlay: dict[str, str] | None = None,
) -> tuple[int, str]:
    env = os.environ.copy()
    if env_overlay:
        for key, value in env_overlay.items():
            env[key] = _expand_env(str(value), env)
    completed = subprocess.run(
        command,
        cwd=repo_root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return completed.returncode, completed.stdout


def _junit_skip_failures(junit_file: Path, *, required_proof_class: str) -> list[str]:
    failures: list[str] = []
    if not junit_file.exists():
        return [f"junit_missing:{junit_file}"]
    tree = ET.parse(junit_file)
    for testcase in tree.iter("testcase"):
        skipped = testcase.find("skipped")
        if skipped is None:
            continue
        test_name = f"{testcase.get('classname', '')}.{testcase.get('name', '')}"
        message = (skipped.get("message") or skipped.text or "").strip()
        if not message:
            failures.append(f"skip_unannotated:{required_proof_class}:{test_name}")
            continue
        required_tokens = ("phase", "gate", "blocker", "non-required")
        missing_tokens = [token for token in required_tokens if token not in message.lower()]
        if missing_tokens:
            failures.append(
                f"skip_missing_annotation:{required_proof_class}:{test_name}:{','.join(missing_tokens)}"
            )
        failures.append(f"required_proof_skip_forbidden:{required_proof_class}:{test_name}")
    return failures


def _validate_manifest(
    *,
    repo_root: Path,
    manifest: dict[str, Any],
    pytest_manifest: dict[str, Any],
) -> list[str]:
    violations: list[str] = []
    if manifest.get("contract_id") != "b23.p5.composite_proof.main":
        violations.append("manifest_contract_id_mismatch")
    if manifest.get("phase") != "B2.3-P5":
        violations.append("manifest_phase_mismatch")
    p0_preservation = manifest.get("p0_preservation") or {}
    p0_contract_path = _resolve(repo_root, str(p0_preservation.get("semantic_authority_contract") or ""))
    required_p0_version = str(p0_preservation.get("required_contract_version") or "")
    if not p0_contract_path.exists():
        violations.append(f"p0_contract_missing:{p0_contract_path}")
    elif required_p0_version:
        p0_contract = _read_json(p0_contract_path)
        observed_p0_version = str(p0_contract.get("contract_version") or "")
        if observed_p0_version != required_p0_version:
            violations.append(
                f"p0_contract_version_regression:{observed_p0_version}!={required_p0_version}"
            )

    composite = manifest.get("composite_check") or {}
    workflow_path = _resolve(repo_root, str(composite.get("workflow_file") or ""))
    job_id = str(composite.get("job_id") or "")
    check_name = str(composite.get("check_name") or "")
    if not workflow_path.exists():
        violations.append(f"workflow_missing:{workflow_path}")
    else:
        workflow_text = workflow_path.read_text(encoding="utf-8")
        job_block = _extract_job_block(workflow_text, job_id)
        if not job_block:
            violations.append(f"ci_missing_composite_job:{job_id}")
        else:
            if f"name: {check_name}" not in job_block:
                violations.append("ci_composite_job_name_mismatch")
            required_job_tokens = (
                "scripts/ci/enforce_b23_p5_composite_proof.py",
                "SKELDIR_B23_P2_REQUIRE_DB_PROOFS: \"1\"",
                "SKELDIR_B23_P3_REQUIRE_DB_PROOFS: \"1\"",
                "SKELDIR_B23_P4_REQUIRE_DB_PROOFS: \"1\"",
                "postgres:15-alpine",
            )
            for token in required_job_tokens:
                if token not in job_block:
                    violations.append(f"ci_composite_job_missing_token:{token}")

    required_paths: list[str] = []
    for gate in manifest.get("required_phase_enforcers", []):
        command = gate.get("command") or []
        if isinstance(command, list) and len(command) >= 2:
            required_paths.append(str(command[1]))
    for suite in manifest.get("required_pytest_suites", []):
        required_paths.append(str(suite.get("path")))
    branch = manifest.get("branch_protection") or {}
    required_paths.append(str(branch.get("verifier")))
    for path in required_paths:
        if path and not _resolve(repo_root, path).exists():
            violations.append(f"required_artifact_missing:{path}")

    required_negative_controls = set(manifest.get("required_negative_controls") or [])
    negative_suite = _resolve(repo_root, "backend/tests/test_b23_p5_composite_proof_negative_controls.py")
    if negative_suite.exists():
        negative_text = negative_suite.read_text(encoding="utf-8")
        for test_name in sorted(required_negative_controls):
            if f"def {test_name}" not in negative_text:
                violations.append(f"required_negative_control_missing:{test_name}")
        forbidden_tokens = ("monkeypatch", "mock.patch", "unittest.mock", "builtins.open")
        for token in forbidden_tokens:
            if token in negative_text:
                violations.append(f"p5_negative_control_forbidden_token:{token}")
    else:
        violations.append(f"required_negative_control_suite_missing:{negative_suite}")

    skip_policy = manifest.get("skip_policy") or {}
    exemptions = set(skip_policy.get("exempt_from_skip_failure") or [])
    forbidden_exemptions = set(skip_policy.get("required_proof_classes_forbidden_from_skip_exemption") or [])
    overlap = sorted(exemptions & forbidden_exemptions)
    if overlap:
        violations.append(f"required_proof_self_exemption_forbidden:{','.join(overlap)}")
    if exemptions:
        deferral_dir = _resolve(repo_root, "contracts-internal/governance/deferrals")
        if not deferral_dir.exists():
            violations.append("skip_exemption_external_deferral_record_missing")

    required_test_files = pytest_manifest.get("required_test_files") or []
    observed_gate_classes: set[str] = set()
    for entry in required_test_files:
        path = str(entry.get("path") or "")
        if not path or not _resolve(repo_root, path).exists():
            violations.append(f"pytest_manifest_required_file_missing:{path}")
        classes = entry.get("gate_classes") or []
        if isinstance(classes, list):
            observed_gate_classes.update(str(item) for item in classes)
    for gate_class in pytest_manifest.get("required_gate_classes") or []:
        if gate_class not in observed_gate_classes:
            violations.append(f"pytest_manifest_gate_class_unmapped:{gate_class}")

    forbidden_scope = " ".join(str(item).lower() for item in manifest.get("forbidden_scope") or [])
    for scope_token in ("p6", "b2.4", "b2.6", "dashboard", "llm explanation"):
        if scope_token not in forbidden_scope:
            violations.append(f"forbidden_scope_not_encoded:{scope_token}")
    return violations


def run_enforcement(
    *,
    repo_root: Path,
    manifest_file: Path,
    pytest_suite_file: Path,
    execute: bool,
    branch_protection_response_file: Path | None,
    summary_file: Path,
) -> tuple[int, dict[str, Any]]:
    manifest = _read_json(manifest_file)
    pytest_manifest = _read_json(pytest_suite_file)
    results: list[GateResult] = []
    violations = _validate_manifest(repo_root=repo_root, manifest=manifest, pytest_manifest=pytest_manifest)
    if violations:
        results.append(GateResult("manifest_integrity", "B2.3-P5", "manifest", "FAIL", violations))

    if execute and not violations:
        for gate in manifest.get("required_phase_enforcers", []):
            gate_id = str(gate.get("gate_id"))
            phase = str(gate.get("phase"))
            proof_class = str(gate.get("required_proof_class"))
            command = [str(part) for part in gate.get("command", [])]
            missing = [
                part
                for part in command[1:2]
                if part.endswith(".py") and not _resolve(repo_root, part).exists()
            ]
            if missing:
                results.append(GateResult(gate_id, phase, proof_class, "FAIL", [f"command_artifact_missing:{missing[0]}"]))
                continue
            code, output = _run_command(
                repo_root=repo_root,
                command=command,
                env_overlay=gate.get("env") if isinstance(gate.get("env"), dict) else None,
            )
            status = "PASS" if code == 0 else "FAIL"
            details = [] if code == 0 else [f"exit_code:{code}", output[-4000:]]
            results.append(GateResult(gate_id, phase, proof_class, status, details))

        artifacts_dir = repo_root / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        for suite in manifest.get("required_pytest_suites", []):
            gate_id = str(suite.get("gate_id"))
            phase = str(suite.get("phase"))
            proof_class = str(suite.get("required_proof_class"))
            test_path = str(suite.get("path"))
            if not _resolve(repo_root, test_path).exists():
                results.append(GateResult(gate_id, phase, proof_class, "FAIL", [f"pytest_file_missing:{test_path}"]))
                continue
            junit_file = artifacts_dir / f"{gate_id}.junit.xml"
            env_overlay = {}
            proof_env = suite.get("required_proof_mode_env")
            if isinstance(proof_env, str) and proof_env:
                env_overlay[proof_env] = "1"
            code, output = _run_command(
                repo_root=repo_root,
                command=["pytest", test_path, "-q", "-rA", f"--junitxml={junit_file}"],
                env_overlay=env_overlay,
            )
            skip_failures = _junit_skip_failures(junit_file, required_proof_class=proof_class)
            details = skip_failures[:]
            if code != 0:
                details.extend([f"exit_code:{code}", output[-4000:]])
            results.append(
                GateResult(gate_id, phase, proof_class, "PASS" if code == 0 and not details else "FAIL", details)
            )

        typegen = manifest.get("frontend_typegen_drift_gate") or {}
        typegen_details: list[str] = []
        for command in typegen.get("commands") or []:
            code, output = _run_command(repo_root=repo_root, command=[str(part) for part in command])
            if code != 0:
                typegen_details.extend([f"command_failed:{' '.join(command)}", output[-4000:]])
                break
        results.append(
            GateResult(
                str(typegen.get("gate_id") or "frontend_typegen_drift"),
                "B2.3-P5",
                str(typegen.get("required_proof_class") or "frontend_typed_boundary_drift"),
                "PASS" if not typegen_details else "FAIL",
                typegen_details,
            )
        )

        branch = manifest.get("branch_protection") or {}
        verifier_cmd = ["python", str(branch.get("verifier"))]
        if branch_protection_response_file is not None:
            verifier_cmd.extend(["--branch-protection-response-file", str(branch_protection_response_file)])
        code, output = _run_command(repo_root=repo_root, command=verifier_cmd)
        results.append(
            GateResult(
                str(branch.get("gate_id") or "branch_protection_required_check"),
                "B2.3-P5",
                "branch_protection_required_check",
                "PASS" if code == 0 else "FAIL",
                [] if code == 0 else [f"exit_code:{code}", output[-4000:]],
            )
        )

    passed = (
        all(result.status == "PASS" for result in results)
        if results
        else not violations
    )
    summary = {
        "contract_id": manifest.get("contract_id"),
        "contract_version": manifest.get("contract_version"),
        "phase": manifest.get("phase"),
        "status": "PASS" if passed else "FAIL",
        "execute": execute,
        "gates": [
            {
                "gate_id": result.gate_id,
                "phase": result.phase,
                "required_proof_class": result.proof_class,
                "status": result.status,
                "details": result.details,
            }
            for result in results
        ],
    }
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    summary_file.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return (0 if summary["status"] == "PASS" else 1), summary


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--manifest-file", default=MANIFEST_FILE)
    parser.add_argument("--pytest-suite-file", default=PYTEST_SUITE_FILE)
    parser.add_argument("--summary-file")
    parser.add_argument("--branch-protection-response-file")
    parser.add_argument("--structural-only", action="store_true")
    args = parser.parse_args(argv[1:])

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    manifest_path = _resolve(repo_root, args.manifest_file)
    manifest = _read_json(manifest_path)
    default_summary = _resolve(repo_root, str((manifest.get("proof_summary") or {}).get("artifact_path") or "artifacts/b23_p5_composite_proof_summary.json"))
    status, summary = run_enforcement(
        repo_root=repo_root,
        manifest_file=manifest_path,
        pytest_suite_file=_resolve(repo_root, args.pytest_suite_file),
        execute=not args.structural_only,
        branch_protection_response_file=_resolve(repo_root, args.branch_protection_response_file)
        if args.branch_protection_response_file
        else None,
        summary_file=_resolve(repo_root, args.summary_file) if args.summary_file else default_summary,
    )
    print(json.dumps(summary, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
