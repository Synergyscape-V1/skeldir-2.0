#!/usr/bin/env python3
"""
Guard script that enforces the Zero Docker Doctrine.

It scans source/workflow directories for forbidden Docker references in both
file names and file contents. Only the archival documentation tree
(docs/forensics/archive/**) is ignored.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

# Directories that contain executable code, scripts, or workflows which must be
# free of Docker usage.
CHECK_ROOT_DIRS = {
    ".github",
    "api-contracts",
    "alembic",
    "backend",
    "db",
    "scripts",
    "tests",
}

# Top-level files that should also be scanned even though they are not within
# a tracked directory (e.g., Makefile, configuration files).
CHECK_ROOT_FILES = {
    ".nvmrc",
    ".replit",
    "Makefile",
    "Procfile",
}

# Directories that are explicitly excluded from scanning.
EXCLUDED_PREFIXES = [
    ("docs", "archive"),
    ("db", "docs"),
    ("backend", "validation", "evidence"),
    ("backend", ".venv311"),
    ("scripts", "__pycache__"),
    ("backend", "__pycache__"),
    (".venv",),
    ("__pycache__",),
    (".git",),
    (".cursor",),
    ("node_modules",),
    ("tmp",),
    (".pytest_cache",),
    (".hypothesis",),
]

ALLOWED_DOCKER_PATHS = {
    Path(".github/workflows/ci.yml"),
    Path(".github/workflows/b07-p4-e2e-operational-readiness.yml"),
    Path("backend/Dockerfile"),
    Path("backend/mock_platform/Dockerfile"),
    Path("scripts/phase8/run_phase8_closure_pack.py"),
}

FORBIDDEN_FILENAME_SNIPPETS = ("dockerfile", "docker-compose")
FORBIDDEN_CONTENT_PATTERNS = (
    b"docker-compose",
    b"docker ",
    b"docker\n",
    b"docker\t",
    b"/docker",
)


def is_excluded(path: Path) -> bool:
    """Return True if the path belongs to an excluded prefix."""
    try:
        parts = path.relative_to(REPO_ROOT).parts
    except ValueError:
        return False

    for prefix in EXCLUDED_PREFIXES:
        if len(parts) >= len(prefix) and parts[: len(prefix)] == prefix:
            return True
    return False


def should_check(path: Path) -> bool:
    """Return True if the file should be inspected for violations."""
    if not path.is_file():
        return False
    if is_excluded(path):
        return False

    rel_parts = path.relative_to(REPO_ROOT).parts
    if len(rel_parts) == 1:
        # Root-level file
        return rel_parts[0] in CHECK_ROOT_FILES or rel_parts[0].startswith(".")

    return rel_parts[0] in CHECK_ROOT_DIRS


def is_allowed_docker_path(path: Path) -> bool:
    """Return True if Docker references are explicitly allowlisted."""
    try:
        rel = path.relative_to(REPO_ROOT)
    except ValueError:
        return False
    return rel in ALLOWED_DOCKER_PATHS


def detect_violations() -> list[str]:
    violations: list[str] = []
    guard_script_path = Path(__file__).resolve()
    for file_path in REPO_ROOT.rglob("*"):
        if not should_check(file_path):
            continue
        if file_path.resolve() == guard_script_path:
            continue
        if is_allowed_docker_path(file_path):
            continue

        lower_name = file_path.name.lower()
        if any(snippet in lower_name for snippet in FORBIDDEN_FILENAME_SNIPPETS):
            violations.append(f"{file_path}: forbidden filename referencing Docker")
            continue

        # Read file content as binary and search for forbidden tokens.
        try:
            data = file_path.read_bytes()
        except Exception as exc:  # pragma: no cover - defensive
            violations.append(f"{file_path}: unable to read file ({exc})")
            continue

        lower_data = data.lower()
        if any(pattern in lower_data for pattern in FORBIDDEN_CONTENT_PATTERNS):
            violations.append(f"{file_path}: contains forbidden Docker reference")

    return violations


def main() -> int:
    violations = detect_violations()
    if violations:
        print("Zero Docker Doctrine violations detected:", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
        print(
            "\nAll references to Docker or container tooling must be removed "
            "or moved to docs/forensics/archive/**.",
            file=sys.stderr,
        )
        return 1

    print("Zero Docker Doctrine check passed: no Docker references found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
