from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        return 127, "", f"{exc.__class__.__name__}: {exc}"
    return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    tf_dir = repo_root / "infra" / "b11_p1" / "terraform"
    out_path = repo_root / "docs" / "forensics" / "evidence" / "b11_p1" / "iac_state_proof.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    bucket = os.environ.get("B11_P1_TF_STATE_BUCKET", "").strip()
    lock_table = os.environ.get("B11_P1_TF_LOCK_TABLE", "").strip()
    state_key = os.environ.get("B11_P1_TF_STATE_KEY", "b11-p1/terraform.tfstate").strip()
    region = os.environ.get("AWS_REGION", "us-east-2").strip()

    lines = [
        f"timestamp_utc={datetime.now(timezone.utc).isoformat()}",
        f"terraform_dir={tf_dir}",
        f"aws_region={region}",
        f"state_bucket={bucket or '<unset>'}",
        f"state_lock_table={lock_table or '<unset>'}",
        f"state_key={state_key}",
        "",
        "# Import commands (executed only when state entries are missing):",
        "terraform import aws_iam_openid_connect_provider.github_actions arn:aws:iam::326730685463:oidc-provider/token.actions.githubusercontent.com",
        "terraform import aws_iam_role.runtime_prod skeldir-app-runtime-prod",
        "terraform import aws_iam_role.runtime_stage skeldir-app-runtime-stage",
        "terraform import aws_iam_role.ci_deploy skeldir-ci-deploy",
        "terraform import aws_iam_role.rotation_lambda skeldir-rotation-lambda",
        "",
    ]

    if not bucket or not lock_table:
        lines.extend(
            [
                "error=missing_backend_configuration",
                "hint=Set B11_P1_TF_STATE_BUCKET and B11_P1_TF_LOCK_TABLE",
                "status=failed",
            ]
        )
        out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        raise SystemExit(1)

    init_cmd = [
        "terraform",
        "init",
        f"-backend-config=bucket={bucket}",
        f"-backend-config=key={state_key}",
        f"-backend-config=region={region}",
        f"-backend-config=dynamodb_table={lock_table}",
        "-backend-config=encrypt=true",
        "-reconfigure",
        "-input=false",
    ]

    for cmd in (["terraform", "fmt", "-check"], init_cmd, ["terraform", "validate"]):
        lines.append("$ " + " ".join(cmd))
        code, out, err = _run(cmd, tf_dir)
        lines.append(f"exit_code={code}")
        lines.append("stdout=" + (out or "<empty>"))
        lines.append("stderr=" + (err or "<empty>"))
        lines.append("")
        if code != 0:
            lines.append("status=failed")
            out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
            raise SystemExit(code)

    state_cmd = ["terraform", "state", "list"]
    lines.append("$ " + " ".join(state_cmd))
    code, out, err = _run(state_cmd, tf_dir)
    lines.append(f"exit_code={code}")
    lines.append("stdout=" + (out or "<empty>"))
    lines.append("stderr=" + (err or "<empty>"))
    lines.append("")
    if code != 0:
        lines.append("status=failed")
        out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        raise SystemExit(code)

    current_state = set((out or "").splitlines())
    import_targets = [
        (
            "aws_iam_openid_connect_provider.github_actions",
            [
                "terraform",
                "import",
                "aws_iam_openid_connect_provider.github_actions",
                "arn:aws:iam::326730685463:oidc-provider/token.actions.githubusercontent.com",
            ],
        ),
        ("aws_iam_role.runtime_prod", ["terraform", "import", "aws_iam_role.runtime_prod", "skeldir-app-runtime-prod"]),
        ("aws_iam_role.runtime_stage", ["terraform", "import", "aws_iam_role.runtime_stage", "skeldir-app-runtime-stage"]),
        ("aws_iam_role.ci_deploy", ["terraform", "import", "aws_iam_role.ci_deploy", "skeldir-ci-deploy"]),
        ("aws_iam_role.rotation_lambda", ["terraform", "import", "aws_iam_role.rotation_lambda", "skeldir-rotation-lambda"]),
    ]

    for state_addr, import_cmd in import_targets:
        if state_addr in current_state:
            lines.append(f"$ skip import {state_addr} (already in state)")
            lines.append("exit_code=0")
            lines.append("stdout=already_in_state")
            lines.append("stderr=<empty>")
            lines.append("")
            continue

        lines.append("$ " + " ".join(import_cmd))
        code, out, err = _run(import_cmd, tf_dir)
        lines.append(f"exit_code={code}")
        lines.append("stdout=" + (out or "<empty>"))
        lines.append("stderr=" + (err or "<empty>"))
        lines.append("")
        if code != 0:
            lines.append("status=failed")
            out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
            raise SystemExit(code)

    lines.append("$ terraform state list")
    code, out, err = _run(["terraform", "state", "list"], tf_dir)
    lines.append(f"exit_code={code}")
    lines.append("stdout=" + (out or "<empty>"))
    lines.append("stderr=" + (err or "<empty>"))
    lines.append("")
    if code != 0 or not (out or "").strip():
        lines.append("status=failed")
        out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        raise SystemExit(1)

    for state_addr in [item[0] for item in import_targets]:
        show_cmd = ["terraform", "state", "show", state_addr]
        lines.append("$ " + " ".join(show_cmd))
        code, out, err = _run(show_cmd, tf_dir)
        lines.append(f"exit_code={code}")
        lines.append("stdout=" + (out or "<empty>"))
        lines.append("stderr=" + (err or "<empty>"))
        lines.append("")
        if code != 0:
            lines.append("status=failed")
            out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
            raise SystemExit(code)

    plan_cmd = [
        "terraform",
        "plan",
        "-detailed-exitcode",
        "-lock=true",
        "-input=false",
        "-var",
        "environment=ci",
        "-var",
        "manage_prefix_policies=false",
        "-var",
        "manage_namespace_placeholders=false",
    ]
    lines.append("$ " + " ".join(plan_cmd))
    code, out, err = _run(plan_cmd, tf_dir)
    lines.append(f"exit_code={code}")
    lines.append("stdout=" + (out or "<empty>"))
    lines.append("stderr=" + (err or "<empty>"))
    lines.append("")

    if code != 0:
        lines.append("status=failed")
        if code == 2:
            lines.append("reason=plan_has_changes_expected_none")
        out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        raise SystemExit(code)

    lines.append("status=pass")
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
