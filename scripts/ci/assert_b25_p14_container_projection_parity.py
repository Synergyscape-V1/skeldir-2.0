#!/usr/bin/env python3
"""B2.5-P14 Gate 4: declared policy == container-resolved policy.

The projection registry is a *file*, and the production image copies it in with
``COPY contracts/trust-api``. That makes two failure modes possible that no
host-run test can see:

  * the image stops shipping the registry (a Dockerfile edit narrows the COPY,
    or the loader's path arithmetic no longer resolves under ``/app``), so the
    contract floor fails closed inside the container while every host gate stays
    green; or
  * the image ships a *different* registry than the tree the proofs ran against,
    so the container's downstream consumers are governed by bytes nobody
    adjudicated.

This script decides both by running the real loader inside the real image and
requiring the four content-addressed profile hashes to equal the host's. It is
the "AUTHORIZED CONFIG = CONTAINER-RESOLVED CONFIG" leg of Gate 4 for the P14
surface. Physical execution and persisted provenance are covered by the C19
topology proof, which the P14 profiles do not change.

Usage::

    python scripts/ci/assert_b25_p14_container_projection_parity.py --image <tag>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

# Run the real loader, not a re-implementation of it. Anything that recomputes
# the hash here would be proving the container agrees with this script rather
# than with the contract.
_PROBE = (
    "import json;"
    "from app.trust.projection_profiles import projection_registry_identity;"
    "print(json.dumps(projection_registry_identity(), sort_keys=True))"
)


def _host_identity() -> dict:
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    sys.path.insert(0, str(REPO_ROOT))
    from app.trust.projection_profiles import (  # noqa: PLC0415
        projection_registry_identity,
    )

    return projection_registry_identity()


def _container_identity(image: str, runtime: str) -> dict:
    result = subprocess.run(
        [runtime, "run", "--rm", "--entrypoint", "python", image, "-c", _PROBE],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise SystemExit(
            "[b25-p14] the production image could not resolve the projection "
            f"registry (exit {result.returncode}):\n{result.stderr.strip()}"
        )
    payload = result.stdout.strip().splitlines()[-1]
    return json.loads(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--runtime", default="docker")
    parser.add_argument("--evidence-out", default="")
    args = parser.parse_args()

    host = _host_identity()
    container = _container_identity(args.image, args.runtime)

    mismatches: list[str] = []
    if host["registry_version"] != container["registry_version"]:
        mismatches.append(
            f"registry_version host={host['registry_version']} "
            f"container={container['registry_version']}"
        )
    host_profiles = host["profiles"]
    container_profiles = container["profiles"]
    for profile_id in sorted(set(host_profiles) | set(container_profiles)):
        if profile_id not in container_profiles:
            mismatches.append(f"{profile_id}: absent from the container")
            continue
        if profile_id not in host_profiles:
            mismatches.append(f"{profile_id}: present only in the container")
            continue
        if host_profiles[profile_id] != container_profiles[profile_id]:
            mismatches.append(
                f"{profile_id}: host={host_profiles[profile_id]} "
                f"container={container_profiles[profile_id]}"
            )

    for profile_id, row in sorted(container_profiles.items()):
        print(f"[b25-p14] container profile={profile_id} hash={row['profile_hash']}")

    if args.evidence_out:
        out = Path(args.evidence_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "image": args.image,
                    "host_registry_identity": host,
                    "container_registry_identity": container,
                    "mismatches": mismatches,
                    "verdict": "PASS" if not mismatches else "FAIL",
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        print(f"[b25-p14] wrote evidence: {out}")

    if mismatches:
        print("[b25-p14] container projection parity FAILED")
        for row in mismatches:
            print(f"  - {row}")
        return 1
    print("[b25-p14] container projection parity PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
