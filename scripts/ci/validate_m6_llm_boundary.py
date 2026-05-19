#!/usr/bin/env python3
"""Validate M6 LLM boundary decision and import guardrails."""

from __future__ import annotations

import argparse
import ast
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
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

REVERSE_FLOW_ROOT = Path("backend/app/llm")
REVERSE_FLOW_FORBIDDEN_MODULES = (
    "app.bayesian",
    "backend.app.bayesian",
    "app.trust",
    "backend.app.trust",
    "app.reconciliation",
    "backend.app.reconciliation",
    "app.revenue_verification",
    "backend.app.revenue_verification",
    "app.policy",
    "backend.app.policy",
    "app.policies",
    "backend.app.policies",
    "app.solver",
    "backend.app.solver",
    "app.envelope",
    "backend.app.envelope",
    "app.mcp",
    "backend.app.mcp",
    "app.tasks.bayesian",
    "backend.app.tasks.bayesian",
)

REVERSE_FLOW_ALLOWED_IMPORTS: set[str] = set()

FORBIDDEN_SYMBOL_REFERENCES = {
    "SkeldirLLMProvider",
    "LLMProvider",
    "provider_boundary",
    "OpenAI",
    "AsyncOpenAI",
    "Anthropic",
    "AsyncAnthropic",
    "Groq",
    "Mistral",
    "Cohere",
    "GenerativeModel",
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


@dataclass(frozen=True)
class ImportRef:
    lineno: int
    module: str
    kind: str


@dataclass(frozen=True)
class DynamicCall:
    lineno: int
    name: str
    argument: str | None


def _normalize_rel(path: Path) -> Path:
    return Path(path.as_posix())


def _rel(path: Path, root: Path = ROOT) -> Path:
    try:
        return _normalize_rel(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return _normalize_rel(path)


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


def _module_name_for_path(path: Path, root: Path) -> str | None:
    rel_path = _rel(path, root)
    if rel_path.parts[:2] == ("backend", "app"):
        module_parts = ("app",) + rel_path.parts[2:]
    elif rel_path.parts[:1] in {("scripts",), ("tests",)}:
        module_parts = rel_path.parts
    else:
        return None
    last = module_parts[-1]
    if not last.endswith(".py"):
        return None
    stem = last[:-3]
    if stem == "__init__":
        return ".".join(module_parts[:-1])
    return ".".join(module_parts[:-1] + (stem,))


def _package_name_for_path(path: Path, root: Path) -> str | None:
    module_name = _module_name_for_path(path, root)
    if not module_name:
        return None
    if path.name == "__init__.py":
        return module_name
    return module_name.rpartition(".")[0]


def _resolve_relative_module(path: Path, root: Path, level: int, module: str | None) -> str | None:
    package_name = _package_name_for_path(path, root)
    if not package_name:
        return None
    package_parts = package_name.split(".")
    if level <= 0:
        return module
    keep = len(package_parts) - (level - 1)
    if keep <= 0:
        return None
    base_parts = package_parts[:keep]
    if module:
        base_parts.extend(module.split("."))
    return ".".join(base_parts)


def _imported_modules(tree: ast.Module, path: Path, root: Path) -> list[ImportRef]:
    imports: list[ImportRef] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(ImportRef(node.lineno, alias.name, "import"))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                resolved = _resolve_relative_module(path, root, node.level, node.module)
                if resolved is None:
                    imports.append(ImportRef(node.lineno, f"<unresolved-relative:{node.level}:{node.module or ''}>", "relative"))
                    continue
                imports.append(ImportRef(node.lineno, resolved, "relative"))
                for alias in node.names:
                    if alias.name != "*":
                        imports.append(ImportRef(node.lineno, f"{resolved}.{alias.name}", "relative"))
            elif node.module:
                imports.append(ImportRef(node.lineno, node.module, "from"))
                for alias in node.names:
                    if alias.name != "*":
                        imports.append(ImportRef(node.lineno, f"{node.module}.{alias.name}", "from"))
    return imports


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        if prefix:
            return f"{prefix}.{node.attr}"
        return node.attr
    return None


def _literal_first_arg(node: ast.Call) -> str | None:
    if not node.args:
        return None
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _dynamic_calls(tree: ast.Module) -> list[DynamicCall]:
    calls: list[DynamicCall] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name in {"importlib.import_module", "__import__", "eval", "exec"}:
            calls.append(DynamicCall(node.lineno, name, _literal_first_arg(node)))
    return calls


def _forbidden_symbol_refs(tree: ast.Module) -> list[tuple[int, str]]:
    refs: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_SYMBOL_REFERENCES:
            refs.append((node.lineno, node.id))
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_SYMBOL_REFERENCES:
            refs.append((node.lineno, node.attr))
    return refs


def _is_forbidden_truth_path(rel_path: Path) -> bool:
    rel_path = _normalize_rel(rel_path)
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


def _is_llm_path(rel_path: Path) -> bool:
    return _normalize_rel(rel_path).parts[:3] == ("backend", "app", "llm")


def _scan_provider_sdk_imports(root: Path = ROOT) -> None:
    violations: list[str] = []
    truth_path_violations: list[str] = []
    for path in _iter_python_files(root):
        rel_path = _rel(path, root)
        tree = _parse_ast(path)
        for import_ref in _imported_modules(tree, path, root):
            if _contains_import(import_ref.module, PROVIDER_SDK_MODULES):
                item = f"{rel_path.as_posix()}:{import_ref.lineno}: {import_ref.module}"
                if rel_path not in ALLOWED_PROVIDER_SDK_IMPORT_PATHS:
                    violations.append(item)
                if _is_forbidden_truth_path(rel_path):
                    truth_path_violations.append(item)
    _require(
        not truth_path_violations,
        "provider SDK import in protected truth path: " + "; ".join(truth_path_violations),
    )
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
        for import_ref in _imported_modules(tree, path, root):
            if import_ref.module.startswith("<unresolved-relative:") or _contains_import(import_ref.module, APP_LLM_MODULES):
                violations.append(f"{rel_path.as_posix()}:{import_ref.lineno}: {import_ref.module}")
    _require(
        not violations,
        "forbidden LLM import in B2.4/truth path: " + "; ".join(violations),
    )


def _scan_dynamic_imports(root: Path = ROOT) -> None:
    violations: list[str] = []
    for path in _iter_python_files(root):
        rel_path = _rel(path, root)
        if not _is_forbidden_truth_path(rel_path):
            continue
        tree = _parse_ast(path)
        for call in _dynamic_calls(tree):
            detail = f"{call.name}({call.argument})" if call.argument is not None else call.name
            violations.append(f"{rel_path.as_posix()}:{call.lineno}: {detail}")
    _require(
        not violations,
        "dynamic import/code execution in protected truth path: " + "; ".join(violations),
    )


def _scan_forbidden_symbols(root: Path = ROOT) -> None:
    violations: list[str] = []
    for path in _iter_python_files(root):
        rel_path = _rel(path, root)
        if not _is_forbidden_truth_path(rel_path):
            continue
        tree = _parse_ast(path)
        for lineno, symbol in _forbidden_symbol_refs(tree):
            violations.append(f"{rel_path.as_posix()}:{lineno}: {symbol}")
    _require(
        not violations,
        "forbidden LLM/provider symbol reference in protected truth path: " + "; ".join(violations),
    )


def _scan_reverse_flow_imports(root: Path = ROOT) -> None:
    violations: list[str] = []
    for path in _iter_python_files(root):
        rel_path = _rel(path, root)
        if not _is_llm_path(rel_path):
            continue
        tree = _parse_ast(path)
        for import_ref in _imported_modules(tree, path, root):
            if (
                _contains_import(import_ref.module, REVERSE_FLOW_FORBIDDEN_MODULES)
                and import_ref.module not in REVERSE_FLOW_ALLOWED_IMPORTS
            ):
                violations.append(f"{rel_path.as_posix()}:{import_ref.lineno}: {import_ref.module}")
        for call in _dynamic_calls(tree):
            if call.name in {"importlib.import_module", "__import__"} and call.argument:
                if _contains_import(call.argument, REVERSE_FLOW_FORBIDDEN_MODULES):
                    violations.append(f"{rel_path.as_posix()}:{call.lineno}: {call.name}({call.argument})")
    _require(
        not violations,
        "forbidden reverse-flow import from LLM into truth internals: " + "; ".join(violations),
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
        "Reverse-Flow Import Policy",
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
    _require("No reverse-flow exceptions are approved during M6" in decision, "decision record must list reverse-flow exceptions")

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
        "relative imports",
        "dynamic imports",
        "reverse-flow",
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

    for token in (
        "Host-native execution is advisory",
        "CI on main is authoritative",
        "M6_NC_RELATIVE_IMPORT_PASS",
        "M6_NC_DYNAMIC_IMPORTLIB_PASS",
        "M6_NC_REVERSE_FLOW_IMPORT_PASS",
        "M6_NC_DECISION_MUTATION_PASS",
    ):
        _require(token in completion, f"{COMPLETION_RECORD_PATH.as_posix()} missing token: {token}")

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
        normalized = _normalize_rel(path)
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


def _write_fixture(root: Path, rel_path: str, content: str) -> Path:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _expect_failure(label: str, func, expected: str) -> None:
    try:
        func()
    except ValidationError as exc:
        message = str(exc)
        _require(expected in message, f"{label} failed for unexpected reason: {message}")
        print(f"{label}: {message}")
        return
    raise ValidationError(f"{label} did not fail")


def _negative_control_scan(label: str, rel_path: str, content: str, scan_func, expected: str) -> None:
    with tempfile.TemporaryDirectory(prefix="m6_negative_control_") as tmp:
        tmp_root = Path(tmp)
        _write_fixture(tmp_root, rel_path, content)
        _expect_failure(label, lambda: scan_func(tmp_root), expected)


def _negative_control_decision_mutation() -> None:
    with tempfile.TemporaryDirectory(prefix="m6_decision_mutation_") as tmp:
        tmp_root = Path(tmp)
        for path in (
            DECISION_PATH,
            GUARDRAIL_PATH,
            B27_PRECONDITION_PATH,
            COMPLETION_RECORD_PATH,
            EVIDENCE_PACK_PATH,
        ):
            destination = tmp_root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / path, destination)
        decision_path = tmp_root / DECISION_PATH
        decision = decision_path.read_text(encoding="utf-8")
        decision = decision.replace("Path B is invalid", "Path B drift is handled later")
        decision_path.write_text(decision, encoding="utf-8")
        _expect_failure(
            "M6_NC_DECISION_MUTATION_PASS",
            lambda: _validate_decision_docs(tmp_root),
            "missing token: Path B is invalid",
        )


def _run_negative_controls() -> None:
    _negative_control_scan(
        "M6_NC_ABSOLUTE_IMPORT_PASS",
        "backend/app/bayesian/m6_bad_absolute.py",
        "from app.llm.provider_boundary import SkeldirLLMProvider\n",
        _scan_forbidden_llm_imports,
        "forbidden LLM import",
    )
    _negative_control_scan(
        "M6_NC_PACKAGE_IMPORT_PASS",
        "backend/app/bayesian/m6_bad_package.py",
        "from app import llm\n",
        _scan_forbidden_llm_imports,
        "forbidden LLM import",
    )
    _negative_control_scan(
        "M6_NC_ALIAS_IMPORT_PASS",
        "backend/app/bayesian/m6_bad_alias.py",
        "import app.llm.provider_boundary as provider_boundary\n",
        _scan_forbidden_llm_imports,
        "forbidden LLM import",
    )
    _negative_control_scan(
        "M6_NC_RELATIVE_IMPORT_PASS",
        "backend/app/bayesian/m6_bad_relative.py",
        "from ..llm import provider_boundary\n",
        _scan_forbidden_llm_imports,
        "forbidden LLM import",
    )
    _negative_control_scan(
        "M6_NC_DYNAMIC_IMPORTLIB_PASS",
        "backend/app/bayesian/m6_bad_importlib.py",
        "import importlib\nprovider = importlib.import_module('app.llm.provider_boundary')\n",
        _scan_dynamic_imports,
        "dynamic import/code execution",
    )
    _negative_control_scan(
        "M6_NC_DYNAMIC_BUILTIN_IMPORT_PASS",
        "backend/app/bayesian/m6_bad_builtin_import.py",
        "provider = __import__('app.llm.provider_boundary')\n",
        _scan_dynamic_imports,
        "dynamic import/code execution",
    )
    _negative_control_scan(
        "M6_NC_DYNAMIC_EVAL_PASS",
        "backend/app/bayesian/m6_bad_eval.py",
        "value = eval('1 + 1')\n",
        _scan_dynamic_imports,
        "dynamic import/code execution",
    )
    _negative_control_scan(
        "M6_NC_DYNAMIC_EXEC_PASS",
        "backend/app/bayesian/m6_bad_exec.py",
        "exec('value = 1')\n",
        _scan_dynamic_imports,
        "dynamic import/code execution",
    )
    _negative_control_scan(
        "M6_NC_PROVIDER_SDK_TRUTH_PATH_PASS",
        "backend/app/bayesian/m6_bad_provider_sdk.py",
        "from openai import OpenAI\n",
        _scan_provider_sdk_imports,
        "provider SDK import in protected truth path",
    )
    _negative_control_scan(
        "M6_NC_FORBIDDEN_SYMBOL_PASS",
        "backend/app/bayesian/m6_bad_symbol.py",
        "def build():\n    return SkeldirLLMProvider\n",
        _scan_forbidden_symbols,
        "forbidden LLM/provider symbol reference",
    )
    _negative_control_scan(
        "M6_NC_REVERSE_FLOW_IMPORT_PASS",
        "backend/app/llm/m6_bad_reverse_flow.py",
        "from app.bayesian import diagnostics\n",
        _scan_reverse_flow_imports,
        "forbidden reverse-flow import",
    )
    _negative_control_decision_mutation()
    print("M6_NEGATIVE_CONTROL_PASS")


def validate_all(args: argparse.Namespace) -> None:
    _validate_decision_docs()
    _validate_governance()
    _scan_provider_sdk_imports()
    _scan_forbidden_llm_imports()
    _scan_dynamic_imports()
    _scan_forbidden_symbols()
    _scan_reverse_flow_imports()
    _validate_pr_diff_scope()
    if args.negative_control:
        _run_negative_controls()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--negative-control",
        action="store_true",
        help="Run bad fixtures proving the validator fails across static, dynamic, reverse-flow, and doc-drift cases.",
    )
    args = parser.parse_args()
    print(f"M6_ENVIRONMENT: python={platform.python_version()} platform={platform.platform()}")
    try:
        validate_all(args)
    except ValidationError as exc:
        print(f"M6_LLM_BOUNDARY_VALIDATION_FAIL: {exc}", file=sys.stderr)
        return 1
    print("M6_LLM_BOUNDARY_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
