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
import fnmatch
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = Path("docs/ci/b25_p12_invariant_registry.yaml")
# The P12 proofs are bound into the B2.5-P11 required context rather than a
# dedicated P12 workflow. Reason recorded honestly: creating
# `.github/workflows/b2_5-p12-ci-gates.yml` requires the `workflow` OAuth scope,
# which the available credentials do not carry. Binding here is not a weaker
# outcome for enforcement -- `B2.5-P11 Export Compatibility` is already a
# required status check on protected main, so a composition regression is
# merge-blocking today. It IS a weaker outcome for gate identity: there is no
# separate P12 context yet. That distinction is reported, never blurred.
BINDING_WORKFLOW = Path(".github/workflows/b2_5-p11-export-compatibility.yml")
BINDING_VALIDATOR = Path("scripts/ci/validate_b25_p11_export_compatibility.py")
DEDICATED_WORKFLOW = Path(".github/workflows/b2_5-p12-ci-gates.yml")

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


def _path_covered(required: str, declared: set[str]) -> bool:
    """Glob-aware coverage: `docs/ci/**` covers `docs/ci/thing.yaml`."""
    if required in declared:
        return True
    for pattern in declared:
        if pattern.endswith("/**"):
            if required.startswith(pattern[:-2]):
                return True
        elif fnmatch.fnmatch(required, pattern):
            return True
    return False


def _declared_trigger_paths(overrides: dict[Path, str] | None = None) -> set[str]:
    declared: set[str] = set()
    for path in sorted((ROOT / ".github/workflows").glob("b2_5-*.yml")):
        workflow = yaml.safe_load(_text(path.relative_to(ROOT), overrides))
        # PyYAML parses the bare `on:` key as boolean True.
        triggers = workflow.get("on") or workflow.get(True) or {}
        for event in ("pull_request", "push"):
            spec = triggers.get(event) or {}
            for entry in spec.get("paths") or []:
                declared.add(entry)
    return declared


