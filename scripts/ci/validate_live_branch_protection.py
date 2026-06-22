#!/usr/bin/env python3
"""Validate live GitHub required contexts against the local contract."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
DEFAULT_OUTPUT = ROOT / "artifacts/b24_p11_live_branch_protection.json"
DEFAULT_SUMMARY = ROOT / "artifacts/b24_p11_ci_gate_matrix.json"


class ValidationError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _load_contract(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(data.get("required_contexts"), list), "contract missing required_contexts")
    _require(data.get("repository"), "contract missing repository")
    _require(data.get("branch"), "contract missing branch")
    return data


def _api_json(url: str, *, token: str | None) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "skeldir-b24-p11-live-branch-protection",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ValidationError(f"GitHub API error {exc.code} for {url}") from exc
    except URLError as exc:
        raise ValidationError(f"GitHub API unreadable for {url}: {exc}") from exc


def _gh_json(endpoint: str) -> Any:
    proc = subprocess.run(
        ["gh", "api", endpoint],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise ValidationError(f"gh api unreadable for {endpoint}: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def _fetch_live(repository: str, branch: str, *, token: str | None) -> dict[str, Any]:
    classic_endpoint = f"/repos/{repository}/branches/{branch}/protection/required_status_checks"
    rulesets_endpoint = f"/repos/{repository}/rulesets"
    if token:
        base = "https://api.github.com"
        classic = _api_json(f"{base}{classic_endpoint}", token=token)
        rulesets = _api_json(f"{base}{rulesets_endpoint}", token=token)
    else:
        classic = _gh_json(classic_endpoint)
        rulesets = _gh_json(rulesets_endpoint)
    return {"classic": classic, "rulesets": rulesets}


def _ruleset_contexts(rulesets: Any, branch: str) -> set[str]:
    contexts: set[str] = set()
    if not isinstance(rulesets, list):
        return contexts
    for ruleset in rulesets:
        if not isinstance(ruleset, dict):
            continue
        if ruleset.get("enforcement") == "disabled":
            continue
        conditions = ruleset.get("conditions") or {}
        refs = conditions.get("ref_name") if isinstance(conditions, dict) else {}
        include = refs.get("include", []) if isinstance(refs, dict) else []
        if include and not any(str(item).endswith(branch) or str(item) == branch for item in include):
            continue
        for rule in ruleset.get("rules", []) or []:
            if not isinstance(rule, dict) or rule.get("type") != "required_status_checks":
                continue
            params = rule.get("parameters") or {}
            for check in params.get("required_status_checks", []) or []:
                if isinstance(check, dict) and check.get("context"):
                    contexts.add(str(check["context"]))
    return contexts


def validate_live(
    *,
    contract_path: Path = DEFAULT_CONTRACT,
    output_path: Path = DEFAULT_OUTPUT,
    mock_live_path: Path | None = None,
    summary_path: Path | None = DEFAULT_SUMMARY,
) -> dict[str, Any]:
    contract = _load_contract(contract_path)
    expected = set(str(item) for item in contract["required_contexts"])
    repository = str(contract["repository"])
    branch = str(contract["branch"])
    if mock_live_path:
        live = json.loads(mock_live_path.read_text(encoding="utf-8"))
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        live = _fetch_live(repository, branch, token=token)
    classic = live.get("classic")
    _require(isinstance(classic, dict), "live classic branch-protection payload unreadable")
    live_contexts = classic.get("contexts")
    _require(isinstance(live_contexts, list), "live required_status_checks payload missing contexts list")
    strict = classic.get("strict")
    _require(strict is True, "live required_status_checks strict mode is not enabled")
    actual = set(str(item) for item in live_contexts)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    _require(not missing, f"live branch protection missing required contexts: {missing}")
    _require(not extra, f"live branch protection has extra stale contexts: {extra}")
    ruleset_contexts = _ruleset_contexts(live.get("rulesets", []), branch)
    if ruleset_contexts:
        _require(
            ruleset_contexts == expected,
            "live ruleset contexts diverge from local contract: "
            f"missing={sorted(expected - ruleset_contexts)} extra={sorted(ruleset_contexts - expected)}",
        )
    payload = {
        "schema_version": "b24-p11-live-branch-protection-v1",
        "repository": repository,
        "branch": branch,
        "commit_sha": os.environ.get("GITHUB_SHA", "local"),
        "run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "timestamp": datetime.now(UTC).isoformat(),
        "expected_context_count": len(expected),
        "live_context_count": len(actual),
        "classic_branch_protection_verified": True,
        "ruleset_context_count": len(ruleset_contexts),
        "rulesets_verified": bool(ruleset_contexts),
        "missing_contexts": [],
        "extra_contexts": [],
        "live_required_status_verified": True,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if summary_path and summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["live_enforcement_status"] = "verified"
        for phase in summary.get("phases", []):
            phase["live_required_status_verified"] = True
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _expect_failure(name: str, func: Any, expected: str) -> None:
    try:
        func()
    except ValidationError as exc:
        _require(expected.lower() in str(exc).lower(), f"{name} failed for wrong reason: {exc}")
    else:
        raise ValidationError(f"negative control did not fail: {name}")


def run_negative_controls(contract_path: Path) -> None:
    contract = _load_contract(contract_path)
    expected = list(str(item) for item in contract["required_contexts"])
    with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as temp:
        base = Path(temp)
        live = base / "live.json"
        good = {"classic": {"contexts": expected, "strict": True}, "rulesets": []}
        _write_json(live, good)
        validate_live(contract_path=contract_path, output_path=base / "good.json", mock_live_path=live, summary_path=None)
        missing = expected[:-1]
        _write_json(live, {"classic": {"contexts": missing, "strict": True}, "rulesets": []})
        _expect_failure("missing_context", lambda: validate_live(contract_path=contract_path, output_path=base / "missing.json", mock_live_path=live, summary_path=None), "missing")
        stale = [*expected, "Obsolete B2.4 Context"]
        _write_json(live, {"classic": {"contexts": stale, "strict": True}, "rulesets": []})
        _expect_failure("stale_context", lambda: validate_live(contract_path=contract_path, output_path=base / "stale.json", mock_live_path=live, summary_path=None), "extra stale")
        _write_json(live, {"classic": {"contexts": expected, "strict": False}, "rulesets": []})
        _expect_failure("strict_disabled", lambda: validate_live(contract_path=contract_path, output_path=base / "strict.json", mock_live_path=live, summary_path=None), "strict")
        _write_json(live, {"classic": {"message": "requires admin"}, "rulesets": []})
        _expect_failure("unreadable_payload", lambda: validate_live(contract_path=contract_path, output_path=base / "unreadable.json", mock_live_path=live, summary_path=None), "missing contexts")
        rulesets = [
            {
                "enforcement": "active",
                "conditions": {"ref_name": {"include": ["refs/heads/main"]}},
                "rules": [
                    {
                        "type": "required_status_checks",
                        "parameters": {"required_status_checks": [{"context": expected[0]}]},
                    }
                ],
            }
        ]
        _write_json(live, {"classic": {"contexts": expected, "strict": True}, "rulesets": rulesets})
        _expect_failure("ruleset_mismatch", lambda: validate_live(contract_path=contract_path, output_path=base / "ruleset.json", mock_live_path=live, summary_path=None), "ruleset")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--mock-live-json")
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    try:
        contract = ROOT / args.contract
        if args.negative_control:
            run_negative_controls(contract)
        validate_live(
            contract_path=contract,
            output_path=ROOT / args.output,
            mock_live_path=ROOT / args.mock_live_json if args.mock_live_json else None,
            summary_path=ROOT / args.summary_path if args.summary_path else None,
        )
    except ValidationError as exc:
        print(f"B24_P11_LIVE_BRANCH_PROTECTION_VALIDATION_FAIL: {exc}")
        return 1
    print("B24_P11_LIVE_BRANCH_PROTECTION_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
