#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _run(cmd: list[str], env: dict[str, str] | None = None) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
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


def _lookup_get_secret_events(aws: str, region: str, start_time: str, max_pages: int) -> tuple[int, list[dict], str]:
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
    parser = argparse.ArgumentParser(description="Generate B11-P6 CI OIDC + CloudTrail retrieval evidence")
    parser.add_argument("--out-dir", default="docs/forensics/evidence/b11_p6")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-2"))
    parser.add_argument("--env", default=os.getenv("B11_P4_ENV", "ci"))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    aws = _aws_bin()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    start_time = (now - timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    max_pages = int(os.getenv("B11_P6_CLOUDTRAIL_MAX_PAGES", "30"))

    failures: list[str] = []

    caller_cmd = [aws, "sts", "get-caller-identity", "--output", "json", "--region", args.region]
    caller_code, caller_out, caller_err = _run(caller_cmd)
    caller_lines = [
        f"timestamp_utc={now_iso}",
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
    retrieval_lines = [f"timestamp_utc={now_iso}", f"region={args.region}", f"env={args.env}"]
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

    wait_seconds = int(os.getenv("B11_P6_CLOUDTRAIL_WAIT_SECONDS", "120"))
    poll_interval_seconds = int(os.getenv("B11_P6_CLOUDTRAIL_POLL_INTERVAL_SECONDS", "15"))
    deadline = time.time() + wait_seconds
    ct_code = 0
    ct_err = ""
    events: list[dict] = []
    matched: list[dict[str, str]] = []
    attempts = 0
    while True:
        attempts += 1
        ct_code, events, ct_err = _lookup_get_secret_events(
            aws=aws,
            region=args.region,
            start_time=start_time,
            max_pages=max_pages,
        )
        matched = []
        for event in events:
            raw = event.get("CloudTrailEvent", "")
            if "skeldir-ci-deploy" not in raw:
                continue
            matched.append(
                {
                    "event_id": event.get("EventId", "unknown"),
                    "event_time": event.get("EventTime", "unknown"),
                    "event_name": event.get("EventName", "unknown"),
                }
            )
        if ct_code != 0 or matched or time.time() >= deadline:
            break
        time.sleep(poll_interval_seconds)

    lines = [
        f"timestamp_utc={now_iso}",
        f"start_time_utc={start_time}",
        f"region={args.region}",
        f"pages_requested={max_pages}",
        f"events_scanned={len(events)}",
        f"cloudtrail_poll_attempts={attempts}",
        f"cloudtrail_wait_seconds={wait_seconds}",
        f"exit_code={ct_code}",
        "stderr=" + (ct_err or "<empty>"),
        "required_role=skeldir-ci-deploy",
        "required_event=secretsmanager:GetSecretValue",
    ]
    if matched:
        lines.append("identity_tether=skeldir-ci-deploy")
        for item in matched[:10]:
            lines.append(
                "matched_event="
                + json.dumps(item, sort_keys=True, separators=(",", ":"))
            )
    else:
        lines.append("identity_tether=missing")
        failures.append("cloudtrail_ci_identity_tether_missing")

    _write(out_dir / "cloudtrail_ci_reads.txt", lines)

    if ct_code != 0:
        failures.append("cloudtrail_lookup_failed")

    if args.strict and failures:
        print("failures=" + ",".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
