#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
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
    "webhook_e2e_valid_invalid.txt",
    "log_redaction_integrity.txt",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(8192)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


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
    parser = argparse.ArgumentParser(description="Generate B11-P6 immutable proof index")
    parser.add_argument("--evidence-dir", default="docs/forensics/evidence/b11_p6")
    args = parser.parse_args()

    evidence_dir = (REPO_ROOT / args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    run_file = evidence_dir / "p6_authoritative_main_run.txt"
    _write_authoritative_run(run_file)

    missing = [name for name in REQUIRED_FILES if not (evidence_dir / name).exists()]
    file_hashes: dict[str, str] = {}
    for name in REQUIRED_FILES:
        path = evidence_dir / name
        if path.exists():
            file_hashes[name] = _sha256(path)

    status = "PASS" if not missing else "FAIL"
    lines = [
        "# B11-P6 PROOF_INDEX",
        "",
        "## Authoritative Mapping",
        f"- commit_sha={os.getenv('GITHUB_SHA', 'unknown')}",
        f"- ref={os.getenv('GITHUB_REF', 'unknown')}",
        f"- run_id={os.getenv('GITHUB_RUN_ID', 'unknown')}",
        f"- run_url={_run_url()}",
        f"- status={status}",
        "",
        "## Stage Trigger Contract",
        "- trigger=deploy_stage_revision_then_hit_GET_/health/ready",
        "- expected_effect=runtime_role_reads_/skeldir/stage/secret/*_and_/skeldir/stage/config/*",
        "- tether_proof=cloudtrail_stage_identity_in_cloudtrail_ci_reads.txt",
        "",
        "## Gate 6.1 Rotation Drill (JWT + envelope)",
        f"- artifact=rotation_drill_jwt_envelope.txt sha256={file_hashes.get('rotation_drill_jwt_envelope.txt', 'missing')}",
        "",
        "## Gate 6.2 No Secrets Anywhere",
        f"- artifact=no_secrets_repo_scan.json sha256={file_hashes.get('no_secrets_repo_scan.json', 'missing')}",
        f"- artifact=workflow_plaintext_scan.txt sha256={file_hashes.get('workflow_plaintext_scan.txt', 'missing')}",
        f"- artifact=db_no_plaintext_webhook_secrets.txt sha256={file_hashes.get('db_no_plaintext_webhook_secrets.txt', 'missing')}",
        "",
        "## Gate 6.3 Readiness Correctness",
        f"- artifact=readiness_fail_closed_test.txt sha256={file_hashes.get('readiness_fail_closed_test.txt', 'missing')}",
        "",
        "## Gate 6.4 CI Audited Retrieval",
        f"- artifact=ci_oidc_assume_role_log.txt sha256={file_hashes.get('ci_oidc_assume_role_log.txt', 'missing')}",
        f"- artifact=cloudtrail_ci_reads.txt sha256={file_hashes.get('cloudtrail_ci_reads.txt', 'missing')}",
        "",
        "## Gate 6.5 Webhook E2E + No Plaintext At Rest",
        f"- artifact=webhook_e2e_valid_invalid.txt sha256={file_hashes.get('webhook_e2e_valid_invalid.txt', 'missing')}",
        f"- artifact=db_no_plaintext_webhook_secrets.txt sha256={file_hashes.get('db_no_plaintext_webhook_secrets.txt', 'missing')}",
        "",
        "## Gate 6.6 Redaction Integrity",
        f"- artifact=log_redaction_integrity.txt sha256={file_hashes.get('log_redaction_integrity.txt', 'missing')}",
        "",
        "## Gate 6.7 Evidence Pack + Index",
        f"- artifact=p6_authoritative_main_run.txt sha256={file_hashes.get('p6_authoritative_main_run.txt', 'missing')}",
    ]
    if missing:
        lines.extend(["", "## Missing Artifacts"])
        for name in missing:
            lines.append(f"- missing={name}")

    (evidence_dir / "PROOF_INDEX.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print((evidence_dir / "PROOF_INDEX.md").as_posix())
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
