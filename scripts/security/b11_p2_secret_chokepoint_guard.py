#!/usr/bin/env python3
from __future__ import annotations

"""Fail when sensitive secrets are read outside app.core.secrets."""

import argparse
import ast
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.managed_settings_contract import MANAGED_SETTINGS_CONTRACT

APP_ROOT = REPO_ROOT / "backend" / "app"
ALLOWED_FILES = {
    "backend/app/core/secrets.py",
    "backend/app/core/config.py",
    "backend/app/core/control_plane.py",
    "backend/app/core/managed_settings_contract.py",
}


def _secret_keys() -> set[str]:
    return {
        key
        for key, contract in MANAGED_SETTINGS_CONTRACT.items()
        if contract.classification == "secret"
    }


def _iter_python_paths(explicit: Iterable[str] | None) -> list[Path]:
    if explicit:
        return [Path(item).resolve() for item in explicit]
    return sorted(APP_ROOT.rglob("*.py"))


def _repo_rel(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _is_allowed(path: Path) -> bool:
    return _repo_rel(path) in ALLOWED_FILES


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
    ):
        return f"{node.value.value.id}.{node.value.attr}.{node.attr}"
    return None


def _const_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _scan_path(path: Path, secret_keys: set[str]) -> list[str]:
    if _is_allowed(path):
        return []

    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    violations: list[str] = []
    rel = _repo_rel(path)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "settings" and node.attr in secret_keys:
                violations.append(f"{rel}:{node.lineno}: forbidden settings secret access settings.{node.attr}")

        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in {"os.getenv", "os.environ.get"} and node.args:
                key = _const_string(node.args[0])
                if key in secret_keys:
                    violations.append(f"{rel}:{node.lineno}: forbidden env secret access {name}('{key}')")

        if isinstance(node, ast.Subscript):
            if (
                isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "os"
                and node.value.attr == "environ"
            ):
                key = _const_string(node.slice)
                if key in secret_keys:
                    violations.append(f"{rel}:{node.lineno}: forbidden env secret access os.environ['{key}']")

    return violations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paths", nargs="*", default=None)
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    secret_keys = _secret_keys()
    paths = _iter_python_paths(args.paths)
    violations: list[str] = []
    for path in paths:
        if path.suffix != ".py" or not path.exists():
            continue
        violations.extend(_scan_path(path, secret_keys))

    report_lines = [
        "b11_p2_secret_chokepoint_scan",
        f"secret_keys={','.join(sorted(secret_keys))}",
        f"scanned_files={len(paths)}",
        f"violations={len(violations)}",
    ]
    report_lines.extend(violations)
    report_text = "\n".join(report_lines) + "\n"

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text, encoding="utf-8")

    print(report_text, end="")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
