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


def _aws_cli() -> str:
    explicit = os.getenv("AWS_CLI_BIN")
    if explicit:
        return explicit
    return "aws.cmd" if os.name == "nt" else "aws"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate B11-P1 AWS proof artifacts")
    parser.add_argument(
        "--out-dir",
        default="docs/forensics/evidence/b11_p1",
        help="Evidence output directory",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    role_name = os.getenv("B11_P1_ROLE_NAME", "skeldir-ci-deploy")
    env_name = os.getenv("B11_P1_ENV", "ci")
    region = os.getenv("AWS_REGION", "us-east-2")

    roles = [
        "skeldir-app-runtime-prod",
        "skeldir-app-runtime-stage",
        "skeldir-ci-deploy",
        "skeldir-rotation-lambda",
    ]
    role_scope_expectations = {
        "skeldir-app-runtime-prod": {
            "allowed_ssm": [f"arn:aws:ssm:{region}:326730685463:parameter/skeldir/prod/config/*"],
            "denied_ssm": [
                f"arn:aws:ssm:{region}:326730685463:parameter/skeldir/stage/*",
                f"arn:aws:ssm:{region}:326730685463:parameter/skeldir/ci/*",
                f"arn:aws:ssm:{region}:326730685463:parameter/skeldir/dev/*",
                f"arn:aws:ssm:{region}:326730685463:parameter/skeldir/local/*",
            ],
            "allowed_secrets": [f"arn:aws:secretsmanager:{region}:326730685463:secret:/skeldir/prod/secret/*"],
            "denied_secrets": [
                f"arn:aws:secretsmanager:{region}:326730685463:secret:/skeldir/stage/*",
                f"arn:aws:secretsmanager:{region}:326730685463:secret:/skeldir/ci/*",
                f"arn:aws:secretsmanager:{region}:326730685463:secret:/skeldir/dev/*",
                f"arn:aws:secretsmanager:{region}:326730685463:secret:/skeldir/local/*",
            ],
        },
        "skeldir-app-runtime-stage": {
            "allowed_ssm": [f"arn:aws:ssm:{region}:326730685463:parameter/skeldir/stage/config/*"],
            "denied_ssm": [
                f"arn:aws:ssm:{region}:326730685463:parameter/skeldir/prod/*",
                f"arn:aws:ssm:{region}:326730685463:parameter/skeldir/ci/*",
                f"arn:aws:ssm:{region}:326730685463:parameter/skeldir/dev/*",
                f"arn:aws:ssm:{region}:326730685463:parameter/skeldir/local/*",
            ],
            "allowed_secrets": [f"arn:aws:secretsmanager:{region}:326730685463:secret:/skeldir/stage/secret/*"],
            "denied_secrets": [
                f"arn:aws:secretsmanager:{region}:326730685463:secret:/skeldir/prod/*",
                f"arn:aws:secretsmanager:{region}:326730685463:secret:/skeldir/ci/*",
                f"arn:aws:secretsmanager:{region}:326730685463:secret:/skeldir/dev/*",
                f"arn:aws:secretsmanager:{region}:326730685463:secret:/skeldir/local/*",
            ],
        },
        "skeldir-ci-deploy": {
            "allowed_ssm": [f"arn:aws:ssm:{region}:326730685463:parameter/skeldir/ci/config/*"],
            "denied_ssm": [
                f"arn:aws:ssm:{region}:326730685463:parameter/skeldir/prod/*",
                f"arn:aws:ssm:{region}:326730685463:parameter/skeldir/stage/*",
                f"arn:aws:ssm:{region}:326730685463:parameter/skeldir/dev/*",
                f"arn:aws:ssm:{region}:326730685463:parameter/skeldir/local/*",
            ],
            "allowed_secrets": [f"arn:aws:secretsmanager:{region}:326730685463:secret:/skeldir/ci/secret/*"],
            "denied_secrets": [
                f"arn:aws:secretsmanager:{region}:326730685463:secret:/skeldir/prod/*",
                f"arn:aws:secretsmanager:{region}:326730685463:secret:/skeldir/stage/*",
                f"arn:aws:secretsmanager:{region}:326730685463:secret:/skeldir/dev/*",
                f"arn:aws:secretsmanager:{region}:326730685463:secret:/skeldir/local/*",
            ],
        },
        "skeldir-rotation-lambda": {
            "allowed_ssm": [f"arn:aws:ssm:{region}:326730685463:parameter/skeldir/*"],
            "denied_ssm": [],
            "allowed_secrets": [f"arn:aws:secretsmanager:{region}:326730685463:secret:/skeldir/*"],
            "denied_secrets": [],
        },
    }
    allowed_ssm_path = f"/skeldir/{env_name}/config/"
    forbidden_ssm_path = "/skeldir/prod/config/" if env_name != "prod" else "/skeldir/stage/config/"

    deny_lines: list[str] = [
        f"timestamp_utc={datetime.now(timezone.utc).isoformat()}",
        f"role_name={role_name}",
        f"region={region}",
        f"allowed_ssm_path={allowed_ssm_path}",
        f"forbidden_ssm_path={forbidden_ssm_path}",
        "",
        "[allow_check] aws ssm get-parameters-by-path",
    ]

    aws_bin = _aws_cli()

    allow_cmd = [
        aws_bin,
        "ssm",
        "get-parameters-by-path",
        "--path",
        allowed_ssm_path,
        "--recursive",
        "--max-results",
        "1",
        "--region",
        region,
    ]
    allow_code, allow_out, allow_err = _run(allow_cmd)
    deny_lines.append(f"exit_code={allow_code}")
    deny_lines.append("stdout=" + (allow_out or "<empty>"))
    deny_lines.append("stderr=" + (allow_err or "<empty>"))
    deny_lines.append("")

    deny_lines.append("[deny_check] aws ssm get-parameters-by-path")
    deny_cmd = [
        aws_bin,
        "ssm",
        "get-parameters-by-path",
        "--path",
        forbidden_ssm_path,
        "--recursive",
        "--max-results",
        "1",
        "--region",
        region,
    ]
    deny_code, deny_out, deny_err = _run(deny_cmd)
    deny_lines.append(f"exit_code={deny_code}")
    deny_lines.append("stdout=" + (deny_out or "<empty>"))
    deny_lines.append("stderr=" + (deny_err or "<empty>"))
    deny_lines.append("")

    if deny_code == 0 or "AccessDenied" not in deny_err:
        deny_lines.append("RESULT=BLOCKED")
        deny_lines.append("reason=Cross-env deny proof did not return AccessDenied")
        deny_lines.append(
            "unblock_request=Validate IAM policy on skeldir-ci-deploy denies /skeldir/prod/config/* for this session"
        )
    elif allow_code != 0:
        deny_lines.append("RESULT=BLOCKED")
        deny_lines.append("reason=Allowed env path read did not succeed")
        deny_lines.append(
            f"unblock_request=Ensure at least one readable SSM parameter exists under {allowed_ssm_path}"
        )
    else:
        deny_lines.append("RESULT=PASS")

    _write(out_dir / "deny_proof_cross_env.txt", "\n".join(deny_lines))

    cloudtrail_lines: list[str] = [
        f"timestamp_utc={datetime.now(timezone.utc).isoformat()}",
        "queries=GetParametersByPath,GetSecretValue",
        "",
    ]
    cloudtrail_fail_reasons: list[str] = []
    cloudtrail_has_ci_identity = False
    cloudtrail_has_events = False

    for event_name in ("GetParametersByPath", "GetSecretValue"):
        cloudtrail_lines.append(f"[lookup:{event_name}]")
        query_cmd = [
            aws_bin,
            "cloudtrail",
            "lookup-events",
            "--lookup-attributes",
            f"AttributeKey=EventName,AttributeValue={event_name}",
            "--max-results",
            "5",
            "--region",
            region,
        ]
        q_code, q_out, q_err = _run(query_cmd)
        cloudtrail_lines.append(f"exit_code={q_code}")
        cloudtrail_lines.append("stdout=" + (q_out or "<empty>"))
        cloudtrail_lines.append("stderr=" + (q_err or "<empty>"))
        cloudtrail_lines.append("")

        if q_code != 0:
            cloudtrail_fail_reasons.append(f"{event_name}:lookup_failed")
            continue

        try:
            payload = json.loads(q_out) if q_out else {}
        except json.JSONDecodeError:
            cloudtrail_fail_reasons.append(f"{event_name}:invalid_json")
            continue

        events = payload.get("Events") or []
        if events:
            cloudtrail_has_events = True

        for event in events:
            cloudtrail_event = event.get("CloudTrailEvent", "")
            if not isinstance(cloudtrail_event, str):
                continue
            if f"assumed-role/{role_name}/" in cloudtrail_event:
                cloudtrail_has_ci_identity = True

    if not cloudtrail_has_events:
        cloudtrail_fail_reasons.append("no_cloudtrail_events_found")
    if not cloudtrail_has_ci_identity:
        cloudtrail_fail_reasons.append("events_not_tethered_to_ci_assumed_role")

    if cloudtrail_fail_reasons:
        cloudtrail_lines.append("RESULT=BLOCKED")
        cloudtrail_lines.append("reason=" + ",".join(sorted(set(cloudtrail_fail_reasons))))
        cloudtrail_lines.append(
            "unblock_request=Grant cloudtrail:LookupEvents to skeldir-ci-deploy and ensure lookup returns events for CI assumed-role reads"
        )
        cloudtrail_blocked = True
    else:
        cloudtrail_lines.append("RESULT=PASS")
        cloudtrail_blocked = False

    _write(out_dir / "cloudtrail_audit_proof.txt", "\n".join(cloudtrail_lines))

    for role in roles:
        iam_code, iam_out, iam_err = _run(
        [
            aws_bin,
            "iam",
                "list-attached-role-policies",
                "--role-name",
                role,
                "--region",
                region,
            ]
        )
        _write(
            out_dir / f"iam_policy_{role}.json",
            json.dumps(
                {
                    "role_name": role,
                    "exit_code": iam_code,
                    "stdout": iam_out,
                    "stderr": iam_err,
                    "expected_scope": role_scope_expectations.get(role, {}),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )

    if "RESULT=PASS" not in "\n".join(deny_lines) or cloudtrail_blocked:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
