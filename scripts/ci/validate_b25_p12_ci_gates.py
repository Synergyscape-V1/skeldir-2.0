#!/usr/bin/env python3
"""B2.5-P12 Plane D: CI meta-validation.

Planes A-C prove trust invariants. This plane proves Planes A-C actually run.

The failure mode it exists for
------------------------------
A test can exist and still prove nothing: skipped, deselected, behind a
condition, never invoked, masked by ``continue-on-error``, or replaced by a
dummy job carrying the right context name. Green CI then means "no job reported
failure", not "the invariant holds". P12-H21 names this directly, and the
Skeldir corpus has hit it before.

So this validator asks the questions a green checkmark cannot answer:

  * Does every required invariant name a validator and workflow that exist?
  * Can a change to a load-bearing trust file evade all relevant proof through
    path filters?
  * Does any B2.5 workflow mask failure with ``continue-on-error``?
  * Do the P12 gates actually invoke their validators with negative controls?
  * Are the declared CI context names stable and unambiguous?

It deliberately does NOT re-run Planes A-C. Duplicating proof adds cost without
epistemic value (P12-H24); the point is to bind the proof that already exists.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = Path("docs/ci/b25_p12_invariant_registry.yaml")
P12_WORKFLOW = Path(".github/workflows/b2_5-p12-ci-gates.yml")

REQUIRED_INVARIANT_COUNT = 22

#: Validators P12 introduces. Each must be invoked with negative controls by the
#: P12 workflow, otherwise the gate is decorative.
P12_VALIDATORS = (
    "scripts/ci/validate_b25_p12_contract_projection.py",
    "scripts/ci/validate_b25_p12_trust_isolation.py",
    "scripts/ci/validate_b25_p12_ci_gates.py",
)

#: Tokens whose presence in a P12 workflow would mask a real failure.
MASKING_TOKENS = ("continue-on-error: true", "|| true", "exit 0  #")


class B25P12CiGateError(RuntimeError):
    """Raised when the CI proof topology is vacuous or incomplete."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise B25P12CiGateError(reason)


def _text(path: Path, overrides: dict[Path, str] | None = None) -> str:
    overrides = overrides or {}
    if path in overrides:
        return overrides[path]
    return (ROOT / path).read_text(encoding="utf-8")


def _yaml(path: Path, overrides: dict[Path, str] | None = None) -> Any:
    return yaml.safe_load(_text(path, overrides))


def validate_registry_completeness(
    overrides: dict[Path, str] | None = None,
) -> int:
    """Every required invariant must name proof that physically exists."""
    registry = _yaml(REGISTRY, overrides)
    invariants = registry.get("invariants") or []
    _require(
        len(invariants) == REQUIRED_INVARIANT_COUNT,
        f"invariant_registry_incomplete:{len(invariants)}/{REQUIRED_INVARIANT_COUNT}",
    )

    ids = [row.get("id") for row in invariants]
    _require(
        sorted(ids) == list(range(1, REQUIRED_INVARIANT_COUNT + 1)),
        f"invariant_ids_not_contiguous:{sorted(ids)}",
    )

    checks = 0
    for row in invariants:
        ident = row.get("id")
        _require(bool(row.get("invariant")), f"invariant_missing_name:{ident}")
        _require(
            row.get("plane") in {"A", "B", "C", "D"},
            f"invariant_missing_plane:{ident}",
        )
        _require(
            row.get("proof_owner") in {"p12", "inherited"},
            f"invariant_missing_proof_owner:{ident}",
        )
        _require(
            bool(row.get("negative_control")), f"invariant_missing_control:{ident}"
        )

        validator = row.get("validator")
        _require(
            isinstance(validator, str) and validator,
            f"invariant_missing_validator:{ident}",
        )
        _require(
            (ROOT / validator).exists(),
            f"invariant_validator_missing_on_disk:{ident}:{validator}",
        )

        workflow = row.get("workflow")
        _require(
            isinstance(workflow, str) and workflow,
            f"invariant_missing_workflow:{ident}",
        )
        _require(
            (ROOT / workflow).exists(),
            f"invariant_workflow_missing_on_disk:{ident}:{workflow}",
        )

        production = row.get("production_path")
        _require(
            isinstance(production, str) and (ROOT / production).exists(),
            f"invariant_production_path_missing:{ident}:{production}",
        )
        checks += 1
    return checks


