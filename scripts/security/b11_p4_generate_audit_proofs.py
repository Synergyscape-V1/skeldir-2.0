#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _run(cmd: list[str]) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        return 127, "", f"{exc.__class__.__name__}: {exc}"
    return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()


def _aws_bin() -> str:
    explicit = os.getenv("AWS_CLI_BIN")
    if explicit:
        return explicit
    return "aws.cmd" if os.name == "nt" else "aws"


def _write(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _render_run_mapping(now: str) -> list[str]:
    run_id = os.getenv("GITHUB_RUN_ID", "unknown")
    run_attempt = os.getenv("GITHUB_RUN_ATTEMPT", "unknown")
    server_url = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    repository = os.getenv("GITHUB_REPOSITORY", "unknown/unknown")
    event_name = os.getenv("GITHUB_EVENT_NAME", "unknown")
    sha = os.getenv("GITHUB_SHA", "unknown")
    workflow = os.getenv("GITHUB_WORKFLOW", "unknown")
    run_url = f"{server_url}/{repository}/actions/runs/{run_id}" if run_id != "unknown" else "unknown"
    return [
        "## CI Run Mapping",
        f"- run_id={run_id}",
        f"- run_attempt={run_attempt}",
        f"- run_url={run_url}",
        f"- workflow={workflow}",
        f"- event={event_name}",
        f"- head_sha={sha}",
        f"- generated_utc={now}",
    ]


def _update_proof_index(out_dir: Path, now: str) -> None:
    proof_index = out_dir / "PROOF_INDEX.md"
    if proof_index.exists():
        text = proof_index.read_text(encoding="utf-8")
    else:
        text = "# B1.1-P4 Proof Index\n"
    marker = "\n## CI Run Mapping"
    if marker in text:
        text = text.split(marker, 1)[0].rstrip() + "\n"
    mapping = "\n".join(_render_run_mapping(now)) + "\n"
    proof_index.write_text(text.rstrip() + "\n\n" + mapping, encoding="utf-8")


def _lookup_cloudtrail_get_secret_events(aws: str, region: str, start_time: str, max_pages: int) -> tuple[int, list[dict], str]:
    events: list[dict] = []
    next_token: str | None = None
    for _ in range(max_pages):
        cmd = [
            aws,
            "cloudtrail",
            "lookup-events",
            "--lookup-attributes",
            "AttributeKey=EventName,AttributeValue=GetSecretValue",
            "--start-time",
            start_time,
            "--max-results",
            "50",
            "--region",
            region,
            "--output",
            "json",
        ]
        if next_token:
            cmd.extend(["--next-token", next_token])
        code, out, err = _run(cmd)
        if code != 0:
            return code, events, err
        payload = json.loads(out or "{}")
        events.extend(payload.get("Events", []))
        next_token = payload.get("NextToken")
        if not next_token:
            break
    return 0, events, ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate B11-P4 CI/runtime audit evidence")
    parser.add_argument("--out-dir", default="docs/forensics/evidence/b11_p4")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--env", default=os.getenv("B11_P4_ENV", "ci"))
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-2"))
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    aws = _aws_bin()
    now = datetime.now(timezone.utc).isoformat()
    lookback_hours = int(os.getenv("B11_P4_CLOUDTRAIL_LOOKBACK_HOURS", "168"))
    max_pages = int(os.getenv("B11_P4_CLOUDTRAIL_MAX_PAGES", "20"))
    start_time = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    failures: list[str] = []

    caller_cmd = [aws, "sts", "get-caller-identity", "--output", "json", "--region", args.region]
    caller_code, caller_out, caller_err = _run(caller_cmd)
    caller_lines = [
        f"timestamp_utc={now}",
        f"region={args.region}",
        f"env={args.env}",
        f"cmd={' '.join(caller_cmd)}",
        f"exit_code={caller_code}",
        "stdout=" + (caller_out or "<empty>"),
        "stderr=" + (caller_err or "<empty>"),
    ]
    _write(out_dir / "ci_oidc_assume_role_log.txt", caller_lines)
    if caller_code != 0:
        failures.append("sts_get_caller_identity_failed")

    secret_reads = [
        f"/skeldir/{args.env}/secret/database/runtime-url",
        f"/skeldir/{args.env}/secret/database/migration-url",
        f"/skeldir/{args.env}/secret/llm/provider-api-key",
    ]
    retrieval_lines = [f"timestamp_utc={now}", f"region={args.region}", f"env={args.env}"]
    for secret_id in secret_reads:
        cmd = [
            aws,
            "secretsmanager",
            "get-secret-value",
            "--secret-id",
            secret_id,
            "--query",
            "SecretString",
            "--output",
            "text",
            "--region",
            args.region,
        ]
        code, out, err = _run(cmd)
        retrieval_lines.append(f"[get-secret-value] secret_id={secret_id}")
        retrieval_lines.append(f"exit_code={code}")
        retrieval_lines.append("stdout=<redacted>" if out else "stdout=<empty>")
        retrieval_lines.append("stderr=" + (err or "<empty>"))
        if code != 0:
            failures.append(f"secret_read_failed:{secret_id}")
    _write(out_dir / "ci_secret_retrieval_log.txt", retrieval_lines)

    ci_code, events, ci_err = _lookup_cloudtrail_get_secret_events(
        aws=aws,
        region=args.region,
        start_time=start_time,
        max_pages=max_pages,
    )
    has_ci_tether = False
    has_stage_tether = False
    for event in events:
        event_raw = event.get("CloudTrailEvent", "")
        if "skeldir-ci-deploy" in event_raw:
            has_ci_tether = True
        if "skeldir-app-runtime-stage" in event_raw:
            has_stage_tether = True
        if has_ci_tether and has_stage_tether:
            break

    ci_lines = [
        f"timestamp_utc={now}",
        "cmd=aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=GetSecretValue",
        f"start_time_utc={start_time}",
        f"pages_requested={max_pages}",
        f"exit_code={ci_code}",
        "stderr=" + (ci_err or "<empty>"),
        f"events_scanned={len(events)}",
    ]
    if has_ci_tether:
        ci_lines.append("identity_tether=skeldir-ci-deploy")
    else:
        ci_lines.append("identity_tether=missing")
    _write(out_dir / "cloudtrail_ci_secret_reads.txt", ci_lines)
    if ci_code != 0 or not has_ci_tether:
        failures.append("cloudtrail_ci_lookup_failed")

    stage_lines = [
        f"timestamp_utc={now}",
        "cmd=aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=GetSecretValue",
        f"start_time_utc={start_time}",
        f"pages_requested={max_pages}",
        f"exit_code={ci_code}",
        f"events_scanned={len(events)}",
        "required_role=skeldir-app-runtime-stage",
        "required_event=secretsmanager:GetSecretValue",
        "required_filter=userIdentity.sessionContext.sessionIssuer.userName=skeldir-app-runtime-stage",
    ]
    if has_stage_tether:
        stage_lines.append("identity_tether=skeldir-app-runtime-stage")
    else:
        stage_lines.append("identity_tether=missing")
    _write(out_dir / "cloudtrail_stage_secret_reads.txt", stage_lines)
    if ci_code != 0 or not has_stage_tether:
        failures.append("cloudtrail_stage_lookup_failed")

    _update_proof_index(out_dir=out_dir, now=now)

    if args.strict and failures:
        print("failures=" + ",".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
