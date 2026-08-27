#!/usr/bin/env python3
"""Fail-closed Directive XIII semantic, route, topology, and CI proof graph."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path("contracts-internal/governance/b25_p13_c13_authority_topology.v1.json")
WORKFLOW = Path(".github/workflows/b2_5-p13-e2e-trust-closure.yml")
SIGNING = Path("backend/app/trust/signing.py")
REGISTRY = Path("backend/app/inference_policy_registry.py")
TESTS = Path("backend/tests/trust/test_b25_p13_c13_signing_truth_boundary.py")
ARTIFACT_VALIDATOR = Path("scripts/ci/validate_b25_p13_c13_artifact_closure.py")
MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/"
    "202608271200_b25_p13_c13_signing_authority.py"
)

EXPECTED_TOPOLOGIES = {
    "backend/Dockerfile",
    "backend/Dockerfile.bayesian",
    "backend/mock_platform/Dockerfile",
    "docker-compose.e2e.yml",
    "docker-compose.local.yml",
    "docker-compose.component-dev.yml",
    "docker-compose.test.yml",
    "docker-compose.mock.yml",
    "docs/forensics/archive/docker_tools/legacy_microservices/Dockerfile.attribution",
    "docs/forensics/archive/docker_tools/legacy_microservices/Dockerfile.auth",
    "docs/forensics/archive/docker_tools/legacy_microservices/Dockerfile.ingestion",
    "docs/forensics/archive/docker_tools/legacy_microservices/Dockerfile.webhooks",
    ".github/workflows/b2_5-p13-e2e-trust-closure.yml",
    "Procfile",
    "netlify.toml",
    "Makefile",
    ".env.example",
}
EXPECTED_SIGN_ROUTES = {
    "backend/app/trust/signing.py",
    "backend/app/trust/export_artifact.py",
    "backend/app/trust/query_continuation.py",
}
LOAD_BEARING_JOBS = {
    "b25-p13-e2e-trust-closure-core",
    "b2-5-p13-c9-positive-confidence",
    "b2-5-p13-c10-artifact-topology",
    "b2-5-p13-c13-semantic-history",
}


class ValidationError(RuntimeError):
    pass


def _read(path: Path) -> str:
    full = ROOT / path
    if not full.is_file():
        raise ValidationError(f"missing_required_file:{path.as_posix()}")
    return full.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate_semantic_boundary(
    signing: str | None = None, registry: str | None = None
) -> None:
    signing = signing if signing is not None else _read(SIGNING)
    registry = registry if registry is not None else _read(REGISTRY)
    boundary = signing.index("validate_envelope_policy_authority(payload)")
    crypto = signing.index("key.private_key.sign(material)")
    _require(boundary < crypto, "semantic_boundary_not_before_private_key_sign")
    for token in (
        "resolve_policy_bundle",
        "resolve_policy_provenance",
        "historical_policy_bundle_not_issuable",
        "policy_bundle_runtime_mismatch",
        "validate_envelope_policy_authority",
    ):
        _require(token in registry, f"semantic_authority_missing:{token}")


def validate_route_inventory(manifest_text: str | None = None) -> None:
    manifest = json.loads(
        manifest_text if manifest_text is not None else _read(MANIFEST)
    )
    declared = {row["path"] for row in manifest["private_key_routes"]}
    actual: set[str] = set()
    for path in (ROOT / "backend/app").rglob("*.py"):
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "sign"
            for node in ast.walk(tree)
        ):
            actual.add(path.relative_to(ROOT).as_posix())
    _require(declared == EXPECTED_SIGN_ROUTES, "sign_route_manifest_drift")
    _require(
        actual == declared,
        f"unclassified_private_key_route:{sorted(actual ^ declared)}",
    )
    trust_routes = [
        r for r in manifest["private_key_routes"] if r["domain"] == "TrustEnvelope"
    ]
    _require(len(trust_routes) == 1, "trust_envelope_signer_not_unique")
    _require(
        trust_routes[0]["semantic_boundary"] == "validate_envelope_policy_authority",
        "trust_envelope_route_bypasses_semantic_boundary",
    )


def validate_topology_manifest(manifest_text: str | None = None) -> None:
    manifest = json.loads(
        manifest_text if manifest_text is not None else _read(MANIFEST)
    )
    rows = manifest["topologies"]
    declared = {row["path"] for row in rows}
    _require(
        declared == EXPECTED_TOPOLOGIES,
        f"topology_inventory_drift:{sorted(declared ^ EXPECTED_TOPOLOGIES)}",
    )
    _require(
        all((ROOT / path).is_file() for path in declared), "declared_topology_missing"
    )
    allowed = {
        "PRODUCTION_AUTHORITY",
        "PRODUCTION_ANALOGUE",
        "SUPPORTED_LOCAL_DEVELOPMENT",
        "TEST_ONLY",
        "LEGACY",
    }
    _require(
        all(row["classification"] in allowed for row in rows),
        "topology_classification_invalid",
    )
    local = next(row for row in rows if row["path"] == "docker-compose.local.yml")
    _require(
        local["classification"] == "SUPPORTED_LOCAL_DEVELOPMENT"
        and local["p13_equivalent"] is False,
        "local_compose_falsely_claims_p13_equivalence",
    )
    _require(
        manifest["p13_equivalence_authority"] == "CI_ONLY",
        "p13_equivalence_authority_drift",
    )


def validate_runtime_topology_sources(procfile_text: str | None = None) -> None:
    procfile = procfile_text if procfile_text is not None else _read(Path("Procfile"))
    lines = {
        line.split(":", 1)[0]: line for line in procfile.splitlines() if ":" in line
    }
    worker = lines.get("worker_bayesian", "")
    publisher = lines.get("worker_bayesian_publisher", "")
    beat = lines.get("beat", "")
    for line, token in (
        (worker, " DATABASE_URL=$WORKER_DATABASE_URL "),
        (worker, "--queues=bayesian"),
        (publisher, " DATABASE_URL=$PUBLISHER_DATABASE_URL "),
        (
            publisher,
            " B24_DISPATCH_PUBLISHER_DATABASE_URL=$PUBLISHER_DATABASE_URL ",
        ),
        (publisher, "--queues=bayesian_publisher"),
        (beat, "celery -A app.celery_app.celery_app beat"),
    ):
        _require(token in line, f"runtime_topology_authority_missing:{token}")


def validate_merge_graph(workflow_text: str | None = None) -> None:
    source = workflow_text if workflow_text is not None else _read(WORKFLOW)
    workflow = yaml.safe_load(source)
    jobs = workflow.get("jobs", {})
    gate = jobs.get("b25-p13-e2e-trust-closure")
    _require(isinstance(gate, dict), "required_aggregator_missing")
    needs = gate.get("needs", [])
    _require(set(needs) == LOAD_BEARING_JOBS, "required_aggregator_dependency_drift")
    _require(gate.get("if") == "always()", "required_aggregator_not_fail_closed")
    run = "\n".join(str(s.get("run", "")) for s in gate.get("steps", []))
    for job in LOAD_BEARING_JOBS:
        _require(job in run, f"aggregator_result_not_asserted:{job}")
    semantic = jobs.get("b2-5-p13-c13-semantic-history", {})
    semantic_run = "\n".join(str(s.get("run", "")) for s in semantic.get("steps", []))
    _require(
        "test_b25_p13_c13_signing_truth_boundary.py" in semantic_run,
        "physical_signer_test_not_merge_blocking",
    )
    artifact = jobs.get("b2-5-p13-c10-artifact-topology", {})
    artifact_run = "\n".join(str(s.get("run", "")) for s in artifact.get("steps", []))
    for token in (
        "validate_b25_p13_c13_artifact_closure.py",
        "docker image inspect",
        "mount-shadow",
    ):
        _require(token in artifact_run, f"artifact_closure_proof_missing:{token}")


def validate_historical_registry_migration() -> None:
    migration = _read(MIGRATION)
    for token in (
        'down_revision = "202608261200"',
        'POLICY_BUNDLE_HASH = "66cb748ab92eca922c27fca5f27e41a2d3282d7d511e7674524f018f9bc83a28"',
        '"trust_issuance_policy"',
        "INSERT INTO public.b24_inference_policy_registry",
        "ON CONFLICT (policy_bundle_hash) DO NOTHING",
    ):
        _require(token in migration, f"historical_registry_migration_missing:{token}")


def validate_all() -> None:
    for path in (
        MANIFEST,
        WORKFLOW,
        SIGNING,
        REGISTRY,
        TESTS,
        ARTIFACT_VALIDATOR,
        MIGRATION,
    ):
        _read(path)
    validate_semantic_boundary()
    validate_route_inventory()
    validate_topology_manifest()
    validate_runtime_topology_sources()
    validate_merge_graph()
    validate_historical_registry_migration()


def run_negative_controls() -> None:
    signing = _read(SIGNING)
    manifest = _read(MANIFEST)
    workflow = _read(WORKFLOW)
    controls = (
        (
            "signer_bypass",
            lambda: validate_semantic_boundary(
                signing.replace(
                    "validate_envelope_policy_authority(payload)", "None", 1
                ),
                None,
            ),
        ),
        (
            "alternate_sign_route",
            lambda: validate_route_inventory(
                manifest.replace(
                    '"private_key_routes": [',
                    '"private_key_routes": [{"path":"backend/app/trust/hostile.py","domain":"TrustEnvelope","classification":"PRODUCTION_AUTHORITY","semantic_boundary":"none"},',
                    1,
                )
            ),
        ),
        (
            "false_local_equivalence",
            lambda: validate_topology_manifest(
                manifest.replace(
                    '"classification":"SUPPORTED_LOCAL_DEVELOPMENT","p13_equivalent":false',
                    '"classification":"PRODUCTION_ANALOGUE","p13_equivalent":true',
                    1,
                )
            ),
        ),
        (
            "publisher_identity_collapsed",
            lambda: validate_runtime_topology_sources(
                _read(Path("Procfile")).replace(
                    "DATABASE_URL=$PUBLISHER_DATABASE_URL",
                    "DATABASE_URL=$WORKER_DATABASE_URL",
                    1,
                )
            ),
        ),
        (
            "semantic_job_detached",
            lambda: validate_merge_graph(
                workflow.replace("      - b2-5-p13-c13-semantic-history\n", "", 1)
            ),
        ),
        (
            "artifact_trace_detached",
            lambda: validate_merge_graph(
                workflow.replace(
                    "validate_b25_p13_c13_artifact_closure.py",
                    "detached_artifact_validator.py",
                )
            ),
        ),
    )
    fired = 0
    for name, runner in controls:
        try:
            runner()
        except (ValidationError, ValueError, json.JSONDecodeError):
            fired += 1
        else:
            raise ValidationError(f"negative_control_did_not_fire:{name}")
    print(f"c13_static_negative_controls_fired={fired}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    try:
        validate_all()
        if args.negative_control:
            run_negative_controls()
    except (ValidationError, yaml.YAMLError, json.JSONDecodeError) as exc:
        print(f"B25_P13_C13_CLOSURE_VALIDATION_FAIL: {exc}")
        return 1
    print("B25_P13_C13_CLOSURE_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