def validate_path_trigger_integrity(
    overrides: dict[Path, str] | None = None,
) -> int:
    """A load-bearing trust file must not be able to evade P12 proof."""
    registry = _yaml(REGISTRY, overrides)
    required_paths = registry.get("path_trigger_required") or []
    _require(bool(required_paths), "path_trigger_required_missing")

    workflow_text = _text(P12_WORKFLOW, overrides)
    workflow = yaml.safe_load(workflow_text)
    # PyYAML parses the bare `on:` key as boolean True.
    triggers = workflow.get("on") or workflow.get(True) or {}
    declared: set[str] = set()
    for event in ("pull_request", "push"):
        spec = triggers.get(event) or {}
        for entry in spec.get("paths") or []:
            declared.add(entry)

    checks = 0
    for required in required_paths:
        _require(
            required in declared,
            f"load_bearing_path_not_triggering_p12:{required}",
        )
        checks += 1
    return checks


def validate_no_failure_masking(overrides: dict[Path, str] | None = None) -> int:
    """No B2.5 workflow may mask a failing proof."""
    checks = 0
    workflow_dir = ROOT / ".github/workflows"
    for path in sorted(workflow_dir.glob("b2_5-*.yml")):
        relative = path.relative_to(ROOT)
        text = _text(relative, overrides)
        for token in MASKING_TOKENS:
            _require(
                token not in text,
                f"failure_masking_token_in_workflow:{relative.name}:{token}",
            )
        checks += 1
    _require(checks > 0, "no_b25_workflows_found")
    return checks


def validate_p12_gate_invocation(overrides: dict[Path, str] | None = None) -> int:
    """The P12 workflow must actually invoke P12 validators with controls."""
    text = _text(P12_WORKFLOW, overrides)
    checks = 0
    for validator in P12_VALIDATORS:
        _require(validator in text, f"p12_validator_not_invoked:{validator}")
        checks += 1

    # Negative controls must be requested, not merely available.
    for validator in P12_VALIDATORS[:2]:
        pattern = re.compile(re.escape(validator) + r"\s+--negative-control")
        _require(
            bool(pattern.search(text)),
            f"p12_validator_invoked_without_negative_control:{validator}",
        )
        checks += 1

    # The gate must assert on validator output rather than trusting exit code
    # alone, so a validator that silently stops emitting proof is caught.
    for token in (
        "B25_P12_CONTRACT_PROJECTION_VALIDATION_PASS",
        "B25_P12_TRUST_ISOLATION_VALIDATION_PASS",
        "B25_P12_CI_GATES_VALIDATION_PASS",
        "projection_negative_controls_fired=3",
        "isolation_negative_controls_fired=3",
    ):
        _require(token in text, f"p12_workflow_missing_output_assertion:{token}")
        checks += 1
    return checks


def validate_context_stability(overrides: dict[Path, str] | None = None) -> int:
    """Declared CI contexts must be stable, unique and actually emitted."""
    registry = _yaml(REGISTRY, overrides)
    contexts = registry.get("ci_contexts") or []
    _require(bool(contexts), "ci_contexts_missing")
    _require(len(contexts) == len(set(contexts)), "ci_contexts_ambiguous")

    workflow = yaml.safe_load(_text(P12_WORKFLOW, overrides))
    job_names = {
        job.get("name")
        for job in (workflow.get("jobs") or {}).values()
        if isinstance(job, dict)
    }
    checks = 0
    for context in contexts:
        _require(
            context in job_names,
            f"declared_context_not_emitted_by_workflow:{context}",
        )
        checks += 1
    return checks


def validate_core(overrides: dict[Path, str] | None = None) -> dict[str, int]:
    return {
        "registry_completeness_controls": validate_registry_completeness(overrides),
        "path_trigger_controls": validate_path_trigger_integrity(overrides),
        "failure_masking_controls": validate_no_failure_masking(overrides),
        "gate_invocation_controls": validate_p12_gate_invocation(overrides),
        "context_stability_controls": validate_context_stability(overrides),
    }


