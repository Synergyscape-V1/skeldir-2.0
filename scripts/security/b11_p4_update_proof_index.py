#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _replace_or_append(text: str, marker: str, body: str) -> str:
    section_header = f"\n## {marker}\n"
    if section_header in text:
        head = text.split(section_header, 1)[0].rstrip() + "\n"
        return f"{head}\n## {marker}\n{body.rstrip()}\n"
    return text.rstrip() + f"\n\n## {marker}\n{body.rstrip()}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Update B11-P4 proof index with immutable mapping/checksums")
    parser.add_argument("--out-dir", default="docs/forensics/evidence/b11_p4")
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    proof_index = out_dir / "PROOF_INDEX.md"
    if proof_index.exists():
        text = proof_index.read_text(encoding="utf-8")
    else:
        text = "# B1.1-P4 Proof Index\n"

    run_id = os.getenv("GITHUB_RUN_ID", "unknown")
    run_attempt = os.getenv("GITHUB_RUN_ATTEMPT", "unknown")
    repository = os.getenv("GITHUB_REPOSITORY", "unknown/unknown")
    server_url = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    run_url = f"{server_url}/{repository}/actions/runs/{run_id}" if run_id != "unknown" else "unknown"
    head_sha = os.getenv("GITHUB_SHA", "unknown")
    generated = datetime.now(timezone.utc).isoformat()

    if run_id != "unknown":
        immutable_mapping = "\n".join(
            [
                f"- run_id={run_id}",
                f"- run_attempt={run_attempt}",
                f"- run_url={run_url}",
                f"- head_sha={head_sha}",
                f"- generated_utc={generated}",
                "- static_artifact_name=b11-p4-static-runtime-evidence",
                "- audit_artifact_name=b11-p4-ci-audit-evidence",
            ]
        )
        text = _replace_or_append(text, "Immutable Run Mapping", immutable_mapping)

    tracked_files = [
        "db_dsn_callsite_scan.txt",
        "db_dsn_fallback_scan.txt",
        "provider_key_callsite_scan.txt",
        "workflow_plaintext_secret_scan.txt",
        "rotation_drill_db_credentials_ci.txt",
        "rotation_drill_provider_key_ci.txt",
        "ci_oidc_assume_role_log.txt",
        "ci_secret_retrieval_log.txt",
        "cloudtrail_ci_secret_reads.txt",
        "cloudtrail_stage_secret_reads.txt",
    ]
    checksum_lines: list[str] = []
    for rel in tracked_files:
        path = out_dir / rel
        if path.exists():
            checksum_lines.append(f"- {rel}: sha256={_sha256(path)} bytes={path.stat().st_size}")
        else:
            checksum_lines.append(f"- {rel}: missing")
    text = _replace_or_append(text, "Artifact Checksums", "\n".join(checksum_lines))

    proof_index.write_text(text, encoding="utf-8")
    print(proof_index.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
