#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _load_contract(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fetch_required_status_checks(repo: str, branch: str, token: str) -> dict:
    url = f"https://api.github.com/repos/{repo}/branches/{branch}/protection/required_status_checks"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "skeldir-ci-required-checks-enforcer",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    contract_path = Path(
        os.environ.get(
            "REQUIRED_STATUS_CHECKS_CONTRACT",
            "contracts-internal/governance/b03_phase2_required_status_checks.main.json",
        )
    )
    if not contract_path.exists():
        print(f"required status checks contract not found: {contract_path}")
        return 2

    contract = _load_contract(contract_path)
    repo = os.environ.get("GITHUB_REPOSITORY", contract.get("repository"))
    branch = os.environ.get("REQUIRED_STATUS_CHECKS_BRANCH", contract.get("branch", "main"))
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

    if not repo:
        print("repository is not set (GITHUB_REPOSITORY or contract.repository)")
        return 2
    if not token:
        print("GH_TOKEN or GITHUB_TOKEN is required")
        return 2

    try:
        payload = _fetch_required_status_checks(repo=repo, branch=branch, token=token)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"failed to fetch branch protection required checks (HTTP {exc.code}): {body}")
        return 1
    except Exception as exc:  # pragma: no cover - defensive runtime path
        print(f"failed to fetch branch protection required checks: {exc}")
        return 1

    expected = contract.get("required_contexts", [])
    actual = payload.get("contexts", [])
    missing = [ctx for ctx in expected if ctx not in actual]
    strict_expected = bool(contract.get("strict_required", True))
    strict_actual = bool(payload.get("strict"))

    if strict_expected and not strict_actual:
        print("required status checks enforcement failed: strict mode is not enabled")
        return 1

    if missing:
        print("required status checks enforcement failed: missing contexts")
        for context in missing:
            print(f"  - {context}")
        print("actual contexts:")
        for context in actual:
            print(f"  - {context}")
        return 1

    print("required status checks enforcement passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