def validate_path_trigger_integrity(
    overrides: dict[Path, str] | None = None,
) -> int:
    """A load-bearing trust file must not evade ALL relevant required proof.

    P12-G8 is satisfied when a change reaches at least one required B2.5 proof,
    not necessarily every one. Paths that reach none are enumerated in
    `path_trigger_known_gaps` and enforced in both directions, so a gap can
    neither appear silently nor linger after it has been fixed.
    """
    registry = _yaml(REGISTRY, overrides)
    required_paths = registry.get("path_trigger_required") or []
    _require(bool(required_paths), "path_trigger_required_missing")
    known_gaps = {
        row["path"] for row in (registry.get("path_trigger_known_gaps") or [])
    }
    declared = _declared_trigger_paths(overrides)

    checks = 0
    for required in required_paths:
        _require(
            _path_covered(required, declared),
            f"load_bearing_path_not_triggering_p12:{required}",
        )
        checks += 1

    for gap in sorted(known_gaps):
        _require(
            not _path_covered(gap, declared),
            f"known_path_gap_is_actually_covered_remove_it:{gap}",
        )
        checks += 1

    # Any P12 validator that is neither covered nor declared as a gap is a
    # silent evasion.
    for validator in P12_VALIDATORS:
        if not _path_covered(validator, declared):
            _require(
                validator in known_gaps,
                f"uncovered_path_not_declared_as_known_gap:{validator}",
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
    """P12 proofs must be reachable from a required context, not merely exist.

    A validator nobody invokes proves nothing. This asserts the binding chain
    that actually runs in CI today:

        b2_5-p11-export-compatibility.yml   (required status check)
            -> validate_b25_p11_export_compatibility.py
                -> _run_p12_composition_proofs()
                    -> validate_b25_p12_contract_projection.validate_projection
                    -> validate_b25_p12_trust_isolation.validate_core
                    -> validate_b25_p12_trust_isolation.validate_runtime_module_trace
    """
    workflow_text = _text(BINDING_WORKFLOW, overrides)
    binder_text = _text(BINDING_VALIDATOR, overrides)
    checks = 0

    # The binding workflow must actually invoke the binding validator.
    _require(
        str(BINDING_VALIDATOR).replace("\\", "/") in workflow_text,
        "binding_workflow_does_not_invoke_binding_validator",
    )
    checks += 1

    # The binding validator must import and call each P12 proof entry point.
    for module, call in (
        ("validate_b25_p12_contract_projection", "projection.validate_projection()"),
        ("validate_b25_p12_trust_isolation", "isolation.validate_core()"),
        (
            "validate_b25_p12_trust_isolation",
            "isolation.validate_runtime_module_trace()",
        ),
    ):
        _require(
            module in binder_text,
            f"p12_proof_module_not_imported_by_binding_validator:{module}",
        )
        _require(
            call in binder_text,
            f"p12_proof_not_invoked_by_binding_validator:{call}",
        )
        checks += 1

    # The binding must be observable in the gate's own output, so a silently
    # removed call is visible rather than merely absent.
    _require(
        "p12_composition_proofs_passed=" in binder_text,
        "p12_binding_not_observable_in_gate_output",
    )
    checks += 1

    # A failing P12 proof must surface as a P11 gate failure, not be swallowed.
    for reason in ("p12_contract_projection_failed", "p12_trust_isolation_failed"):
        _require(
            reason in binder_text,
            f"p12_proof_failure_not_propagated:{reason}",
        )
        checks += 1

    # Each P12 validator must remain independently runnable with controls.
    for validator in P12_VALIDATORS:
        _require((ROOT / validator).exists(), f"p12_validator_missing:{validator}")
        source = _text(Path(validator), overrides)
        _require(
            "--negative-control" in source,
            f"p12_validator_lacks_negative_control_mode:{validator}",
        )
        checks += 1
    return checks


def validate_context_stability(overrides: dict[Path, str] | None = None) -> int:
    """Declared CI contexts must be stable, unique and actually emitted.

    Only contexts a workflow really emits may be declared. A context that exists
    solely in a registry would be an eligibility claim with nothing behind it,
    which is precisely the conflation P12-G5 forbids.
    """
    registry = _yaml(REGISTRY, overrides)
    contexts = registry.get("ci_contexts") or []
    _require(bool(contexts), "ci_contexts_missing")
    _require(len(contexts) == len(set(contexts)), "ci_contexts_ambiguous")

    emitted: set[str] = set()
    for path in sorted((ROOT / ".github/workflows").glob("b2_5-*.yml")):
        workflow = yaml.safe_load(_text(path.relative_to(ROOT), overrides))
        for job in (workflow.get("jobs") or {}).values():
            if isinstance(job, dict) and job.get("name"):
                emitted.add(job["name"])

    checks = 0
    for context in contexts:
        _require(
            context in emitted,
            f"declared_context_not_emitted_by_any_workflow:{context}",
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
    """Semantic falsifiers for the enforcement topology itself."""
    controls: tuple[tuple[str, dict[Path, str], str], ...] = (
        (
            # A load-bearing path loses its ONLY covering workflow. Anchored to
            # backend/app/api/export.py because the binding workflow is its sole
            # coverage: removing a path that several workflows also declare
            # would leave coverage intact and the control would prove nothing.
            "NC-P12-CI-01",
            _mutate_workflow_paths_remove(
                BINDING_WORKFLOW, "backend/app/api/export.py"
            ),
            "load_bearing_path_not_triggering_p12",
        ),
        (
            # The binding validator stops invoking a P12 proof, so the proof
            # exists but nothing runs it.
            "NC-P12-CI-02",
            _mutate(
                BINDING_VALIDATOR,
                "        isolation.validate_runtime_module_trace()",
                "        pass  # runtime trace removed",
            ),
            "p12_proof_not_invoked_by_binding_validator",
        ),
        (
            # An invariant loses its proof binding.
            "NC-P12-CI-03",
            _mutate(
                REGISTRY,
                "    validator: scripts/ci/validate_b25_p10_trust_api_surface.py",
                "    validator: scripts/ci/validate_b25_p10_does_not_exist.py",
            ),
            "invariant_validator_missing_on_disk",
        ),
        (
            # Failure masking is reintroduced into a B2.5 workflow.
            "NC-P12-CI-04",
            _mutate(
                BINDING_WORKFLOW,
                "    runs-on: ubuntu-latest",
                "    runs-on: ubuntu-latest\n    continue-on-error: true",
            ),
            "failure_masking_token_in_workflow",
        ),
        (
            # A P12 proof failure stops propagating into the bound gate, so a
            # real regression would be swallowed instead of turning CI red.
            "NC-P12-CI-05",
            _mutate(
                BINDING_VALIDATOR,
                'raise B25P11ValidationError(f"p12_contract_projection_failed:{exc}") from exc',
                "pass  # swallowed",
            ),
            "p12_proof_failure_not_propagated",
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
            _require(negative_controls == 5, "ci_gate_negative_control_count_drift")
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