def _mutate(path: Path, old: str, new: str) -> dict[Path, str]:
    """Text mutation with a uniqueness proof.

    P12-H23: a replacement that silently matches the wrong occurrence yields a
    control that fires for the wrong reason, or not at all. Refusing ambiguous
    anchors makes that failure loud instead of silent.
    """
    source = _text(path)
    occurrences = source.count(old)
    _require(
        occurrences == 1,
        f"negative_control_anchor_not_unique:{path.name}:{occurrences}",
    )
    return {path: source.replace(old, new, 1)}


def _mutate_workflow_paths_remove(path: Path, target: str) -> dict[Path, str]:
    """Structured YAML mutation: drop a trigger path from every event.

    The same path legitimately appears under both ``pull_request`` and ``push``,
    so a text anchor is ambiguous by construction. Mutating the parsed document
    removes it from all events at once and proves the intended structure changed
    rather than an arbitrary matching line.
    """
    document = yaml.safe_load(_text(path))
    triggers = document.get("on") or document.get(True) or {}
    removed = 0
    for event in ("pull_request", "push"):
        spec = triggers.get(event) or {}
        paths = spec.get("paths") or []
        if target in paths:
            spec["paths"] = [entry for entry in paths if entry != target]
            removed += 1
    _require(
        removed > 0,
        f"negative_control_path_not_present:{path.name}:{target}",
    )
    return {path: yaml.safe_dump(document, sort_keys=False)}


def run_negative_controls() -> int:
    controls: tuple[tuple[str, dict[Path, str], str], ...] = (
        (
            # A load-bearing trust path stops triggering P12.
            "NC-P12-CI-01",
            _mutate_workflow_paths_remove(P12_WORKFLOW, "backend/app/trust/**"),
            "load_bearing_path_not_triggering_p12",
        ),
        (
            # A P12 gate stops requesting negative controls.
            "NC-P12-CI-02",
            _mutate(
                P12_WORKFLOW,
                "python scripts/ci/validate_b25_p12_trust_isolation.py --negative-control",
                "python scripts/ci/validate_b25_p12_trust_isolation.py",
            ),
            "p12_validator_invoked_without_negative_control",
        ),
        (
            # An invariant loses its proof binding.
            "NC-P12-CI-03",
            _mutate(
                REGISTRY,
                "    validator: scripts/ci/validate_b25_p12_trust_isolation.py\n    workflow: .github/workflows/b2_5-p12-ci-gates.yml\n    negative_control: NC-P12-ISO-01",
                "    validator: scripts/ci/validate_b25_p12_does_not_exist.py\n    workflow: .github/workflows/b2_5-p12-ci-gates.yml\n    negative_control: NC-P12-ISO-01",
            ),
            "invariant_validator_missing_on_disk",
        ),
        (
            # Failure masking is reintroduced into a B2.5 workflow.
            "NC-P12-CI-04",
            _mutate(
                P12_WORKFLOW,
                "    runs-on: ubuntu-latest",
                "    runs-on: ubuntu-latest\n    continue-on-error: true",
            ),
            "failure_masking_token_in_workflow",
        ),
    )
    fired = 0
    for name, overrides, expected in controls:
        try:
            validate_core(overrides)
        except B25P12CiGateError as exc:
            reason = str(exc)
            _require(
                reason.startswith(expected),
                f"negative_control_wrong_reason:{name}:expected={expected}:observed={reason[:120]}",
            )
            fired += 1
            continue
        raise B25P12CiGateError(f"negative_control_silent:{name}")
    return fired


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate B2.5-P12 CI proof topology.")
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args(argv)

    try:
        counters = validate_core()
        negative_controls = run_negative_controls() if args.negative_control else 0
        if args.negative_control:
            _require(negative_controls == 4, "ci_gate_negative_control_count_drift")
    except B25P12CiGateError as exc:
        print(f"B25_P12_CI_GATES_VALIDATION_FAIL:{exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"B25_P12_CI_GATES_VALIDATION_FAIL:unexpected:{exc}")
        return 1

    print("B25_P12_CI_GATES_VALIDATION_PASS")
    print(f"required_invariants={REQUIRED_INVARIANT_COUNT}")
    for key, value in counters.items():
        print(f"{key}_passed={value}")
    print(f"ci_gate_negative_controls_fired={negative_controls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
