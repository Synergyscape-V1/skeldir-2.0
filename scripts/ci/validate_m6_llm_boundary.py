#!/usr/bin/env python3
"""Validate M6 LLM boundary decision and import guardrails."""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DECISION_PATH = Path("docs/llm/provider_boundary_decision.md")
GUARDRAIL_PATH = Path("docs/llm/provider_boundary_guardrail.md")
B27_PRECONDITION_PATH = Path("docs/b2_7/preconditions.md")
COMPLETION_RECORD_PATH = Path("docs/maintainability/m6_completion_record.md")
EVIDENCE_PACK_PATH = Path("docs/maintainability/M6 Remediation Evidence Pack .md")
REGISTRY_PATH = Path("docs/ci/enforcer_registry.yaml")
SUBSUMPTION_PATH = Path("docs/ci/gate_subsumption_matrix.yaml")
MAKEFILE_PATH = Path("Makefile")
WORKFLOW_PATH = Path(".github/workflows/b2_4-gate-dry-run.yml")

M6_GATE_ID = "validate-m6-llm-boundary"
M6_SCRIPT = "scripts/ci/validate_m6_llm_boundary.py"
M6_MAKE_TARGET = "validate-m6-llm-boundary"

PROVIDER_SDK_MODULES = (
    "aisuite",
    "openai",
    "anthropic",
    "groq",
    "google.generativeai",
    "google.genai",
    "vertexai",
    "cohere",
    "mistralai",
)

APP_LLM_MODULES = ("app.llm", "backend.app.llm")

ALLOWED_PROVIDER_SDK_IMPORT_PATHS = {
    Path("backend/app/llm/provider_boundary.py"),
}

FORBIDDEN_LLM_IMPORT_EXACT_PATHS = {
    Path("backend/app/tasks/bayesian.py"),
}

FORBIDDEN_LLM_IMPORT_COMPONENTS = {
    "bayesian",
    "trust",
    "reconciliation",
    "revenue_verification",
    "policy",
    "policies",
    "solver",
    "envelope",
    "mcp",
}

ALLOWED_APP_LLM_IMPORT_PATHS = {
    Path("backend/app/api/attribution.py"),
    Path("backend/app/api/budget.py"),
    Path("backend/app/api/investigations.py"),
    Path("backend/app/services/llm_authority_contract.py"),
    Path("backend/app/workers/llm.py"),
}

PR_DIFF_FORBIDDEN_EXACT = {
    Path("backend/app/llm/provider_boundary.py"),
    Path("backend/app/tasks/bayesian.py"),
}

PR_DIFF_FORBIDDEN_PREFIXES = (
    Path("backend/app/bayesian"),
    Path("backend/app/api"),
    Path("frontend"),
    Path("alembic/versions"),
)

PR_DIFF_FORBIDDEN_DEPENDENCIES = {
    Path("pyproject.toml"),
    Path("requirements.txt"),
    Path("package.json"),
    Path("package-lock.json"),
    Path("backend/requirements.txt"),
    Path("backend/requirements-dev.txt"),
    Path("backend/requirements-lock.txt"),
    Path("frontend/package.json"),
    Path("frontend/package-lock.json"),
}

PLACEHOLDER_PATTERN = re.compile(r"\b(TODO|TBD|PLACEHOLDER|PENDING|XXX)\b", re.I)


class ValidationError(RuntimeError):
    pass


def _rel(path: Path, root: Path = ROOT) -> Path:
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError:
        return path


