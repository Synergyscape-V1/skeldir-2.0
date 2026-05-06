#!/usr/bin/env python3
"""Fail-closed B2.3-P5 branch-protection required-check verifier."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_FILE = "contracts-internal/governance/b23_p5_composite_proof.main.json"


def _resolve(repo_root: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (repo_root / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json_payload_not_object:{path}")
    return payload


def _fetch_branch_protection(repo: str, branch: str, token: str) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{repo}/branches/{branch}/protection"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "skeldir-b23-p5-branch-protection-verifier",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("branch_protection_payload_not_object")
    return payload


def _required_contexts(payload: dict[str, Any]) -> set[str]:
    required_status_checks = payload.get("required_status_checks") or {}
    contexts: set[str] = set()
    raw_contexts = required_status_checks.get("contexts") or []
    if isinstance(raw_contexts, list):
        contexts.update(str(context) for context in raw_contexts if context)
    raw_checks = required_status_checks.get("checks") or []
    if isinstance(raw_checks, list):
        for check in raw_checks:
            if isinstance(check, dict) and check.get("context"):
                contexts.add(str(check["context"]))
    return contexts


def _extract_job_block(workflow_text: str, job_id: str) -> str:
    pattern = re.compile(rf"^  {re.escape(job_id)}:\s*$", re.MULTILINE)
    match = pattern.search(workflow_text)
    if match is None:
        return ""
    next_job = re.search(r"^  [A-Za-z0-9_-]+:\s*$", workflow_text[match.end() :], re.MULTILINE)
    if next_job is None:
        return workflow_text[match.start() :]
    return workflow_text[match.start() : match.end() + next_job.start()]


def run_verification(
    *,
    repo_root: Path,
    manifest_file: Path,
    workflow_file: Path | None,
    protection_response_file: Path | None,
    repository: str | None,
    branch: str | None,
    token: str | None,
) -> tuple[int, list[str], dict[str, Any]]:
    violations: list[str] = []
    manifest = _read_json(manifest_file)
    composite = manifest.get("composite_check") or {}
    branch_cfg = manifest.get("branch_protection") or {}

    check_name = str(branch_cfg.get("required_check_name") or composite.get("check_name") or "")
    job_id = str(composite.get("job_id") or "")
    workflow_path = workflow_file or _resolve(repo_root, str(composite.get("workflow_file") or ""))
    repository = repository or os.environ.get("GITHUB_REPOSITORY") or str(branch_cfg.get("repository") or manifest.get("repository") or "")
    branch = branch or str(branch_cfg.get("branch") or composite.get("required_on_branch") or manifest.get("branch") or "main")

    if not check_name:
        violations.append("manifest_missing_required_check_name")
    if not job_id:
        violations.append("manifest_missing_composite_job_id")
    if not workflow_path.exists():
        violations.append(f"workflow_file_missing:{workflow_path}")
    else:
        workflow_text = workflow_path.read_text(encoding="utf-8")
        job_block = _extract_job_block(workflow_text, job_id)
        if not job_block:
            violations.append(f"workflow_missing_composite_job:{job_id}")
        elif f"name: {check_name}" not in job_block:
            violations.append("workflow_composite_job_name_mismatch")
        if "scripts/ci/enforce_b23_p5_composite_proof.py" not in workflow_text:
            violations.append("workflow_missing_composite_harness_command")

    if protection_response_file is not None:
        protection_payload = _read_json(protection_response_file)
        source = "fixture"
    else:
        if not repository:
            violations.append("repository_missing")
            protection_payload = {}
            source = "none"
        elif not token:
            violations.append("github_token_missing_fail_closed")
            protection_payload = {}
            source = "none"
        else:
            try:
                protection_payload = _fetch_branch_protection(repository, branch, token)
                source = "github_api"
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                violations.append(f"github_branch_protection_api_error:{exc.code}:{body[:400]}")
                protection_payload = {}
                source = "github_api_error"
            except Exception as exc:
                violations.append(f"github_branch_protection_api_error:{exc}")
                protection_payload = {}
                source = "github_api_error"

    contexts = _required_contexts(protection_payload)
    if check_name and check_name not in contexts:
        violations.append(f"required_check_missing_from_branch_protection:{check_name}")

    details = {
        "repository": repository,
        "branch": branch,
        "required_check_name": check_name,
        "workflow_job_id": job_id,
        "source": source,
        "observed_required_contexts": sorted(contexts),
    }
    return (1 if violations else 0), violations, details


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--manifest-file", default=MANIFEST_FILE)
    parser.add_argument("--workflow-file")
    parser.add_argument("--branch-protection-response-file")
    parser.add_argument("--repository")
    parser.add_argument("--branch")
    args = parser.parse_args(argv[1:])

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations, details = run_verification(
        repo_root=repo_root,
        manifest_file=_resolve(repo_root, args.manifest_file),
        workflow_file=_resolve(repo_root, args.workflow_file) if args.workflow_file else None,
        protection_response_file=_resolve(repo_root, args.branch_protection_response_file)
        if args.branch_protection_response_file
        else None,
        repository=args.repository,
        branch=args.branch,
        token=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"),
    )

    print("b23_p5_branch_protection_verifier")
    print(json.dumps({"status": "PASS" if status == 0 else "FAIL", **details}, sort_keys=True))
    if violations:
        for violation in violations:
            print(violation)
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
