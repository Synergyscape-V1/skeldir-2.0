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
import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = Path("docs/ci/b25_p12_invariant_registry.yaml")
# The P12 proofs run in BOTH the dedicated `B2.5-P12 CI Gates` context and,
# retained deliberately, the `B2.5-P11 Export Compatibility` context. Both are
# required status checks on protected main, so a composition regression is
# merge-blocking on two independent gates rather than one. The earlier comment
# here described a period when the dedicated workflow could not be created for
# lack of the `workflow` OAuth scope; that is no longer true and the stale text
# is removed rather than left to mislead a reader into thinking gate identity is
# still missing.
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


def _resolve_negative_control(ident: object, row: dict) -> None:
    """Prove an invariant's negative control resolves to something executable.

    This check previously read::

        _require(bool(row.get("negative_control")), ...)

    which is satisfied by any non-empty string. Every *other* reference in this
    loop -- validator, workflow, production_path -- is resolved against disk;
    the control alone was checked for truthiness. Two consequences were
    reproduced against protected main:

    * fifteen of twenty-two controls were free-text prose ("p2 ordering/
      permutation mutations"), which can never resolve because it is not the
      name of anything;
    * substituting the invented identifier ``NC-P12-DOES-NOT-EXIST`` left Plane D
      passing with ``registry_completeness_controls_passed=22``.

    A control is now resolved by class, and each class is verified differently
    rather than uniformly asserted:

    ``source_identifier``
        The identifier must literally occur in the named validator's source, so
        the registry row is bound to code rather than to a label.
    ``validator_control_mode``
        The named validator must expose an executable ``--negative-control``
        mode. Granularity is mode-level: this proves the validator has firing
        falsifiers, NOT that one control maps to one domain. The registry records
        that limit instead of implying per-control precision it does not have.
    ``drift_check``
        A regeneration/diff falsifier, which has a command rather than a mode.
    """
    control = row.get("negative_control")
    _require(isinstance(control, dict), f"invariant_control_not_structured:{ident}")
    control_id = control.get("id")
    _require(
        isinstance(control_id, str) and control_id.startswith("NC-"),
        f"invariant_control_missing_id:{ident}:{control_id}",
    )
    resolution = control.get("resolution")
    _require(
        resolution in {"source_identifier", "validator_control_mode", "drift_check"},
        f"invariant_control_unknown_resolution:{ident}:{resolution}",
    )
    target = control.get("resolves_in")
    _require(
        isinstance(target, str) and (ROOT / target).exists(),
        f"invariant_control_target_missing:{ident}:{target}",
    )
    source = (ROOT / target).read_text(encoding="utf-8", errors="replace")

    if resolution == "source_identifier":
        _require(
            control_id in source,
            f"invariant_control_not_executable:{ident}:{control_id}:absent_from:{target}",
        )
    elif resolution == "validator_control_mode":
        _require(
            "--negative-control" in source,
            f"invariant_control_mode_missing:{ident}:{target}",
        )
        _require(
            control.get("granularity") == "mode_level",
            f"invariant_control_granularity_overclaimed:{ident}",
        )
    else:
        _require(
            bool(control.get("falsifier_command")),
            f"invariant_control_missing_falsifier_command:{ident}",
        )


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
        _resolve_negative_control(ident, row)

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


def _invoked_scripts(workflow: str, overrides: dict[Path, str] | None = None) -> set[str]:
    """Scripts a workflow actually invokes in its run steps.

    Reading the run text is deliberate. The alternative -- trusting the registry's
    own ``workflow`` column -- is the defect this function exists to close: the
    column recorded where a proof was *bound* historically, not where it runs.
    """
    path = Path(workflow)
    if not (ROOT / path).exists():
        return set()
    text = _text(path, overrides)
    return set(re.findall(r"(?:scripts|backend/scripts)/[A-Za-z0-9_./-]+\.(?:py|sh)", text))


def validate_inherited_proof_binding(overrides: dict[Path, str] | None = None) -> int:
    """Every invariant's workflow must actually invoke its validator.

    Registry completeness proves the validator and workflow *files exist*. That is
    not enforcement. Reproduced at `bcee1a055`: eight of twenty-two invariants
    named a workflow that never invoked their validator -- seven P12 domains still
    pointed at the binding-era `b2_5-p11-export-compatibility.yml` while those
    validators had moved to the dedicated P12 workflow. The proofs did run, one
    hop deeper through the P11 validator, but the registry asserted an edge that
    did not exist. "P6 passed once" is not P12 enforcement, and neither is a
    workflow column nobody traverses.
    """
    registry = _yaml(REGISTRY, overrides)
    checks = 0
    for row in registry.get("invariants") or []:
        ident = row.get("id")
        validator = row.get("validator")
        workflow = row.get("workflow")
        _require(
            validator in _invoked_scripts(workflow, overrides),
            f"invariant_workflow_does_not_invoke_validator:{ident}:{workflow}:{validator}",
        )
        checks += 1
    _require(
        checks == REQUIRED_INVARIANT_COUNT,
        f"inherited_binding_coverage_incomplete:{checks}",
    )
    return checks


