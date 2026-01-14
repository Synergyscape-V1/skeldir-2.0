#!/usr/bin/env python3
"""
Fail-closed hermeticity enforcement for backend runtime code.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple


FORBIDDEN_MODULES = {
    "openai",
    "anthropic",
    "google.generativeai",
    "vertexai",
    "bedrock",
    "boto3",
    "requests",
    "httpx",
    "aiohttp",
    "socket",
    "urllib.request",
    "importlib",
}

ALLOWLIST_MODULES = {"urllib.parse"}

ENTRYPOINTS = [
    "backend/app/tasks/llm.py",
    "backend/app/workers/llm.py",
    "backend/app/celery_app.py",
]

SUBPROCESS_FUNCS = {
    ("subprocess", "run"),
    ("subprocess", "call"),
    ("subprocess", "check_call"),
    ("subprocess", "check_output"),
    ("subprocess", "Popen"),
    ("os", "system"),
}

SUBPROCESS_BANNED = {"curl", "wget"}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def iter_python_files(root: Path) -> Iterable[Path]:
    return root.rglob("*.py")


def resolve_module_to_path(module: str, base_file: Path) -> Optional[Path]:
    if not module:
        return None
    if module.startswith("app."):
        rel = module[len("app.") :].replace(".", "/")
        return repo_root() / "backend" / "app" / f"{rel}.py"
    if module == "app":
        return repo_root() / "backend" / "app" / "__init__.py"
    if module.startswith("backend.app."):
        rel = module[len("backend.app.") :].replace(".", "/")
        return repo_root() / "backend" / "app" / f"{rel}.py"
    if module == "backend.app":
        return repo_root() / "backend" / "app" / "__init__.py"
    if module.startswith("."):
        base_dir = base_file.parent
        rel = module.lstrip(".").replace(".", "/")
        if rel:
            return base_dir / f"{rel}.py"
        return base_dir / "__init__.py"
    return None


def classify_import(module: str, names: Optional[List[str]]) -> Tuple[Set[str], Set[str]]:
    forbidden: Set[str] = set()
    allowed: Set[str] = set()

    if module in ALLOWLIST_MODULES:
        allowed.add(module)
        return forbidden, allowed

    if module in FORBIDDEN_MODULES:
        forbidden.add(module)
        return forbidden, allowed

    if module == "urllib" and names:
        for name in names:
            full = f"urllib.{name}"
            if full in ALLOWLIST_MODULES:
                allowed.add(full)
            else:
                forbidden.add(full)
        return forbidden, allowed

    if module == "google" and names:
        for name in names:
            if name == "generativeai":
                forbidden.add("google.generativeai")
        return forbidden, allowed

    return forbidden, allowed


def _extract_command_token(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.List) and node.elts:
        first = node.elts[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
    return None


def parse_file(path: Path) -> Tuple[List[Tuple[int, str]], List[Tuple[int, str]], List[Tuple[int, str]]]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    forbidden_hits: List[Tuple[int, str]] = []
    allowed_hits: List[Tuple[int, str]] = []
    subprocess_hits: List[Tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                forbidden, allowed = classify_import(alias.name, None)
                for name in sorted(forbidden):
                    forbidden_hits.append((node.lineno, name))
                for name in sorted(allowed):
                    allowed_hits.append((node.lineno, name))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
            forbidden, allowed = classify_import(module, names)
            for name in sorted(forbidden):
                forbidden_hits.append((node.lineno, name))
            for name in sorted(allowed):
                allowed_hits.append((node.lineno, name))
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                forbidden_hits.append((node.lineno, "__import__"))
            if isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "importlib":
                    forbidden_hits.append((node.lineno, "importlib.import_module"))
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                func_key = (func.value.id, func.attr)
                if func_key in SUBPROCESS_FUNCS and node.args:
                    token = _extract_command_token(node.args[0])
                    if token:
                        for banned in SUBPROCESS_BANNED:
                            if banned in token:
                                subprocess_hits.append((node.lineno, f"subprocess:{banned}"))

    return forbidden_hits, allowed_hits, subprocess_hits


def build_reachability(entrypoints: Iterable[Path]) -> Set[Path]:
    seen: Set[Path] = set()
    queue: List[Path] = []

    for entry in entrypoints:
        if entry.exists():
            queue.append(entry)

    while queue:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)

        try:
            tree = ast.parse(current.read_text(encoding="utf-8"), filename=str(current))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = resolve_module_to_path(alias.name, current)
                    if target and target.exists():
                        queue.append(target)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level and module:
                    module = "." * node.level + module
                target = resolve_module_to_path(module, current)
                if target and target.exists():
                    queue.append(target)

    return seen


def scan_runtime(root: Path, reachable: Set[Path]) -> Tuple[List[str], List[str]]:
    violations: List[str] = []
    allowlist_hits: List[str] = []

    for path in iter_python_files(root):
        forbidden_hits, allowed_hits, subprocess_hits = parse_file(path)
        rel_path = path.relative_to(repo_root())
        for lineno, name in allowed_hits:
            allowlist_hits.append(f"{rel_path}:{lineno} allow:{name}")
        for lineno, name in forbidden_hits:
            severity = "HIGH" if path in reachable else "MEDIUM"
            violations.append(f"{rel_path}:{lineno} {severity} forbidden:{name}")
        for lineno, name in subprocess_hits:
            severity = "HIGH" if path in reachable else "MEDIUM"
            violations.append(f"{rel_path}:{lineno} {severity} forbidden:{name}")

    return violations, allowlist_hits


def write_output(lines: List[str], output_path: Optional[Path]) -> None:
    payload = "\n".join(lines) + ("\n" if lines else "")
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    print(payload, end="")


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce hermetic runtime imports")
    parser.add_argument("--output", help="Optional output log path")
    args = parser.parse_args()

    repo = repo_root()
    runtime_root = repo / "backend" / "app"
    entrypoints = [repo / entry for entry in ENTRYPOINTS]
    reachable = build_reachability(entrypoints)

    violations, allowlist_hits = scan_runtime(runtime_root, reachable)
    header = [
        "Hermetic runtime scan",
        f"Scanned root: {runtime_root}",
        f"Reachable modules: {len(reachable)}",
        f"Violations: {len(violations)}",
    ]
    output_lines: List[str] = (
        header
        + [""]
        + ["Allowlist hits:"]
        + allowlist_hits
        + [""]
        + ["Violations:"]
        + violations
    )

    output_path = Path(args.output) if args.output else None
    write_output(output_lines, output_path)

    if violations:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
