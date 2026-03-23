#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request


DEFAULT_REQUIRED_CONTEXT = "B1.4 P7 E2E Privacy System Proofs"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture B1.4-P7 branch-protection hardware evidence")
    parser.add_argument(
        "--required-checks-contract",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument(
        "--branch-protection-integrity-contract",
        default="contracts-internal/governance/main_branch_protection_integrity.main.json",
    )
    parser.add_argument("--workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument("--required-context", default=DEFAULT_REQUIRED_CONTEXT)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--output", default="artifacts/b14_p7/p7_branch_protection_evidence.json")
    parser.add_argument("--required-status-output", default="artifacts/b14_p7/p7_required_status_checks_live.json")
    parser.add_argument("--branch-protection-output", default="artifacts/b14_p7/p7_branch_protection_live.json")
    parser.add_argument("--require-live", action="store_true")
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_workflow_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _fetch_github_api(*, url: str, token: str, user_agent: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": user_agent,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_required_status_checks(*, repository: str, branch: str, token: str) -> dict[str, Any]:
    return _fetch_github_api(
        url=f"https://api.github.com/repos/{repository}/branches/{branch}/protection/required_status_checks",
        token=token,
        user_agent="skeldir-b14-p7-required-checks-capture",
    )


def _fetch_branch_protection(*, repository: str, branch: str, token: str) -> dict[str, Any]:
    return _fetch_github_api(
        url=f"https://api.github.com/repos/{repository}/branches/{branch}/protection",
        token=token,
        user_agent="skeldir-b14-p7-branch-protection-capture",
    )


def main() -> int:
    args = _parse_args()
    required_checks_path = Path(args.required_checks_contract)
    branch_integrity_path = Path(args.branch_protection_integrity_contract)
    workflow_path = Path(args.workflow_file)
    output_path = Path(args.output)

    missing = [
        str(path)
        for path in (required_checks_path, branch_integrity_path, workflow_path)
        if not path.exists()
    ]
    if missing:
        print("B1.4-P7 branch-protection evidence capture failed:")
        for item in missing:
            print(f"  - missing file: {item}")
        return 1

    required_checks_contract = _load_json(required_checks_path)
    branch_integrity_contract = _load_json(branch_integrity_path)
    workflow_text = _load_workflow_text(workflow_path)
    repository = (args.repository or str(required_checks_contract.get("repository") or "")).strip()
    if not repository:
        print("B1.4-P7 branch-protection evidence capture failed: repository is required")
        return 1

    required_context = str(args.required_context).strip()
    expected_contexts = required_checks_contract.get("required_contexts")
    if not isinstance(expected_contexts, list):
        print("B1.4-P7 branch-protection evidence capture failed: required_contexts missing in contract")
        return 1
    expected_contexts = [str(ctx).strip() for ctx in expected_contexts if str(ctx).strip()]
    b14_contexts = [ctx for ctx in expected_contexts if ctx.startswith("B1.4 P")]

    hardware = required_checks_contract.get("hardware_enforcement")
    branch_hardware = branch_integrity_contract.get("hardware_enforcement")

    payload: dict[str, Any] = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository": repository,
        "branch": args.branch,
        "required_context": required_context,
        "required_checks_contract_path": str(required_checks_path),
        "branch_integrity_contract_path": str(branch_integrity_path),
        "workflow_path": str(workflow_path),
        "required_context_present_in_contract": required_context in expected_contexts,
        "required_context_present_in_workflow": required_context in workflow_text,
        "b14_contexts_in_contract": b14_contexts,
        "contract_exact_match": bool(required_checks_contract.get("exact_match", False)),
        "contract_hardware_enforcement": hardware,
        "branch_integrity_hardware_enforcement": branch_hardware,
        "branch_integrity_require_live_on_main": bool(
            branch_integrity_contract.get("require_live_on_main", False)
        ),
    }

    token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    authority_mode = "fallback_workflow_contract_only"
    live_error: str | None = None
    required_status_live: dict[str, Any] | None = None
    branch_protection_live: dict[str, Any] | None = None

    if token:
        try:
            required_status_live = _fetch_required_status_checks(
                repository=repository,
                branch=args.branch,
                token=token,
            )
            branch_protection_live = _fetch_branch_protection(
                repository=repository,
                branch=args.branch,
                token=token,
            )
            authority_mode = "live_branch_protection_api"
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            live_error = f"http_{exc.code}: {body}"
        except Exception as exc:  # pragma: no cover
            live_error = str(exc)
    else:
        live_error = "missing GH_TOKEN/GITHUB_TOKEN"

    payload["authority_mode"] = authority_mode
    payload["live_api_error"] = live_error

    errors: list[str] = []
    if not payload["required_context_present_in_contract"]:
        errors.append("required context absent from required checks contract")
    if not payload["required_context_present_in_workflow"]:
        errors.append("required context absent from workflow")

    if not isinstance(hardware, dict) or str(hardware.get("status", "")).strip().lower() != "enforced":
        errors.append("required checks contract hardware_enforcement.status must be 'enforced'")
    elif isinstance(hardware.get("deferred_contexts"), list) and hardware.get("deferred_contexts"):
        errors.append("required checks contract deferred_contexts must be empty in P7")

    if not isinstance(branch_hardware, dict) or str(branch_hardware.get("status", "")).strip().lower() != "enforced":
        errors.append("branch integrity contract hardware_enforcement.status must be 'enforced'")

    if not payload["branch_integrity_require_live_on_main"]:
        errors.append("branch integrity contract require_live_on_main must be true in P7")

    if authority_mode == "live_branch_protection_api":
        assert required_status_live is not None
        assert branch_protection_live is not None
        contexts = required_status_live.get("contexts")
        if not isinstance(contexts, list):
            errors.append("live required_status_checks payload missing contexts list")
            contexts = []

        strict_live = bool(required_status_live.get("strict", False))
        missing_expected = [ctx for ctx in expected_contexts if ctx not in contexts]
        extra_live = [ctx for ctx in contexts if ctx not in expected_contexts]
        missing_b14 = [ctx for ctx in b14_contexts if ctx not in contexts]

        payload["live_required_status_checks"] = required_status_live
        payload["live_branch_protection"] = branch_protection_live
        payload["required_context_present_in_live"] = required_context in contexts
        payload["live_strict"] = strict_live
        payload["live_missing_expected_contexts"] = missing_expected
        payload["live_extra_contexts"] = extra_live
        payload["live_missing_b14_contexts"] = missing_b14

        if required_context not in contexts:
            errors.append("required context absent from live required status checks")
        if not strict_live:
            errors.append("live required status checks strict mode is false")
        if missing_b14:
            errors.append(f"live required status checks missing B1.4 contexts: {missing_b14}")
        if bool(required_checks_contract.get("exact_match", False)) and extra_live:
            errors.append(f"live required status checks include unexpected extra contexts: {extra_live}")

        _write_json(Path(args.required_status_output), required_status_live)
        _write_json(Path(args.branch_protection_output), branch_protection_live)
    else:
        payload["required_context_present_in_live"] = False
        if args.require_live:
            errors.append(f"live branch-protection capture required but unavailable: {live_error}")

    _write_json(output_path, payload)

    if errors:
        print("B1.4-P7 branch-protection evidence capture failed:")
        for error in errors:
            print(f"  - {error}")
        print(f"  output={output_path}")
        return 1

    print("B1.4-P7 branch-protection evidence captured.")
    print(f"  authority_mode={authority_mode}")
    print(f"  output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
