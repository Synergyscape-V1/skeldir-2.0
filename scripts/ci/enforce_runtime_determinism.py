#!/usr/bin/env python3
"""
Fail-closed determinism enforcement for backend runtime code.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
from typing import Iterable, List, Optional, Set


ENTRYPOINTS = [
    "backend/app/tasks/llm.py",
    "backend/app/workers/llm.py",
    "backend/app/celery_app.py",
]

ENTROPY_CALLS = {
    ("uuid", "uuid4"),
    ("uuid", "uuid1"),
    ("random", "random"),
    ("random", "randint"),
    ("random", "randrange"),
    ("random", "choice"),
    ("random", "choices"),
    ("random", "shuffle"),
    ("secrets", "token_hex"),
    ("secrets", "token_bytes"),
    ("secrets", "token_urlsafe"),
    ("os", "urandom"),
    ("time", "time"),
    ("datetime", "now"),
    ("datetime", "utcnow"),
}


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


def _is_entropy_call(func: ast.AST) -> Optional[str]:
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        key = (func.value.id, func.attr)
        if key in ENTROPY_CALLS:
            return f"{func.value.id}.{func.attr}"
    if isinstance(func, ast.Name):
        if ("uuid", func.id) in ENTROPY_CALLS:
            return f"uuid.{func.id}"
        if ("random", func.id) in ENTROPY_CALLS:
            return f"random.{func.id}"
    return None


def _detect_default_factory(node: ast.Call) -> Optional[str]:
    for keyword in node.keywords:
        if keyword.arg != "default_factory":
            continue
        value = keyword.value
        if isinstance(value, ast.Name) and value.id == "uuid4":
            return "default_factory:uuid4"
        if isinstance(value, ast.Attribute) and value.attr == "uuid4":
            return "default_factory:uuid4"
    return None


def parse_file(path: Path) -> List[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    hits: List[tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            entropy = _is_entropy_call(node.func)
            if entropy:
                hits.append((node.lineno, entropy))
            default_factory = _detect_default_factory(node)
            if default_factory:
                hits.append((node.lineno, default_factory))

    return hits


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


def scan_runtime(root: Path, reachable: Set[Path]) -> List[str]:
    violations: List[str] = []
    for path in iter_python_files(root):
        hits = parse_file(path)
        if not hits:
            continue
        if path not in reachable:
            continue
        rel_path = path.relative_to(repo_root())
        for lineno, name in hits:
            violations.append(f"{rel_path}:{lineno} forbidden:{name}")
    return violations


def write_output(lines: List[str], output_path: Optional[Path]) -> None:
    payload = "\n".join(lines) + ("\n" if lines else "")
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    print(payload, end="")


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce deterministic runtime behavior")
    parser.add_argument("--output", help="Optional output log path")
    args = parser.parse_args()

    repo = repo_root()
    runtime_root = repo / "backend" / "app"
    entrypoints = [repo / entry for entry in ENTRYPOINTS]
    reachable = build_reachability(entrypoints)

    violations = scan_runtime(runtime_root, reachable)
    header = [
        "Determinism scan",
        f"Scanned root: {runtime_root}",
        f"Reachable modules: {len(reachable)}",
        f"Violations: {len(violations)}",
    ]
    output_lines: List[str] = header + [""] + ["Violations:"] + violations

    output_path = Path(args.output) if args.output else None
    write_output(output_lines, output_path)

    if violations:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
