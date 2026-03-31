#!/usr/bin/env python3
"""B1.6-P1 guard: provider boundary must not absorb investigation/budget domain SQL logic."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
from typing import Iterable


BOUNDARY_PATH = Path("backend/app/llm/provider_boundary.py")

FORBIDDEN_IMPORT_PREFIXES = (
    "app.services.investigation",
    "app.services.budget_job",
    "app.api.investigations",
    "app.api.budget",
)

FORBIDDEN_SYMBOLS = {
    "InvestigationService",
    "BudgetJobService",
    "InvestigationJob",
    "BudgetJobRecord",
}

FORBIDDEN_SQL_IDENTIFIERS = {
    "investigation_jobs",
    "budget_jobs",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_scan_paths(root: Path, explicit: list[str] | None) -> list[Path]:
    if not explicit:
        return [root / BOUNDARY_PATH]

    resolved: list[Path] = []
    for raw in explicit:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = (root / candidate).resolve()
        if candidate.is_dir():
            resolved.extend(p for p in candidate.rglob("*.py") if p.is_file())
        elif candidate.is_file() and candidate.suffix == ".py":
            resolved.append(candidate)
    return resolved


def _import_name(node: ast.AST) -> str:
    if isinstance(node, ast.Import):
        return ",".join(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        return module
    return ""


def _has_forbidden_import(name: str) -> bool:
    return any(name == p or name.startswith(p + ".") for p in FORBIDDEN_IMPORT_PREFIXES)


def _contains_forbidden_sql_identifier(text: str) -> str | None:
    lowered = text.lower()
    for token in FORBIDDEN_SQL_IDENTIFIERS:
        if token in lowered:
            return token
    return None


def _scan_file(path: Path, root: Path) -> list[str]:
    try:
        rel = path.relative_to(root) if path.is_absolute() else path
    except ValueError:
        rel = path
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            name = _import_name(node)
            if _has_forbidden_import(name):
                violations.append(f"{rel}:{node.lineno} forbidden domain import: {name}")

        if isinstance(node, ast.Name) and node.id in FORBIDDEN_SYMBOLS:
            violations.append(f"{rel}:{node.lineno} forbidden domain symbol reference: {node.id}")

        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            token = _contains_forbidden_sql_identifier(node.value)
            if token:
                violations.append(
                    f"{rel}:{node.lineno} forbidden domain SQL/table identifier in string literal: {token}"
                )

    return violations


def _write_output(lines: list[str], output: Path | None) -> None:
    payload = "\n".join(lines) + ("\n" if lines else "")
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    print(payload, end="")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail if provider_boundary.py contains investigation/budget domain SQL or imports.",
    )
    parser.add_argument("--paths", nargs="*", help="Optional files/directories to scan")
    parser.add_argument("--output", help="Optional output log file")
    args = parser.parse_args()

    root = _repo_root()
    scan_paths = _resolve_scan_paths(root, args.paths)
    violations: list[str] = []
    for path in scan_paths:
        violations.extend(_scan_file(path, root))

    lines = [
        "B1.6-P1 provider boundary domain SQL/import scan",
        f"Scanned files: {len(scan_paths)}",
        f"Violations: {len(violations)}",
        "",
        "Violations:",
        *violations,
    ]
    out = Path(args.output) if args.output else None
    _write_output(lines, out)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
