#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enforce main branch-protection integrity contract")
    parser.add_argument(
        "--contract-file",
        default="contracts-internal/governance/main_branch_protection_integrity.main.json",
    )
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--branch", default=None)
    parser.add_argument("--protection-json", default=None)
    parser.add_argument("--allow-api-unavailable", action="store_true")
    parser.add_argument("--run-negative-control", action="store_true")
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            return json.loads(path.read_text(encoding=encoding))
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("utf-8", b"", 0, 1, f"unable to decode JSON file: {path}")


def _fetch_branch_protection(repo: str, branch: str, token: str) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{repo}/branches/{branch}/protection"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "skeldir-branch-protection-integrity-enforcer",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _is_main_push(branch: str) -> bool:
    event_name = (os.environ.get("GITHUB_EVENT_NAME") or "").strip().lower()
    ref_name = (os.environ.get("GITHUB_REF_NAME") or "").strip()
    ref = (os.environ.get("GITHUB_REF") or "").strip()
    return event_name == "push" and (ref_name == branch or ref == f"refs/heads/{branch}")


def _allowance_values(allowances: Any, key: str) -> list[Any]:
    if not isinstance(allowances, dict):
        return []
    value = allowances.get(key)
    if isinstance(value, list):
        return value
    return []


def _validate_integrity(
    *,
    protection: dict[str, Any],
    contract: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    review_policy = protection.get("required_pull_request_reviews")
    if not isinstance(review_policy, dict):
        errors.append("branch protection missing required_pull_request_reviews object")
        return errors

    contract_review = contract.get("review_policy")
    if not isinstance(contract_review, dict):
        errors.append("contract missing review_policy object")
        return errors

    min_approvals = int(contract_review.get("required_approving_review_count_min", 1))
    required_approvals = int(review_policy.get("required_approving_review_count", 0))
    if required_approvals < min_approvals:
        errors.append(
            "required_approving_review_count must be >= "
            f"{min_approvals}; observed={required_approvals}"
        )

    expected_codeowners = bool(contract_review.get("require_code_owner_reviews", True))
    observed_codeowners = bool(review_policy.get("require_code_owner_reviews", False))
    if observed_codeowners != expected_codeowners:
        errors.append(
            "require_code_owner_reviews mismatch: "
            f"expected={expected_codeowners} observed={observed_codeowners}"
        )

    require_enforce_admins = bool(contract.get("enforce_admins_required", True))
    if require_enforce_admins:
        enforce_admins = protection.get("enforce_admins")
        enabled = bool(enforce_admins.get("enabled")) if isinstance(enforce_admins, dict) else False
        if not enabled:
            errors.append("enforce_admins.enabled must be true")

    forbid_bypass = bool(contract.get("forbid_bypass_pull_request_allowances", True))
    if forbid_bypass:
        allowances = review_policy.get("bypass_pull_request_allowances")
        users = _allowance_values(allowances, "users")
        teams = _allowance_values(allowances, "teams")
        apps = _allowance_values(allowances, "apps")
        if users or teams or apps:
            errors.append(
                "bypass_pull_request_allowances must be empty "
                f"(users={len(users)} teams={len(teams)} apps={len(apps)})"
            )

    return errors


def main() -> int:
    args = _parse_args()
    contract_path = Path(args.contract_file)
    if not contract_path.exists():
        print(f"branch protection integrity gate failed: contract missing: {contract_path}")
        return 1

    contract = _load_json(contract_path)
    branch = args.branch or str(contract.get("branch") or "main")
    repository = args.repository or str(contract.get("repository") or "").strip()
    if not repository:
        print("branch protection integrity gate failed: repository is required")
        return 1

    if args.run_negative_control:
        contract_review = contract.get("review_policy") or {}
        min_approvals = int(contract_review.get("required_approving_review_count_min", 0))
        expected_codeowners = bool(contract_review.get("require_code_owner_reviews", False))
        forbid_bypass = bool(contract.get("forbid_bypass_pull_request_allowances", True))
        control_payload = {
            "required_pull_request_reviews": {
                "required_approving_review_count": min_approvals,
                "require_code_owner_reviews": expected_codeowners,
                "bypass_pull_request_allowances": {
                    "users": [{"login": "forbidden-bypass"}] if forbid_bypass else [],
                    "teams": [],
                    "apps": [],
                },
            },
            "enforce_admins": {"enabled": bool(contract.get("enforce_admins_required", True))},
        }
        if not forbid_bypass:
            control_payload["required_pull_request_reviews"]["require_code_owner_reviews"] = (
                not expected_codeowners
            )
        errors = _validate_integrity(protection=control_payload, contract=contract)
        if not errors:
            print(
                "branch protection integrity negative control failed: "
                "mutated payload unexpectedly passed validation"
            )
            return 1
        print("branch protection integrity negative control passed.")
        print(f"  detected_errors={len(errors)}")
        return 0

    require_live_on_main = bool(contract.get("require_live_on_main", True))
    require_live_context = require_live_on_main and _is_main_push(branch)

    protection: dict[str, Any]
    source_mode = "live_api"

    if args.protection_json:
        protection_path = Path(args.protection_json)
        if not protection_path.exists():
            print(f"branch protection integrity gate failed: --protection-json missing: {protection_path}")
            return 1
        protection = _load_json(protection_path)
        source_mode = f"fixture:{protection_path}"
    else:
        token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
        if not token:
            if args.allow_api_unavailable:
                scope = "main push" if require_live_context else "non-main context"
                print(
                    "branch protection integrity gate warning: token unavailable; "
                    f"skipping live validation in {scope} due to --allow-api-unavailable"
                )
                return 0
            if require_live_context:
                print("branch protection integrity gate failed: GH_TOKEN/GITHUB_TOKEN required on main push")
                return 1
            print("branch protection integrity gate failed: GH_TOKEN/GITHUB_TOKEN required")
            return 1
        try:
            protection = _fetch_branch_protection(repository, branch, token)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if args.allow_api_unavailable and exc.code in {403, 404}:
                scope = "main push" if require_live_context else "non-main context"
                print(
                    "branch protection integrity gate warning: API unavailable in "
                    f"{scope} (HTTP {exc.code}); skipping live validation due to --allow-api-unavailable"
                )
                return 0
            if require_live_context:
                print(
                    "branch protection integrity gate failed: "
                    f"unable to fetch live branch protection on main push (HTTP {exc.code}): {body}"
                )
                return 1
            print(f"branch protection integrity gate failed: HTTP {exc.code}: {body}")
            return 1
        except Exception as exc:  # pragma: no cover - defensive path
            if args.allow_api_unavailable:
                scope = "main push" if require_live_context else "non-main context"
                print(
                    "branch protection integrity gate warning: API unavailable in "
                    f"{scope}; skipping live validation due to --allow-api-unavailable ({exc})"
                )
                return 0
            if require_live_context:
                print(
                    "branch protection integrity gate failed: "
                    f"unable to fetch live branch protection on main push: {exc}"
                )
                return 1
            print(f"branch protection integrity gate failed: {exc}")
            return 1

    errors = _validate_integrity(protection=protection, contract=contract)
    if errors:
        print("branch protection integrity gate failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    review_policy = protection.get("required_pull_request_reviews") or {}
    approvals = int(review_policy.get("required_approving_review_count", 0))
    codeowners = bool(review_policy.get("require_code_owner_reviews", False))
    enforce_admins = protection.get("enforce_admins") or {}
    enforce_admins_enabled = bool(enforce_admins.get("enabled"))

    print("branch protection integrity gate passed.")
    print(f"  source={source_mode}")
    print(f"  repository={repository}")
    print(f"  branch={branch}")
    print(f"  required_approving_review_count={approvals}")
    print(f"  require_code_owner_reviews={codeowners}")
    print(f"  enforce_admins.enabled={enforce_admins_enabled}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
