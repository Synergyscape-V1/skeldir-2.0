#!/usr/bin/env python3
"""
Run a phase chain enforcing prerequisites from phase_manifest.yaml.
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
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "docs" / "phases" / "phase_manifest.yaml"
EVIDENCE_DIR = REPO_ROOT / "backend" / "validation" / "evidence" / "phases"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def _ci_run_url() -> str:
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server and repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return ""


class ChainError(RuntimeError):
    pass


def load_manifest() -> Dict[str, Any]:
    with MANIFEST_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def topological_order(target_phase: str, manifest: Dict[str, Any]) -> List[str]:
    phases = {p["id"]: p for p in manifest.get("phases", [])}
    if target_phase not in phases:
        raise ChainError(f"Phase {target_phase} not found.")
    graph = defaultdict(set)  # phase -> prerequisites
    indegree = defaultdict(int)
    for pid, phase in phases.items():
        prereqs = phase.get("prerequisites", [])
        graph[pid] = set(prereqs)
        indegree[pid] = len(prereqs)

    order: List[str] = []
    queue = deque([target_phase])
    visited: Set[str] = set()

    while queue:
        pid = queue.popleft()
        if pid in visited:
            continue
        # ensure prereqs added first
        unmet = [p for p in graph[pid] if p not in visited]
        if unmet:
            queue.appendleft(pid)
            for pre in unmet:
                if pre not in visited:
                    queue.appendleft(pre)
            continue
        order.append(pid)
        visited.add(pid)
    return order


def run_phase(phase_id: str) -> int:
    cmd = [sys.executable, str(REPO_ROOT / "scripts" / "phase_gates" / "run_phase.py"), phase_id]
    proc = subprocess.run(cmd, cwd=REPO_ROOT)
    return proc.returncode


def main() -> int:
    target = sys.argv[1].upper() if len(sys.argv) > 1 else "B0.4"
    manifest = load_manifest()
    chain = topological_order(target, manifest)
    summary_path = EVIDENCE_DIR / f"{target.lower()}_chain_summary.json"
    results: List[Dict[str, Any]] = []
    status = "success"
    for phase_id in chain:
        code = run_phase(phase_id)
        results.append({"phase": phase_id, "exit_code": code})
        if code != 0:
            status = "failure"
            break
    summary = {
        "target": target,
        "candidate_sha": (os.environ.get("GITHUB_SHA") or os.environ.get("CI_COMMIT_SHA") or ""),
        "ci_run_url": _ci_run_url(),
        "status": status,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "chain": results,
    }
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    return 0 if status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
