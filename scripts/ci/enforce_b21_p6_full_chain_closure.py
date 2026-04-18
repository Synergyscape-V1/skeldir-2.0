#!/usr/bin/env python3
"""B2.1-P6 full-chain closure and downstream-readiness structural enforcer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_CHECKS_FILE = "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
CI_WORKFLOW_FILE = ".github/workflows/ci.yml"
P6_RUNTIME_FILE = "backend/tests/integration/test_b21_p6_end_to_end_runtime.py"
P6_EVIDENCE_FILE = "docs/forensics/B2.1-P6 Remediation Evidence Pack .md"
CONTEXT_REPORT_FILE = "docs/forensics/B2.1_Context_Inventory_Report.md"
FORENSICS_INDEX_FILE = "docs/forensics/INDEX.md"

REQUIRED_CONTEXT = "B2.1-P6 Full End-to-End Closure + Downstream Readiness"


def _resolve(repo_root: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (repo_root / path).resolve()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(_read_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def run_enforcement(
    *,
    repo_root: Path,
    required_checks_file: Path,
    ci_workflow_file: Path,
    p6_runtime_file: Path,
    p6_evidence_file: Path,
    context_report_file: Path,
    forensics_index_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_files = (
        required_checks_file,
        ci_workflow_file,
        p6_runtime_file,
        p6_evidence_file,
        context_report_file,
        forensics_index_file,
    )
    missing_files = [path for path in required_files if not path.exists()]
    if missing_files:
        return 1, [f"missing_required_file:{path}" for path in missing_files]

    required_checks = _read_json(required_checks_file)
    required_contexts = required_checks.get("required_contexts", [])
    if not isinstance(required_contexts, list):
        violations.append("required_checks_required_contexts_invalid")
        required_contexts = []
    if REQUIRED_CONTEXT not in required_contexts:
        violations.append(f"required_checks_missing_context:{REQUIRED_CONTEXT}")

    future_contexts = required_checks.get("future_required_context_declarations", [])
    if isinstance(future_contexts, list):
        future_names = {
            item.get("name")
            for item in future_contexts
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        if REQUIRED_CONTEXT in future_names:
            violations.append(
                f"required_checks_context_must_not_be_future_declared:{REQUIRED_CONTEXT}"
            )

    workflow_text = _read_text(ci_workflow_file)
    workflow_tokens = (
        f"name: {REQUIRED_CONTEXT}",
        (
            "needs: [checkout, validate-contracts, b21-p0-runtime-authority-closeout, "
            "b21-p1-semantic-replay-lock, b21-p2-strategy-kernel-session-boundary, "
            "b21-p3-persistence-read-surface, b21-p4-queue-isolation-performance-lock, "
            "b21-p5-non-vacuous-proof-harness]"
        ),
        "pytest backend/tests/integration/test_b21_p6_end_to_end_runtime.py -q",
        "python scripts/benchmarks/b21_p4_queue_isolation_benchmark.py",
        "--event-count 10000",
        "--threshold-seconds 5",
        "python scripts/ci/enforce_b21_p4_benchmark_adjudication.py",
        "python scripts/ci/enforce_b21_p6_full_chain_closure.py",
        "pytest backend/tests/test_b21_p6_full_chain_closure_enforcer.py -q",
    )
    for token in workflow_tokens:
        if token not in workflow_text:
            violations.append(f"workflow_missing_token:{token}")

    runtime_text = _read_text(p6_runtime_file)
    runtime_tokens = (
        "EventIngestionService",
        "test_b21_p6_full_chain_ingestion_to_persistence_to_channels_is_authoritative",
        "test_b21_p6_chain_blocks_cross_tenant_reads_and_preserves_over_24h_session_separation",
        "\"first_touch\", \"last_touch\", \"linear\", \"time_decay\"",
        "customer.b21.p6@example.test",
        "\"/api/attribution/channels\"",
        "ATTRIBUTION_PROJECTION_NOT_FOUND",
    )
    for token in runtime_tokens:
        if token not in runtime_text:
            violations.append(f"p6_runtime_missing_token:{token}")

    context_text = _read_text(context_report_file)
    context_tokens = (
        "# B2.1_Context_Inventory_Report",
        "Section 4: Contradiction Register",
        "Contradiction Register Closure: PASS",
    )
    for token in context_tokens:
        if token not in context_text:
            violations.append(f"context_report_missing_token:{token}")

    evidence_text = _read_text(p6_evidence_file)
    evidence_tokens = (
        "# B2.1-P6 Remediation Evidence Pack",
        "Exit Gate 1",
        "Exit Gate 6",
        "Downstream readiness",
    )
    for token in evidence_tokens:
        if token not in evidence_text:
            violations.append(f"p6_evidence_missing_token:{token}")

    index_text = _read_text(forensics_index_file)
    if "docs/forensics/B2.1_Context_Inventory_Report.md" not in index_text:
        violations.append("forensics_index_missing_context_inventory_entry")
    if "docs/forensics/B2.1-P6 Remediation Evidence Pack .md" not in index_text:
        violations.append("forensics_index_missing_p6_evidence_entry")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce B2.1-P6 full-chain closure and downstream-readiness adjudication plane."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--required-checks-file", default=REQUIRED_CHECKS_FILE)
    parser.add_argument("--ci-workflow-file", default=CI_WORKFLOW_FILE)
    parser.add_argument("--p6-runtime-file", default=P6_RUNTIME_FILE)
    parser.add_argument("--p6-evidence-file", default=P6_EVIDENCE_FILE)
    parser.add_argument("--context-report-file", default=CONTEXT_REPORT_FILE)
    parser.add_argument("--forensics-index-file", default=FORENSICS_INDEX_FILE)
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b21_p6_full_chain_closure_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        repo_root=repo_root,
        required_checks_file=_resolve(repo_root, args.required_checks_file),
        ci_workflow_file=_resolve(repo_root, args.ci_workflow_file),
        p6_runtime_file=_resolve(repo_root, args.p6_runtime_file),
        p6_evidence_file=_resolve(repo_root, args.p6_evidence_file),
        context_report_file=_resolve(repo_root, args.context_report_file),
        forensics_index_file=_resolve(repo_root, args.forensics_index_file),
    )
    lines = ["b21_p6_full_chain_closure_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append(
            "enforcement=b21_p6_chain_tenant_privacy_replay_perf_required_check_docs_bound"
        )
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
