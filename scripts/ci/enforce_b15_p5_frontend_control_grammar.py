#!/usr/bin/env python3
"""B1.5-P5 frontend control grammar and strict rendering enforcement."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve(repo_root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_block(text: str, marker: str) -> str:
    index = text.find(marker)
    if index < 0:
        return ""
    return text[index : index + 1500]


def run_enforcement(
    *,
    contract_file: Path,
    app_file: Path,
    agent_shell_investigations_file: Path,
    budget_surface_file: Path,
    investigations_surface_file: Path,
    lifecycle_component_file: Path,
    lifecycle_helper_file: Path,
    budget_hook_file: Path,
    investigation_hook_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_files = (
        contract_file,
        app_file,
        agent_shell_investigations_file,
        budget_surface_file,
        investigations_surface_file,
        lifecycle_component_file,
        lifecycle_helper_file,
        budget_hook_file,
        investigation_hook_file,
    )
    missing_files = [path for path in required_files if not path.exists()]
    if missing_files:
        return 1, [f"missing_file:{path}" for path in missing_files]

    contract = _read_json(contract_file)
    if contract.get("phase") != "B1.5-P5":
        violations.append("contract_invalid_phase")

    lifecycle_helper_text = _read_text(lifecycle_helper_file)
    for status in contract.get("required_lifecycle_statuses", []):
        if f'"{status}"' not in lifecycle_helper_text:
            violations.append(f"missing_lifecycle_status:{status}")

    if "snapshot.reviewRequired" not in lifecycle_helper_text:
        violations.append("review_gating_helper_missing_review_required_check")
    if 'snapshot.status !== "ready_for_review"' not in lifecycle_helper_text:
        violations.append("review_gating_helper_missing_ready_for_review_check")
    if "RESULT_READY_STATUSES" not in lifecycle_helper_text:
        violations.append("result_ready_statuses_missing")

    lifecycle_component_text = _read_text(lifecycle_component_file)
    if "showReviewRail" not in lifecycle_component_text:
        violations.append("lifecycle_component_missing_review_rail_branch")
    if "nonReviewActions" not in lifecycle_component_text:
        violations.append("lifecycle_component_missing_non_review_action_filter")
    if 'snapshot.status === "timeout"' not in lifecycle_component_text:
        violations.append("lifecycle_component_missing_timeout_branch")
    if 'snapshot.status === "cancelled"' not in lifecycle_component_text:
        violations.append("lifecycle_component_missing_cancelled_branch")
    if 'snapshot.status === "failed"' not in lifecycle_component_text:
        violations.append("lifecycle_component_missing_failed_branch")
    if 'snapshot.status === "rejected"' not in lifecycle_component_text:
        violations.append("lifecycle_component_missing_rejected_branch")
    if 'snapshot.status === "refine_requested"' not in lifecycle_component_text:
        violations.append("lifecycle_component_missing_refine_requested_branch")

    budget_hook_text = _read_text(budget_hook_file)
    investigation_hook_text = _read_text(investigation_hook_file)
    required_poll_ms = int(contract.get("required_poll_interval_ms", 5000))
    if f"const STATUS_POLL_INTERVAL_MS = {required_poll_ms};" not in budget_hook_text:
        violations.append("budget_hook_missing_required_poll_interval")
    if (
        f"const STATUS_POLL_INTERVAL_MS = {required_poll_ms};"
        not in investigation_hook_text
    ):
        violations.append("investigation_hook_missing_required_poll_interval")

    budget_poll_block = _extract_block(budget_hook_text, "const pollStatus = async")
    if (
        "getBudgetRecommendationStatus" not in budget_poll_block
        and "fetchStatus(" not in budget_poll_block
    ):
        violations.append("budget_poll_block_missing_status_call")
    if "getBudgetRecommendation(" in budget_poll_block:
        violations.append("budget_poll_block_calls_result_route")

    investigation_poll_block = _extract_block(
        investigation_hook_text, "const pollStatus = async"
    )
    if (
        "getInvestigationStatus" not in investigation_poll_block
        and "fetchStatus(" not in investigation_poll_block
    ):
        violations.append("investigation_poll_block_missing_status_call")
    if "getInvestigationResult(" in investigation_poll_block:
        violations.append("investigation_poll_block_calls_result_route")

    if "if (!isResultReadyStatus(statusResponse.status))" not in budget_hook_text:
        violations.append("budget_hook_missing_result_ready_gate")
    if "if (!isResultReadyStatus(statusResponse.status))" not in investigation_hook_text:
        violations.append("investigation_hook_missing_result_ready_gate")

    required_idempotency_marker = contract.get("required_idempotency_header_marker", "")
    if required_idempotency_marker not in budget_hook_text:
        violations.append("budget_hook_missing_idempotency_key")
    if required_idempotency_marker not in investigation_hook_text:
        violations.append("investigation_hook_missing_idempotency_key")

    budget_surface_text = _read_text(budget_surface_file)
    investigations_surface_text = _read_text(investigations_surface_file)
    if (
        "authorityRecommendation" not in budget_surface_text
        or "deterministic_recommendation" not in budget_hook_text
    ):
        violations.append("budget_surface_missing_deterministic_authority_render")
    if "LLM Synthesis (Non-Authoritative)" not in budget_surface_text:
        violations.append("budget_surface_missing_synthesis_secondary_render")
    if (
        "authorityFindings" not in investigations_surface_text
        or "deterministic_findings" not in investigation_hook_text
    ):
        violations.append("investigation_surface_missing_deterministic_authority_render")
    if "LLM Synthesis (Non-Authoritative)" not in investigations_surface_text:
        violations.append("investigation_surface_missing_synthesis_secondary_render")

    forbidden_sim_markers = contract.get("forbidden_local_simulation_markers", [])
    for marker in forbidden_sim_markers:
        if marker in budget_surface_text:
            violations.append(f"budget_surface_contains_forbidden_marker:{marker}")
        if marker in investigations_surface_text:
            violations.append(
                f"investigations_surface_contains_forbidden_marker:{marker}"
            )

    forbidden_synthesis_markers = contract.get(
        "forbidden_authority_from_synthesis_markers", []
    )
    for marker in forbidden_synthesis_markers:
        if marker in budget_surface_text:
            violations.append(f"budget_surface_parses_synthesis:{marker}")
        if marker in investigations_surface_text:
            violations.append(f"investigation_surface_parses_synthesis:{marker}")

    app_text = _read_text(app_file)
    if "function BudgetScenarioListPage()" not in app_text:
        violations.append("app_missing_budget_scenario_list_page_wrapper")
    if "function BudgetScenarioDetailPage()" not in app_text:
        violations.append("app_missing_budget_scenario_detail_page_wrapper")
    if 'return <Navigate to="/budget" replace />;' not in app_text:
        violations.append("app_missing_budget_scenario_b3_redirect")
    if "AgentShellBudgetScenarioList" in app_text:
        violations.append("app_still_imports_b3_budget_scenario_list_shell")
    if "AgentShellBudgetScenarioDetail" in app_text:
        violations.append("app_still_imports_b3_budget_scenario_detail_shell")

    shell_text = _read_text(agent_shell_investigations_file)
    if "InvestigationQueue" in shell_text or "InvestigationDetail" in shell_text:
        violations.append("investigation_shell_still_binds_queue_detail_productization")
    if "InvestigationConsole" not in shell_text:
        violations.append("investigation_shell_missing_bounded_console_surface")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="B1.5-P5 frontend control grammar enforcer"
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument(
        "--contract-file",
        default="contracts-internal/governance/b15_p5_frontend_control_grammar.main.json",
    )
    parser.add_argument("--app-file", default="frontend/src/App.tsx")
    parser.add_argument(
        "--agent-shell-investigations-file",
        default="frontend/src/investigations/AgentShellInvestigations.tsx",
    )
    parser.add_argument(
        "--budget-surface-file",
        default="frontend/src/budget/components/BudgetOptimizer.tsx",
    )
    parser.add_argument(
        "--investigations-surface-file",
        default="frontend/src/investigations/InvestigationConsole.tsx",
    )
    parser.add_argument(
        "--lifecycle-component-file",
        default="frontend/src/components/llm/InvestigationStatePanel.tsx",
    )
    parser.add_argument(
        "--lifecycle-helper-file",
        default="frontend/src/components/llm/controlPlane.ts",
    )
    parser.add_argument(
        "--budget-hook-file",
        default="frontend/src/components/llm/useBudgetCentaurController.ts",
    )
    parser.add_argument(
        "--investigation-hook-file",
        default="frontend/src/components/llm/useInvestigationCentaurController.ts",
    )
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b15_p5_frontend_control_grammar_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        contract_file=_resolve(repo_root, args.contract_file),
        app_file=_resolve(repo_root, args.app_file),
        agent_shell_investigations_file=_resolve(
            repo_root, args.agent_shell_investigations_file
        ),
        budget_surface_file=_resolve(repo_root, args.budget_surface_file),
        investigations_surface_file=_resolve(
            repo_root, args.investigations_surface_file
        ),
        lifecycle_component_file=_resolve(repo_root, args.lifecycle_component_file),
        lifecycle_helper_file=_resolve(repo_root, args.lifecycle_helper_file),
        budget_hook_file=_resolve(repo_root, args.budget_hook_file),
        investigation_hook_file=_resolve(repo_root, args.investigation_hook_file),
    )

    lines = ["b15_p5_frontend_control_grammar_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=frontend_control_grammar_strict_rendering_enforced")
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