def validate_detector_self_protection(overrides: dict[Path, str] | None = None) -> int:
    """A load-bearing detector must itself be covered by its workflow's triggers.

    An engineer weakening a validator is a change to proof, not to production
    code, so a path-filtered workflow that does not list the validator's own file
    will not run it -- the weakened detector never gets a chance to notice its own
    weakening. Reproduced: three validators were unprotected this way.

    Coverage plus the ``--negative-control`` invocation proven by
    :func:`validate_p12_gate_invocation` gives the real chain: editing a detector
    triggers the workflow, the workflow runs the detector with its falsifiers, and
    a neutered detector makes its own control go silent.
    """
    registry = _yaml(REGISTRY, overrides)
    checks = 0
    for row in registry.get("invariants") or []:
        ident = row.get("id")
        validator = row.get("validator")
        workflow = row.get("workflow")
        declared = _workflow_paths(workflow, overrides)
        _require(
            _path_covered(validator, declared),
            f"detector_not_self_protected:{ident}:{validator}:not_triggered_by:{workflow}",
        )
        checks += 1
    return checks


def _workflow_paths(workflow: str, overrides: dict[Path, str] | None = None) -> set[str]:
    """Trigger paths declared by ONE workflow, across pull_request and push."""
    path = Path(workflow)
    if not (ROOT / path).exists():
        return set()
    spec = yaml.safe_load(_text(path, overrides)) or {}
    triggers = spec.get("on") or spec.get(True) or {}
    declared: set[str] = set()
    for event in ("pull_request", "push"):
        if event not in triggers:
            continue
        event_spec = triggers.get(event) or {}
        if not isinstance(event_spec, dict) or "paths" not in event_spec:
            # No `paths` key means the event is not path-filtered at all, so it
            # covers every file by construction. `branches:` alone does not
            # filter by path -- reading a `branches`-only spec as "no coverage"
            # would report a workflow that runs on every PR as protecting
            # nothing. Required contexts must be unfiltered (H00-I), so this is
            # the normal case rather than an exception.
            declared.add("**")
            continue
        for entry in event_spec.get("paths") or []:
            declared.add(entry)
    return declared


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


def _require_relevant_detector(
    required: str,
    registry: Any,
    overrides: dict[Path, str] | None = None,
) -> int:
    """Prove a load-bearing path reaches the detector RESPONSIBLE for it.

    The previous check flattened trigger paths from every ``b2_5-*.yml`` workflow
    into one set, so a path counted as covered when *any* B2.5 workflow declared
    it -- even a workflow that never runs the validator guarding that path's
    invariant. Editing a canonicalization file could satisfy path-trigger
    integrity by way of an unrelated broad workflow while the canonicalization
    proof itself never ran.

    Relevance is derived from the registry rather than hand-maintained in a second
    list: a path's relevant detectors are the validators of the invariants whose
    ``production_path`` the path matches. Coverage must come from a workflow that
    both declares the path AND invokes those detectors.
    """
    relevant: set[str] = set()
    for row in registry.get("invariants") or []:
        production = row.get("production_path") or ""
        if not production:
            continue
        if production == required or fnmatch.fnmatch(production, required):
            validator = row.get("validator")
            if validator:
                relevant.add(validator)
    if not relevant:
        return 0

    reaching: set[str] = set()
    for workflow_path in sorted((ROOT / ".github/workflows").glob("b2_5-*.yml")):
        rel = workflow_path.relative_to(ROOT).as_posix()
        if not _path_covered(required, _workflow_paths(rel, overrides)):
            continue
        reaching |= _invoked_scripts(rel, overrides)

    missing = sorted(relevant - reaching)
    _require(
        not missing,
        f"load_bearing_path_reaches_no_relevant_detector:{required}:{missing}",
    )
    return len(relevant)


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
        checks += _require_relevant_detector(required, registry, overrides)

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
        "inherited_binding_controls": validate_inherited_proof_binding(overrides),
        "detector_self_protection_controls": validate_detector_self_protection(overrides),
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


