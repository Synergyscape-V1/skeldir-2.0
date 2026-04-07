#!/usr/bin/env python3
"""B1.7-P5 merge-blocking adjudication enforcer."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_CONTEXT = "B1.7 Explanation Runtime Adjudication"
REQUIRED_JOB_ID = "b17-explanation-runtime-adjudication"
REQUIRED_ROUTE = "/api/attribution/explain/{entity_type}/{entity_id}"
REQUIRED_COMMAND_TOKENS = (
    "test_b17_p1_explanation_authority_runtime.py",
    "test_b17_p2_explanation_fastpath_runtime.py",
    "test_b17_p3_cache_correctness_runtime.py",
    "test_b17_p4_strategy_closure_runtime.py",
    "test_b17_p5_anti_chat_surface_runtime.py",
    "test_route_fidelity.py::test_b17_canonical_explain_route_mounted_and_runtime_openapi_converged",
    "test_route_fidelity.py::test_contract_to_route_mapping",
)


def _resolve(repo_root: Path, raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else (repo_root / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _extract_job_block(ci_text: str, job_id: str) -> str:
    pattern = re.compile(rf"(?ms)^  {re.escape(job_id)}:\n(.*?)(?=^  [a-z0-9][a-z0-9-]*:\n|\Z)")
    match = pattern.search(ci_text)
    return match.group(1) if match else ""


def _manifest_requirement_for_operation(
    manifest: dict[str, Any],
    operation_id: str,
) -> dict[str, Any] | None:
    for domain_payload in manifest.values():
        if not isinstance(domain_payload, dict):
            continue
        requirements = domain_payload.get("requirements", [])
        if not isinstance(requirements, list):
            continue
        for requirement in requirements:
            if isinstance(requirement, dict) and requirement.get("operation_id") == operation_id:
                return requirement
    return None


def run_enforcement(
    *,
    required_checks_contract_file: Path,
    ci_workflow_file: Path,
    contract_scope_file: Path,
    semantics_skip_allowlist_file: Path,
    route_fidelity_file: Path,
    anti_chat_runtime_file: Path,
    coverage_manifest_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_files = (
        required_checks_contract_file,
        ci_workflow_file,
        contract_scope_file,
        semantics_skip_allowlist_file,
        route_fidelity_file,
        anti_chat_runtime_file,
        coverage_manifest_file,
    )
    missing_files = [path for path in required_files if not path.exists()]
    if missing_files:
        return 1, [f"missing_file:{path}" for path in missing_files]

    required_checks = _read_json(required_checks_contract_file)
    required_contexts = required_checks.get("required_contexts", [])
    if not isinstance(required_contexts, list):
        violations.append("required_checks_required_contexts_invalid")
        required_contexts = []
    if REQUIRED_CONTEXT not in required_contexts:
        violations.append("required_checks_missing_b17_required_context")

    future_declarations = required_checks.get("future_required_context_declarations", [])
    if isinstance(future_declarations, list):
        for declaration in future_declarations:
            if isinstance(declaration, dict) and declaration.get("name") == REQUIRED_CONTEXT:
                violations.append("required_checks_b17_context_must_not_be_future_declared")
                break

    ci_text = ci_workflow_file.read_text(encoding="utf-8", errors="replace")
    job_block = _extract_job_block(ci_text, REQUIRED_JOB_ID)
    if not job_block:
        violations.append(f"ci_missing_required_job:{REQUIRED_JOB_ID}")
    else:
        if f"name: {REQUIRED_CONTEXT}" not in job_block:
            violations.append("ci_required_job_name_mismatch")
        for token in REQUIRED_COMMAND_TOKENS:
            if token not in job_block:
                violations.append(f"ci_required_job_missing_command:{token}")

    scope = _read_yaml(contract_scope_file)
    mappings = scope.get("spec_mappings", {})
    if not isinstance(mappings, dict):
        violations.append("contract_scope_spec_mappings_invalid")
    elif mappings.get("/api/attribution") != "api-contracts/dist/openapi/v1/attribution.bundled.yaml":
        violations.append("contract_scope_attribution_mapping_mismatch")

    skip_allowlist = _read_yaml(semantics_skip_allowlist_file).get("bundles", {})
    if not isinstance(skip_allowlist, dict):
        violations.append("semantics_skip_allowlist_invalid")
        skip_allowlist = {}
    for forbidden_bundle in ("attribution.bundled.yaml", "llm-explanations.bundled.yaml"):
        if forbidden_bundle in skip_allowlist:
            violations.append(f"semantics_skip_allowlist_forbidden_bundle:{forbidden_bundle}")

    route_fidelity_text = route_fidelity_file.read_text(encoding="utf-8", errors="replace")
    if "B1.7 explanation route fidelity drift is merge-blocking" not in route_fidelity_text:
        violations.append("route_fidelity_missing_b17_fail_closed_guard")
    if REQUIRED_ROUTE not in route_fidelity_text:
        violations.append("route_fidelity_missing_canonical_route_reference")

    anti_chat_text = anti_chat_runtime_file.read_text(encoding="utf-8", errors="replace")
    for required_token in (
        "WebSocketRoute",
        REQUIRED_ROUTE,
        "/chat",
        "/stream",
        "text/event-stream",
    ):
        if required_token not in anti_chat_text:
            violations.append(f"anti_chat_runtime_missing_token:{required_token}")

    coverage_manifest = _read_yaml(coverage_manifest_file)
    requirement = _manifest_requirement_for_operation(
        coverage_manifest, "explainAttributionEntity"
    )
    if requirement is None:
        violations.append("coverage_manifest_missing_explain_operation")
    else:
        if requirement.get("status") != "implemented":
            violations.append("coverage_manifest_explain_operation_not_implemented")
        proof_contexts = requirement.get("proof_contexts", [])
        if not isinstance(proof_contexts, list):
            violations.append("coverage_manifest_proof_contexts_invalid")
            proof_contexts = []
        for required_proof in (REQUIRED_CONTEXT, "Contract Semantic Drift Gate"):
            if required_proof not in proof_contexts:
                violations.append(f"coverage_manifest_missing_proof_context:{required_proof}")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="B1.7-P5 merge-blocking adjudication enforcer"
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument(
        "--required-checks-contract-file",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument("--ci-workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument("--contract-scope-file", default="backend/app/config/contract_scope.yaml")
    parser.add_argument("--semantics-skip-allowlist-file", default="tests/contract/semantics_skip_allowlist.yaml")
    parser.add_argument("--route-fidelity-file", default="tests/contract/test_route_fidelity.py")
    parser.add_argument("--anti-chat-runtime-file", default="backend/tests/test_b17_p5_anti_chat_surface_runtime.py")
    parser.add_argument("--coverage-manifest-file", default="api-contracts/governance/coverage-manifest.yaml")
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b17_p5_merge_blocking_adjudication_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        required_checks_contract_file=_resolve(repo_root, args.required_checks_contract_file),
        ci_workflow_file=_resolve(repo_root, args.ci_workflow_file),
        contract_scope_file=_resolve(repo_root, args.contract_scope_file),
        semantics_skip_allowlist_file=_resolve(repo_root, args.semantics_skip_allowlist_file),
        route_fidelity_file=_resolve(repo_root, args.route_fidelity_file),
        anti_chat_runtime_file=_resolve(repo_root, args.anti_chat_runtime_file),
        coverage_manifest_file=_resolve(repo_root, args.coverage_manifest_file),
    )

    lines = ["b17_p5_merge_blocking_adjudication_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=b17_p5_merge_blocking_adjudication_closed")
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
