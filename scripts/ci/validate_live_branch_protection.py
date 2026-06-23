#!/usr/bin/env python3
"""Validate live GitHub required contexts against the local contract."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
DEFAULT_OUTPUT = ROOT / "artifacts/b24_p11_live_branch_protection.json"
DEFAULT_SUMMARY = ROOT / "artifacts/b24_p11_ci_gate_matrix.json"
CONTRACT_RELATIVE = "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
TOKEN_ENV_NAMES = ("GH_TOKEN", "GITHUB_TOKEN")


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


def _load_trusted_baseline_contract(path: Path | None = None) -> dict[str, Any]:
    if path:
        return _load_contract(path)
    git_path = CONTRACT_RELATIVE
    for command in (
        ["git", "show", f"origin/main:{git_path}"],
        ["git", "show", f"refs/remotes/origin/main:{git_path}"],
    ):
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=30)
        if completed.returncode == 0:
            data = json.loads(completed.stdout)
            _require(isinstance(data, dict), "trusted baseline contract must be a JSON object")
            _require(isinstance(data.get("required_contexts"), list), "trusted baseline missing required_contexts")
            return data
    fetch = subprocess.run(
        ["git", "fetch", "--no-tags", "--depth=1", "origin", "main:refs/remotes/origin/main"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )
    if fetch.returncode != 0:
        raise ValidationError(f"unable to fetch trusted origin/main baseline: {fetch.stderr.strip()}")
    completed = subprocess.run(
        ["git", "show", f"origin/main:{git_path}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    if completed.returncode != 0:
        raise ValidationError(f"unable to load trusted origin/main baseline: {completed.stderr.strip()}")
    data = json.loads(completed.stdout)
    _require(isinstance(data, dict), "trusted baseline contract must be a JSON object")
    _require(isinstance(data.get("required_contexts"), list), "trusted baseline missing required_contexts")
    return data


def _live_token() -> str | None:
    for name in TOKEN_ENV_NAMES:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _assert_no_live_token() -> None:
    present = [name for name in TOKEN_ENV_NAMES if os.environ.get(name)]
    _require(not present, f"PR mode must not receive live enforcement token variables: {present}")


def _resolve_mode(mode: str) -> str:
    if mode != "auto":
        return mode
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    ref = os.environ.get("GITHUB_REF", "")
    if event == "pull_request":
        return "pr"
    if ref == "refs/heads/main":
        return "main"
    return "pr"


def _context_delta(baseline: dict[str, Any], proposed: dict[str, Any]) -> dict[str, list[str]]:
    baseline_contexts = {str(item) for item in baseline["required_contexts"]}
    proposed_contexts = {str(item) for item in proposed["required_contexts"]}
    removed = sorted(baseline_contexts - proposed_contexts)
    added = sorted(proposed_contexts - baseline_contexts)
    return {"added": added, "removed_or_renamed": removed}


def _validate_pr_mode(
    *,
    contract_path: Path,
    output_path: Path,
    baseline_contract_path: Path | None,
    summary_path: Path | None,
) -> dict[str, Any]:
    _assert_no_live_token()
    proposed = _load_contract(contract_path)
    baseline = _load_trusted_baseline_contract(baseline_contract_path)
    _require(proposed["repository"] == baseline["repository"], "proposed contract repository diverges from baseline")
    _require(proposed["branch"] == baseline["branch"], "proposed contract branch diverges from baseline")
    delta = _context_delta(baseline, proposed)
    _require(
        not delta["removed_or_renamed"],
        f"PR required-status governance delta removes or renames required contexts: {delta['removed_or_renamed']}",
    )
    payload = {
        "schema_version": "b24-p11-live-branch-protection-v2",
        "mode": "pr",
        "repository": proposed["repository"],
        "branch": proposed["branch"],
        "commit_sha": os.environ.get("GITHUB_SHA", "local"),
        "run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "timestamp": datetime.now(UTC).isoformat(),
        "trusted_baseline_source": str(baseline_contract_path) if baseline_contract_path else "origin/main",
        "proposed_context_count": len(proposed["required_contexts"]),
        "baseline_context_count": len(baseline["required_contexts"]),
        "added_contexts": delta["added"],
        "removed_or_renamed_contexts": [],
        "live_enforcement_query_performed": False,
        "pr_safe_validation_verified": True,
        "live_required_status_verified": False,
        "credential_isolation_verified": True,
        "required_status_addition_deadlock_avoided": True,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if summary_path and summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["live_enforcement_status"] = "pr_safe_baseline_validated"
        summary["live_enforcement_mode"] = "pr"
        for phase in summary.get("phases", []):
            phase["live_required_status_verified"] = False
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return payload


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
    fetch_live: Callable[[str, str, str | None], dict[str, Any]] | None = None,
    mode: str = "auto",
    baseline_contract_path: Path | None = None,
) -> dict[str, Any]:
    resolved_mode = _resolve_mode(mode)
    if resolved_mode == "pr":
        return _validate_pr_mode(
            contract_path=contract_path,
            output_path=output_path,
            baseline_contract_path=baseline_contract_path,
            summary_path=summary_path,
        )
    _require(resolved_mode == "main", f"unsupported live branch protection mode: {mode}")
    contract = _load_contract(contract_path)
    expected = set(str(item) for item in contract["required_contexts"])
    repository = str(contract["repository"])
    branch = str(contract["branch"])
    if mock_live_path:
        live = json.loads(mock_live_path.read_text(encoding="utf-8"))
    elif fetch_live:
        token = _live_token()
        live = fetch_live(repository, branch, token)
    else:
        token = _live_token()
        _require(token is not None, "missing live enforcement token for main mode")
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
        "mode": "main",
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
        "trusted_live_enforcement_verified": True,
        "credential_boundary": "main-only read-only GitHub token",
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


def _expect_failure(name: str, func: Any, expected: str) -> dict[str, str]:
    try:
        func()
    except ValidationError as exc:
        _require(expected.lower() in str(exc).lower(), f"{name} failed for wrong reason: {exc}")
        result = {
            "name": name,
            "status": "pass",
            "expected_failure_reason": expected,
            "observed_failure_reason": str(exc),
        }
        print(f"B24_P11_NEGATIVE_CONTROL_PASS {name}: {exc}")
        return result
    else:
        raise ValidationError(f"negative control did not fail: {name}")


def run_negative_controls(contract_path: Path) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    contract = _load_contract(contract_path)
    expected = list(str(item) for item in contract["required_contexts"])
    with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as temp:
        base = Path(temp)
        live = base / "live.json"
        good = {"classic": {"contexts": expected, "strict": True}, "rulesets": []}
        _write_json(live, good)
        validate_live(contract_path=contract_path, output_path=base / "good.json", mock_live_path=live, summary_path=None, mode="main")
        results.append(
            _expect_failure(
                "api_unreadable",
                lambda: validate_live(
                    contract_path=contract_path,
                    output_path=base / "api_unreadable.json",
                    fetch_live=lambda _repository, _branch, _token: (_ for _ in ()).throw(
                        ValidationError("GitHub API unreadable for injected transport failure")
                    ),
                    summary_path=None,
                    mode="main",
                ),
                "GitHub API unreadable",
            )
        )
        results.append(
            _expect_failure(
                "permission_denied",
                lambda: validate_live(
                    contract_path=contract_path,
                    output_path=base / "permission_denied.json",
                    fetch_live=lambda _repository, _branch, _token: (_ for _ in ()).throw(
                        ValidationError("GitHub API error 403 permission denied for injected transport failure")
                    ),
                    summary_path=None,
                    mode="main",
                ),
                "permission",
            )
        )
        missing = expected[:-1]
        _write_json(live, {"classic": {"contexts": missing, "strict": True}, "rulesets": []})
        results.append(_expect_failure("missing_context", lambda: validate_live(contract_path=contract_path, output_path=base / "missing.json", mock_live_path=live, summary_path=None, mode="main"), "missing"))
        stale = [*expected, "Obsolete B2.4 Context"]
        _write_json(live, {"classic": {"contexts": stale, "strict": True}, "rulesets": []})
        results.append(_expect_failure("stale_context", lambda: validate_live(contract_path=contract_path, output_path=base / "stale.json", mock_live_path=live, summary_path=None, mode="main"), "extra stale"))
        _write_json(live, {"classic": {"contexts": expected, "strict": False}, "rulesets": []})
        results.append(_expect_failure("strict_disabled", lambda: validate_live(contract_path=contract_path, output_path=base / "strict.json", mock_live_path=live, summary_path=None, mode="main"), "strict"))
        _write_json(live, {"classic": {"message": "requires admin"}, "rulesets": []})
        results.append(_expect_failure("unreadable_payload", lambda: validate_live(contract_path=contract_path, output_path=base / "unreadable.json", mock_live_path=live, summary_path=None, mode="main"), "missing contexts"))
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
        results.append(_expect_failure("ruleset_mismatch", lambda: validate_live(contract_path=contract_path, output_path=base / "ruleset.json", mock_live_path=live, summary_path=None, mode="main"), "ruleset"))
        baseline = base / "baseline_contract.json"
        proposed = base / "proposed_contract.json"
        baseline_payload = dict(contract)
        proposed_payload = dict(contract)
        _write_json(baseline, baseline_payload)
        proposed_payload["required_contexts"] = [*expected, "New Required Context"]
        _write_json(proposed, proposed_payload)
        old_env = {name: os.environ.get(name) for name in TOKEN_ENV_NAMES}
        try:
            for name in TOKEN_ENV_NAMES:
                os.environ.pop(name, None)
            pr_payload = validate_live(
                contract_path=proposed,
                output_path=base / "pr_addition.json",
                baseline_contract_path=baseline,
                summary_path=None,
                mode="pr",
            )
            _require(
                pr_payload["added_contexts"] == ["New Required Context"]
                and pr_payload["live_enforcement_query_performed"] is False,
                "pr_add_context_no_deadlock did not prove PR-safe no-live addition handling",
            )
            print("B24_P11_NEGATIVE_CONTROL_PASS pr_add_context_no_deadlock: proposed addition did not query live main")
            results.append(
                {
                    "name": "pr_add_context_no_deadlock",
                    "status": "pass",
                    "expected_failure_reason": "not applicable - addition allowed in PR mode without live query",
                    "observed_failure_reason": "PR mode recorded added context without live-enforcement query",
                }
            )
            proposed_payload["required_contexts"] = expected[:-1]
            _write_json(proposed, proposed_payload)
            results.append(
                _expect_failure(
                    "pr_required_context_removal",
                    lambda: validate_live(
                        contract_path=proposed,
                        output_path=base / "pr_removal.json",
                        baseline_contract_path=baseline,
                        summary_path=None,
                        mode="pr",
                    ),
                    "removes or renames",
                )
            )
        finally:
            for name, value in old_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
        _write_json(live, {"classic": {"contexts": expected, "strict": True}, "rulesets": []})
        proposed_payload["required_contexts"] = [*expected, "New Required Context"]
        _write_json(proposed, proposed_payload)
        results.append(
            _expect_failure(
                "main_missing_new_required_context",
                lambda: validate_live(
                    contract_path=proposed,
                    output_path=base / "main_missing_new.json",
                    mock_live_path=live,
                    summary_path=None,
                    mode="main",
                ),
                "missing",
            )
        )
        old_env = {name: os.environ.get(name) for name in TOKEN_ENV_NAMES}
        try:
            os.environ["GH_TOKEN"] = "skeldir_pr_mode_token_should_fail"
            os.environ.pop("GITHUB_TOKEN", None)
            results.append(
                _expect_failure(
                    "pr_token_present",
                    lambda: validate_live(
                        contract_path=contract_path,
                        output_path=base / "pr_token_present.json",
                        baseline_contract_path=baseline,
                        summary_path=None,
                        mode="pr",
                    ),
                    "must not receive",
                )
            )
        finally:
            for name, value in old_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
        results.extend(_run_subprocess_credential_controls(contract_path, base))
    return results


def _clean_subprocess_env(*, token: str | None) -> dict[str, str]:
    keep = ("PATH", "SystemRoot", "COMSPEC", "PATHEXT", "TEMP", "TMP", "HOME")
    env = {name: value for name in keep if (value := os.environ.get(name))}
    env["PYTHONIOENCODING"] = "utf-8"
    if token is not None:
        env["GH_TOKEN"] = token
    return env


def _run_validator_subprocess(contract_path: Path, output_path: Path, *, token: str | None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--mode",
            "main",
            "--contract",
            str(contract_path),
            "--output",
            str(output_path),
            "--summary-path",
            "",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=90,
        env=_clean_subprocess_env(token=token),
    )


def _assert_token_not_disclosed(name: str, output: str, token: str | None) -> None:
    forbidden = ["Authorization", "Bearer"]
    if token:
        forbidden.extend([token, token[:12]])
    leaked = [item for item in forbidden if item and item in output]
    _require(not leaked, f"{name} leaked token material: {leaked}")


def _run_subprocess_credential_controls(contract_path: Path, base: Path) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    invalid_token = "skeldir_invalid_token_material_III_1234567890"
    invalid = _run_validator_subprocess(contract_path, base / "subprocess_invalid_token.json", token=invalid_token)
    invalid_output = f"{invalid.stdout}\n{invalid.stderr}"
    _require(invalid.returncode != 0, "subprocess_invalid_token unexpectedly succeeded")
    _require("GitHub API error" in invalid_output or "VALIDATION_FAIL" in invalid_output, "subprocess_invalid_token lacked safe failure reason")
    _assert_token_not_disclosed("subprocess_invalid_token", invalid_output, invalid_token)
    print("B24_P11_NEGATIVE_CONTROL_PASS subprocess_invalid_token: CLI failed closed without token disclosure")
    results.append(
        {
            "name": "subprocess_invalid_token",
            "status": "pass",
            "expected_failure_reason": "invalid token fails closed",
            "observed_failure_reason": "validator subprocess exited nonzero without token disclosure",
        }
    )
    missing = _run_validator_subprocess(contract_path, base / "subprocess_missing_token.json", token=None)
    missing_output = f"{missing.stdout}\n{missing.stderr}"
    _require(missing.returncode != 0, "subprocess_missing_token unexpectedly succeeded")
    _require("missing live enforcement token" in missing_output, "subprocess_missing_token lacked missing-token failure reason")
    _assert_token_not_disclosed("subprocess_missing_token", missing_output, None)
    print("B24_P11_NEGATIVE_CONTROL_PASS subprocess_missing_token: CLI failed closed with no credential")
    results.append(
        {
            "name": "subprocess_missing_token",
            "status": "pass",
            "expected_failure_reason": "missing token fails closed",
            "observed_failure_reason": "validator subprocess exited nonzero without credential inheritance",
        }
    )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--mock-live-json")
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--negative-control", action="store_true")
    parser.add_argument("--mode", choices=("auto", "pr", "main"), default="auto")
    parser.add_argument("--baseline-contract")
    args = parser.parse_args()
    try:
        contract = ROOT / args.contract
        negative_results: list[dict[str, str]] = []
        if args.negative_control:
            negative_results = run_negative_controls(contract)
        payload = validate_live(
            contract_path=contract,
            output_path=ROOT / args.output,
            mock_live_path=ROOT / args.mock_live_json if args.mock_live_json else None,
            summary_path=ROOT / args.summary_path if args.summary_path else None,
            mode=args.mode,
            baseline_contract_path=ROOT / args.baseline_contract if args.baseline_contract else None,
        )
        if negative_results:
            payload["negative_control_status"] = "pass"
            payload["negative_controls"] = negative_results
            (ROOT / args.output).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except ValidationError as exc:
        print(f"B24_P11_LIVE_BRANCH_PROTECTION_VALIDATION_FAIL: {exc}")
        return 1
    print("B24_P11_LIVE_BRANCH_PROTECTION_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
