#!/usr/bin/env python3
"""B2.6-P2 Corrective X tested-artifact identity adjudicator.

Build-once law: the candidate tree produces ONE immutable image; every
  load-bearing proof runs against that exact digest; deployment selects
  that digest, never a rebuild. This script adjudicates PRESENTED facts
  only -- it invokes no container tooling itself (all image inspection
  happens in the already-authorized workflow surface, which passes facts
  here as arguments):

  --image-id        resolved image digest (sha256:64hex), REQUIRED
  --repo-digests    registry digest list as reported (optional)
  --tree-sha        candidate tree SHA (optional but expected)
  --commit-sha      candidate commit SHA (optional but expected)
  --base-image-ref  base image reference line (Dockerfile FROM)
  --probe-in-image  flag: the health probe ships inside the image
  --expect-digest   required digest: mismatch is post-proof
                    substitution and is RED, never assumed equivalent

Base-image pinning and probe shipping live in M1-owned files and
cannot be landed from this seat without waiving M1 scope: an unpinned
base or an unshipped probe is RECORDED here, never waived, and tracked
as an explicit residual in the remediation report.

Exit code is the gate: 0 on PASS, 1 plus a violation list on FAIL.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

_IMAGE_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Adjudicate B2.6-P2 Corrective X artifact identity."
    )
    parser.add_argument("--image-tag", default="")
    parser.add_argument("--image-id", default=None)
    parser.add_argument("--repo-digests", default="")
    parser.add_argument("--tree-sha", default="")
    parser.add_argument("--commit-sha", default="")
    parser.add_argument("--base-image-ref", default="")
    parser.add_argument(
        "--probe-in-image", action="store_true", default=False
    )
    parser.add_argument("--expect-digest", default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict[str, object] = {}
    try:
        if not args.image_id or not _IMAGE_ID_RE.match(args.image_id):
            violations.append("x_artifact_image_id_missing_or_malformed")
            checks["image_id"] = args.image_id or ""
        else:
            checks["image_tag"] = args.image_tag
            checks["image_id"] = args.image_id
            checks["repo_digests"] = args.repo_digests
            if args.expect_digest and args.image_id != args.expect_digest:
                violations.append(
                    "x_artifact_post_proof_substitution:"
                    f"expected={args.expect_digest[:19]}"
                    f" observed={args.image_id[:19]}"
                )
                checks["substitution"] = "RED_post_proof_image_replaced"
            else:
                checks["substitution"] = "none_or_matches"
        checks["tree_sha"] = args.tree_sha
        if not args.tree_sha:
            violations.append("x_artifact_tree_unresolvable")
        checks["commit_sha"] = args.commit_sha
        if not args.commit_sha:
            violations.append("x_artifact_commit_unresolvable")
        checks["base_image_ref"] = args.base_image_ref
        checks["base_digest_pinned"] = "@sha256:" in args.base_image_ref
        if "@sha256:" not in args.base_image_ref:
            checks["base_pin_residual"] = (
                "unpinned_base_requires_m1_coordination"
            )
        checks["probe_in_image"] = bool(args.probe_in_image)
        if not args.probe_in_image:
            checks["probe_ship_residual"] = (
                "probe_not_in_image_requires_m1_coordination"
            )
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
