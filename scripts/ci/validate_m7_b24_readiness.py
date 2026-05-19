#!/usr/bin/env python3
"""Validate M7 B2.4 readiness adjudication artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]

VERDICT_PATH = Path("docs/maintainability/m7_b24_readiness_verdict.md")
DEBT_PATH = Path("docs/maintainability/m7_final_debt_register.yaml")
CLEAN_CLONE_PATH = Path("docs/maintainability/m7_clean_clone_validation_transcript.md")
TEST_PATH = Path("docs/maintainability/m7_test_validation_transcript.md")
CI_PATH = Path("docs/maintainability/m7_ci_registry_validation_transcript.md")
ARTIFACT_INDEX_PATH = Path("docs/maintainability/m7_artifact_index.md")
EVIDENCE_PACK_PATH = Path("docs/maintainability/M7 Remediation Evidence Pack .md")

REGISTRY_PATH = Path("docs/ci/enforcer_registry.yaml")
SUBSUMPTION_PATH = Path("docs/ci/gate_subsumption_matrix.yaml")
MAKEFILE_PATH = Path("Makefile")
WORKFLOW_PATH = Path(".github/workflows/b2_4-gate-dry-run.yml")

ALLOWED_VERDICTS = {
    "B2.4_READY",
    "B2.4_READY_WITH_EXPLICIT_DEBT",
    "B2.4_BLOCKED",
}

REQUIRED_ARTIFACTS = [
    VERDICT_PATH,
    DEBT_PATH,
    CLEAN_CLONE_PATH,
    TEST_PATH,
    CI_PATH,
    ARTIFACT_INDEX_PATH,
    EVIDENCE_PACK_PATH,
]

PHASE_RECORDS = {
    "M0_PASS": Path("docs/maintainability/m0_completion_record.md"),
    "M1_PASS": Path("docs/maintainability/m1_completion_record.md"),
    "M2_PASS": Path("docs/maintainability/m2_completion_record.md"),
    "M3_PASS": Path("docs/maintainability/m3_completion_record.md"),
    "M4_PASS": Path("docs/maintainability/m4_completion_record.md"),
    "M5_PASS": Path("docs/maintainability/m5_completion_record.md"),
    "M6_PASS": Path("docs/maintainability/m6_completion_record.md"),
}

REQUIRED_VERDICT_TOKENS = [
    "Executive Verdict",
    "Current Main Coordinate",
    "M0-M6 Closure Table",
    "Clean-Clone Validation",
    "Test Topology Validation",
    "CI Governance Validation",
    "Operational Readiness Validation",
    "B2.4 Substrate Validation",
    "LLM Boundary Validation",
    "Feature Contamination Scan",
    "Final Debt Register Summary",
    "Authorization",
    "B2.4 may begin:",
]

REQUIRED_HYPOTHESES = [f"H{i:02d}" for i in range(1, 16)]
REQUIRED_GATES = [f"M7-{letter}" for letter in "ABCDEFGHIJKLM"]
ALLOWED_STATUSES = {"PASS", "FAIL", "PARTIAL", "UNKNOWN", "N/A_WITH_REASON"}

PROHIBITED_PLACEHOLDERS = re.compile(
    r"\b(TODO|TBD|PLACEHOLDER|recorded after|M6_CONDITIONAL)\b", re.IGNORECASE
)
PROHIBITED_ACTIVE_DEP_PATTERN = re.compile(
    r"^\s*(pymc|arviz|pymc-marketing|pymc_marketing)\b", re.IGNORECASE | re.MULTILINE
)
PROHIBITED_ACTIVE_DEP_PATHS = [
    Path("backend/requirements.txt"),
    Path("backend/requirements-lock.txt"),
    Path("backend/requirements-dev.txt"),
    Path("requirements.txt"),
    Path("pyproject.toml"),
]

AUTHORIZED_M7_DIFF_PREFIXES = {
    Path("docs/maintainability"),
    Path("scripts/ci"),
    Path("docs/ci"),
    Path(".github/workflows"),
    Path("Makefile"),
}


class ValidationError(RuntimeError):
    pass


def read(path: Path) -> str:
    full = ROOT / path
    if not full.exists():
        raise ValidationError(f"missing required path: {path.as_posix()}")
    return full.read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(read(path))


def validate_artifacts() -> None:
    for path in REQUIRED_ARTIFACTS:
        text = read(path)
        match = PROHIBITED_PLACEHOLDERS.search(text)
        require(
            match is None,
            f"{path.as_posix()} contains unresolved placeholder token: {match.group(0) if match else ''}",
        )

    verdict = read(VERDICT_PATH)
    for token in REQUIRED_VERDICT_TOKENS:
        require(token in verdict, f"{VERDICT_PATH.as_posix()} missing required section/token: {token}")
    for hypothesis in REQUIRED_HYPOTHESES:
        require(hypothesis in verdict, f"{VERDICT_PATH.as_posix()} missing hypothesis status: {hypothesis}")
    for gate in REQUIRED_GATES:
        require(gate in verdict, f"{VERDICT_PATH.as_posix()} missing gate status: {gate}")
    require(
        sum(verdict.count(item) for item in ALLOWED_VERDICTS) >= 1,
        "M7 verdict document missing allowed verdict token",
    )


def extract_verdict() -> str:
    verdict_text = read(VERDICT_PATH)
    match = re.search(r"(?m)^\*\*Verdict:\*\*\s*`?([A-Z0-9._]+)`?", verdict_text)
    if not match:
        match = re.search(r"\b(B2\.4_READY_WITH_EXPLICIT_DEBT|B2\.4_READY|B2\.4_BLOCKED)\b", verdict_text)
    require(match is not None, "could not parse M7 verdict")
    verdict = match.group(1)
    require(verdict in ALLOWED_VERDICTS, f"invalid M7 verdict: {verdict}")
    return verdict


def validate_phase_closure() -> None:
    for status, path in PHASE_RECORDS.items():
        text = read(path)
        require(status in text, f"{path.as_posix()} missing status {status}")
        if status == "M6_PASS":
            require("M7 may begin: YES" in text, "M6 record must authorize M7")


def validate_hypothesis_and_gate_statuses() -> None:
    verdict = read(VERDICT_PATH)
    for item in REQUIRED_HYPOTHESES + REQUIRED_GATES:
        pattern = rf"\|\s*{re.escape(item)}\s*\|\s*({'|'.join(ALLOWED_STATUSES)})\s*\|"
        require(
            re.search(pattern, verdict) is not None,
            f"{item} must appear in a verdict table with an allowed status",
        )


def validate_debt_register(verdict: str) -> None:
    data = load_yaml(DEBT_PATH)
    require(isinstance(data, dict), "debt register must be a YAML mapping")
    require(data.get("verdict") == verdict, "debt register verdict must match verdict document")
    items = data.get("residual_debt")
    require(isinstance(items, list), "debt register missing residual_debt list")
    if verdict == "B2.4_READY":
        require(len(items) == 0, "B2.4_READY cannot carry residual debt")
    if verdict == "B2.4_READY_WITH_EXPLICIT_DEBT":
        require(len(items) > 0, "READY_WITH_EXPLICIT_DEBT requires at least one debt item")
    for item in items:
        require(isinstance(item, dict), "each debt item must be a mapping")
        for field in ("id", "status", "severity", "b24_impact", "owner_phase", "reopen_trigger", "rationale"):
            require(item.get(field), f"debt item missing field {field}")
        require(
            item["status"] in {"B2.4_BLOCKING", "B2.4_NONBLOCKING", "DEFERRED_OPERATIONAL", "DEFERRED_COSMETIC"},
            f"debt item has invalid status: {item['status']}",
        )
    if verdict != "B2.4_BLOCKED":
        blocking = [item["id"] for item in items if item["status"] == "B2.4_BLOCKING"]
        require(not blocking, f"non-blocked verdict cannot include B2.4 blocking debt: {blocking}")


def validate_governance_wiring() -> None:
    registry = load_yaml(REGISTRY_PATH)
    subsumption = load_yaml(SUBSUMPTION_PATH)
    makefile = read(MAKEFILE_PATH)
    workflow = read(WORKFLOW_PATH)

    require(
        re.search(r"^validate-m7-b24-readiness:", makefile, re.MULTILINE) is not None,
        "Makefile missing validate-m7-b24-readiness target",
    )
    require("make validate-m7-b24-readiness" in workflow, "B2.4 dry-run workflow missing M7 validation step")

    require(isinstance(registry, list), "enforcer registry must be a YAML list")
    m7_entries = [entry for entry in registry if entry.get("id") == "validate-m7-b24-readiness"]
    require(len(m7_entries) == 1, "enforcer registry must contain exactly one M7 gate entry")
    entry = m7_entries[0]
    require(entry.get("path") == "scripts/ci/validate_m7_b24_readiness.py", "M7 registry path mismatch")
    require(entry.get("execution_cohort") == "b2-4-dry-run", "M7 registry cohort mismatch")
    require(entry.get("default_execution") is True, "M7 registry must default execute")

    require(isinstance(subsumption, list), "gate subsumption matrix must be a YAML list")
    m7_matrix = [entry for entry in subsumption if entry.get("gate_id") == "validate-m7-b24-readiness"]
    require(len(m7_matrix) == 1, "gate subsumption matrix must contain exactly one M7 gate entry")


def validate_no_feature_contamination() -> None:
    require(not (ROOT / "backend/app/bayesian").exists(), "B2.4 implementation directory exists")

    migrations = ROOT / "alembic/versions"
    if migrations.exists():
        migration_text = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in migrations.rglob("*.py")
        ).lower()
        for token in ("bayesian_model_fits", "bayesian_artifacts"):
            require(token not in migration_text, f"Bayesian migration/table detected: {token}")

    for dep_path in PROHIBITED_ACTIVE_DEP_PATHS:
        full = ROOT / dep_path
        if full.exists():
            require(
                not PROHIBITED_ACTIVE_DEP_PATTERN.search(full.read_text(encoding="utf-8", errors="ignore")),
                f"active dependency file installs PyMC/ArviZ: {dep_path.as_posix()}",
            )

    llm_boundary = ROOT / "backend/app/llm/provider_boundary.py"
    if llm_boundary.exists():
        text = llm_boundary.read_text(encoding="utf-8", errors="ignore").lower()
        require("app.bayesian" not in text, "LLM provider boundary imports Bayesian modules")


def git_changed_files() -> list[Path]:
    current = subprocess_run(["git", "branch", "--show-current"])
    if current in {"main", "master"}:
        return []
    merge_base = subprocess_run(["git", "merge-base", "HEAD", "origin/main"])
    if not merge_base:
        return []
    diff = subprocess_run(["git", "diff", "--name-only", f"{merge_base}...HEAD"])
    return [Path(line.strip()) for line in diff.splitlines() if line.strip()]


def subprocess_run(args: list[str]) -> str:
    import subprocess

    completed = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def validate_diff_scope() -> None:
    changed = git_changed_files()
    violations: list[str] = []
    for path in changed:
        normalized = Path(path.as_posix())
        if normalized in AUTHORIZED_M7_DIFF_PREFIXES:
            continue
        if not any(
            normalized == prefix or prefix in normalized.parents
            for prefix in AUTHORIZED_M7_DIFF_PREFIXES
        ):
            violations.append(normalized.as_posix())
    require(not violations, "M7 diff touches unauthorized surfaces: " + ", ".join(violations))


def run_negative_control() -> None:
    with tempfile.TemporaryDirectory(prefix="m7_bad_verdict_") as tmp:
        tmp_root = Path(tmp)
        bad = tmp_root / VERDICT_PATH
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text("**Verdict:** `B2.4_MAYBE`\n", encoding="utf-8")
        original_root = globals()["ROOT"]
        try:
            globals()["ROOT"] = tmp_root
            try:
                extract_verdict()
            except ValidationError as exc:
                print(f"M7_NEGATIVE_CONTROL_PASS: {exc}")
                return
            raise ValidationError("negative control did not reject invalid verdict")
        finally:
            globals()["ROOT"] = original_root


def validate_all(args: argparse.Namespace) -> None:
    validate_artifacts()
    verdict = extract_verdict()
    validate_phase_closure()
    validate_hypothesis_and_gate_statuses()
    validate_debt_register(verdict)
    validate_governance_wiring()
    validate_no_feature_contamination()
    validate_diff_scope()
    if args.negative_control:
        run_negative_control()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    try:
        validate_all(args)
    except ValidationError as exc:
        print(f"M7_B24_READINESS_VALIDATION_FAIL: {exc}", file=sys.stderr)
        return 1
    print("M7_B24_READINESS_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
