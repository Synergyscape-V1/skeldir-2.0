#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

INDEX_PATH = Path("docs/forensics/INDEX.md")
EVIDENCE_ROOT = Path("docs/forensics")
PLACEHOLDER_TOKENS = ("pending", "local-uncommitted", "ci-pending")
B057_PHASE_TAG = "B0.5.7"
GIT_FETCH_ATTEMPTS = 4
GIT_FETCH_BACKOFF_SECONDS = 2.0


def fetch_base_ref(base_ref: str) -> None:
    last_error: subprocess.CalledProcessError | None = None
    for attempt in range(1, GIT_FETCH_ATTEMPTS + 1):
        try:
            subprocess.run(
                ["git", "fetch", "origin", base_ref, "--depth=1"],
                check=True,
                capture_output=True,
                text=True,
            )
            return
        except subprocess.CalledProcessError as error:
            last_error = error
            if attempt == GIT_FETCH_ATTEMPTS:
                break
            sleep_seconds = GIT_FETCH_BACKOFF_SECONDS * attempt
            print(
                f"git fetch origin {base_ref} failed on attempt {attempt}/"
                f"{GIT_FETCH_ATTEMPTS}; retrying in {sleep_seconds:.1f}s",
                file=sys.stderr,
            )
            time.sleep(sleep_seconds)
    if last_error is not None:
        raise last_error


def git_diff(base_ref: str | None, path: str | None = None) -> list[str]:
    diff_args: list[str] = []
    if path:
        diff_args = ["--", path]
    if base_ref:
        fetch_base_ref(base_ref)
        try:
            diff = run_git(
                ["git", "diff", "--unified=0", f"origin/{base_ref}...HEAD", *diff_args]
            )
        except subprocess.CalledProcessError:
            diff = run_git(
                ["git", "diff", "--unified=0", f"origin/{base_ref}..HEAD", *diff_args]
            )
    else:
        try:
            head_parent = run_git(["git", "rev-parse", "HEAD^"])
        except subprocess.CalledProcessError:
            return []
        diff = run_git(["git", "diff", "--unified=0", head_parent, "HEAD", *diff_args])
    return diff.splitlines()


def changed_index_rows() -> list[str]:
    if os.environ.get("GITHUB_EVENT_NAME") == "pull_request":
        base_ref = os.environ.get("GITHUB_BASE_REF")
    else:
        base_ref = None

    rows: list[str] = []
    for line in git_diff(base_ref, str(INDEX_PATH)):
        if not line.startswith("+|"):
            continue
        # Skip diff metadata for files
        if line.startswith("+++"):
            continue
        row = line[1:].strip()
        if row.startswith("| ---"):
            continue
        if row.count("|") < 5:
            continue
        rows.append(row)
    return rows


def parse_commit_sha(row: str) -> str | None:
    columns = [col.strip() for col in row.split("|")]
    if len(columns) < 6:
        return None
    commit = columns[4]
    return commit or None


def row_is_b057_scope(row: str) -> bool:
    lower = row.lower()
    return B057_PHASE_TAG.lower() in lower or "b057_" in lower or "b057-" in lower


def run_git(args: list[str]) -> str:
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def changed_files() -> list[str]:
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    if event == "pull_request":
        base_ref = os.environ.get("GITHUB_BASE_REF")
        if base_ref:
            fetch_base_ref(base_ref)
            try:
                diff = run_git(
                    ["git", "diff", "--name-only", f"origin/{base_ref}...HEAD"]
                )
            except subprocess.CalledProcessError:
                diff = run_git(
                    ["git", "diff", "--name-only", f"origin/{base_ref}..HEAD"]
                )
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
        if f"| {B057_PHASE_TAG}" in line:
            lower = line.lower()
            if any(token in lower for token in PLACEHOLDER_TOKENS):
                errors.append(f"Placeholder token in B0.5.7 INDEX row: {line}")

    expected_sha = os.environ.get("ADJUDICATED_SHA") or os.environ.get("GITHUB_SHA")
    if expected_sha:
        changed_rows = changed_index_rows()
        for row in changed_rows:
            if not row_is_b057_scope(row):
                continue
            commit = parse_commit_sha(row)
            if not commit:
                errors.append(f"Missing commit SHA in INDEX row: {row}")
                continue
            if commit != expected_sha:
                errors.append(
                    "INDEX commit SHA mismatch for B0.5.7 row: "
                    f"expected {expected_sha}, got {commit}"
                )

    if errors:
        print("Forensics INDEX enforcement failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("Forensics INDEX enforcement passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
