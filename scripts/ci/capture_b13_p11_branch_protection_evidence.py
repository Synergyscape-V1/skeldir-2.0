#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import urllib.error
import urllib.request


DEFAULT_REQUIRED_CONTEXT = "B1.3 P11 E2E System Proofs"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture B1.3-P11 branch-protection evidence")
    parser.add_argument(
        "--required-checks-contract",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument("--workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument("--required-context", default=DEFAULT_REQUIRED_CONTEXT)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--output", default="artifacts/b13_p11/p11_branch_protection_evidence.json")
    parser.add_argument("--require-live", action="store_true")
    return parser.parse_args()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_workflow_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _fetch_required_status_checks(*, repository: str, branch: str, token: str) -> dict:
    url = f"https://api.github.com/repos/{repository}/branches/{branch}/protection/required_status_checks"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "skeldir-b13-p11-branch-protection-capture",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    args = _parse_args()
    contract_path = Path(args.required_checks_contract)
    workflow_path = Path(args.workflow_file)
    output_path = Path(args.output)

    missing = [str(path) for path in (contract_path, workflow_path) if not path.exists()]
    if missing:
        print("B1.3-P11 branch-protection evidence capture failed:")
        for item in missing:
            print(f"  - missing file: {item}")
        return 1

    contract = _load_json(contract_path)
    workflow_text = _load_workflow_text(workflow_path)
    repository = (args.repository or str(contract.get("repository") or "")).strip()
    if not repository:
        print("B1.3-P11 branch-protection evidence capture failed: repository is required")
        return 1

    expected_contexts = contract.get("required_contexts")
    if not isinstance(expected_contexts, list):
        print("B1.3-P11 branch-protection evidence capture failed: required_contexts missing from contract")
        return 1

    required_context = str(args.required_context).strip()
    token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    now = datetime.now(timezone.utc).isoformat()

    payload: dict[str, object] = {
        "captured_at_utc": now,
        "repository": repository,
        "branch": args.branch,
        "required_context": required_context,
        "contract_path": str(contract_path),
        "workflow_path": str(workflow_path),
    }

    try:
        if not token:
            raise RuntimeError("missing GH_TOKEN/GITHUB_TOKEN")
        live = _fetch_required_status_checks(repository=repository, branch=args.branch, token=token)
        contexts = live.get("contexts")
        if not isinstance(contexts, list):
            raise RuntimeError("live required_status_checks payload missing contexts list")
        strict_live = bool(live.get("strict"))
        payload.update(
            {
                "authority_mode": "live_branch_protection_api",
                "live_required_status_checks": live,
                "required_context_present_in_live": required_context in contexts,
                "required_context_present_in_contract": required_context in expected_contexts,
                "required_context_present_in_workflow": required_context in workflow_text,
                "strict_live": strict_live,
            }
        )
    except Exception as exc:
        if args.require_live:
            print("B1.3-P11 branch-protection evidence capture failed:")
            print(f"  - live branch-protection fetch required but unavailable: {exc}")
            return 1
        payload.update(
            {
                "authority_mode": "fallback_workflow_contract_only",
                "live_api_error": str(exc),
                "required_context_present_in_contract": required_context in expected_contexts,
                "required_context_present_in_workflow": required_context in workflow_text,
                "strict_contract": bool(contract.get("strict_required", True)),
            }
        )

    _write_json(output_path, payload)

    required_in_contract = bool(payload.get("required_context_present_in_contract"))
    required_in_workflow = bool(payload.get("required_context_present_in_workflow"))
    required_in_live = bool(payload.get("required_context_present_in_live"))
    authority_mode = str(payload.get("authority_mode") or "")

    if not required_in_contract:
        print("B1.3-P11 branch-protection evidence capture failed: required context absent from contract")
        return 1
    if not required_in_workflow:
        print("B1.3-P11 branch-protection evidence capture failed: required context absent from workflow")
        return 1
    if authority_mode == "live_branch_protection_api" and not required_in_live:
        print("B1.3-P11 branch-protection evidence capture failed: required context absent from live branch protection")
        return 1

    print("B1.3-P11 branch-protection evidence captured.")
    print(f"  authority_mode={authority_mode}")
    print(f"  output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