def _read_text(path: Path, root: Path = ROOT) -> str:
    full = root / path
    if not full.exists():
        raise ValidationError(f"missing required path: {path.as_posix()}")
    return full.read_text(encoding="utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _contains_import(module: str, candidates: tuple[str, ...]) -> bool:
    return any(module == candidate or module.startswith(f"{candidate}.") for candidate in candidates)


def _iter_python_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for base in ("backend", "scripts", "tests"):
        full = root / base
        if full.exists():
            paths.extend(path for path in full.rglob("*.py") if "__pycache__" not in path.parts)
    return sorted(paths)


def _parse_ast(path: Path) -> ast.Module:
    try:
        return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    except SyntaxError as exc:
        raise ValidationError(f"could not parse Python file {path}: {exc}") from exc


def _imported_modules(tree: ast.Module) -> list[tuple[int, str]]:
    modules: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append((node.lineno, node.module))
    return modules


def _is_forbidden_truth_path(rel_path: Path) -> bool:
    if rel_path in ALLOWED_APP_LLM_IMPORT_PATHS:
        return False
    if rel_path.parts[:3] == ("backend", "app", "llm"):
        return False
    if rel_path in FORBIDDEN_LLM_IMPORT_EXACT_PATHS:
        return True
    parts = {part.lower() for part in rel_path.parts}
    if parts & FORBIDDEN_LLM_IMPORT_COMPONENTS:
        return True
    name = rel_path.name.lower()
    return any(token in name for token in FORBIDDEN_LLM_IMPORT_COMPONENTS)


def _scan_provider_sdk_imports(root: Path = ROOT) -> None:
    violations: list[str] = []
    for path in _iter_python_files(root):
        rel_path = _rel(path, root)
        tree = _parse_ast(path)
        for lineno, module in _imported_modules(tree):
            if _contains_import(module, PROVIDER_SDK_MODULES) and rel_path not in ALLOWED_PROVIDER_SDK_IMPORT_PATHS:
                violations.append(f"{rel_path.as_posix()}:{lineno}: {module}")
    _require(
        not violations,
        "provider SDK imports outside approved locations: " + "; ".join(violations),
    )


def _scan_forbidden_llm_imports(root: Path = ROOT) -> None:
    violations: list[str] = []
    for path in _iter_python_files(root):
        rel_path = _rel(path, root)
        if not _is_forbidden_truth_path(rel_path):
            continue
        tree = _parse_ast(path)
        for lineno, module in _imported_modules(tree):
            if _contains_import(module, APP_LLM_MODULES):
                violations.append(f"{rel_path.as_posix()}:{lineno}: {module}")
    _require(
        not violations,
        "forbidden LLM import in B2.4/truth path: " + "; ".join(violations),
    )


def _validate_decision_docs(root: Path = ROOT) -> None:
    decision = _read_text(DECISION_PATH, root)
    guardrail = _read_text(GUARDRAIL_PATH, root)
    preconditions = _read_text(B27_PRECONDITION_PATH, root)
    completion = _read_text(COMPLETION_RECORD_PATH, root)
    evidence = _read_text(EVIDENCE_PACK_PATH, root)

    required_decision_tokens = [
        "Selected path: Path B",
        "B2.4 Touchpoint Classification",
        "B2.4 diagnostics",
        "B2.4 fit worker",
        "B2.4 artifact store",
        "B2.4 fallback",
        "B2.4 confidence projection",
        "B2.4 CI gates",
        "B2.4 API exposure",
        "Decision Rule",
        "Invalidation Rule",
        "Path B is invalid",
        "Path A facade-preserving decomposition becomes mandatory",
        "Allowed LLM Import Locations",
        "Forbidden Import Locations",
        "Provider SDK Import Policy",
        "Effect on B2.4",
        "Effect on B2.7",
        "Effect on Trust API and MCP Paths",
        "Non-Implementation Boundary",
        "Maturity Mode",
        "End-User Value Test",
    ]
    for token in required_decision_tokens:
        _require(token in decision, f"{DECISION_PATH.as_posix()} missing token: {token}")

    _require(
        "LLM touchpoint" in decision and "| NO |" in decision,
        "decision record must classify B2.4 LLM touchpoints",
    )
    for module in PROVIDER_SDK_MODULES:
        _require(module in decision, f"decision record missing provider SDK policy token: {module}")

    if "Selected path: Path A" in decision:
        plan = root / "docs/llm/provider_boundary_decomposition_plan.md"
        _require(plan.exists(), "Path A selected but decomposition plan is missing")
        plan_text = plan.read_text(encoding="utf-8")
        for token in ("SkeldirLLMProvider", "facade", "regression", "llm/budget.py"):
            _require(token in plan_text, f"Path A decomposition plan missing token: {token}")

    for token in (
        "Path B Guardrail",
        "Machine Enforcement",
        "negative control",
        "Path B is invalid",
    ):
        _require(token in guardrail, f"{GUARDRAIL_PATH.as_posix()} missing token: {token}")

    for token in (
        "B2.7 cannot begin",
        "decomposed behind the retained `SkeldirLLMProvider` facade",
        "Waiver Requirements",
        "owner",
        "expiry or review date",
        "No open-ended waiver is valid",
        "If B2.4 introduces explanation/provider behavior",
    ):
        _require(token in preconditions, f"{B27_PRECONDITION_PATH.as_posix()} missing token: {token}")

    for path, text in (
        (COMPLETION_RECORD_PATH, completion),
        (EVIDENCE_PACK_PATH, evidence),
    ):
        match = PLACEHOLDER_PATTERN.search(text)
        _require(match is None, f"{path.as_posix()} contains placeholder token: {match.group(0) if match else ''}")


def _validate_governance(root: Path = ROOT) -> None:
    registry = _read_text(REGISTRY_PATH, root)
    subsumption = _read_text(SUBSUMPTION_PATH, root)
    makefile = _read_text(MAKEFILE_PATH, root)
    workflow = _read_text(WORKFLOW_PATH, root)

    for text, path in ((registry, REGISTRY_PATH), (subsumption, SUBSUMPTION_PATH)):
        _require(M6_GATE_ID in text, f"{path.as_posix()} missing M6 gate id")
        _require(M6_SCRIPT in text, f"{path.as_posix()} missing M6 script path")
        _require(M6_MAKE_TARGET in text, f"{path.as_posix()} missing M6 make target")

    _require(
        re.search(r"^validate-m6-llm-boundary:", makefile, re.M) is not None,
        "Makefile missing validate-m6-llm-boundary target",
    )
    _require(
        "make validate-m6-llm-boundary" in workflow,
        "B2.4 dry-run workflow missing M6 validation command",
    )


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)


