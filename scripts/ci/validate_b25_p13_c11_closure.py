#!/usr/bin/env python3
"""C11 structural/semantic closure validator with causal in-memory controls."""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _require_tokens(path: Path, tokens: tuple[str, ...]) -> None:
    source = path.read_text(encoding="utf-8")
    missing = [token for token in tokens if token not in source]
    if missing:
        raise RuntimeError(f"c11_required_tokens_missing:{path}:{missing}")


def validate() -> None:
    from app.bayesian.inference_profile import (
        B24_INFERENCE_PROFILE,
        assert_live_policy_registry_correspondence,
    )
    from app.inference_policy_registry import (
        CURRENT_POLICY_BUNDLE_HASH,
        current_manifest,
        semantic_digest,
    )

    assert_live_policy_registry_correspondence()
    if semantic_digest(current_manifest()) != CURRENT_POLICY_BUNDLE_HASH:
        raise RuntimeError("c11_bundle_derivation_not_canonical")
    if B24_INFERENCE_PROFILE.policy_bundle_hash() != CURRENT_POLICY_BUNDLE_HASH:
        raise RuntimeError("c11_producer_bundle_identity_drift")

    _require_tokens(
        ROOT
        / "alembic/versions/007_skeldir_foundation/202608251200_b25_p13_c11_semantic_authority.py",
        (
            "app_dispatch_publisher",
            "b24_inference_policy_registry",
            "b24_fit_policy_replan_lineage",
            "b24_available_policy_provenance_unresolvable",
            "b24_policy_replan_evidence_incomplete",
            "b24_policy_lineage_complete",
            "b24_policy_registry_immutable",
        ),
    )
    _require_tokens(
        ROOT / "backend/app/trust/builder.py",
        ("validate_policy_provenance", "PolicyRegistryError"),
    )
    _require_tokens(
        ROOT / "backend/app/bayesian/child_environment.py",
        (
            "B24_SAMPLER_SUPERVISOR_DEADLINE_S",
            "BAYESIAN_TASK_SOFT_TIME_LIMIT_S",
            "BAYESIAN_TASK_TIME_LIMIT_S",
        ),
    )
    dispatch_source = (ROOT / "backend/app/bayesian/dispatch_outbox.py").read_text(
        encoding="utf-8"
    )
    if "app.b24_initial_dispatch_publisher" in dispatch_source:
        raise RuntimeError("c11_self_assertable_publisher_guc_present")
    _require_tokens(
        ROOT / "backend/app/tasks/bayesian_publisher.py",
        (
            "create_dispatch_publisher_engine",
            "b24_assert_dispatch_publisher",
            "bayesian_publisher",
        ),
    )


def negative_controls() -> int:
    from app.inference_policy_registry import (
        CURRENT_POLICY_BUNDLE_HASH,
        current_manifest,
        semantic_digest,
    )

    fired = 0
    for component, field, hostile in (
        ("sampling_policy", "draws_per_chain", 999),
        ("diagnostic_policy", "ess_min_threshold", 399.0),
        ("runtime_policy", "celery_soft_time_limit_seconds", 271),
    ):
        manifest = deepcopy(current_manifest())
        manifest["components"][component]["semantics"][field] = hostile
        if semantic_digest(manifest) == CURRENT_POLICY_BUNDLE_HASH:
            raise RuntimeError(f"c11_negative_control_did_not_fire:{component}")
        fired += 1
    return fired


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    validate()
    fired = negative_controls() if args.negative_control else 0
    print("B25_P13_C11_CLOSURE_VALIDATION_PASS")
    print(f"c11_semantic_negative_controls_fired={fired}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
