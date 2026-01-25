#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ALLOWED_PREFIXES = (
    ".hypothesis/",
    "docs/forensics/",
    "artifacts_vt_run3/",
    "backend/validation/evidence/",
    "artifacts/",
)
ALLOWED_PATHS = {
    "AGENTS.md",
    "backend/tests/test_b051_celery_foundation.py",
    "backend/58b. B0.4.7.1 Observability Remediation – Execution Summary.md",
    "scripts/ci/enforce_postgres_only.py",
}

REDIS_PATTERN = re.compile(r"(redis://|\bredis\b|\bREDIS\b)", re.IGNORECASE)


def git_ls_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="surrogateescape",
    )
    return [path for path in result.stdout.split("\0") if path]


def is_allowed(path: str) -> bool:
    if path in ALLOWED_PATHS:
        return True
    return path.startswith(ALLOWED_PREFIXES)


def scan_file(path: str) -> tuple[int, str] | None:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            for line_no, line in enumerate(handle, start=1):
                if REDIS_PATTERN.search(line):
                    return line_no, line.rstrip("\n")
    except OSError as exc:
        return -1, f"<unreadable: {exc}>"
    return None


def main() -> int:
    violations: list[str] = []

    for path in git_ls_files():
        if is_allowed(path):
            continue
        hit = scan_file(path)
        if hit:
            line_no, line = hit
            violations.append(f"{path}:{line_no}: {line}")

    if violations:
        print("Redis references detected outside allowlist:")
        for entry in violations:
            print(f"  - {entry}")
        print("\nAllowed prefixes:")
        for prefix in ALLOWED_PREFIXES:
            print(f"  - {prefix}")
        print("Allowed files:")
        for path in sorted(ALLOWED_PATHS):
            print(f"  - {path}")
        return 1

    print("Postgres-only guardrail passed: no Redis references outside allowlist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
