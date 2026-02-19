from __future__ import annotations

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

    lines = [
        f"timestamp_utc={datetime.now(timezone.utc).isoformat()}",
        f"terraform_dir={tf_dir}",
        "",
        "# Import commands (run once before first managed apply):",
        "terraform import aws_iam_openid_connect_provider.github_actions arn:aws:iam::326730685463:oidc-provider/token.actions.githubusercontent.com",
        "terraform import aws_iam_role.runtime_prod skeldir-app-runtime-prod",
        "terraform import aws_iam_role.runtime_stage skeldir-app-runtime-stage",
        "terraform import aws_iam_role.ci_deploy skeldir-ci-deploy",
        "terraform import aws_iam_role.rotation_lambda skeldir-rotation-lambda",
        "",
    ]

    for cmd in (
        ["terraform", "fmt", "-check"],
        ["terraform", "init", "-backend=false"],
        ["terraform", "validate"],
        ["terraform", "plan", "-var", "environment=ci", "-lock=false", "-input=false"],
        ["terraform", "state", "list"],
    ):
        lines.append("$ " + " ".join(cmd))
        code, out, err = _run(cmd, tf_dir)
        lines.append(f"exit_code={code}")
        lines.append("stdout=" + (out or "<empty>"))
        lines.append("stderr=" + (err or "<empty>"))
        lines.append("")

    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
