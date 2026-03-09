#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_SECURE_PATHS = (
    "backend/app/security/auth.py",
    "backend/app/core/secrets.py",
    "backend/app/services/platform_credentials.py",
    "backend/app/api/platforms.py",
    "contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    "contracts-internal/governance/b13_p0_provider_capability_matrix.main.json",
    ".github/workflows/ci.yml",
)


@dataclass(frozen=True)
class CodeownersRule:
    pattern: str
    owners: tuple[str, ...]


def _normalize_pattern(pattern: str) -> str:
    value = pattern.strip()
    if value.startswith("/"):
        value = value[1:]
    return value


def _pattern_matches(pattern: str, path: str) -> bool:
    norm = _normalize_pattern(pattern)
    if not norm:
        return False
    if norm.endswith("/"):
        return path.startswith(norm)

    candidate = PurePosixPath(path)
    if candidate.match(norm):
        return True
    if path == norm:
        return True
    if norm.startswith("**/") and candidate.match(norm[3:]):
        return True
    return False


def _parse_codeowners(path: Path) -> list[CodeownersRule]:
    rules: list[CodeownersRule] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            raise ValueError(f"Invalid CODEOWNERS rule at line {line_no}: {raw}")
        pattern = parts[0]
        owners = tuple(parts[1:])
        rules.append(CodeownersRule(pattern=pattern, owners=owners))
    if not rules:
        raise ValueError("CODEOWNERS has no active rules")
    return rules


def _owners_for_path(rules: list[CodeownersRule], path: str) -> tuple[str, ...]:
    owners: tuple[str, ...] = tuple()
    for rule in rules:
        if _pattern_matches(rule.pattern, path):
            owners = rule.owners
    return owners


def _github_get(url: str, token: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "skeldir-b13-p0-codeowners-gate",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="B1.3-P0 CODEOWNERS + review governance enforcement")
    parser.add_argument("--codeowners-file", default=".github/CODEOWNERS")
    parser.add_argument("--required-owner", default="@Muk223")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", "Synergyscape-V1/skeldir-2.0"))
    parser.add_argument("--branch", default="main")
    parser.add_argument(
        "--codeowners-ref",
        default=(
            os.environ.get("ADJUDICATED_SHA")
            or os.environ.get("GITHUB_SHA")
            or os.environ.get("REQUIRED_STATUS_CHECKS_REF")
            or "main"
        ),
    )
    parser.add_argument("--skip-github-api", action="store_true")
    parser.add_argument("--allow-api-unavailable", action="store_true")
    args = parser.parse_args()

    codeowners_path = (REPO_ROOT / args.codeowners_file).resolve()
    if not codeowners_path.exists():
        print(f"B1.3-P0 CODEOWNERS gate failed: file not found {codeowners_path}")
        return 1

    try:
        rules = _parse_codeowners(codeowners_path)
    except ValueError as exc:
        print(f"B1.3-P0 CODEOWNERS gate failed: {exc}")
        return 1

    errors: list[str] = []

    for required_path in REQUIRED_SECURE_PATHS:
        owners = _owners_for_path(rules, required_path)
        if not owners:
            errors.append(f"Missing CODEOWNERS coverage for secure path: {required_path}")
            continue
        if args.required_owner not in owners:
            errors.append(
                "Required security owner missing for secure path: "
                f"{required_path} owners={owners} required={args.required_owner}"
            )

    for rule in rules:
        for owner in rule.owners:
            if not owner.startswith("@"):
                errors.append(f"Invalid owner reference (must start with @): pattern={rule.pattern} owner={owner}")

    if not args.skip_github_api:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            if args.allow_api_unavailable:
                print("B1.3-P0 CODEOWNERS gate warning: GH token unavailable, skipping live API checks")
            else:
                errors.append("GH_TOKEN or GITHUB_TOKEN is required for live CODEOWNERS/review-policy checks")
        else:
            repo = args.repository
            codeowners_url = (
                f"https://api.github.com/repos/{repo}/codeowners/errors?ref={args.codeowners_ref}"
            )
            protection_url = f"https://api.github.com/repos/{repo}/branches/{args.branch}/protection"
            try:
                codeowners_errors_payload = _github_get(codeowners_url, token)
                codeowners_errors = codeowners_errors_payload.get("errors", [])
                if codeowners_errors:
                    errors.append(
                        "GitHub CODEOWNERS parser reports errors: "
                        + "; ".join(str(item.get("message", item)) for item in codeowners_errors)
                    )

                protection = _github_get(protection_url, token)
                review_policy = protection.get("required_pull_request_reviews") or {}
                require_code_owner_reviews = bool(review_policy.get("require_code_owner_reviews", False))
                required_approvals = int(review_policy.get("required_approving_review_count", 0))

                if not require_code_owner_reviews:
                    errors.append("Branch protection must set require_code_owner_reviews=true")
                if required_approvals < 1:
                    errors.append("Branch protection must set required_approving_review_count >= 1")
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if args.allow_api_unavailable and exc.code in {403, 404}:
                    print(
                        "B1.3-P0 CODEOWNERS gate warning: GitHub API unavailable in this context "
                        f"(HTTP {exc.code}); continuing due to --allow-api-unavailable"
                    )
                else:
                    errors.append(f"GitHub API call failed (HTTP {exc.code}): {body}")
            except Exception as exc:  # pragma: no cover - defensive path
                if args.allow_api_unavailable:
                    print(
                        "B1.3-P0 CODEOWNERS gate warning: unexpected live API failure "
                        f"({exc}); continuing due to --allow-api-unavailable"
                    )
                else:
                    errors.append(f"Unexpected GitHub API failure: {exc}")

    if errors:
        print("B1.3-P0 CODEOWNERS gate failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("B1.3-P0 CODEOWNERS gate passed.")
    print(f"  required_owner={args.required_owner}")
    for required_path in REQUIRED_SECURE_PATHS:
        owners = _owners_for_path(rules, required_path)
        print(f"  {required_path}: {', '.join(owners)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
