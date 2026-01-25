#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

INDEX_PATH = Path("docs/forensics/INDEX.md")
EVIDENCE_ROOT = Path("docs/forensics")
PLACEHOLDER_TOKENS = ("pending", "local-uncommitted", "ci-pending")


def run_git(args: list[str]) -> str:
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def changed_files() -> list[str]:
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    if event == "pull_request":
        base_ref = os.environ.get("GITHUB_BASE_REF")
        if base_ref:
            subprocess.run(["git", "fetch", "origin", base_ref, "--depth=1"], check=True)
            diff = run_git(["git", "diff", "--name-only", f"origin/{base_ref}...HEAD"])
            return [line for line in diff.splitlines() if line.strip()]

    try:
        head_parent = run_git(["git", "rev-parse", "HEAD^"])
    except subprocess.CalledProcessError:
        return []

    diff = run_git(["git", "diff", "--name-only", head_parent, "HEAD"])
    return [line for line in diff.splitlines() if line.strip()]


def main() -> int:
    if not INDEX_PATH.exists():
        print("docs/forensics/INDEX.md not found")
        return 1

    index_text = INDEX_PATH.read_text(encoding="utf-8")
    modified = set(changed_files())

    evidence_changed = [
        path
        for path in modified
        if path.startswith(str(EVIDENCE_ROOT))
        and path.lower().endswith(".md")
        and Path(path) != INDEX_PATH
    ]

    errors: list[str] = []

    if evidence_changed and str(INDEX_PATH) not in modified:
        errors.append(
            "docs/forensics/INDEX.md must be updated when evidence packs change."
        )

    for path in evidence_changed:
        if path not in index_text:
            errors.append(f"Missing INDEX entry for evidence pack: {path}")

    for line in index_text.splitlines():
        if "| B0.5.7" in line:
            lower = line.lower()
            if any(token in lower for token in PLACEHOLDER_TOKENS):
                errors.append(f"Placeholder token in B0.5.7 INDEX row: {line}")

    if errors:
        print("Forensics INDEX enforcement failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("Forensics INDEX enforcement passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())