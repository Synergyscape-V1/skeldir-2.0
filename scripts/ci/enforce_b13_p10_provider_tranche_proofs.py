#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import xml.etree.ElementTree as ET


REQUIRED_CONTEXT = "B1.3 P10 Provider Tranche Proofs"
REQUIRED_RUNTIME_TESTS = (
    "test_b13_p10_provider_lifecycle_tranche_proofs_cover_target_six_runtime_backed_providers",
    "test_b13_p10_refresh_concurrency_topology_avoids_shared_mutable_seeded_credentials",
)
REQUIRED_RUNTIME_ARTIFACTS = (
    "p10_active_tranche_runtime_report.json",
    "p10_proof_topology_report.json",
)
ALLOWED_PROOF_MODES = {
    "deterministic",
    "seeded_sandbox",
    "real_authorize_url_callback_shape",
    "real_refresh_revoke_account_identity",
    "serialized_live_provider_lane",
}
ALLOWED_CONCURRENCY_STRATEGIES = {
    "isolated_per_test_database_and_nonshared_tokens",
    "serialized_live_provider_lane_with_concurrency_lock",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B1.3-P10 provider tranche enforcement")
    parser.add_argument("--workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument(
        "--required-checks-contract",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument(
        "--p0-capability-contract",
        default="contracts-internal/governance/b13_p0_provider_capability_matrix.main.json",
    )
    parser.add_argument(
        "--p5-capability-contract",
        default="contracts-internal/governance/b13_p5_oauth_adapter_capabilities.main.json",
    )
    parser.add_argument(
        "--p10-tranche-contract",
        default="contracts-internal/governance/b13_p10_provider_rollout_tranches.main.json",
    )
    parser.add_argument("--adapter-file", default="backend/app/services/provider_oauth_lifecycle.py")
    parser.add_argument("--registry-file", default="backend/app/services/realtime_revenue_providers.py")
    parser.add_argument(
        "--tests-file",
        default="backend/tests/integration/test_b13_p10_provider_tranche_proofs.py",
    )
    parser.add_argument("--require-runtime-execution", action="store_true")
    parser.add_argument("--junit-xml", default=None)
    parser.add_argument("--artifacts-dir", default="artifacts/b13_p10")
    return parser.parse_args()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_literal_assignment(tree: ast.Module, name: str) -> object | None:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                try:
                    return ast.literal_eval(node.value)
                except (ValueError, SyntaxError):
                    return None
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name and node.value is not None:
                try:
                    return ast.literal_eval(node.value)
                except (ValueError, SyntaxError):
                    return None
    return None


def _parse_registry_provider_keys(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    class_to_key: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            for target in item.targets:
                if isinstance(target, ast.Name) and target.id == "provider_key":
                    if isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                        class_to_key[node.name] = item.value.value

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "DEFAULT_PROVIDER_REGISTRY" for target in node.targets):
            continue
        if not isinstance(node.value, ast.Call):
            break
        providers_list: list[ast.AST] = []
        for keyword in node.value.keywords:
            if keyword.arg == "providers" and isinstance(keyword.value, ast.List):
                providers_list = list(keyword.value.elts)
        keys: set[str] = set()
        for provider_ctor in providers_list:
            if not isinstance(provider_ctor, ast.Call) or not isinstance(provider_ctor.func, ast.Name):
                continue
            cls_name = provider_ctor.func.id
            provider_key = class_to_key.get(cls_name)
            if provider_key:
                keys.add(provider_key)
        return keys
    return set()


def _load_junit_cases(junit_path: Path) -> dict[str, str]:
    root = ET.fromstring(junit_path.read_text(encoding="utf-8"))
    outcomes: dict[str, str] = {}
    for case in root.iter("testcase"):
        name = case.attrib.get("name", "").strip()
        if not name:
            continue
        if case.find("failure") is not None:
            outcomes[name] = "failed"
        elif case.find("error") is not None:
            outcomes[name] = "error"
        elif case.find("skipped") is not None:
            outcomes[name] = "skipped"
        else:
            outcomes[name] = "passed"
    return outcomes


def _resolve_case_outcome(outcomes: dict[str, str], test_name: str) -> str | None:
    if test_name in outcomes:
        return outcomes[test_name]
    for name, outcome in outcomes.items():
        if name.startswith(f"{test_name}["):
            return outcome
    return None


def _check_required_context(workflow_text: str, required_checks: dict, errors: list[str]) -> None:
    if REQUIRED_CONTEXT not in workflow_text:
        errors.append(f"workflow missing required context name: {REQUIRED_CONTEXT}")
    contexts = required_checks.get("required_contexts")
    if not isinstance(contexts, list):
        errors.append("required checks contract missing required_contexts list")
        return
    if REQUIRED_CONTEXT not in contexts:
        errors.append(f"required checks contract missing context: {REQUIRED_CONTEXT}")


def _check_workflow_surface(workflow_text: str, errors: list[str]) -> None:
    required_fragments = (
        "name: B1.3 P10 Provider Tranche Proofs",
        "python scripts/ci/enforce_b13_p10_provider_tranche_proofs.py",
        "pytest backend/tests/integration/test_b13_p10_provider_tranche_proofs.py -q -rs",
        "--junitxml=artifacts/b13_p10/junit.xml",
        "--require-runtime-execution",
        "name: b13-p10-runtime-artifacts",
        "path: artifacts/b13_p10",
    )
    for fragment in required_fragments:
        if fragment not in workflow_text:
            errors.append(f"workflow missing P10 fragment: {fragment}")


def _check_tranche_contract(tranche_contract: dict, errors: list[str]) -> tuple[set[str], set[str], set[str]]:
    target = tranche_contract.get("target_runtime_backed_provider_set")
    if not isinstance(target, list):
        errors.append("p10 contract missing target_runtime_backed_provider_set list")
        return set(), set(), set()
    target_set = {str(item).strip() for item in target if str(item).strip()}
    if len(target_set) != 6:
        errors.append(f"p10 target_runtime_backed_provider_set must contain exactly six providers; got {sorted(target_set)}")
    if list(target) != sorted(target):
        errors.append("p10 target_runtime_backed_provider_set must be sorted")

    deferred = tranche_contract.get("deferred_non_target_providers")
    if not isinstance(deferred, list):
        errors.append("p10 contract missing deferred_non_target_providers list")
        deferred_set = set()
    else:
        deferred_set = {str(item).strip() for item in deferred if str(item).strip()}
        if target_set & deferred_set:
            errors.append("p10 deferred_non_target_providers must not overlap target_runtime_backed_provider_set")

    tranches = tranche_contract.get("tranches")
    if not isinstance(tranches, list) or not tranches:
        errors.append("p10 contract missing tranches list")
        active_providers: set[str] = set()
    else:
        tranche_ids: set[str] = set()
        sequence_values: list[int] = []
        active_providers = set()
        active_id = str(tranche_contract.get("current_active_tranche_id") or "").strip()
        active_found = False
        for tranche in tranches:
            if not isinstance(tranche, dict):
                errors.append("p10 tranche entries must be objects")
                continue
            tranche_id = str(tranche.get("tranche_id") or "").strip()
            if not tranche_id:
                errors.append("p10 tranche missing tranche_id")
                continue
            if tranche_id in tranche_ids:
                errors.append(f"p10 duplicate tranche_id: {tranche_id}")
            tranche_ids.add(tranche_id)
            sequence = tranche.get("sequence")
            if not isinstance(sequence, int) or sequence < 1:
                errors.append(f"p10 tranche sequence must be positive int: {tranche_id}")
            else:
                sequence_values.append(sequence)
            providers = tranche.get("providers")
            if not isinstance(providers, list) or not providers:
                errors.append(f"p10 tranche providers missing/empty: {tranche_id}")
                continue
            provider_set = {str(item).strip() for item in providers if str(item).strip()}
            if not provider_set.issubset(target_set):
                errors.append(
                    f"p10 tranche providers must be subset of target set: tranche={tranche_id} providers={sorted(provider_set)}"
                )
            if tranche_id == active_id:
                active_found = True
                active_providers = provider_set
        if sequence_values and sorted(sequence_values) != list(range(1, len(sequence_values) + 1)):
            errors.append(f"p10 tranche sequence must be contiguous from 1: {sorted(sequence_values)}")
        if not active_id:
            errors.append("p10 current_active_tranche_id is required")
        elif not active_found:
            errors.append(f"p10 current_active_tranche_id does not exist in tranches: {active_id}")

    topology = tranche_contract.get("provider_proof_topology")
    if not isinstance(topology, dict):
        errors.append("p10 contract missing provider_proof_topology object")
    else:
        topology_keys = {str(key).strip() for key in topology.keys()}
        if topology_keys != target_set:
            errors.append(
                "p10 provider_proof_topology keys must exactly match target_runtime_backed_provider_set: "
                f"topology={sorted(topology_keys)} target={sorted(target_set)}"
            )
        for provider in sorted(target_set):
            entry = topology.get(provider)
            if not isinstance(entry, dict):
                errors.append(f"p10 provider_proof_topology[{provider}] must be object")
                continue
            proof_mode = str(entry.get("proof_mode") or "").strip()
            refresh_mode = str(entry.get("refresh_proof_mode") or "").strip()
            strategy = str(entry.get("credential_concurrency_strategy") or "").strip()
            live_credentials_required = bool(entry.get("live_credentials_required"))
            rotation_possible = bool(entry.get("refresh_token_rotation_possible"))
            tests = entry.get("provider_specific_tests")

            if proof_mode not in ALLOWED_PROOF_MODES:
                errors.append(f"p10 proof_mode invalid for {provider}: {proof_mode}")
            if refresh_mode not in ALLOWED_PROOF_MODES and refresh_mode != "deterministic_refresh_revoke_account_identity":
                errors.append(f"p10 refresh_proof_mode invalid for {provider}: {refresh_mode}")
            if strategy not in ALLOWED_CONCURRENCY_STRATEGIES:
                errors.append(f"p10 credential_concurrency_strategy invalid for {provider}: {strategy}")
            if not isinstance(tests, list) or not tests:
                errors.append(f"p10 provider_specific_tests missing for {provider}")
            if rotation_possible and live_credentials_required and strategy != "serialized_live_provider_lane_with_concurrency_lock":
                errors.append(
                    f"p10 provider {provider} uses live rotating credentials without serialized concurrency strategy"
                )
            if rotation_possible and not live_credentials_required and strategy != "isolated_per_test_database_and_nonshared_tokens":
                errors.append(
                    f"p10 provider {provider} must use isolated non-shared credential topology when live credentials are disabled"
                )

    lifecycle_gates = tranche_contract.get("required_lifecycle_gates")
    if not isinstance(lifecycle_gates, list):
        errors.append("p10 contract missing required_lifecycle_gates list")
    else:
        required = {
            "authorize_connect",
            "encrypted_credential_persistence",
            "expiry_tracking",
            "scheduled_refresh",
            "revoke_degradation_handling",
            "account_scope_identity_proof",
            "provider_specific_ci_proof",
        }
        if {str(item).strip() for item in lifecycle_gates} != required:
            errors.append("p10 required_lifecycle_gates mismatch")

    return target_set, deferred_set, active_providers


def _check_alignment(
    *,
    p0_contract: dict,
    p5_contract: dict,
    adapter_text: str,
    registry_keys: set[str],
    target_set: set[str],
    deferred_set: set[str],
    errors: list[str],
) -> None:
    p0_runtime = {
        str(item).strip() for item in p0_contract.get("runtime_backed_providers", []) if str(item).strip()
    }
    if p0_runtime != target_set:
        errors.append(f"p10 target set mismatch with p0 runtime_backed_providers: p0={sorted(p0_runtime)} target={sorted(target_set)}")
    if p0_runtime & deferred_set:
        errors.append("p0 runtime_backed_providers overlaps deferred providers")

    p5_runtime = {
        str(item.get("provider")).strip()
        for item in p5_contract.get("adapter_capabilities", [])
        if isinstance(item, dict) and str(item.get("mode")).strip() == "runtime_backed"
    }
    if p5_runtime != target_set:
        errors.append(f"p10 target set mismatch with p5 runtime-backed providers: p5={sorted(p5_runtime)} target={sorted(target_set)}")

    adapter_tree = ast.parse(adapter_text)
    declarations = _extract_literal_assignment(adapter_tree, "OAUTH_LIFECYCLE_CAPABILITY_DECLARATIONS")
    if not isinstance(declarations, dict):
        errors.append("unable to parse OAUTH_LIFECYCLE_CAPABILITY_DECLARATIONS")
        declared_runtime: set[str] = set()
    else:
        declared_runtime = {
            str(provider).strip()
            for provider, entry in declarations.items()
            if isinstance(entry, dict) and str(entry.get("mode")).strip() == "runtime_backed"
        }
        if declared_runtime != target_set:
            errors.append(
                "runtime adapter declarations must match p10 target set: "
                f"adapter={sorted(declared_runtime)} target={sorted(target_set)}"
            )

    runtime_registry = set(registry_keys) - {"dummy"}
    if runtime_registry != target_set:
        errors.append(
            "runtime provider registry must match p10 target set: "
            f"registry={sorted(runtime_registry)} target={sorted(target_set)}"
        )
    if runtime_registry & deferred_set:
        errors.append("runtime provider registry overlaps deferred providers")


def _check_no_shared_rotating_credential_risk(workflow_text: str, errors: list[str]) -> None:
    dangerous_tokens = (
        "REFRESH_TOKEN",
        "ACCESS_TOKEN",
        "CLIENT_SECRET",
        "OAUTH_TOKEN",
    )
    if "name: B1.3 P10 Provider Tranche Proofs" not in workflow_text:
        return
    p10_section = workflow_text.split("name: B1.3 P10 Provider Tranche Proofs", 1)[1]
    p10_section = p10_section.split("\n  b", 1)[0]
    for token in dangerous_tokens:
        if token in p10_section:
            errors.append(
                f"p10 workflow contains potential shared mutable credential env/secret token marker: {token}"
            )


def _check_tests_surface(tests_text: str, target_set: set[str], errors: list[str]) -> None:
    required_names = (
        "test_b13_p10_gate_passes_repo_state",
        "test_b13_p10_provider_lifecycle_tranche_proofs_cover_target_six_runtime_backed_providers",
        "test_b13_p10_refresh_concurrency_topology_avoids_shared_mutable_seeded_credentials",
    )
    for name in required_names:
        if name not in tests_text:
            errors.append(f"p10 proof suite missing required test: {name}")
    for provider in sorted(target_set):
        if provider not in tests_text:
            errors.append(f"p10 tests do not reference target provider: {provider}")


def _check_runtime_execution(*, junit_path: Path, artifacts_dir: Path, target_set: set[str], errors: list[str]) -> None:
    if not junit_path.exists():
        errors.append(f"missing junit xml for runtime execution verification: {junit_path}")
        return
    outcomes = _load_junit_cases(junit_path)
    for name in REQUIRED_RUNTIME_TESTS:
        outcome = _resolve_case_outcome(outcomes, name)
        if outcome is None:
            errors.append(f"missing runtime testcase in junit xml: {name}")
            continue
        if outcome != "passed":
            errors.append(f"runtime testcase did not pass (outcome={outcome}): {name}")

    if not artifacts_dir.exists():
        errors.append(f"missing p10 artifacts directory: {artifacts_dir}")
        return

    runtime_payload: dict | None = None
    topology_payload: dict | None = None
    for artifact in REQUIRED_RUNTIME_ARTIFACTS:
        path = artifacts_dir / artifact
        if not path.exists():
            errors.append(f"missing p10 runtime artifact: {path}")
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if artifact == "p10_active_tranche_runtime_report.json":
            runtime_payload = payload
        else:
            topology_payload = payload

    if isinstance(runtime_payload, dict):
        providers = runtime_payload.get("providers")
        if not isinstance(providers, dict):
            errors.append("p10 runtime report missing providers object")
        else:
            provider_keys = {str(key) for key in providers}
            if provider_keys != target_set:
                errors.append(
                    "p10 runtime report providers mismatch target set: "
                    f"runtime={sorted(provider_keys)} target={sorted(target_set)}"
                )
            for provider, entry in providers.items():
                if not isinstance(entry, dict):
                    errors.append(f"p10 runtime report provider entry must be object: {provider}")
                    continue
                if entry.get("refresh_status") != "refreshed":
                    errors.append(f"p10 runtime report missing refreshed status for provider: {provider}")
                if entry.get("revoked_code") != "provider_revoked":
                    errors.append(f"p10 runtime report missing provider_revoked proof for provider: {provider}")

    if isinstance(topology_payload, dict):
        if topology_payload.get("shared_mutable_refresh_credential_detected") is not False:
            errors.append("p10 topology report indicates shared mutable refresh credentials")


def main() -> int:
    args = _parse_args()
    paths = {
        "workflow": Path(args.workflow_file),
        "required_checks": Path(args.required_checks_contract),
        "p0": Path(args.p0_capability_contract),
        "p5": Path(args.p5_capability_contract),
        "p10": Path(args.p10_tranche_contract),
        "adapter": Path(args.adapter_file),
        "registry": Path(args.registry_file),
        "tests": Path(args.tests_file),
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        print("B1.3-P10 provider tranche gate failed:")
        for item in missing:
            print(f"  - missing file: {item}")
        return 1

    workflow_text = _read_text(paths["workflow"])
    required_checks = _load_json(paths["required_checks"])
    p0_contract = _load_json(paths["p0"])
    p5_contract = _load_json(paths["p5"])
    p10_contract = _load_json(paths["p10"])
    adapter_text = _read_text(paths["adapter"])
    tests_text = _read_text(paths["tests"])
    registry_keys = _parse_registry_provider_keys(paths["registry"])

    errors: list[str] = []
    _check_required_context(workflow_text, required_checks, errors)
    _check_workflow_surface(workflow_text, errors)
    target_set, deferred_set, active_providers = _check_tranche_contract(p10_contract, errors)
    if target_set and not active_providers:
        errors.append("p10 active tranche providers cannot be empty")
    _check_alignment(
        p0_contract=p0_contract,
        p5_contract=p5_contract,
        adapter_text=adapter_text,
        registry_keys=registry_keys,
        target_set=target_set,
        deferred_set=deferred_set,
        errors=errors,
    )
    _check_no_shared_rotating_credential_risk(workflow_text, errors)
    _check_tests_surface(tests_text, target_set, errors)

    if args.require_runtime_execution:
        junit_xml = Path(args.junit_xml) if args.junit_xml else None
        if junit_xml is None:
            errors.append("--require-runtime-execution requires --junit-xml")
        else:
            _check_runtime_execution(
                junit_path=junit_xml,
                artifacts_dir=Path(args.artifacts_dir),
                target_set=target_set,
                errors=errors,
            )

    if errors:
        print("B1.3-P10 provider tranche gate failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("B1.3-P10 provider tranche gate passed.")
    print(f"  required_context={REQUIRED_CONTEXT}")
    print(f"  target_runtime_backed_providers={sorted(target_set)}")
    print(f"  active_tranche_providers={sorted(active_providers)}")
    print("  proof_topology=ci-safe_non-vacuous")
    print("  refresh_credential_model=non-shared_and_rotation-safe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
