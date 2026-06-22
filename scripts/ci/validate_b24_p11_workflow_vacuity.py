#!/usr/bin/env python3
"""Scan B2.4 required-context workflows for path filters and dummy jobs."""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
CONTRACT = ROOT / "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
MANIFEST = ROOT / "docs/ci/b24_p11_execution_manifest.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts/b24_p11_workflow_vacuity.json"
DEFAULT_SUMMARY = ROOT / "artifacts/b24_p11_ci_gate_matrix.json"


class ValidationError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError(f"invalid workflow YAML {path}: {exc}") from exc


def _required_b24_contexts(contract_path: Path) -> set[str]:
    data = json.loads(contract_path.read_text(encoding="utf-8"))
    contexts = data.get("required_contexts")
    _require(isinstance(contexts, list), "required-status contract missing required_contexts")
    return {str(item) for item in contexts if str(item).startswith("B2.4")}


def _manifest_commands(manifest_path: Path) -> dict[str, list[str]]:
    rows = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    _require(isinstance(rows, list), "execution manifest must be a list")
    mapping: dict[str, list[str]] = {}
    for row in rows:
        _require(isinstance(row, dict), "execution manifest row must be a mapping")
        job = str(row.get("workflow_job", ""))
        fragments = row.get("required_command_fragments", [])
        _require(isinstance(fragments, list) and fragments, f"manifest row missing required_command_fragments: {job}")
        mapping[job] = [str(item) for item in fragments]
    return mapping


def _on_block(workflow: dict[str, Any]) -> Any:
    return workflow.get("on", workflow.get(True))


