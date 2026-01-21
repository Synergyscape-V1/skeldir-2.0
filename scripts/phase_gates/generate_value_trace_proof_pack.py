#!/usr/bin/env python3
"""
Generate an authoritative EG-5 proof pack for VALUE_01..VALUE_05 inside CI.

This script is intended to run inside GitHub Actions and produces:
- backend/validation/evidence/proof_pack/value_trace_proof_pack.json
- docs/forensics/proof_pack/value_trace_proof_pack.md

It queries GitHub's API for the CURRENT run to bind:
- candidate_sha == GITHUB_SHA
- run_id == GITHUB_RUN_ID
- VALUE gate job URLs
- VALUE evidence artifact IDs (phase-VALUE_0X-evidence)

On success, prints:
  EG-5 PASS: proof pack matches GITHUB_SHA and GITHUB_RUN_ID
and exits 0. Otherwise exits 1.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


VALUE_GATES: List[str] = ["VALUE_01", "VALUE_02", "VALUE_03", "VALUE_04", "VALUE_05"]


@dataclass(frozen=True)
class GateRecord:
    gate_id: str
    job_url: str
    artifact_name: str
    artifact_id: int


def _required_env(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


def _api_get_json(url: str, *, token: str) -> Dict[str, Any]:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "skeldir-eg5-proof-pack")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read().decode("utf-8")
        return json.loads(data)


def _collect_run_artifacts(api_url: str, repo: str, run_id: str, token: str) -> Dict[str, int]:
    url = f"{api_url}/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100"
    payload = _api_get_json(url, token=token)
    artifacts = payload.get("artifacts", [])
    mapping: Dict[str, int] = {}
    for a in artifacts:
        name = a.get("name")
        aid = a.get("id")
        if isinstance(name, str) and isinstance(aid, int):
            mapping[name] = aid
    return mapping


def _collect_run_jobs(api_url: str, repo: str, run_id: str, token: str) -> Dict[str, str]:
    url = f"{api_url}/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100"
    payload = _api_get_json(url, token=token)
    jobs = payload.get("jobs", [])
    mapping: Dict[str, str] = {}
    for j in jobs:
        name = j.get("name")
        html_url = j.get("html_url")
        if isinstance(name, str) and isinstance(html_url, str):
            mapping[name] = html_url
    return mapping


def _render_md(
    *,
    candidate_sha: str,
    run_id: str,
    run_url: str,
    records: List[GateRecord],
) -> str:
    lines: List[str] = []
    lines.append("# Value Trace Proof Pack (CI-Generated, EG-5 Authoritative)")
    lines.append("")
    lines.append(f"- candidate_sha: `{candidate_sha}`")
    lines.append(f"- run_id: `{run_id}`")
    lines.append(f"- run_url: `{run_url}`")
    lines.append(f"- generated_at_utc: `{datetime.now(tz=timezone.utc).isoformat()}`")
    lines.append("")
    lines.append("## VALUE gate bindings (same run)")
    lines.append("")
    lines.append("| gate_id | job_url | artifact_name | artifact_id |")
    lines.append("|--------|---------|---------------|-------------|")
    for r in records:
        lines.append(f"| {r.gate_id} | `{r.job_url}` | `{r.artifact_name}` | `{r.artifact_id}` |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    try:
        candidate_sha = _required_env("GITHUB_SHA")
        run_id = _required_env("GITHUB_RUN_ID")
        event_name = os.environ.get("GITHUB_EVENT_NAME", "").strip()
        server_url = _required_env("GITHUB_SERVER_URL")
        repo = _required_env("GITHUB_REPOSITORY")
        api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com").strip() or "https://api.github.com"
        token = _required_env("GITHUB_TOKEN")

        run_url = f"{server_url}/{repo}/actions/runs/{run_id}"

        artifacts_by_name = _collect_run_artifacts(api_url, repo, run_id, token)
        jobs_by_name = _collect_run_jobs(api_url, repo, run_id, token)

        records: List[GateRecord] = []
        missing: List[str] = []

        for gate in VALUE_GATES:
            artifact_name = f"phase-{gate}-evidence"
            job_name = f"Phase Gates ({gate})"

            artifact_id = artifacts_by_name.get(artifact_name)
            job_url = jobs_by_name.get(job_name)

            if artifact_id is None:
                missing.append(f"missing artifact: {artifact_name}")
                continue
            if job_url is None:
                missing.append(f"missing job url: {job_name}")
                continue

            records.append(
                GateRecord(
                    gate_id=gate,
                    job_url=job_url,
                    artifact_name=artifact_name,
                    artifact_id=int(artifact_id),
                )
            )

        out_dir = Path("backend/validation/evidence/proof_pack")
        doc_dir = Path("docs/forensics/proof_pack")
        out_dir.mkdir(parents=True, exist_ok=True)
        doc_dir.mkdir(parents=True, exist_ok=True)

        json_path = out_dir / "value_trace_proof_pack.json"
        md_path = doc_dir / "value_trace_proof_pack.md"

        payload: dict[str, Any] = {
            "candidate_sha": candidate_sha,
            "run_id": run_id,
            "run_url": run_url,
            "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
            "value_gates": [
                {
                    "gate_id": r.gate_id,
                    "job_url": r.job_url,
                    "artifact_name": r.artifact_name,
                    "artifact_id": r.artifact_id,
                }
                for r in records
            ],
        }

        # EG-5 enforcement: strict on non-PR runs; PRs may omit VALUE gate jobs/artifacts.
        if missing or len(records) != 5:
            if event_name == "pull_request":
                payload["status"] = "SKIPPED"
                payload["missing"] = missing
                json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                md_path.write_text(
                    _render_md(
                        candidate_sha=candidate_sha,
                        run_id=run_id,
                        run_url=run_url,
                        records=records,
                    )
                    + "\n"
                    + "## EG-5 status\n\n"
                    + "- status: `SKIPPED`\n"
                    + "- reason: VALUE gate jobs/artifacts not present in this PR run\n"
                    + ("\n".join([f"- {m}" for m in missing]) + "\n" if missing else ""),
                    encoding="utf-8",
                )
                print("EG-5 SKIP: VALUE gate jobs/artifacts not present in this PR run")
                return 0
            raise RuntimeError("EG-5 FAIL: " + "; ".join(missing) if missing else f"EG-5 FAIL: expected 5 VALUE gate records, got {len(records)}")

        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        md_path.write_text(
            _render_md(
                candidate_sha=candidate_sha,
                run_id=run_id,
                run_url=run_url,
                records=records,
            ),
            encoding="utf-8",
        )

        # Final self-consistency checks (EG-5.2)
        parsed = json.loads(json_path.read_text(encoding="utf-8"))
        if parsed.get("candidate_sha") != candidate_sha:
            raise RuntimeError("EG-5 FAIL: candidate_sha mismatch in generated JSON")
        if str(parsed.get("run_id")) != str(run_id):
            raise RuntimeError("EG-5 FAIL: run_id mismatch in generated JSON")

        print("EG-5 PASS: proof pack matches GITHUB_SHA and GITHUB_RUN_ID")
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


