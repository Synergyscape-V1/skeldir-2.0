#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
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


def _workflow_text() -> str:
    workflows_dir = Path(".github/workflows")
    parts: list[str] = []
    for path in sorted(workflows_dir.glob("*.yml")):
        parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def _is_main_push(branch: str) -> bool:
    event_name = (os.environ.get("GITHUB_EVENT_NAME") or "").strip().lower()
    ref_name = (os.environ.get("GITHUB_REF_NAME") or "").strip()
    ref = (os.environ.get("GITHUB_REF") or "").strip()
    return event_name == "push" and (ref_name == branch or ref == f"refs/heads/{branch}")


def _context_declared(context: str, workflow_text: str) -> bool:
    if context in workflow_text:
        return True
    match = re.match(r"^Phase Gates \(([^)]+)\)$", context)
    if match:
        phase = match.group(1)
        manifest = Path("docs/phases/phase_manifest.yaml")
        if not manifest.exists():
            return False
        manifest_text = manifest.read_text(encoding="utf-8", errors="replace")
        return "name: Phase Gates" in workflow_text and phase in manifest_text
    return False


def _workflow_fallback_passes(expected: list[str]) -> bool:
    workflow_text = _workflow_text()
    missing_in_workflows = [ctx for ctx in expected if not _context_declared(ctx, workflow_text)]
    if missing_in_workflows:
        print("required status checks fallback failed: expected contexts missing from workflow definitions")
        for context in missing_in_workflows:
            print(f"  - {context}")
        return False

    print("required status checks fallback passed (branch protection API unavailable in this context).")
    return True


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

    expected = contract.get("required_contexts", [])
    strict_expected = bool(contract.get("strict_required", True))
    exact_match = bool(contract.get("exact_match", False))
    hardware_enforcement = contract.get("hardware_enforcement", {})
    deferred_contexts: list[str] = []
    hardware_status = ""
    if isinstance(hardware_enforcement, dict):
        hardware_status = str(hardware_enforcement.get("status", "")).strip().lower()
        if hardware_status == "deferred":
            raw_deferred = hardware_enforcement.get("deferred_contexts", [])
            if isinstance(raw_deferred, list):
                deferred_contexts = [ctx for ctx in raw_deferred if isinstance(ctx, str)]

    require_live_on_main_push = hardware_status == "enforced" and _is_main_push(branch)
    allow_workflow_token_fallback = (
        os.environ.get("SKELDIR_REQUIRED_CHECKS_ALLOW_WORKFLOW_TOKEN_FALLBACK", "")
        .strip()
        .lower()
        in {"1", "true", "yes"}
    )
    unexpected_deferred = [ctx for ctx in deferred_contexts if ctx not in expected]
    if unexpected_deferred:
        print("required status checks contract invalid: deferred contexts must be part of required_contexts")
        for context in unexpected_deferred:
            print(f"  - {context}")
        return 1

    expected_for_live = [ctx for ctx in expected if ctx not in deferred_contexts]

    try:
        payload = _fetch_required_status_checks(repo=repo, branch=branch, token=token)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if require_live_on_main_push and exc.code == 401 and allow_workflow_token_fallback:
            # GitHub's default Actions token cannot be granted repository
            # Administration read access, which the branch-protection endpoint
            # requires. Preserve CI coverage by proving the required contexts
            # remain declared, while out-of-band closure evidence records the
            # live branch-protection API result with an admin-capable token.
            print(
                "required status checks live API returned HTTP 401 for the workflow token; "
                "using explicit workflow-declaration fallback."
            )
            return 0 if _workflow_fallback_passes(expected) else 1
        if require_live_on_main_push:
            print(
                "required status checks enforcement failed: "
                f"live branch-protection required on main push (HTTP {exc.code})"
            )
            print(body)
            return 1
        if exc.code not in {403, 404}:
            print(f"failed to fetch branch protection required checks (HTTP {exc.code}): {body}")
            return 1

        # PR-scoped GitHub tokens commonly cannot access branch-protection APIs.
        # Fallback proves required check names are declared in workflow sources.
        return 0 if _workflow_fallback_passes(expected) else 1
    except Exception as exc:  # pragma: no cover - defensive runtime path
        if require_live_on_main_push:
            print(
                "required status checks enforcement failed: "
                f"live branch-protection required on main push: {exc}"
            )
            return 1
        print(f"failed to fetch branch protection required checks: {exc}")
        return 1

    actual = payload.get("contexts", [])
    missing = [ctx for ctx in expected_for_live if ctx not in actual]
    allowed_actual = set(expected_for_live).union(deferred_contexts)
    extra = [ctx for ctx in actual if ctx not in allowed_actual]
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

    deferred_missing_live = [ctx for ctx in deferred_contexts if ctx not in actual]
    if deferred_missing_live:
        print("required status checks note: deferred hardware contexts are not yet live-enforced")
        for context in deferred_missing_live:
            print(f"  - {context}")

    if exact_match and extra:
        print("required status checks enforcement failed: unexpected extra contexts present")
        for context in extra:
            print(f"  - {context}")
        print("expected contexts:")
        for context in expected:
            print(f"  - {context}")
        return 1

    print("required status checks enforcement passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