def _contains_path_filter(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in {"paths", "paths-ignore"}:
                return True
            if _contains_path_filter(child):
                return True
    if isinstance(value, list):
        return any(_contains_path_filter(item) for item in value)
    return False


def _run_text(job: dict[str, Any]) -> str:
    lines: list[str] = []
    for step in job.get("steps", []) or []:
        if isinstance(step, dict) and step.get("run"):
            lines.append(str(step["run"]))
    return "\n".join(lines)


def _step_if_disallowed(step: dict[str, Any]) -> bool:
    if "if" not in step:
        return False
    expr = str(step["if"]).lower()
    if expr.strip() in {"${{ always() }}", "always()"} and "upload" in str(step.get("name", "")).lower():
        return False
    return True


def _job_if_disallowed(job: dict[str, Any]) -> bool:
    if "if" not in job:
        return False
    expr = str(job["if"]).lower().strip()
    allowed = {"${{ always() }}", "always()"}
    if expr in allowed:
        return False
    blocked_tokens = ("github.event_name", "paths", "path", "changed", "skip", "false")
    return any(token in expr for token in blocked_tokens) or bool(expr)


def validate_workflows(
    *,
    workflows_dir: Path = WORKFLOWS,
    contract_path: Path = CONTRACT,
    manifest_path: Path = MANIFEST,
    output_path: Path = DEFAULT_OUTPUT,
    summary_path: Path | None = DEFAULT_SUMMARY,
) -> dict[str, Any]:
    required = _required_b24_contexts(contract_path)
    command_fragments = _manifest_commands(manifest_path)
    seen: dict[str, str] = {}
    scanned_files: set[str] = set()
    for path in sorted(workflows_dir.glob("*.y*ml")):
        workflow = _load_yaml(path)
        if not isinstance(workflow, dict):
            continue
        jobs = workflow.get("jobs")
        if not isinstance(jobs, dict):
            continue
        required_jobs: list[tuple[str, dict[str, Any]]] = []
        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                continue
            name = str(job.get("name") or job_id)
            if name in required:
                required_jobs.append((name, job))
                if name in seen:
                    raise ValidationError(f"required B2.4 context duplicated across workflows: {name}")
                seen[name] = path.relative_to(ROOT).as_posix()
        if not required_jobs:
            continue
        scanned_files.add(path.relative_to(ROOT).as_posix())
        _require(not _contains_path_filter(_on_block(workflow)), f"{path} defines required B2.4 jobs with paths/paths-ignore filters")
        for name, job in required_jobs:
            _require(not _job_if_disallowed(job), f"{name} has disallowed job-level if condition")
            for step in job.get("steps", []) or []:
                if isinstance(step, dict):
                    _require(not _step_if_disallowed(step), f"{name} has disallowed step-level if condition: {step.get('name')}")
            run_text = _run_text(job)
            fragments = command_fragments.get(name)
            _require(fragments, f"{name} missing execution manifest command fragments")
            missing = [fragment for fragment in fragments if fragment not in run_text]
            _require(not missing, f"{name} does not execute required proof command fragments: {missing}")
            _require("echo success" not in run_text.lower(), f"{name} contains dummy echo success bypass")
    missing_contexts = sorted(required - set(seen))
    _require(not missing_contexts, f"required B2.4 contexts absent from workflow scan: {missing_contexts}")
    payload = {
        "schema_version": "b24-p11-workflow-vacuity-v1",
        "timestamp": datetime.now(UTC).isoformat(),
        "required_context_count": len(required),
        "scanned_workflows": sorted(scanned_files),
        "path_filter_status": "pass",
        "non_vacuity_status": "pass",
        "required_context_workflow_map": seen,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if summary_path and summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["workflow_vacuity_status"] = "verified"
        for phase in summary.get("phases", []):
            phase["path_filter_status"] = "pass"
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def _write_fixture(base: Path, workflow_text: str, manifest_text: str, contract_contexts: list[str]) -> tuple[Path, Path, Path]:
    workflows = base / ".github/workflows"
    workflows.mkdir(parents=True)
    (workflows / "b2_4.yml").write_text(workflow_text, encoding="utf-8")
    contract = base / "contract.json"
    contract.write_text(json.dumps({"required_contexts": contract_contexts}), encoding="utf-8")
    manifest = base / "manifest.yaml"
    manifest.write_text(manifest_text, encoding="utf-8")
    return workflows, contract, manifest


def _expect_failure(name: str, func: Any, expected: str) -> dict[str, str]:
    try:
        func()
    except ValidationError as exc:
        _require(expected.lower() in str(exc).lower(), f"{name} failed for wrong reason: {exc}")
        result = {
            "name": name,
            "status": "pass",
            "expected_failure_reason": expected,
            "observed_failure_reason": str(exc),
        }
        print(f"B24_P11_NEGATIVE_CONTROL_PASS {name}: {exc}")
        return result
    else:
        raise ValidationError(f"negative control did not fail: {name}")


def run_negative_controls() -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    job = "B2.4-P11 CI Gates and Negative Control Harness"
    manifest = yaml.safe_dump(
        [
            {
                "workflow_job": job,
                "required_command_fragments": ["make validate-b24-p11-ci-gates"],
            }
        ],
        sort_keys=False,
    )
    good = f"""
name: fixture
on:
  pull_request:
  push:
jobs:
  p11:
    name: {job}
    runs-on: ubuntu-latest
    steps:
      - run: make validate-b24-p11-ci-gates
"""
    with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as temp:
        base = Path(temp)
        workflows, contract, manifest_path = _write_fixture(base, good, manifest, [job])
        validate_workflows(workflows_dir=workflows, contract_path=contract, manifest_path=manifest_path, output_path=base / "good.json", summary_path=None)
        duplicate_base = base / "duplicate_required_context"
        duplicate_workflows = duplicate_base / ".github/workflows"
        duplicate_workflows.mkdir(parents=True)
        (duplicate_workflows / "b2_4_a.yml").write_text(good, encoding="utf-8")
        (duplicate_workflows / "b2_4_b.yml").write_text(good.replace("name: fixture", "name: duplicate fixture"), encoding="utf-8")
        duplicate_contract = duplicate_base / "contract.json"
        duplicate_contract.write_text(json.dumps({"required_contexts": [job]}), encoding="utf-8")
        duplicate_manifest = duplicate_base / "manifest.yaml"
        duplicate_manifest.write_text(manifest, encoding="utf-8")
        results.append(
            _expect_failure(
                "duplicate_required_context",
                lambda: validate_workflows(
                    workflows_dir=duplicate_workflows,
                    contract_path=duplicate_contract,
                    manifest_path=duplicate_manifest,
                    output_path=base / "duplicate_required_context.json",
                    summary_path=None,
                ),
                "duplicated across workflows",
            )
        )
        path_filtered = good.replace("pull_request:", "pull_request:\n    paths:\n      - docs/**")
        workflows, contract, manifest_path = _write_fixture(base / "paths", path_filtered, manifest, [job])
        results.append(_expect_failure("paths", lambda: validate_workflows(workflows_dir=workflows, contract_path=contract, manifest_path=manifest_path, output_path=base / "paths.json", summary_path=None), "paths"))
        paths_ignore = good.replace("pull_request:", "pull_request:\n    paths-ignore:\n      - docs/**")
        workflows, contract, manifest_path = _write_fixture(base / "paths_ignore", paths_ignore, manifest, [job])
        results.append(_expect_failure("paths_ignore", lambda: validate_workflows(workflows_dir=workflows, contract_path=contract, manifest_path=manifest_path, output_path=base / "paths_ignore.json", summary_path=None), "paths"))
        conditional = good.replace("runs-on: ubuntu-latest", "if: ${{ github.event_name == 'push' }}\n    runs-on: ubuntu-latest")
        workflows, contract, manifest_path = _write_fixture(base / "if", conditional, manifest, [job])
        results.append(_expect_failure("conditional", lambda: validate_workflows(workflows_dir=workflows, contract_path=contract, manifest_path=manifest_path, output_path=base / "if.json", summary_path=None), "if condition"))
        dummy = good.replace("make validate-b24-p11-ci-gates", "echo success")
        workflows, contract, manifest_path = _write_fixture(base / "dummy", dummy, manifest, [job])
        results.append(_expect_failure("dummy", lambda: validate_workflows(workflows_dir=workflows, contract_path=contract, manifest_path=manifest_path, output_path=base / "dummy.json", summary_path=None), "required proof command"))
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    try:
        negative_results: list[dict[str, str]] = []
        if args.negative_control:
            negative_results = run_negative_controls()
        payload = validate_workflows(
            output_path=ROOT / args.output,
            summary_path=ROOT / args.summary_path if args.summary_path else None,
        )
        if negative_results:
            payload["negative_control_status"] = "pass"
            payload["negative_controls"] = negative_results
            (ROOT / args.output).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except ValidationError as exc:
        print(f"B24_P11_WORKFLOW_VACUITY_VALIDATION_FAIL: {exc}")
        return 1
    print("B24_P11_WORKFLOW_VACUITY_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
