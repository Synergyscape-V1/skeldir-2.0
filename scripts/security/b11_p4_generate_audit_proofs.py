#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
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

    cloudtrail_ci_cmd = [
        aws,
        "cloudtrail",
        "lookup-events",
        "--lookup-attributes",
        "AttributeKey=EventName,AttributeValue=GetSecretValue",
        "--max-results",
        "20",
        "--region",
        args.region,
        "--output",
        "json",
    ]
    ci_code, ci_out, ci_err = _run(cloudtrail_ci_cmd)
    ci_lines = [
        f"timestamp_utc={now}",
        f"cmd={' '.join(cloudtrail_ci_cmd)}",
        f"exit_code={ci_code}",
        "stderr=" + (ci_err or "<empty>"),
    ]
    if ci_out:
        try:
            payload = json.loads(ci_out)
            events = payload.get("Events", [])
            ci_lines.append(f"events_count={len(events)}")
            for event in events:
                event_raw = event.get("CloudTrailEvent", "")
                if "skeldir-ci-deploy" in event_raw:
                    ci_lines.append("identity_tether=skeldir-ci-deploy")
                    break
        except Exception:
            ci_lines.append("events_count_parse_error=true")
    else:
        ci_lines.append("events_count=0")
    _write(out_dir / "cloudtrail_ci_secret_reads.txt", ci_lines)
    if ci_code != 0:
        failures.append("cloudtrail_ci_lookup_failed")

    stage_lines = [
        f"timestamp_utc={now}",
        "status=PENDING_EXTERNAL_STAGE_RUNTIME_CAPTURE",
        "required_role=skeldir-app-runtime-stage",
        "required_event=secretsmanager:GetSecretValue",
        "required_filter=userIdentity.sessionContext.sessionIssuer.userName=skeldir-app-runtime-stage",
    ]
    _write(out_dir / "cloudtrail_stage_secret_reads.txt", stage_lines)

    if args.strict and failures:
        print("failures=" + ",".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