def _changed_files_against_base() -> list[Path]:
    branch = _run_git(["git", "branch", "--show-current"]).stdout.strip()
    if branch in {"main", "master"}:
        return []

    base_ref = "origin/main"
    merge_base = _run_git(["git", "merge-base", "HEAD", base_ref])
    if merge_base.returncode != 0 or not merge_base.stdout.strip():
        return []

    diff = _run_git(["git", "diff", "--name-only", f"{merge_base.stdout.strip()}...HEAD"])
    if diff.returncode != 0:
        return []
    return [Path(line.strip()) for line in diff.stdout.splitlines() if line.strip()]


def _validate_pr_diff_scope() -> None:
    changed = _changed_files_against_base()
    if not changed:
        return

    violations: list[str] = []
    for path in changed:
        normalized = Path(path.as_posix())
        if normalized in PR_DIFF_FORBIDDEN_EXACT or normalized in PR_DIFF_FORBIDDEN_DEPENDENCIES:
            violations.append(normalized.as_posix())
            continue
        for prefix in PR_DIFF_FORBIDDEN_PREFIXES:
            if normalized == prefix or prefix in normalized.parents:
                violations.append(normalized.as_posix())
                break
    _require(
        not violations,
        "M6 diff includes unauthorized implementation/provider/API/dependency/frontend paths: "
        + "; ".join(sorted(set(violations))),
    )


def _run_negative_control() -> None:
    with tempfile.TemporaryDirectory(prefix="m6_bad_import_") as tmp:
        tmp_root = Path(tmp)
        bad_file = tmp_root / "backend/app/bayesian/m6_bad_import.py"
        bad_file.parent.mkdir(parents=True, exist_ok=True)
        bad_file.write_text(
            "from app.llm.provider_boundary import SkeldirLLMProvider\n",
            encoding="utf-8",
        )
        try:
            _scan_forbidden_llm_imports(tmp_root)
        except ValidationError as exc:
            print(f"M6_NEGATIVE_CONTROL_PASS: {exc}")
            return
        raise ValidationError("negative control failed to detect forbidden B2.4 LLM import")


def validate_all(args: argparse.Namespace) -> None:
    _validate_decision_docs()
    _validate_governance()
    _scan_provider_sdk_imports()
    _scan_forbidden_llm_imports()
    _validate_pr_diff_scope()
    if args.negative_control:
        _run_negative_control()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--negative-control",
        action="store_true",
        help="Run a bad B2.4 import fixture proving the validator fails.",
    )
    args = parser.parse_args()
    try:
        validate_all(args)
    except ValidationError as exc:
        print(f"M6_LLM_BOUNDARY_VALIDATION_FAIL: {exc}", file=sys.stderr)
        return 1
    print("M6_LLM_BOUNDARY_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
