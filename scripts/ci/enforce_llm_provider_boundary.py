#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


ALLOWED_PATHS = {
    "backend/app/llm/provider_boundary.py",
}

ALLOWED_PREFIXES = (
    "docs/forensics/",
    "artifacts/",
    "artifacts_vt_run3/",
)

# Future-facing: these imports must remain inside the provider boundary wrapper.
FORBIDDEN_MODULE_PREFIXES = (
    "aisuite",
    "openai",
    "anthropic",
    "cohere",
    "mistralai",
    "litellm",
    "google.generativeai",
)

IMPORT_LINE_RE = re.compile(r"^\s*(from|import)\s+([a-zA-Z0-9_\.]+)\b")
DYNAMIC_IMPORT_RE = re.compile(r"__import__\(\s*['\"]([a-zA-Z0-9_\.]+)['\"]\s*\)")
FORBIDDEN_DIRECT_CALL_PATTERNS = (
    re.compile(r"\.chat\.completions\.create\s*\("),
    re.compile(r"\.responses\.create\s*\("),
    re.compile(r"\.messages\.create\s*\("),
)


@dataclass(frozen=True, slots=True)
class Violation:
    path: str
    line_no: int
    line: str


def _git_ls_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="surrogateescape",
    )
    return [path for path in result.stdout.split("\0") if path]


def _is_allowed(path: str) -> bool:
    if path in ALLOWED_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def _is_forbidden_import(module: str) -> bool:
    return any(
        module == prefix or module.startswith(prefix + ".")
        for prefix in FORBIDDEN_MODULE_PREFIXES
    )


def _scan_lines(path: Path) -> list[Violation]:
    violations: list[Violation] = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line_no, line in enumerate(handle, start=1):
                m = IMPORT_LINE_RE.match(line)
                if m:
                    module = m.group(2)
                    if _is_forbidden_import(module):
                        violations.append(
                            Violation(str(path), line_no, line.rstrip("\n"))
                        )
                        continue
                dyn = DYNAMIC_IMPORT_RE.search(line)
                if dyn and _is_forbidden_import(dyn.group(1)):
                    violations.append(Violation(str(path), line_no, line.rstrip("\n")))
                if any(
                    pattern.search(line) for pattern in FORBIDDEN_DIRECT_CALL_PATTERNS
                ):
                    violations.append(Violation(str(path), line_no, line.rstrip("\n")))
    except OSError as exc:
        violations.append(Violation(str(path), -1, f"<unreadable: {exc}>"))
    return violations


def _iter_python_files(paths: Iterable[Path]) -> Iterable[Path]:
    for base in paths:
        if base.is_file():
            if base.suffix == ".py":
                yield base
            continue
        if base.is_dir():
            yield from (p for p in base.rglob("*.py") if p.is_file())


def _resolve_scan_roots(args: argparse.Namespace) -> list[Path]:
    if args.paths:
        return [Path(p) for p in args.paths]
    return [Path(p) for p in _git_ls_files() if p.endswith(".py")]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce that LLM provider SDK imports only occur inside the provider boundary wrapper.",
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        default=[],
        help="Optional explicit paths to scan (files or directories). Defaults to git-tracked *.py files.",
    )
    parsed = parser.parse_args(argv[1:])

    violations: list[Violation] = []
    for path in _iter_python_files(_resolve_scan_roots(parsed)):
        rel = str(path).replace("\\", "/")
        if _is_allowed(rel):
            continue
        violations.extend(_scan_lines(path))

    if violations:
        print("Provider dependency references detected outside allowlisted boundary:")
        for v in violations:
            print(f"  - {v.path}:{v.line_no}: {v.line}")
        print("\nAllowlisted paths:")
        for p in sorted(ALLOWED_PATHS):
            print(f"  - {p}")
        print("Allowlisted prefixes:")
        for p in ALLOWED_PREFIXES:
            print(f"  - {p}")
        print("Forbidden module prefixes:")
        for m in FORBIDDEN_MODULE_PREFIXES:
            print(f"  - {m}")
        return 1

    print("Provider boundary enforcement passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
