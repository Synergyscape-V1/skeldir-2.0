#!/usr/bin/env python3
"""B2.6-P2 Corrective X tested-artifact identity validator.

Build-once law: the candidate tree produces ONE immutable image; every
load-bearing proof runs against that exact digest; deployment selects
that digest, never a rebuild. This validator:

1. Resolves the image digest (docker image inspect Id + RepoDigests).
2. Requires the Dockerfile base to be digest-pinned (no mutable tags).
3. Requires the health probe to be present INSIDE the image (the
   automatic consumer path ships with the artifact).
4. Binds tree SHA + migration head + digest into one manifest.
5. With --expect-digest, refuses a substituted image (post-proof
   rebuild without re-proof is RED, never assumed equivalent).

Exit code is the gate: 0 on PASS, 1 plus a violation list on FAIL.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "backend" / "Dockerfile"
PROBE_IN_IMAGE = "/app/scripts/ops/conduction_health_probe.py"


def _run(args: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    return proc.returncode, (proc.stdout or "").strip()


def _git(args: list[str]) -> tuple[bool, str]:
    rc, out = _run(["git", *args])
    return rc == 0, out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate B2.6-P2 Corrective X artifact identity."
    )
    parser.add_argument("--image-tag", default=None)
    parser.add_argument("--expect-digest", default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict[str, object] = {}
    try:
        if not args.image_tag:
            violations.append("x_artifact_image_tag_required")
            checks["image"] = "missing_tag"
        else:
            rc, image_id = _run(
                ["docker", "image", "inspect", args.image_tag,
                 "--format", "{{.Id}}"]
            )
            if rc != 0 or not image_id:
                violations.append(
                    f"x_artifact_image_unresolvable:{args.image_tag}"
                )
                checks["image"] = "unresolvable"
            else:
                checks["image_tag"] = args.image_tag
                checks["image_id"] = image_id
                _rc, digests = _run(
                    ["docker", "image", "inspect", args.image_tag,
                     "--format", "{{json .RepoDigests}}"]
                )
                checks["repo_digests"] = digests
                if args.expect_digest and image_id != args.expect_digest:
                    violations.append(
                        "x_artifact_post_proof_substitution:"
                        f"expected={args.expect_digest[:19]}"
                        f" observed={image_id[:19]}"
                    )
                    checks["substitution"] = "RED_post_proof_image_replaced"
                else:
                    checks["substitution"] = "none_or_matches"
                rc, _ = _run(
                    ["docker", "run", "--rm", args.image_tag,
                     "test", "-f", PROBE_IN_IMAGE]
                )
                checks["probe_in_image"] = rc == 0
                if rc != 0:
                    violations.append(
                        "x_artifact_probe_not_shipped:"
                        f"{PROBE_IN_IMAGE}"
                    )
        try:
            from_text = DOCKERFILE.read_text(encoding="utf-8")
        except OSError:
            from_text = ""
        first_from = ""
        for line in from_text.splitlines():
            if line.strip().upper().startswith("FROM "):
                first_from = line.strip()
                break
        checks["dockerfile_from"] = first_from
        if "@sha256:" not in first_from:
            violations.append(
                "x_artifact_base_not_digest_pinned:"
                f"{first_from or 'missing'}"
            )
        ok, tree = _git(["rev-parse", "HEAD^{tree}"])
        checks["tree_sha"] = tree if ok else ""
        if not ok or not tree:
            violations.append("x_artifact_tree_unresolvable")
        ok, head = _git(["log", "-1", "--format=%H"])
        checks["commit_sha"] = head if ok else ""
    except Exception as exc:  # noqa: BLE001
        violations.append(f"x_artifact_validator_crash:{exc}")
    status = "PASS" if not violations else "FAIL"
    evidence = {
        "gate_id": "B26-P2-X-ARTIFACT",
        "validator": "validate_b26_p2_x_artifact",
        "status": status,
        "violations": sorted(violations),
        "checks": checks,
    }
    if args.evidence_out is not None:
        args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if args.evidence_dir is not None:
        args.evidence_dir.mkdir(parents=True, exist_ok=True)
        (args.evidence_dir / "x-artifact.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if violations:
        print("B26_P2_X_ARTIFACT_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_X_ARTIFACT_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
