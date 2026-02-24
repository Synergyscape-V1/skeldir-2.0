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


def _assume_stage_role(aws: str, region: str, role_arn: str, session_name: str) -> tuple[int, dict, str]:
    cmd = [
        aws,
        "sts",
        "assume-role",
        "--role-arn",
        role_arn,
        "--role-session-name",
        session_name,
        "--duration-seconds",
        "900",
        "--region",
        region,
        "--output",
        "json",
    ]
    code, out, err = _run(cmd)
    if code != 0:
        return code, {}, err
    return 0, json.loads(out or "{}"), ""


def _invoke_stage_secret_read_with_assumed_role(
    aws: str,
    region: str,
    creds_payload: dict,
    secret_id: str,
) -> tuple[int, str, str]:
    credentials = creds_payload.get("Credentials", {})
    access_key = credentials.get("AccessKeyId", "")
    secret_key = credentials.get("SecretAccessKey", "")
    session_token = credentials.get("SessionToken", "")
    env = os.environ.copy()
    env["AWS_ACCESS_KEY_ID"] = access_key
    env["AWS_SECRET_ACCESS_KEY"] = secret_key
    env["AWS_SESSION_TOKEN"] = session_token
    cmd = [
        aws,
        "secretsmanager",
        "get-secret-value",
        "--secret-id",
        secret_id,
        "--query",
        "VersionId",
        "--output",
        "text",
        "--region",
        region,
    ]
    return _run(cmd, env=env)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate B11-P6 run-causal stage CloudTrail tether evidence")
    parser.add_argument("--out", default="docs/forensics/evidence/b11_p6/cloudtrail_stage_run_causal.txt")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-2"))
    parser.add_argument(
        "--runtime-role-arn",
        default=os.getenv("B11_P6_STAGE_RUNTIME_ROLE_ARN", "arn:aws:iam::326730685463:role/skeldir-app-runtime-stage"),
    )
    parser.add_argument(
        "--secret-id",
        default=os.getenv("B11_P6_STAGE_TRIGGER_SECRET_ID", "/skeldir/stage/secret/auth/jwt-secret"),
    )
    parser.add_argument(
        "--allow-passive-fallback",
        action="store_true",
        default=os.getenv("B11_P6_STAGE_TETHER_ALLOW_PASSIVE_FALLBACK", "1") == "1",
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    aws = _aws_bin()
    now = datetime.now(timezone.utc)
    run_id = os.getenv("GITHUB_RUN_ID", "unknown")
    run_attempt = os.getenv("GITHUB_RUN_ATTEMPT", "unknown")
    marker = f"P6_RUN_ID={run_id};ATTEMPT={run_attempt}"
    session_name = f"p6-{run_id}-{run_attempt}".replace("_", "-")[:64]

    failures: list[str] = []
    lines = [
        f"timestamp_utc={now.isoformat()}",
        f"region={args.region}",
        f"correlation_marker={marker}",
        f"trigger_mode=assume_role_direct",
        f"runtime_role_arn={args.runtime_role_arn}",
        f"trigger_secret_id={args.secret_id}",
        f"trigger_start_time_utc={now.strftime('%Y-%m-%dT%H:%M:%SZ')}",
    ]

    assume_code, assume_payload, assume_err = _assume_stage_role(
        aws=aws,
        region=args.region,
        role_arn=args.runtime_role_arn,
        session_name=session_name,
    )
    lines.append(f"assume_role_exit_code={assume_code}")
    lines.append(f"assume_role_session_name={session_name}")
    lines.append("assume_role_stderr=" + (assume_err or "<empty>"))
    if assume_code != 0:
        failures.append("assume_role_failed")
    else:
        trigger_code, trigger_out, trigger_err = _invoke_stage_secret_read_with_assumed_role(
            aws=aws,
            region=args.region,
            creds_payload=assume_payload,
            secret_id=args.secret_id,
        )
        lines.append(f"trigger_get_secret_exit_code={trigger_code}")
        lines.append("trigger_get_secret_stdout=<redacted>" if trigger_out else "trigger_get_secret_stdout=<empty>")
        lines.append("trigger_get_secret_stderr=" + (trigger_err or "<empty>"))
        if trigger_code != 0:
            failures.append("trigger_get_secret_failed")

    max_pages = int(os.getenv("B11_P6_CLOUDTRAIL_MAX_PAGES", "30"))
    delay_seconds = int(os.getenv("B11_P6_STAGE_TETHER_CLOUDTRAIL_DELAY_SECONDS", "20"))
    wait_seconds = int(os.getenv("B11_P6_STAGE_TETHER_CLOUDTRAIL_WAIT_SECONDS", "180"))
    poll_interval_seconds = int(os.getenv("B11_P6_CLOUDTRAIL_POLL_INTERVAL_SECONDS", "15"))
    time.sleep(delay_seconds)
    fallback_lookback_hours = int(os.getenv("B11_P6_STAGE_TETHER_FALLBACK_LOOKBACK_HOURS", "24"))
    strict_start = (now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fallback_start = (now - timedelta(hours=fallback_lookback_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    start_time = strict_start
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
            if "skeldir-app-runtime-stage" not in raw:
                continue
            if session_name not in raw and args.secret_id not in raw:
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

    passive_fallback_matched = False
    if not matched and assume_code != 0 and args.allow_passive_fallback and ct_code == 0:
        start_time = fallback_start
        ct_code, events, ct_err = _lookup_get_secret_events(
            aws=aws,
            region=args.region,
            start_time=start_time,
            max_pages=max_pages,
        )
        if ct_code == 0:
            for event in events:
                raw = event.get("CloudTrailEvent", "")
                if "skeldir-app-runtime-stage" not in raw:
                    continue
                matched.append(
                    {
                        "event_id": event.get("EventId", "unknown"),
                        "event_time": event.get("EventTime", "unknown"),
                        "event_name": event.get("EventName", "unknown"),
                    }
                )
            passive_fallback_matched = bool(matched)

    lines.append(f"cloudtrail_lookup_start_time_utc={start_time}")
    lines.append(f"cloudtrail_pages_requested={max_pages}")
    lines.append(f"cloudtrail_poll_attempts={attempts}")
    lines.append(f"cloudtrail_wait_seconds={wait_seconds}")
    lines.append(f"cloudtrail_exit_code={ct_code}")
    lines.append("cloudtrail_stderr=" + (ct_err or "<empty>"))
    lines.append(f"cloudtrail_events_scanned={len(events)}")
    lines.append(f"passive_fallback_enabled={args.allow_passive_fallback}")

    if ct_code != 0:
        failures.append("cloudtrail_lookup_failed")

    if matched:
        lines.append("identity_tether=skeldir-app-runtime-stage")
        if passive_fallback_matched:
            lines.append("run_causal_tether=passive_fallback")
            lines.append(f"fallback_start_time_utc={fallback_start}")
        else:
            lines.append("run_causal_tether=present")
        for item in matched[:10]:
            lines.append(
                "matched_event="
                + json.dumps(item, sort_keys=True, separators=(",", ":"))
            )
    else:
        lines.append("identity_tether=missing")
        lines.append("run_causal_tether=missing")
        failures.append("run_causal_stage_tether_missing")

    out_path = Path(args.out).resolve()
    _write(out_path, lines)

    if args.strict and failures:
        print("failures=" + ",".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
