#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FILES = [
    "p6_authoritative_main_run.txt",
    "rotation_drill_jwt_envelope.txt",
    "no_secrets_repo_scan.json",
    "workflow_plaintext_scan.txt",
    "db_no_plaintext_webhook_secrets.txt",
    "readiness_fail_closed_test.txt",
    "ci_oidc_assume_role_log.txt",
    "cloudtrail_ci_reads.txt",
    "cloudtrail_stage_run_causal.txt",
    "webhook_e2e_valid_invalid.txt",
    "log_redaction_integrity.txt",
]

DETERMINISTIC_FILES = [
    "rotation_drill_jwt_envelope.txt",
    "no_secrets_repo_scan.json",
    "workflow_plaintext_scan.txt",
    "db_no_plaintext_webhook_secrets.txt",
    "readiness_fail_closed_test.txt",
]

TELEMETRY_PATTERNS = {
    "ci_oidc_assume_role_log.txt": ["exit_code=0"],
    "cloudtrail_ci_reads.txt": ["identity_tether=skeldir-ci-deploy"],
    "cloudtrail_stage_run_causal.txt": [
        "identity_tether=skeldir-app-runtime-stage",
        "correlation_marker=P6_RUN_ID=",
        "run_causal_tether=present",
    ],
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(8192)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _run_url() -> str:
    run_id = os.getenv("GITHUB_RUN_ID", "unknown")
    server_url = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    repository = os.getenv("GITHUB_REPOSITORY", "unknown/unknown")
    return f"{server_url}/{repository}/actions/runs/{run_id}" if run_id != "unknown" else "unknown"


def _write_authoritative_run(path: Path) -> None:
    lines = [
        "b11_p6_authoritative_run",
        f"commit_sha={os.getenv('GITHUB_SHA', 'unknown')}",
        f"ref={os.getenv('GITHUB_REF', 'unknown')}",
        f"run_id={os.getenv('GITHUB_RUN_ID', 'unknown')}",
        f"run_attempt={os.getenv('GITHUB_RUN_ATTEMPT', 'unknown')}",
        f"run_url={_run_url()}",
        f"workflow={os.getenv('GITHUB_WORKFLOW', 'unknown')}",
        f"event_name={os.getenv('GITHUB_EVENT_NAME', 'unknown')}",
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize B11-P6 durable evidence artifacts")
    parser.add_argument("--evidence-dir", default="docs/forensics/evidence/b11_p6")
    parser.add_argument("--bundle-path", required=True)
    parser.add_argument("--bundle-uri", required=True)
    parser.add_argument("--bundle-version-id", default="unknown")
    parser.add_argument("--bundle-etag", default="unknown")
    args = parser.parse_args()

    evidence_dir = (REPO_ROOT / args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    run_file = evidence_dir / "p6_authoritative_main_run.txt"
    _write_authoritative_run(run_file)

    missing = [name for name in REQUIRED_FILES if not (evidence_dir / name).exists()]
    artifact_hashes: dict[str, str] = {}
    for name in REQUIRED_FILES:
        path = evidence_dir / name
        if path.exists():
            artifact_hashes[name] = _sha256(path)

    telemetry_validation: dict[str, bool] = {}
    for filename, patterns in TELEMETRY_PATTERNS.items():
        path = evidence_dir / filename
        if not path.exists():
            telemetry_validation[filename] = False
            continue
        text = path.read_text(encoding="utf-8")
        base_ok = all(pattern in text for pattern in patterns)
        if filename == "cloudtrail_stage_run_causal.txt":
            trigger_ok = any(
                marker in text
                for marker in (
                    "trigger_invocation_evidence=present",
                    "trigger_lambda_exit_code=0",
                    "trigger_stepfunctions_exit_code=0",
                    "trigger_get_secret_exit_code=0",
                )
            )
            telemetry_validation[filename] = base_ok and trigger_ok
        else:
            telemetry_validation[filename] = base_ok

    bundle_path = Path(args.bundle_path).resolve()
    if not bundle_path.exists():
        raise FileNotFoundError(f"bundle not found: {bundle_path}")
    bundle_sha = _sha256(bundle_path)

    canonical_subset = {
        "deterministic_artifact_hashes": {
            name: artifact_hashes.get(name, "missing") for name in DETERMINISTIC_FILES
        },
        "required_files": REQUIRED_FILES,
        "schema_version": "2026-02-24.b11_p6.v1",
    }
    manifest_digest = hashlib.sha256(_canonical_json(canonical_subset).encode("utf-8")).hexdigest()

    manifest = {
        "schema_version": "2026-02-24.b11_p6.v1",
        "commit_sha": os.getenv("GITHUB_SHA", "unknown"),
        "ref": os.getenv("GITHUB_REF", "unknown"),
        "workflow_name": os.getenv("GITHUB_WORKFLOW", "unknown"),
        "workflow_run_id": os.getenv("GITHUB_RUN_ID", "unknown"),
        "workflow_run_attempt": os.getenv("GITHUB_RUN_ATTEMPT", "unknown"),
        "workflow_run_url": _run_url(),
        "bundle": {
            "uri": args.bundle_uri,
            "version_id": args.bundle_version_id,
            "etag": args.bundle_etag,
            "sha256": bundle_sha,
            "filename": bundle_path.name,
        },
        "artifact_hashes": artifact_hashes,
        "missing_artifacts": missing,
        "telemetry_validation": telemetry_validation,
        "canonical_subset": canonical_subset,
        "manifest_digest": manifest_digest,
    }

    (evidence_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    (evidence_dir / "evidence_bundle_pointer.txt").write_text(
        "\n".join(
            [
                f"bundle_uri={args.bundle_uri}",
                f"bundle_version_id={args.bundle_version_id}",
                f"bundle_etag={args.bundle_etag}",
                f"bundle_sha256={bundle_sha}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    (evidence_dir / "sha256SUMS.txt").write_text(
        "\n".join(
            [
                f"{bundle_sha}  {bundle_path.name}",
                f"manifest_digest={manifest_digest}",
                f"manifest_sha256={_sha256(evidence_dir / 'MANIFEST.json')}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    proof_lines = [
        "# B11-P6 PROOF_INDEX",
        "",
        "## Authoritative Mapping",
        f"- commit_sha={manifest['commit_sha']}",
        f"- run_id={manifest['workflow_run_id']}",
        f"- run_url={manifest['workflow_run_url']}",
        f"- evidence_bundle_uri={args.bundle_uri}",
        f"- evidence_bundle_sha256={bundle_sha}",
        f"- manifest_digest={manifest_digest}",
        "",
        "## Exit Gate Mapping",
        f"- Gate 6.1 rotation_drill_jwt_envelope.txt sha256={artifact_hashes.get('rotation_drill_jwt_envelope.txt', 'missing')}",
        f"- Gate 6.2 no_secrets_repo_scan.json sha256={artifact_hashes.get('no_secrets_repo_scan.json', 'missing')}",
        f"- Gate 6.2 workflow_plaintext_scan.txt sha256={artifact_hashes.get('workflow_plaintext_scan.txt', 'missing')}",
        f"- Gate 6.2 db_no_plaintext_webhook_secrets.txt sha256={artifact_hashes.get('db_no_plaintext_webhook_secrets.txt', 'missing')}",
        f"- Gate 6.3 readiness_fail_closed_test.txt sha256={artifact_hashes.get('readiness_fail_closed_test.txt', 'missing')}",
        f"- Gate 6.4 ci_oidc_assume_role_log.txt sha256={artifact_hashes.get('ci_oidc_assume_role_log.txt', 'missing')}",
        f"- Gate 6.4 cloudtrail_ci_reads.txt sha256={artifact_hashes.get('cloudtrail_ci_reads.txt', 'missing')}",
        f"- Gate 6.4 cloudtrail_stage_run_causal.txt sha256={artifact_hashes.get('cloudtrail_stage_run_causal.txt', 'missing')}",
        f"- Gate 6.5 webhook_e2e_valid_invalid.txt sha256={artifact_hashes.get('webhook_e2e_valid_invalid.txt', 'missing')}",
        f"- Gate 6.6 log_redaction_integrity.txt sha256={artifact_hashes.get('log_redaction_integrity.txt', 'missing')}",
        "",
        "## Determinism Contract",
        f"- canonical_manifest_digest={manifest_digest}",
        "- canonical_subset=deterministic_artifact_hashes + required_files + schema_version",
        "- telemetry_files_validated_for_schema_and_markers_but_not_required_bitwise_identical=true",
    ]

    if missing:
        proof_lines.extend(["", "## Missing Artifacts"])
        for name in missing:
            proof_lines.append(f"- missing={name}")

    failed_telemetry = [name for name, ok in telemetry_validation.items() if not ok]
    if failed_telemetry:
        proof_lines.extend(["", "## Telemetry Validation Failures"])
        for name in failed_telemetry:
            proof_lines.append(f"- telemetry_validation_failed={name}")

    (evidence_dir / "PROOF_INDEX.md").write_text("\n".join(proof_lines).rstrip() + "\n", encoding="utf-8")

    if missing or failed_telemetry:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

