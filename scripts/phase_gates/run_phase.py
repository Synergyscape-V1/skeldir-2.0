#!/usr/bin/env python3
"""
Run a phase gate defined in docs/phases/phase_manifest.yaml.
"""
from __future__ import annotations

# Bootstrap sys.path FIRST (environment-invariant)
import _bootstrap
_bootstrap.bootstrap()
del _bootstrap

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "docs" / "phases" / "phase_manifest.yaml"
EVIDENCE_DIR = REPO_ROOT / "backend" / "validation" / "evidence" / "phases"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def _ci_run_url() -> str:
    """
    Best-effort CI run URL anchoring.

    GitHub Actions provides:
    - GITHUB_SERVER_URL (e.g. https://github.com)
    - GITHUB_REPOSITORY (e.g. org/repo)
    - GITHUB_RUN_ID
    """
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server and repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return ""


class PhaseError(RuntimeError):
    pass


def load_manifest() -> Dict[str, Any]:
    with MANIFEST_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def get_phase(phase_id: str) -> Dict[str, Any]:
    data = load_manifest()
    for phase in data.get("phases", []):
        if phase.get("id") == phase_id:
            return phase
    raise PhaseError(f"Phase {phase_id} not found in manifest.")


def run_command(cmd: List[str]) -> int:
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    return result.returncode


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: run_phase.py <PHASE_ID>", file=sys.stderr)
        return 2
    phase_id = sys.argv[1].upper()
    summary_path = EVIDENCE_DIR / f"{phase_id.lower()}_summary.json"
    try:
        phase = get_phase(phase_id)
        command = phase["ci_gate"]["command"]
        if not isinstance(command, list) or not all(isinstance(x, str) for x in command):
            raise PhaseError(f"Phase {phase_id} command must be a list of strings.")
        cmd_list = list(command)
        code = run_command(cmd_list)
        artifacts = phase["ci_gate"].get("artifacts", [])
        missing: List[str] = []
        if code == 0:
            for rel_path in artifacts:
                artifact_path = REPO_ROOT / rel_path
                if not artifact_path.exists():
                    missing.append(rel_path)
            if missing:
                code = 1
        summary = {
            "phase": phase_id,
            "candidate_sha": (os.environ.get("GITHUB_SHA") or os.environ.get("CI_COMMIT_SHA") or ""),
            "ci_run_url": _ci_run_url(),
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "command": cmd_list,
            "status": "success" if code == 0 else "failure",
            "missing_artifacts": missing,
        }
        with summary_path.open("w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
        return code
    except Exception as exc:
        summary = {
            "phase": phase_id,
            "candidate_sha": (os.environ.get("GITHUB_SHA") or os.environ.get("CI_COMMIT_SHA") or ""),
            "ci_run_url": _ci_run_url(),
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "status": "failure",
            "error": str(exc),
        }
        with summary_path.open("w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
        print(f"Phase {phase_id} failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