def _mutate_workflow_paths_remove(target: str) -> dict[Path, str]:
    """Structured YAML mutation: drop a trigger path from EVERY B2.5 workflow.

    Removing it from a single workflow is not a falsifier: several workflows
    declare the same load-bearing paths, so coverage survives and the control
    goes silent. That happened twice while building this gate. The invariant
    under test is "this path reaches at least one required proof", so the
    mutation must remove every route to it.

    Mutating the parsed document rather than matching text also avoids the
    ambiguity of a path that legitimately appears under both `pull_request` and
    `push` (P12-H23).
    """
    overrides: dict[Path, str] = {}
    removed_total = 0
    for path in sorted((ROOT / ".github/workflows").glob("b2_5-*.yml")):
        relative = path.relative_to(ROOT)
        document = yaml.safe_load(_text(relative))
        triggers = document.get("on") or document.get(True) or {}
        removed_here = 0
        for event in ("pull_request", "push"):
            spec = triggers.get(event) or {}
            paths = spec.get("paths") or []
            if target in paths:
                spec["paths"] = [entry for entry in paths if entry != target]
                removed_here += 1
        if removed_here:
            overrides[relative] = yaml.safe_dump(document, sort_keys=False)
            removed_total += removed_here
    _require(
        removed_total > 0,
        f"negative_control_path_not_present_in_any_workflow:{target}",
    )
    return overrides


def _mutate_p12_workflow_excluding_detector() -> dict[Path, str]:
    """Narrow the P12 workflow's triggers so they no longer cover its own detector.

    Structured YAML rather than text substitution: an unfiltered ``pull_request``
    covers every path by construction, so a control that only stripped the push
    path would leave the property satisfied and fire silently. Both events are
    narrowed to a path set that deliberately omits the isolation validator.
    """
    spec = yaml.safe_load((ROOT / DEDICATED_WORKFLOW).read_text(encoding="utf-8"))
    triggers = spec.get("on") or spec.get(True) or {}
    kept = [
        entry
        for entry in (triggers.get("push") or {}).get("paths") or []
        if "validate_b25_p12_trust_isolation" not in entry
    ]
    triggers["pull_request"] = {"paths": list(kept)}
    triggers["push"] = {"branches": ["main"], "paths": list(kept)}
    if True in spec:
        spec[True] = triggers
    else:
        spec["on"] = triggers
    return {DEDICATED_WORKFLOW: yaml.safe_dump(spec, sort_keys=False, width=200)}


def run_negative_controls() -> int:
    """Semantic falsifiers for the enforcement topology itself."""
    controls: tuple[tuple[str, dict[Path, str], str], ...] = (
        (
            # A load-bearing path loses coverage across every B2.5 workflow.
            "NC-P12-CI-01",
            _mutate_workflow_paths_remove("backend/app/api/export.py"),
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
                "  validator: scripts/ci/validate_b25_p10_trust_api_surface.py",
                "  validator: scripts/ci/validate_b25_p10_does_not_exist.py",
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
        (
            # H00-F: an invariant points at a workflow that never runs its
            # validator. This is the shape the registry was actually in --
            # seven P12 domains named the binding-era P11 workflow while their
            # validators had moved to the dedicated P12 gate.
            "NC-P12-CI-06",
            _mutate(
                REGISTRY,
                "  workflow: .github/workflows/b2_5-p12-ci-gates.yml\n"
                "  negative_control:\n"
                "    id: NC-P12-ISO-01",
                "  workflow: .github/workflows/b2_5-p9-machine-identity.yml\n"
                "  negative_control:\n"
                "    id: NC-P12-ISO-01",
            ),
            "invariant_workflow_does_not_invoke_validator",
        ),
        (
            # H00-H: the detector stops being reachable by its own workflow's
            # triggers, so weakening it would not run it. Both events must be
            # narrowed: an unfiltered `pull_request` covers every file, so
            # removing only the push path would leave the property intact and
            # the control silent.
            "NC-P12-CI-07",
            _mutate_p12_workflow_excluding_detector(),
            "detector_not_self_protected",
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
            # Seven: five original, plus NC-P12-CI-06 (inherited proof binding)
            # and NC-P12-CI-07 (detector self-protection), added when H00-F
            # and H00-H were closed. Asserted exactly so a deleted control is
            # a failure rather than a smaller number nobody reads.
            _require(negative_controls == 7, "ci_gate_negative_control_count_drift")
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
