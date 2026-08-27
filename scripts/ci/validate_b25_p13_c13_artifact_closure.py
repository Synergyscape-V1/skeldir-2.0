#!/usr/bin/env python3
"""Run inside Dockerfile.bayesian and prove its dependency closure."""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path


APP_ROOT = Path("/app")
MODULES = (
    "app.celery_app",
    "app.bayesian.inference_profile",
    "app.bayesian.runtime_policy",
    "app.bayesian.sampling_policy",
    "app.bayesian.diagnostics",
    "app.confidence_projection.policy",
    "app.inference_policy_registry",
    "app.trust.signing",
)
RESOURCES = (
    "/app/contracts/trust-api/confidence-metadata.schema.json",
    "/app/contracts/trust-api/hash-domain-manifest.v1.yaml",
    "/app/contracts/trust-api/temporal-policy.v1.yaml",
    "/app/contracts-internal/governance/b25_p13_c13_authority_topology.v1.json",
)


def _fail(reason: str, trace: dict[str, object]) -> int:
    print(f"B25_P13_C13_ARTIFACT_CLOSURE_FAIL:{reason}", file=sys.stderr)
    print("TRACE " + json.dumps(trace, sort_keys=True), file=sys.stderr)
    return 1


def main() -> int:
    trace: dict[str, object] = {"pid": os.getpid(), "modules": {}, "resources": {}}
    mountinfo = Path("/proc/self/mountinfo").read_text(
        encoding="utf-8", errors="replace"
    )
    forbidden_mounts = [
        line
        for line in mountinfo.splitlines()
        if any(
            f" {target} " in line
            for target in (
                "/app/backend",
                "/app/backend/app",
                "/app/contracts",
                "/app/contracts-internal",
            )
        )
    ]
    trace["governed_bind_mounts"] = forbidden_mounts
    if forbidden_mounts:
        return _fail("host_mount_shadows_governed_runtime", trace)
    # Import-only probe values satisfy configuration shape without contacting a
    # service. They are deliberately container-local and are recorded so this
    # trace cannot be mistaken for a live database/broker proof (C9/C11 own it).
    probe_environment = {
        "DATABASE_URL": "postgresql+asyncpg://app_worker:probe@127.0.0.1:5432/probe",
        "CELERY_BROKER_URL": "sqla+postgresql://app_worker:probe@127.0.0.1:5432/probe",
        "CELERY_RESULT_BACKEND": "db+postgresql://app_worker:probe@127.0.0.1:5432/probe",
        "AUTH_JWT_SECRET": "c13-artifact-import-probe",
        "AUTH_JWT_PUBLIC_KEY_RING": "c13-artifact-import-probe",
        "PLATFORM_TOKEN_ENCRYPTION_KEY": "c13-artifact-import-probe",
        "PLATFORM_TOKEN_KEY_ID": "c13-artifact-import-probe",
        "TESTING": "1",
    }
    for name, value in probe_environment.items():
        os.environ.setdefault(name, value)
    trace["configuration_probe_only"] = sorted(probe_environment)
    for resource in RESOURCES:
        path = Path(resource)
        trace["resources"][resource] = {
            "exists": path.is_file(),
            "bytes": path.stat().st_size if path.is_file() else None,
        }
        if not path.is_file():
            return _fail(f"resource_missing:{resource}", trace)
    for name in MODULES:
        try:
            module = importlib.import_module(name)
        except Exception as exc:
            trace["modules"][name] = {"error": f"{type(exc).__name__}:{exc}"}
            return _fail(f"module_import_failed:{name}", trace)
        module_path = str(Path(module.__file__).resolve())
        trace["modules"][name] = module_path
        if not module_path.startswith("/app/backend/app/"):
            return _fail(f"module_outside_image_authority:{name}", trace)
    from app.inference_policy_registry import CURRENT_POLICY_BUNDLE_HASH
    from app.bayesian.inference_profile import B24_INFERENCE_PROFILE

    trace["policy_bundle_hash"] = CURRENT_POLICY_BUNDLE_HASH
    trace["profile_bundle_hash"] = B24_INFERENCE_PROFILE.policy_bundle_hash()
    if trace["policy_bundle_hash"] != trace["profile_bundle_hash"]:
        return _fail("producer_registry_bundle_mismatch", trace)
    print("B25_P13_C13_ARTIFACT_CLOSURE_PASS")
    print("TRACE " + json.dumps(trace, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
