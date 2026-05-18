#!/usr/bin/env python3
"""Validate M5 B2.4 readiness design artifacts without running B2.4."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DOC_REQUIREMENTS = {
    "docs/b2_4/b2_4_readiness_substrate.md": [
        "## Module Home",
        "## Existing Stub Classification",
        "## Allowed Imports",
        "## Forbidden Imports",
        "## Consumer Surfaces",
        "## Source Substrates",
        "## Worker Lifecycle",
        "## Future Implementation Sequence",
        "backend/app/bayesian/",
        "backend/app/tasks/bayesian.py",
        "Design Partner Mode",
    ],
    "docs/b2_4/diagnostic_protocol.md": [
        "## Fit Request Identity",
        "## Required Source Substrate",
        "## Eligibility Check Outputs",
        "## Lifecycle Statuses",
        "## Diagnostic Metrics",
        "## Error Classes",
        "## B2.5 Projection Behavior",
        "B24-COLD-G1",
        "R-hat",
        "ESS",
        "divergences",
        "fallback_only/insufficient_data",
        "source_snapshot_hash",
    ],
    "docs/b2_4/model_artifact_persistence_requirements.md": [
        "## `bayesian_model_fits`",
        "## `bayesian_artifacts`",
        "## Resolver Contract",
        "## RLS/GUC Expectations",
        "## Migration Expectations",
        "artifact_ref",
        "artifact_hash",
        "storage_backend",
        "source_snapshot_hash",
        "credible_interval_status",
    ],
    "docs/b2_4/dependency_decision_record.md": [
        "## Decision",
        "## Candidate Stack",
        "## Installation and Pinning Plan",
        "## Fork and Vendor Policy",
        "## Compatibility Risks",
        "## Authorization Point",
        "M5 installs nothing",
        "no fork, no clone, no vendoring",
        "PyMC",
        "ArviZ",
        "PyMC-Marketing deferred",
    ],
    "docs/b2_4/b2_4_ci_gate_strategy.md": [
        "## Strategy",
        "## Future Validator Names",
        "## Negative Controls",
        "## DB-Backed Gates",
        "## Worker Runtime Gates",
        "## Branch Protection and Required Contexts",
        "## M3 Insertion Lane Usage",
        "M3-created B2.4 insertion lane",
        "validate-m5-b24-readiness-design",
    ],
    "docs/b2_4/fallback_doctrine.md": [
        "## Deterministic Truth Sovereignty",
        "## Fallback Semantics",
        "## Projection Fields",
        "## B2.5 Behavior",
        "## Forbidden Behavior",
        "insufficient_data",
        "24-hour compute refit lock",
        "must not set `last_fit_at`",
        "never overrides",
    ],
    "docs/b2_4/non_goals.md": [
        "Model fitting",
        "PyMC installation",
        "MCMC execution",
        "New migrations",
        "Public API endpoints",
        "Trust API implementation",
        "LLM explanation behavior changes",
        "B2.3 redesign",
        "Frontend/dashboard work",
        "MCP tools",
        "Production Bayesian activation",
    ],
    "docs/maintainability/m5_completion_record.md": [
        "Executive verdict",
        "Final main commit SHA",
        "PR URL",
        "CI workflow URL",
        "Validation command and output",
        "Negative-control evidence",
        "Hypothesis Matrix",
        "Root-Cause Findings",
        "Diff Scope Inventory",
        "Non-Implementation Proof",
        "Residual Risk Register",
        "Exit Gate Table",
        "Next phase authorization statement",
    ],
}

SCHEMA_PATH = "contracts/internal/b2_4_confidence_metadata.schema.json"
REGISTRY_PATH = "docs/ci/enforcer_registry.yaml"
SUBSUMPTION_PATH = "docs/ci/gate_subsumption_matrix.yaml"
MAKEFILE_PATH = "Makefile"
WORKFLOW_PATH = ".github/workflows/b2_4-gate-dry-run.yml"

REQUIRED_SCHEMA_FIELDS = {
    "bayesian_convergence_status",
    "credible_interval_status",
    "data_completeness_status",
    "fallback_applied",
    "fallback_reason",
    "action_authority",
    "confidence_available",
    "source_snapshot_hash",
    "artifact_ref",
    "artifact_hash",
}

PROHIBITED_ACTIVE_DEP_PATHS = [
    "backend/requirements.txt",
    "backend/requirements-lock.txt",
    "backend/requirements-dev.txt",
    "pyproject.toml",
    "requirements.txt",
]

PROHIBITED_DEP_PATTERN = re.compile(r"^\s*(pymc|arviz|pymc-marketing|pymc_marketing)\b", re.I | re.M)


class ValidationError(RuntimeError):
    pass


def rel(path: str) -> Path:
    return ROOT / path


def read(path: str) -> str:
    full = rel(path)
    if not full.exists():
        raise ValidationError(f"missing required path: {path}")
    return full.read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate_docs(root: Path = ROOT) -> None:
    for path, tokens in DOC_REQUIREMENTS.items():
        full = root / path
        require(full.exists(), f"missing required M5 artifact: {path}")
        text = full.read_text(encoding="utf-8")
        for token in tokens:
            require(token in text, f"{path} missing required token: {token}")


def validate_schema(root: Path = ROOT) -> None:
    full = root / SCHEMA_PATH
    require(full.exists(), f"missing schema: {SCHEMA_PATH}")
    schema = json.loads(full.read_text(encoding="utf-8"))
    require(schema.get("$schema"), "confidence schema missing $schema")
    properties = schema.get("properties")
    require(isinstance(properties, dict), "confidence schema missing properties")
    missing = REQUIRED_SCHEMA_FIELDS - set(properties)
    require(not missing, f"confidence schema missing fields: {sorted(missing)}")
    required = set(schema.get("required", []))
    for field in (
        "bayesian_convergence_status",
        "credible_interval_status",
        "data_completeness_status",
        "fallback_applied",
        "action_authority",
        "source_snapshot_hash",
    ):
        require(field in required, f"confidence schema field must be required: {field}")


def validate_governance(root: Path = ROOT) -> None:
    registry = (root / REGISTRY_PATH).read_text(encoding="utf-8")
    subsumption = (root / SUBSUMPTION_PATH).read_text(encoding="utf-8")
    makefile = (root / MAKEFILE_PATH).read_text(encoding="utf-8")
    workflow = (root / WORKFLOW_PATH).read_text(encoding="utf-8")
    for text, name in (
        (registry, REGISTRY_PATH),
        (subsumption, SUBSUMPTION_PATH),
    ):
        require("validate-m5-b24-readiness-design" in text, f"{name} missing M5 gate id")
        require("validate_m5_b24_readiness_design.py" in text, f"{name} missing M5 script")
    require(
        re.search(r"^validate-m5-b24-readiness:", makefile, re.M),
        "Makefile missing validate-m5-b24-readiness target",
    )
    require(
        "make validate-m5-b24-readiness" in workflow,
        "B2.4 workflow missing M5 validation command",
    )
    require(
        "make ci-b24-gate-dry-run" in workflow,
        "B2.4 workflow no longer preserves M3 dry-run command",
    )


def validate_non_implementation(root: Path = ROOT) -> None:
    require(
        not (root / "backend/app/bayesian").exists(),
        "M5 must not add production backend/app/bayesian implementation files",
    )
    migrations = root / "alembic/versions"
    if migrations.exists():
        migration_text = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in migrations.rglob("*.py")
        ).lower()
        for token in ("bayesian_model_fits", "bayesian_artifacts"):
            require(token not in migration_text, f"M5 must not add migration table: {token}")

    api_dir = root / "backend/app/api"
    if api_dir.exists():
        api_text = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in api_dir.rglob("*.py")
        ).lower()
        require("bayesian" not in api_text and "b2_4" not in api_text, "M5 must not add public Bayesian API routes")

    llm_dir = root / "backend/app/llm"
    if llm_dir.exists():
        # M5 is allowed to leave existing files untouched; this scan only ensures no Bayesian coupling exists.
        llm_text = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in llm_dir.rglob("*.py")
        ).lower()
        require("app.bayesian" not in llm_text, "LLM provider path must not import B2.4 Bayesian modules")

    for dep_path in PROHIBITED_ACTIVE_DEP_PATHS:
        full = root / dep_path
        if full.exists():
            text = full.read_text(encoding="utf-8", errors="ignore")
            require(
                not PROHIBITED_DEP_PATTERN.search(text),
                f"M5 must not install PyMC/ArviZ in active dependency file: {dep_path}",
            )


def run_negative_control() -> None:
    with tempfile.TemporaryDirectory(prefix="m5_bad_design_") as tmp:
        tmp_root = Path(tmp)
        for path in DOC_REQUIREMENTS:
            src = rel(path)
            dst = tmp_root / path
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        schema_src = rel(SCHEMA_PATH)
        schema_dst = tmp_root / SCHEMA_PATH
        schema_dst.parent.mkdir(parents=True, exist_ok=True)
        schema_dst.write_text(schema_src.read_text(encoding="utf-8"), encoding="utf-8")
        target = tmp_root / "docs/b2_4/diagnostic_protocol.md"
        mutated = target.read_text(encoding="utf-8").replace("## Diagnostic Metrics", "## Metrics")
        target.write_text(mutated, encoding="utf-8")
        try:
            validate_docs(tmp_root)
        except ValidationError as exc:
            print(f"M5_NEGATIVE_CONTROL_PASS: {exc}")
            return
        raise ValidationError("negative control failed to detect removed Diagnostic Metrics section")


def validate_all(args: argparse.Namespace) -> None:
    validate_docs()
    validate_schema()
    validate_governance()
    validate_non_implementation()
    if args.negative_control:
        run_negative_control()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--negative-control",
        action="store_true",
        help="Run fixture-copy mutation proving the validator fails on missing required content.",
    )
    args = parser.parse_args()
    try:
        validate_all(args)
    except ValidationError as exc:
        print(f"M5_B24_READINESS_VALIDATION_FAIL: {exc}", file=sys.stderr)
        return 1
    print("M5_B24_READINESS_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
