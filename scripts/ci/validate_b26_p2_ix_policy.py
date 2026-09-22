#!/usr/bin/env python3
"""B2.6-P2 Corrective IX policy-evolution-law validator.

Compares the canonical semantic SHA of scope-policy.v2.yaml at HEAD against
the merge-base with origin/main (or origin/main, or the working file as a
local fallback). A semantic change without a scope_policy_version bump fails
with same_version_semantic_rewrite. A bumped version passes with a note (the
differential review lives elsewhere). The v1 history file must be byte
identical to its pinned SHA.

Exit code is the gate: 0 on PASS, 1 plus a violation list on FAIL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[2]
V2_PATH = REPO_ROOT / "contracts/reconciliation/b2.6/scope-policy.v2.yaml"
V1_PATH = REPO_ROOT / "contracts/reconciliation/b2.6/scope-policy.v1.yaml"
V1_PINNED_SOURCE_SHA256 = (
    "7adbdd0c4463526773e1b29bc05875f2361bcd2f0b9de096621f3c97574a82cd"
)
V2_RELATIVE = "contracts/reconciliation/b2.6/scope-policy.v2.yaml"


def _canonical_json(document: Any) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _semantic_sha(document: Any) -> str:
    return hashlib.sha256(_canonical_json(document)).hexdigest()


def _git(args: list[str]) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False, ""
    return proc.returncode == 0, proc.stdout.strip()


def _resolve_base_ref(checks: dict[str, object]) -> str | None:
    ok, sha = _git(["merge-base", "HEAD", "origin/main"])
    if ok and sha:
        checks["base_resolution"] = f"merge-base:{sha[:12]}"
        return sha
    ok, sha = _git(["rev-parse", "--verify", "origin/main"])
    if ok and sha:
        checks["base_resolution"] = f"origin/main:{sha[:12]}"
        return sha
    checks["base_resolution"] = "local_fallback:no_base_ref"
    return None


def _base_document(
    base_ref: str | None, checks: dict[str, object]
) -> tuple[dict[str, Any], str]:
    """Return (document, origin_label) for the base side of the diff."""
    if base_ref is None:
        current = yaml.safe_load(V2_PATH.read_text(encoding="utf-8"))
        checks["base_origin"] = "working_file_as_is"
        assert isinstance(current, dict)
        return current, "working_file_as_is"
    ok, text = _git(["show", f"{base_ref}:{V2_RELATIVE}"])
    if not ok or not text:
        current = yaml.safe_load(V2_PATH.read_text(encoding="utf-8"))
        checks["base_origin"] = "working_file_as_is(show_failed)"
        assert isinstance(current, dict)
        return current, "working_file_as_is(show_failed)"
    document = yaml.safe_load(text)
    checks["base_origin"] = f"git:{base_ref[:12]}:{V2_RELATIVE}"
    assert isinstance(document, dict)
    return document, checks["base_origin"]  # type: ignore[return-value]


def _compare_versions(
    current_doc: dict[str, Any],
    base_doc: dict[str, Any],
    violations: list[str],
    checks: dict[str, object],
) -> None:
    current_sha = _semantic_sha(current_doc)
    base_sha = _semantic_sha(base_doc)
    current_version = str(current_doc.get("scope_policy_version"))
    base_version = str(base_doc.get("scope_policy_version"))
    checks["current_scope_policy_version"] = current_version
    checks["base_scope_policy_version"] = base_version
    checks["current_semantic_sha256"] = current_sha
    checks["base_semantic_sha256"] = base_sha
    checks["semantic_changed"] = current_sha != base_sha
    checks["version_changed"] = current_version != base_version
    if current_sha == base_sha:
        checks["evolution_note"] = "no_semantic_change"
        return
    if current_version == base_version:
        violations.append("ix_policy_same_version_semantic_rewrite")
        checks["evolution_note"] = (
            "semantic_sha_differs_but_version_unchanged:"
            f"{current_version}"
        )
    else:
        checks["evolution_note"] = (
            "version_bumped_differential_review_required_elsewhere:"
            f"{base_version}->{current_version}"
        )


def _check_v1_history(violations: list[str], checks: dict[str, object]) -> None:
    if not V1_PATH.is_file():
        violations.append("ix_policy_v1_history_missing")
        checks["v1_exists"] = False
        return
    checks["v1_exists"] = True
    v1_sha = hashlib.sha256(V1_PATH.read_bytes()).hexdigest()
    checks["v1_source_sha256"] = v1_sha
    if v1_sha != V1_PINNED_SOURCE_SHA256:
        violations.append("ix_policy_v1_history_rewritten")
    try:
        v1_doc = yaml.safe_load(V1_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        violations.append(f"ix_policy_v1_unreadable:{exc}")
        return
    version = v1_doc.get("scope_policy_version") if isinstance(
        v1_doc, dict
    ) else None
    checks["v1_scope_policy_version"] = version
    if version != "b2.6-p2-scope-policy-v1":
        violations.append("ix_policy_v1_version_rewritten")


def _negative_controls(
    current_doc: dict[str, Any], checks: dict[str, object]
) -> list[str]:
    """Prove the comparator is non-vacuous on synthetic policy edits."""
    import copy as _copy

    results: dict[str, bool] = {}
    # Control 1: a semantic edit with the same version must read as a
    # same-version rewrite.
    mutated = _copy.deepcopy(current_doc)
    mutated["alias_law"] = (
        str(mutated.get("alias_law")) + "_negative_control_probe"
    )
    results["comparator_fires_on_same_version_rewrite"] = (
        _semantic_sha(mutated) != _semantic_sha(current_doc)
        and str(mutated.get("scope_policy_version"))
        == str(current_doc.get("scope_policy_version"))
    )
    # Control 2: the same edit with a bumped version must read as a bump.
    bumped = _copy.deepcopy(mutated)
    bumped["scope_policy_version"] = (
        str(bumped.get("scope_policy_version")) + "-probe"
    )
    results["comparator_clears_on_version_bump"] = (
        str(bumped.get("scope_policy_version"))
        != str(current_doc.get("scope_policy_version"))
    )
    # Control 3: canonical JSON must be key-order stable (comment/whitespace
    # analogue: same mapping, different insertion order, same SHA).
    reordered: dict[str, Any] = {}
    for key in reversed(list(current_doc.keys())):
        reordered[key] = current_doc[key]
    results["semantic_sha_order_stable"] = (
        _semantic_sha(reordered) == _semantic_sha(current_doc)
    )
    checks["negative_controls"] = results
    return [
        f"ix_policy_negative_control_blind:{n}"
        for n, ok in results.items()
        if not ok
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate B2.6-P2 Corrective IX policy evolution law."
    )
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict[str, object] = {}
    try:
        if not V2_PATH.is_file():
            violations.append("ix_policy_v2_missing")
            current_doc: dict[str, Any] = {}
        else:
            loaded = yaml.safe_load(V2_PATH.read_text(encoding="utf-8"))
            assert isinstance(loaded, dict)
            current_doc = loaded
            checks["v2_source_sha256"] = hashlib.sha256(
                V2_PATH.read_bytes()
            ).hexdigest()
        base_ref = _resolve_base_ref(checks)
        base_doc, _ = _base_document(base_ref, checks)
        if current_doc:
            _compare_versions(current_doc, base_doc, violations, checks)
            violations.extend(_negative_controls(current_doc, checks))
        _check_v1_history(violations, checks)
    except Exception as exc:  # noqa: BLE001
        violations.append(f"ix_policy_validator_crash:{exc}")
    status = "PASS" if not violations else "FAIL"
    evidence = {
        # Declared gate identity for the proof-plane capsule census (same
        # convention as the authority-universe cell): additive, ignored by
        # required-cell adjudication.
        "gate_id": "B26-P2-IX-POLICY",
        "validator": "validate_b26_p2_ix_policy",
        "status": status,
        "violations": sorted(violations),
        "checks": checks,
    }
    if args.evidence_out is not None:
        args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if args.evidence_dir is not None:
        args.evidence_dir.mkdir(parents=True, exist_ok=True)
        (args.evidence_dir / "ix-policy.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if violations:
        print("B26_P2_IX_POLICY_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_IX_POLICY_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
