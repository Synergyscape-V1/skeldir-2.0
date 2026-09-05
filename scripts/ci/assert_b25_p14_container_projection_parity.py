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
    "from app.explanation.templates import "
    "EXPLANATION_TEMPLATE_REGISTRY_VERSION, EXPLANATION_TEMPLATES, "
    "explanation_template_registry_hash;"
    "print(json.dumps({"
    "  'projection': projection_registry_identity(),"
    "  'narrative_frames': {"
    "     'registry_version': EXPLANATION_TEMPLATE_REGISTRY_VERSION,"
    "     'registry_hash': explanation_template_registry_hash(),"
    "     'frame_count': len(EXPLANATION_TEMPLATES),"
    "  },"
    "}, sort_keys=True))"
)


def _host_identity() -> dict:
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    sys.path.insert(0, str(REPO_ROOT))
    from app.explanation.templates import (  # noqa: PLC0415
        EXPLANATION_TEMPLATES,
        EXPLANATION_TEMPLATE_REGISTRY_VERSION,
        explanation_template_registry_hash,
    )
    from app.trust.projection_profiles import (  # noqa: PLC0415
        projection_registry_identity,
    )

    return {
        "projection": projection_registry_identity(),
        "narrative_frames": {
            "registry_version": EXPLANATION_TEMPLATE_REGISTRY_VERSION,
            "registry_hash": explanation_template_registry_hash(),
            "frame_count": len(EXPLANATION_TEMPLATES),
        },
    }


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


# Gate 7 asks for behaviour, not only bytes: the container must *refuse* what the
# host refuses. This probe composes an explanation from a shipped contract
# example inside the image, requires an unregistered causal narrative to be
# refused, and requires B2.8 to invoke the solver zero times without an explicit
# request. It runs the real boundaries, so a stale application layer that ships
# the right contract with the wrong code is caught here rather than in
# production.
_BEHAVIOUR_PROBE = r"""
import copy, json, pathlib
from app.explanation.contract import ExplanationRequest
from app.explanation.conservation import ExplanationConservationError
from app.explanation.service import compose_explanation
from app.simulation.service import simulate_from_trust
from app.simulation.solver import solver_invocations, reset_solver_invocations
from app.trust.projection_profiles import DEFAULT_LLM_PROFILE_ID
from app.trust.refusal import tagged_sha256

TENANT = "11111111-2222-3333-4444-555555555555"
path = pathlib.Path(
    "/app/contracts/trust-api/examples/"
    "attribution_result_valid_with_model_assumption_and_causal_status.json"
)
envelope = json.loads(path.read_text(encoding="utf-8"))
envelope["tenant_id_hash"] = tagged_sha256({"tenant_id": TENANT})
request = ExplanationRequest(
    tenant_id=TENANT,
    envelope_id=envelope["envelope_id"],
    subject_type=envelope["subject_type"],
    subject_ref_hash=envelope["subject_ref_hash"],
    profile_id=DEFAULT_LLM_PROFILE_ID,
    requested_by="agent:p14-container-probe",
)
result = {}
lawful = compose_explanation(envelope, request=request)
result["lawful_explanation_claims"] = len(lawful.claims)
result["narrative_is_derived"] = lawful.narrative == " ".join(
    claim.rendered for claim in lawful.claims
)
try:
    compose_explanation(
        envelope,
        request=request,
        narrative_override="The email channel produced this additional revenue.",
    )
    result["causal_prose_refused"] = False
    result["causal_prose_reason"] = "accepted"
except ExplanationConservationError as exc:
    result["causal_prose_refused"] = True
    result["causal_prose_reason"] = str(exc)
reset_solver_invocations()
refusal = simulate_from_trust(envelope, request=None)
result["b28_no_request_reason"] = getattr(refusal, "reason_code", None)
result["b28_solver_invocations"] = solver_invocations()
print(json.dumps(result, sort_keys=True))
"""


def _container_behaviour(image: str, runtime: str) -> dict:
    completed = subprocess.run(
        [
            runtime,
            "run",
            "--rm",
            "--entrypoint",
            "python",
            image,
            "-c",
            _BEHAVIOUR_PROBE,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if completed.returncode != 0:
        raise SystemExit(
            "[b25-p14] the production image could not run the conservation probe "
            f"(exit {completed.returncode}): {completed.stderr.strip()}"
        )
    return json.loads(completed.stdout.strip().splitlines()[-1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--runtime", default="docker")
    parser.add_argument("--evidence-out", default="")
    args = parser.parse_args()

    host = _host_identity()
    container = _container_identity(args.image, args.runtime)
    behaviour = _container_behaviour(args.image, args.runtime)

    mismatches: list[str] = []
    host_projection = host["projection"]
    container_projection = container["projection"]
    if host_projection["registry_version"] != container_projection["registry_version"]:
        mismatches.append(
            f"registry_version host={host_projection['registry_version']} "
            f"container={container_projection['registry_version']}"
        )
    # The B2.7 frame corpus is code, not a contract file, so it reaches the
    # image through a different Docker layer than the projection registry. A
    # stale or partial application layer would leave the container composing
    # explanations under a corpus nobody adjudicated, which is the same Gate 4
    # failure mode one artifact class over.
    if host["narrative_frames"] != container["narrative_frames"]:
        mismatches.append(
            f"narrative_frames host={host['narrative_frames']} "
            f"container={container['narrative_frames']}"
        )
    if not behaviour.get("causal_prose_refused"):
        mismatches.append(
            "the container accepted an unregistered causal narrative: "
            f"{behaviour.get('causal_prose_reason')}"
        )
    if "narrative_not_derived_from_claims" not in str(
        behaviour.get("causal_prose_reason", "")
    ):
        mismatches.append(
            "the container refused for an unexpected cause: "
            f"{behaviour.get('causal_prose_reason')}"
        )
    if not behaviour.get("narrative_is_derived"):
        mismatches.append("the container composed a non-derived narrative")
    if behaviour.get("b28_no_request_reason") != "simulation_no_explicit_request":
        mismatches.append(
            "the container did not refuse an unrequested simulation: "
            f"{behaviour.get('b28_no_request_reason')}"
        )
    if behaviour.get("b28_solver_invocations") != 0:
        mismatches.append(
            "the container invoked the solver without a request: "
            f"{behaviour.get('b28_solver_invocations')}"
        )
    host_profiles = host_projection["profiles"]
    container_profiles = container_projection["profiles"]
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
    print(
        "[b25-p14] container narrative_frames hash="
        f"{container['narrative_frames']['registry_hash']} "
        f"count={container['narrative_frames']['frame_count']}"
    )
    print(
        "[b25-p14] container conservation probe: causal_prose_refused="
        f"{behaviour.get('causal_prose_refused')} "
        f"b28_solver_invocations={behaviour.get('b28_solver_invocations')}"
    )

    if args.evidence_out:
        out = Path(args.evidence_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "image": args.image,
                    "host_registry_identity": host,
                    "container_registry_identity": container,
                    "container_conservation_probe": behaviour,
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
