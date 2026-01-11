#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys


DOCS_ROOT = "docs/"
ALLOWED_ROOTS = (
    DOCS_ROOT,
    "backend/docs/",
    "db/docs/",
    "api-contracts/",
)
EVIDENCE_REGEX = re.compile(
    r"(evidence|handover|github_analyst|forensic|context_gathering|validation_report|(^|/)([bB]0|[bB]05|[bB]055|R2|V[0-9]))"
)


def _git_ls_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    files = _git_ls_files()
    md_files = [path for path in files if path.lower().endswith(".md")]
    evidence_files = [path for path in md_files if EVIDENCE_REGEX.search(path)]
    violations = [path for path in evidence_files if not path.startswith(ALLOWED_ROOTS)]

    if violations:
        print("Evidence docs must live under docs/")
        for path in violations:
            print(path)
        return 1

    print("Evidence placement OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
