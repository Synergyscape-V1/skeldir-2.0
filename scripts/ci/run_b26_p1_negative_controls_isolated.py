#!/usr/bin/env python3
"""Run the B2.6-P1 mutating battery in an owned disposable worktree."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence-out",
        default="artifacts/b26_p1/static/negative-controls.json",
    )
    args = parser.parse_args()

    temp_root = Path(tempfile.mkdtemp(prefix="b26p1-nc-worktree-"))
    evidence_rel = Path(args.evidence_out)
    try:
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(temp_root), "HEAD"],
            cwd=str(ROOT),
            check=True,
        )
        env = dict(os.environ)
        env["B26_P1_ISOLATED_WORKTREE"] = "1"
        completed = subprocess.run(
            [
                sys.executable,
                str(temp_root / "scripts/ci/test_b26_p1_negative_controls.py"),
                "--evidence-out",
                str(temp_root / evidence_rel),
            ],
            cwd=str(temp_root),
            env=env,
        )
        if completed.returncode != 0:
            return completed.returncode
        source = temp_root / evidence_rel
        target = ROOT / evidence_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return 0
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(temp_root)],
            cwd=str(ROOT),
            check=False,
        )
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
