#!/usr/bin/env python3
"""
Validate phase_manifest.yaml for structural and referential integrity.

B2.5-P13 Corrective XV. This validator advertised "referential integrity" while
checking only that artifact strings were non-empty, so it printed
``PHASE MANIFEST VALID`` for a manifest naming files that were not in the
repository. An independent audit found nine such references and recorded the
combination -- a manifest asserting required outputs that do not exist, and a
validator that approves it -- as decisive.

The references are now actually resolved. Note the distinction that the previous
framing missed: ``ci_gate.artifacts`` are *outputs a gate produces*, and
``run_phase.py`` already verifies them after running the gate, so requiring them
in a clean checkout would be wrong. What must hold statically is:

* every gate ``command`` names a script that exists -- a manifest pointing at a
  deleted runner is a gate that cannot run;
* every artifact path is repo-relative and normalized, so no declaration can
  escape the repository or address a file by two different names;
* every artifact that git tracks is present on disk -- a tracked-but-deleted
  artifact is a genuinely broken reference;
* no two phases silently claim the same artifact path.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Set

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "docs" / "phases" / "phase_manifest.yaml"


class ManifestError(RuntimeError):
    pass


def load_manifest() -> Dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise ManifestError(f"Manifest file not found: {MANIFEST_PATH}")
    with MANIFEST_PATH.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict) or "phases" not in data:
        raise ManifestError("Manifest must contain a top-level 'phases' list.")
    if not isinstance(data["phases"], list):
        raise ManifestError("'phases' must be a list.")
    return data


def validate_manifest(data: Dict[str, Any]) -> None:
    phases = data["phases"]
    ids: Set[str] = set()
    for phase in phases:
        if "id" not in phase:
            raise ManifestError("All phases must have an 'id'.")
        pid = phase["id"]
        if pid in ids:
            raise ManifestError(f"Duplicate phase id: {pid}")
        ids.add(pid)
        if not phase.get("intent"):
            raise ManifestError(f"Phase {pid} missing intent.")
        if "ci_gate" not in phase or "command" not in phase["ci_gate"]:
            raise ManifestError(f"Phase {pid} missing ci_gate.command.")
        cmd = phase["ci_gate"]["command"]
        if not isinstance(cmd, list) or not all(isinstance(x, str) for x in cmd):
            raise ManifestError(f"Phase {pid} ci_gate.command must be a list of strings.")
        artifacts = phase["ci_gate"].get("artifacts", [])
        if not isinstance(artifacts, list) or not artifacts or not all(isinstance(a, str) for a in artifacts):
            raise ManifestError(f"Phase {pid} ci_gate.artifacts must be a non-empty list of strings.")
        if not phase.get("exit_gates"):
            raise ManifestError(f"Phase {pid} must declare exit_gates.")

    for phase in phases:
        pid = phase["id"]
        prereqs: List[str] = phase.get("prerequisites", [])
        for prereq in prereqs:
            if prereq not in ids:
                raise ManifestError(f"Phase {pid} references missing prerequisite {prereq}")


def _tracked_paths() -> Set[str]:
    """Paths git currently tracks, as repo-relative POSIX strings."""

    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ManifestError("git ls-files failed; cannot resolve manifest references")
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _command_script(command: List[str]) -> str | None:
    """Return the repo-relative script a gate command executes, if it names one."""

    for token in command:
        if token.endswith(".py") or token.endswith(".sh"):
            return token
    return None


def validate_referential_integrity(data: Dict[str, Any]) -> None:
    """Resolve every path the manifest names. This is the part that was missing."""

    tracked = _tracked_paths()
    claimed_by: Dict[str, str] = {}

    for phase in data["phases"]:
        pid = phase["id"]
        command = phase["ci_gate"]["command"]

        script = _command_script(command)
        if script is not None:
            if not (REPO_ROOT / script).exists():
                raise ManifestError(
                    f"Phase {pid} ci_gate.command references missing script: {script}"
                )

        for artifact in phase["ci_gate"].get("artifacts", []):
            posix = PurePosixPath(artifact)
            if posix.is_absolute() or ".." in posix.parts:
                raise ManifestError(
                    f"Phase {pid} artifact must be a normalized repo-relative "
                    f"path: {artifact}"
                )
            if str(posix) != artifact:
                raise ManifestError(
                    f"Phase {pid} artifact path is not normalized: {artifact}"
                )
            owner = claimed_by.setdefault(artifact, pid)
            if owner != pid:
                raise ManifestError(
                    f"Artifact {artifact} is claimed by both {owner} and {pid}"
                )
            # A gate output need not exist before the gate runs -- run_phase.py
            # checks that after execution. But an artifact git tracks and the
            # working tree lacks is a broken reference, which is exactly the
            # class this validator previously approved.
            if artifact in tracked and not (REPO_ROOT / artifact).exists():
                raise ManifestError(
                    f"Phase {pid} declares tracked artifact that is absent from "
                    f"the working tree: {artifact}"
                )


def main() -> int:
    try:
        data = load_manifest()
        validate_manifest(data)
        validate_referential_integrity(data)
        print("PHASE MANIFEST VALID")
        return 0
    except ManifestError as exc:
        print(f"Manifest validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
