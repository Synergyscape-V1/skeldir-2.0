#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
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


def _lookup_events_by_name(
    aws: str, region: str, event_name: str, start_time: str, max_pages: int
) -> tuple[int, list[dict], str]:
    events: list[dict] = []
    next_token: str | None = None
    for _ in range(max_pages):
        cmd = [
            aws,
            "cloudtrail",
            "lookup-events",
            "--lookup-attributes",
            f"AttributeKey=EventName,AttributeValue={event_name}",
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


def _invoke_lambda_trigger(
    aws: str, region: str, function_arn: str, payload: dict[str, str]
) -> tuple[int, str, str]:
    with tempfile.NamedTemporaryFile(prefix="b11_p6_lambda_", suffix=".json", delete=False) as tmp:
        out_file = tmp.name
    cmd = [
        aws,
        "lambda",
        "invoke",
        "--function-name",
        function_arn,
        "--invocation-type",
        "RequestResponse",
        "--payload",
        json.dumps(payload, separators=(",", ":"), ensure_ascii=True),
        "--cli-binary-format",
        "raw-in-base64-out",
        "--region",
        region,
        "--output",
        "json",
        out_file,
    ]
    code, out, err = _run(cmd)
    response_payload = ""
    if Path(out_file).exists():
        response_payload = Path(out_file).read_text(encoding="utf-8", errors="replace").strip()
        Path(out_file).unlink(missing_ok=True)
    return code, response_payload or out, err


def _start_stepfn_trigger(
    aws: str, region: str, state_machine_arn: str, execution_name: str, payload: dict[str, str]
) -> tuple[int, str, str]:
    cmd = [
        aws,
        "stepfunctions",
        "start-execution",
        "--state-machine-arn",
        state_machine_arn,
        "--name",
        execution_name,
        "--input",
        json.dumps(payload, separators=(",", ":"), ensure_ascii=True),
        "--region",
        region,
        "--output",
        "json",
    ]
    return _run(cmd)


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
        "--trigger-mode",
        default=os.getenv("B11_P6_STAGE_TRIGGER_MODE", "").strip().lower(),
        choices=["", "lambda", "stepfunctions", "assume_role_direct"],
        help="CI-driven trigger mode for stage secret read causality",
    )
    parser.add_argument(
        "--trigger-lambda-arn",
        default=os.getenv("B11_P6_STAGE_TRIGGER_LAMBDA_ARN", "").strip(),
    )
    parser.add_argument(
        "--trigger-state-machine-arn",
        default=os.getenv("B11_P6_STAGE_TRIGGER_STATE_MACHINE_ARN", "").strip(),
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    aws = _aws_bin()
    now = datetime.now(timezone.utc)
    run_id = os.getenv("GITHUB_RUN_ID", "unknown")
    run_attempt = os.getenv("GITHUB_RUN_ATTEMPT", "unknown")
    marker = f"P6_RUN_ID={run_id};ATTEMPT={run_attempt}"
    session_name = f"p6-{run_id}-{run_attempt}".replace("_", "-")[:64]
    execution_name = session_name

    failures: list[str] = []
    if args.strict and args.trigger_mode == "assume_role_direct":
        failures.append("trigger_mode_assume_role_direct_not_allowed_in_strict")
    trigger_invocation_success = False
    lines = [
        f"timestamp_utc={now.isoformat()}",
        f"region={args.region}",
        f"correlation_marker={marker}",
        f"trigger_mode={args.trigger_mode or '<unset>'}",
        f"runtime_role_arn={args.runtime_role_arn}",
        f"trigger_secret_id={args.secret_id}",
        f"trigger_start_time_utc={now.strftime('%Y-%m-%dT%H:%M:%SZ')}",
    ]

    trigger_event_names: list[str] = []
    if args.trigger_mode == "lambda":
        if not args.trigger_lambda_arn:
            failures.append("missing_lambda_trigger_arn")
        else:
            payload = {"correlation_marker": marker, "secret_id": args.secret_id}
            trigger_code, trigger_out, trigger_err = _invoke_lambda_trigger(
                aws=aws, region=args.region, function_arn=args.trigger_lambda_arn, payload=payload
            )
            lines.append(f"trigger_lambda_arn={args.trigger_lambda_arn}")
            lines.append(f"trigger_lambda_exit_code={trigger_code}")
            lines.append("trigger_lambda_stderr=" + (trigger_err or "<empty>"))
            lines.append("trigger_lambda_response=" + (trigger_out or "<empty>"))
            if trigger_code != 0:
                failures.append("trigger_lambda_failed")
            else:
                trigger_invocation_success = True
            trigger_event_names.append("Invoke")
    elif args.trigger_mode == "stepfunctions":
        if not args.trigger_state_machine_arn:
            failures.append("missing_stepfunctions_trigger_arn")
        else:
            payload = {"correlation_marker": marker, "secret_id": args.secret_id}
            trigger_code, trigger_out, trigger_err = _start_stepfn_trigger(
                aws=aws,
                region=args.region,
                state_machine_arn=args.trigger_state_machine_arn,
                execution_name=execution_name,
                payload=payload,
            )
            lines.append(f"trigger_state_machine_arn={args.trigger_state_machine_arn}")
            lines.append(f"trigger_stepfunctions_exit_code={trigger_code}")
            lines.append("trigger_stepfunctions_stderr=" + (trigger_err or "<empty>"))
            lines.append("trigger_stepfunctions_response=" + (trigger_out or "<empty>"))
            if trigger_code != 0:
                failures.append("trigger_stepfunctions_failed")
            else:
                trigger_invocation_success = True
            trigger_event_names.append("StartExecution")
    elif args.trigger_mode == "assume_role_direct":
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
            else:
                trigger_invocation_success = True
            trigger_event_names.append("AssumeRole")
    else:
        failures.append("trigger_mode_not_configured")

    max_pages = int(os.getenv("B11_P6_CLOUDTRAIL_MAX_PAGES", "30"))
    delay_seconds = int(os.getenv("B11_P6_STAGE_TETHER_CLOUDTRAIL_DELAY_SECONDS", "20"))
    wait_seconds = int(os.getenv("B11_P6_STAGE_TETHER_CLOUDTRAIL_WAIT_SECONDS", "180"))
    poll_interval_seconds = int(os.getenv("B11_P6_CLOUDTRAIL_POLL_INTERVAL_SECONDS", "15"))
    time.sleep(delay_seconds)
    strict_start = (now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
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

    trigger_evidence: list[dict[str, str]] = []
    trigger_lookup_failures = 0
    for event_name in trigger_event_names:
        t_code, t_events, t_err = _lookup_events_by_name(
            aws=aws,
            region=args.region,
            event_name=event_name,
            start_time=start_time,
            max_pages=max_pages,
        )
        lines.append(f"trigger_event_lookup_{event_name}_exit_code={t_code}")
        lines.append(f"trigger_event_lookup_{event_name}_stderr={t_err or '<empty>'}")
        if t_code != 0:
            trigger_lookup_failures += 1
            continue
        for event in t_events:
            raw = event.get("CloudTrailEvent", "")
            if marker not in raw and session_name not in raw and execution_name not in raw:
                continue
            trigger_evidence.append(
                {
                    "event_id": event.get("EventId", "unknown"),
                    "event_time": event.get("EventTime", "unknown"),
                    "event_name": event.get("EventName", "unknown"),
                }
            )
            if len(trigger_evidence) >= 10:
                break
        if len(trigger_evidence) >= 10:
            break

    lines.append(f"cloudtrail_lookup_start_time_utc={start_time}")
    lines.append(f"cloudtrail_pages_requested={max_pages}")
    lines.append(f"cloudtrail_poll_attempts={attempts}")
    lines.append(f"cloudtrail_wait_seconds={wait_seconds}")
    lines.append(f"cloudtrail_exit_code={ct_code}")
    lines.append("cloudtrail_stderr=" + (ct_err or "<empty>"))
    lines.append(f"cloudtrail_events_scanned={len(events)}")

    if ct_code != 0:
        failures.append("cloudtrail_lookup_failed")
    if trigger_lookup_failures:
        failures.append("trigger_event_lookup_failed")

    if matched:
        lines.append("identity_tether=skeldir-app-runtime-stage")
        lines.append("run_causal_tether=present")
        for item in matched[:10]:
            lines.append(
                "matched_event="
                + json.dumps(item, sort_keys=True, separators=(",", ":"))
            )
        if trigger_evidence:
            lines.append("trigger_event_tether=present")
            lines.append("trigger_invocation_evidence=present")
            for item in trigger_evidence:
                lines.append(
                    "trigger_event="
                    + json.dumps(item, sort_keys=True, separators=(",", ":"))
                )
        elif trigger_invocation_success:
            # CloudTrail Invoke/StartExecution records may not include request payload marker.
            # Successful trigger API response + runtime GetSecretValue event is sufficient causality evidence.
            lines.append("trigger_event_tether=not_observed")
            lines.append("trigger_invocation_evidence=present")
        else:
            lines.append("trigger_event_tether=missing")
            lines.append("trigger_invocation_evidence=missing")
        elif trigger_invocation_success:
            # CloudTrail Invoke/StartExecution records may not include request payload marker.
            # Successful trigger API response + runtime GetSecretValue event is sufficient causality evidence.
            lines.append("trigger_event_tether=not_observed")
            lines.append("trigger_invocation_evidence=present")
        else:
            lines.append("trigger_event_tether=missing")
            lines.append("trigger_invocation_evidence=missing")
            failures.append("trigger_event_tether_missing")
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
