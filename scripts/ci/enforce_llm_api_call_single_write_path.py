#!/usr/bin/env python3
"""
Fail-closed enforcement for a single runtime write path to llm_api_calls.

Only the provider boundary may construct or insert LLMApiCall rows.
"""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path
from typing import Iterable


WRITE_BOUNDARY = Path("backend/app/llm/provider_boundary.py")
RAW_INSERT_PATTERN = re.compile(r"insert\s+into\s+llm_api_calls", re.IGNORECASE)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _iter_python_paths(root: Path) -> Iterable[Path]:
    for path in (root / "backend" / "app").rglob("*.py"):
        if path.is_file():
            yield path


def _name_of(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _contains_llm_api_call_ref(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "LLMApiCall"
    if isinstance(node, ast.Attribute):
        return node.attr == "LLMApiCall"
    return False


def _scan_file(path: Path, root: Path) -> list[str]:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    if rel == WRITE_BOUNDARY:
        return []

    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = _name_of(node.func)
            if func_name == "LLMApiCall":
                violations.append(f"{rel}:{node.lineno} forbidden LLMApiCall constructor outside write boundary")
            if func_name == "insert" and node.args and _contains_llm_api_call_ref(node.args[0]):
                violations.append(f"{rel}:{node.lineno} forbidden insert(LLMApiCall) outside write boundary")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if RAW_INSERT_PATTERN.search(node.value):
                violations.append(f"{rel}:{node.lineno} forbidden raw SQL INSERT INTO llm_api_calls outside write boundary")

    return violations


def _resolve_scan_paths(root: Path, explicit: list[str] | None) -> list[Path]:
    if not explicit:
        return list(_iter_python_paths(root))

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


def _write_output(lines: list[str], output: Path | None) -> None:
    payload = "\n".join(lines) + ("\n" if lines else "")
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    print(payload, end="")


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce single write path for llm_api_calls")
    parser.add_argument("--paths", nargs="*", help="Optional files/directories to scan")
    parser.add_argument("--output", help="Optional output log file")
    args = parser.parse_args()

    root = _repo_root()
    scan_paths = _resolve_scan_paths(root, args.paths)
    violations: list[str] = []
    for path in scan_paths:
        violations.extend(_scan_file(path, root))

    lines = [
        "LLMApiCall single-write-path scan",
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
