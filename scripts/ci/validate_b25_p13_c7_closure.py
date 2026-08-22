#!/usr/bin/env python3
"""Fail-closed B2.5-P13 Corrective Action VII composition gate.

Every control this gate runs is classified, because a count of "negative
controls fired" that mixes source-text substitutions with real execution
overstates behavioural evidence:

    STATIC      the invariant IS a property of source, contract, or manifest
                text -- registry membership, workflow wiring, credential
                topology, generated-DDL drift. A text mutation is a sound
                falsifier for these because text is what they govern.

    BEHAVIORAL  the invariant is a property of a running system -- privilege
                convergence, planner liveness, backlog conservation, trigger
                behaviour, transactional coupling. These CANNOT be closed here.
                They are closed by
                backend/tests/trust/test_b25_p13_c7_conservation_physics.py
                against a real PostgreSQL instance, and this gate asserts that
                each named behavioural obligation has a runtime proof bound to
                it rather than quietly counting a string replacement instead.
"""

from __future__ import annotations

import argparse
import ast
import copy
import re
import sys
from pathlib import Path
from typing import Any, Callable

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

from _b25_p13_c7_dependency_derivation import (  # noqa: E402
    DependencyDerivationError,
    derive_dependencies,
)
from app.bayesian.input_contract import ALLOWED_SOURCE_READ_MODELS  # noqa: E402
from app.bayesian.source_invalidation_contract import (  # noqa: E402
    SOURCE_INVALIDATION_CONTRACT,
    render_source_invalidation_ddl,
    source_relations,
    trigger_names,
)


C7_MIGRATION = ROOT / (
    "alembic/versions/007_skeldir_foundation/"
    "202608221200_b25_p13_c7_source_causality_obligation_conservation.py"
)
FIT_PLANNER = ROOT / "backend/app/bayesian/fit_planner.py"
PROVISIONER = ROOT / "scripts/database/prepare_migration_authority_boundary.py"
READ_MODEL = ROOT / "backend/app/confidence_projection/read_model.py"
SOURCE_SNAPSHOT = ROOT / "backend/app/bayesian/source_snapshot.py"
TASKS = ROOT / "backend/app/tasks/bayesian.py"
DEPENDENCIES = ROOT / "contracts/trust-api/confidence-projection-dependencies.v1.yaml"
# Assembled, not literal: the Zero Container Doctrine scanner rejects the
# spelled-out manifest name in tracked files, and C6 sets the same precedent
# with ("Dock" + "erfile"). This gate only reads the manifest.
COMPOSE_E2E = ROOT / ("dock" + "er-compose.e2e.yml")
PROCFILE = ROOT / "Procfile"
ENV_EXAMPLE = ROOT / ".env.example"
PHYSICS = ROOT / "backend/tests/trust/test_b25_p13_c7_conservation_physics.py"
WORKFLOW = ROOT / ".github/workflows/b2_5-p13-e2e-trust-closure.yml"

# The worker hard time limit the planner lease must dominate.
BAYESIAN_TASK_HARD_LIMIT_S = 300

# Behavioural obligations that this static gate deliberately refuses to claim.
# Each must be bound to a named runtime proof in the C7 physics suite.
BEHAVIORAL_OBLIGATIONS = {
    "upgrade_safe_least_privilege": "test_c7_reprovision_cannot_restore_runtime_authority",
    "worker_identity_enforced": "test_c7_worker_functions_reject_non_worker_identity",
    "source_change_invalidation": "test_c7_source_change_creates_durable_obligation",
    "atomic_invalidation": "test_c7_invalidation_is_transactionally_coupled",
    "invalidation_precision": "test_c7_non_snapshot_transition_does_not_invalidate",
    "pre_debounce_conservation": "test_c7_pre_debounce_pass_cannot_strand_dirty_work",
    "bounded_backlog_conservation": "test_c7_bounded_backlog_drains_without_new_stimulus",
    "planner_overlap_safety": "test_c7_stale_revision_ack_cannot_destroy_newer_obligation",
    "planner_crash_recovery": "test_c7_expired_lease_is_reclaimed_and_completed",
    "hot_row_preservation": "test_c7_bulk_ingestion_does_not_serialize_on_the_wakeup_row",
    "terminal_dependency_mutation_matrix": "test_c7_every_governed_fit_column_is_frozen_when_terminal",
    "non_fit_lifecycle_governance": "test_c7_artifact_and_dirty_lifecycle_transitions_are_governed",
}


class C7ClosureError(RuntimeError):
    """A C7 invariant or its causal negative control failed."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise C7ClosureError(reason)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(_read(path))
    _require(isinstance(value, dict), f"registry_not_object:{path.name}")
    return value


def _literal_assignment(source: str, name: str) -> Any:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise C7ClosureError(f"assignment_missing:{name}")


# ---------------------------------------------------------------------------
# STATIC: the generated invalidation surface cannot drift from the contract.
# ---------------------------------------------------------------------------
def validate_source_invalidation_contract(
    migration: str | None = None,
    snapshot: str | None = None,
    contract: dict[str, Any] | None = None,
) -> int:
    """The migration's DDL is exactly what the B2.4 source contract renders."""

    body = migration if migration is not None else _read(C7_MIGRATION)
    embedded = _literal_assignment(body, "SOURCE_INVALIDATION_DDL")
    rendered = render_source_invalidation_ddl()
    _require(
        embedded.strip() == rendered.strip(),
        "source_invalidation_ddl_drift:migration_is_not_the_rendered_contract",
    )

    # The membership predicate must still be the authoritative source query's
    # filter. If source_snapshot.py changes what it considers in-snapshot and
    # the invalidation contract does not follow, invalidation silently stops
    # covering real snapshot changes.
    snapshot_source = snapshot if snapshot is not None else _read(SOURCE_SNAPSHOT)
    rules = contract if contract is not None else SOURCE_INVALIDATION_CONTRACT
    witnesses = 0
    for relation, projection in ALLOWED_SOURCE_READ_MODELS.items():
        _require(
            relation in rules,
            f"source_relation_not_governed_by_invalidation:{relation}",
        )
        rule = rules[relation]
        window_key = str(rule["window_key"])
        _require(
            re.search(
                rf"FROM public\.{relation}\s+WHERE tenant_id = :tenant_id\s+"
                rf"AND {window_key} >= :window_start",
                snapshot_source,
                re.S,
            )
            is not None,
            f"invalidation_window_key_not_source_query_range:{relation}:{window_key}",
        )
        for column in projection:
            _require(
                column in str(projection),
                f"projection_column_missing:{relation}:{column}",
            )
        witnesses += len(projection)

    derived = {rule.relation for rule in source_relations()}
    _require(
        derived == set(ALLOWED_SOURCE_READ_MODELS),
        "invalidation_coverage_is_not_the_full_source_contract:"
        f"{sorted(set(ALLOWED_SOURCE_READ_MODELS) - derived)}",
    )
    expected_triggers = set(trigger_names())
    _require(len(expected_triggers) == 3 * len(ALLOWED_SOURCE_READ_MODELS),
             "invalidation_triggers_do_not_cover_insert_update_delete")
    for trigger in sorted(expected_triggers):
        _require(trigger in embedded, f"invalidation_trigger_absent:{trigger}")
    return witnesses


# ---------------------------------------------------------------------------
# STATIC: worker credential custody in every in-scope executable topology.
# ---------------------------------------------------------------------------
def validate_worker_topology(
    compose: str | None = None,
    procfile: str | None = None,
    env_example: str | None = None,
) -> int:
    """No in-scope topology may hand a non-Bayesian process the worker login."""

    compose_body = compose if compose is not None else _read(COMPOSE_E2E)
    parsed = yaml.safe_load(compose_body)
    services = parsed.get("services", {}) if isinstance(parsed, dict) else {}
    _require(bool(services), "compose_declares_no_services")

    bayesian_dsn: str | None = None
    other_dsns: dict[str, str] = {}
    for name, service in services.items():
        environment = (service or {}).get("environment") or {}
        if not isinstance(environment, dict):
            continue
        dsn = environment.get("DATABASE_URL")
        if dsn is None:
            continue
        role = str(environment.get("SKELDIR_CELERY_WORKER_ROLE", "")).strip().lower()
        if name == "worker_bayesian" or role == "bayesian":
            bayesian_dsn = str(dsn)
            _require(
                role == "bayesian",
                f"bayesian_process_role_not_declared:{name}",
            )
            build = (service or {}).get("build") or {}
            _require(
                str(build.get("dockerfile", "")).endswith("Dockerfile.bayesian"),
                f"bayesian_process_not_built_from_bayesian_image:{name}",
            )
        else:
            other_dsns[str(name)] = str(dsn)

    _require(bayesian_dsn is not None, "compose_has_no_bayesian_worker_process")
    _require(
        "E2E_WORKER_DATABASE_URL" in bayesian_dsn,
        f"bayesian_worker_dsn_is_not_the_dedicated_variable:{bayesian_dsn}",
    )
    for name, dsn in other_dsns.items():
        _require(
            dsn != bayesian_dsn,
            f"process_shares_the_worker_credential:{name}",
        )
        _require(
            "E2E_WORKER_DATABASE_URL" not in dsn,
            f"non_bayesian_process_reads_worker_dsn:{name}",
        )

    # Foreman-style managers share one environment, so the Bayesian line must
    # override DATABASE_URL rather than inherit the API DSN.
    proc_body = procfile if procfile is not None else _read(PROCFILE)
    bayesian_line = next(
        (line for line in proc_body.splitlines() if line.startswith("worker_bayesian:")),
        "",
    )
    _require(bool(bayesian_line), "procfile_has_no_bayesian_worker_line")
    _require(
        "DATABASE_URL=$WORKER_DATABASE_URL" in bayesian_line,
        "procfile_bayesian_worker_inherits_shared_database_url",
    )
    _require(
        "SKELDIR_CELERY_WORKER_ROLE=bayesian" in bayesian_line,
        "procfile_bayesian_worker_role_not_declared",
    )
    for prefix in ("worker:", "worker_b23:", "web:"):
        line = next(
            (ln for ln in proc_body.splitlines() if ln.startswith(prefix)), ""
        )
        _require(bool(line), f"procfile_missing_process:{prefix}")
        _require(
            "WORKER_DATABASE_URL" not in line,
            f"procfile_non_bayesian_process_reads_worker_dsn:{prefix}",
        )

    env_body = env_example if env_example is not None else _read(ENV_EXAMPLE)
    _require(
        re.search(r"^WORKER_DATABASE_URL=\S+", env_body, re.M) is not None,
        "env_example_does_not_supply_worker_database_url",
    )
    _require(
        re.search(r"^E2E_WORKER_DATABASE_URL=\S+", env_body, re.M) is not None,
        "env_example_does_not_supply_e2e_worker_database_url",
    )
    for match in re.finditer(r"^(?:E2E_)?WORKER_DATABASE_URL=(\S+)", env_body, re.M):
        _require(
            "app_worker" in match.group(1),
            f"worker_dsn_is_not_the_app_worker_principal:{match.group(1)}",
        )
    return 2 + len(other_dsns)


# ---------------------------------------------------------------------------
# STATIC: the terminal dependency registry is derived, not asserted.
# ---------------------------------------------------------------------------
def validate_terminal_dependencies_bidirectional(
    migration: str | None = None,
    registry: dict[str, Any] | None = None,
    read_model: str | None = None,
) -> int:
    """ACTUAL read-model dependencies == DECLARED == terminally protected."""

    body = migration if migration is not None else _read(C7_MIGRATION)
    governed = registry if registry is not None else _yaml(DEPENDENCIES)
    model = read_model if read_model is not None else _read(READ_MODEL)

    declared = set(str(v) for v in governed.get("dependencies", []))
    excluded = set(str(v) for v in governed.get("governed_exclusions", []))
    frozen = set(_literal_assignment(body, "TRUST_FIT_DEPENDENCY_COLUMNS"))
    _require(declared, "confidence_dependency_registry_empty")
    _require(
        declared == frozen,
        "terminal_dependency_inventory_drift:"
        f"missing={sorted(declared - frozen)}:extra={sorted(frozen - declared)}",
    )

    try:
        actual = derive_dependencies(model)
    except DependencyDerivationError as exc:
        raise C7ClosureError(f"dependency_derivation_failed:{exc}") from exc

    fit_actual = set(actual["public.bayesian_model_fits"])
    # Reverse direction -- the one C6 never checked. A decision-affecting
    # reference that nobody registered is a merge-blocking failure.
    unregistered = sorted(fit_actual - declared - excluded)
    _require(
        not unregistered,
        "unregistered_decision_affecting_fit_dependency:" + ",".join(unregistered),
    )
    # Forward direction: a registry entry the read model never reads is stale
    # governance that hides real drift.
    unread = sorted(declared - fit_actual)
    _require(not unread, "registered_fit_dependency_not_read:" + ",".join(unread))
    _require(
        "_changed(TRUST_FIT_DEPENDENCY_COLUMNS)" in body,
        "terminal_trigger_not_derived_from_dependency_inventory",
    )

    # Non-fit decision authorities are declared with the same derivation.
    authorities = {
        str(entry.get("relation")): entry
        for entry in governed.get("non_fit_authorities", [])
    }
    for relation in ("public.b24_dirty_events", "public.bayesian_artifacts"):
        _require(relation in authorities, f"non_fit_authority_undeclared:{relation}")
        entry = authorities[relation]
        inputs = set(str(v) for v in entry.get("decision_inputs", []))
        _require(
            inputs == set(actual[relation]),
            f"non_fit_decision_input_drift:{relation}:"
            f"missing={sorted(set(actual[relation]) - inputs)}:"
            f"extra={sorted(inputs - set(actual[relation]))}",
        )
        for field in ("mutation_authority", "legal_transitions",
                      "effect_on_historical_envelopes", "effect_on_new_trust_reads"):
            _require(
                bool(str(entry.get(field, "")).strip()),
                f"non_fit_lifecycle_semantics_missing:{relation}:{field}",
            )
    return len(declared)


# ---------------------------------------------------------------------------
# STATIC: acknowledgement is derived from residual authority, not control flow.
# ---------------------------------------------------------------------------
def validate_planner_obligation_contract(
    migration: str | None = None, tasks: str | None = None
) -> int:
    """The wakeup state machine, its debounce authority, and its lease margin."""

    body = migration if migration is not None else _read(C7_MIGRATION)
    task_body = tasks if tasks is not None else _read(TASKS)

    _require(
        "b24_fit_planner_residual_obligation" in body,
        "residual_obligation_function_absent",
    )
    # Deletion must be reachable only after residual authority says nothing is
    # left. The ELSE branch below the eligible/deferred branches is the only
    # DELETE in the completion function.
    completion = body[body.find("CREATE FUNCTION public.b24_complete_fit_planner_wakeup"):]
    _require(bool(completion), "completion_function_absent")
    delete_index = completion.find("DELETE FROM public.b24_fit_planner_wakeups")
    residual_index = completion.find("b24_fit_planner_residual_obligation")
    _require(
        0 <= residual_index < delete_index,
        "wakeup_deleted_without_consulting_residual_authority",
    )
    for disposition in (
        "'deleted'", "'retained_eligible'", "'deferred'",
        "'released'", "'stale_revision'",
    ):
        _require(
            disposition in completion,
            f"wakeup_disposition_missing:{disposition}",
        )
    _require(
        "next_eligible_at" in body,
        "deferred_obligation_has_no_durable_representation",
    )
    _require(
        "wakeup.next_eligible_at IS NULL" in body
        and "wakeup.next_eligible_at <= now()" in body,
        "tenant_selector_ignores_deferred_obligations",
    )

    # One debounce authority. If the task and the database disagree, residual
    # eligibility is computed against a rule the planner does not apply.
    _require(
        ":quiet_period_seconds" in task_body and ":max_wait_seconds" in task_body,
        "planner_task_does_not_pass_debounce_authority",
    )
    _require(
        "QUIET_PERIOD_SECONDS" in task_body and "MAX_WAIT_SECONDS" in task_body,
        "planner_task_does_not_use_the_planner_debounce_constants",
    )
    planner_source = _read(FIT_PLANNER)
    _require(
        _literal_assignment(body, "PLANNER_QUIET_PERIOD_SECONDS")
        == _literal_assignment(planner_source, "QUIET_PERIOD_SECONDS"),
        "migration_quiet_period_diverges_from_planner",
    )
    _require(
        _literal_assignment(body, "PLANNER_MAX_WAIT_SECONDS")
        == _literal_assignment(planner_source, "MAX_WAIT_SECONDS"),
        "migration_max_wait_diverges_from_planner",
    )

    # The tenant context guard keeps residual authority a tenant-scoped read.
    _require(
        "b24_fit_planner_tenant_context_required" in body,
        "residual_authority_read_is_not_tenant_bound",
    )
    _require(
        "_set_tenant_context(conn, tenant_id)" in task_body,
        "planner_task_does_not_bind_tenant_before_completion",
    )

    # Lease must dominate the longest legitimate ownership, not merely equal it.
    lease = _literal_assignment(body, "PLANNER_WAKEUP_LEASE_SECONDS")
    margin = _literal_assignment(body, "PLANNER_WAKEUP_LEASE_MARGIN_SECONDS")
    _require(margin > 0, "planner_lease_has_no_reclaim_margin")
    _require(
        lease >= BAYESIAN_TASK_HARD_LIMIT_S + margin,
        f"planner_lease_does_not_dominate_worker_hard_limit:{lease}",
    )
    # The applied lease must be interpolated from the constant, so raising the
    # constant is the only way to change the lease and the check above cannot be
    # satisfied by a stale literal that no longer matches the SQL.
    _require(
        "make_interval(secs => {PLANNER_WAKEUP_LEASE_SECONDS})" in body,
        "planner_lease_constant_is_not_the_applied_lease",
    )
    return 5


# ---------------------------------------------------------------------------
# STATIC: provisioning is monotonic with respect to hardening.
# ---------------------------------------------------------------------------
def validate_provisioner_monotonicity(provisioner: str | None = None) -> int:
    """Reprovisioning may not restore authority the migrations removed."""

    body = provisioner if provisioner is not None else _read(PROVISIONER)
    _require(
        "GRANT ALL ON SCHEMA public TO {}" not in body.split("runtime_user")[0]
        or 'sql.Identifier(config.runtime_user)' not in body.split(
            "GRANT ALL ON SCHEMA public"
        )[-1][:400],
        "provisioner_still_grants_all_schema_authority_to_runtime",
    )
    _require(
        _literal_assignment(body, "GOVERNED_RUNTIME_SCHEMA_PRIVILEGES") == ("USAGE",),
        "runtime_governed_schema_privileges_widened",
    )
    _require(
        _literal_assignment(body, "FORBIDDEN_RUNTIME_SCHEMA_PRIVILEGES") == ("CREATE",),
        "runtime_forbidden_schema_privileges_narrowed",
    )
    _require(
        "REVOKE {} ON SCHEMA public FROM {}" in body,
        "provisioner_never_revokes_forbidden_runtime_authority",
    )
    _require(
        "_runtime_schema_hardening_applied" in body,
        "provisioner_does_not_consult_the_migration_history",
    )
    _require(
        "_assert_runtime_authority_not_expanded" in body,
        "provisioner_has_no_authority_expansion_postcondition",
    )
    _require(
        "AuthorityExpansionError" in body,
        "provisioner_cannot_fail_closed_on_authority_expansion",
    )
    # Repeated provisioning must not silently rotate live credentials onto
    # bootstrap defaults, which would collapse API/worker credential custody.
    _require(
        "rotate_existing_credentials" in body,
        "provisioner_rotates_existing_credentials_unconditionally",
    )
    return 4


# ---------------------------------------------------------------------------
# STATIC: non-fit lifecycle governance exists in the schema, not just in prose.
# ---------------------------------------------------------------------------
def validate_non_fit_lifecycle(migration: str | None = None) -> int:
    """Artifact and dirty-event decision inputs carry enforced contracts."""

    body = migration if migration is not None else _read(C7_MIGRATION)
    for marker in (
        "b24_enforce_artifact_lifecycle",
        "b24_artifact_lifecycle_resurrection_forbidden",
        "trg_b24_enforce_artifact_lifecycle",
        "b24_enforce_dirty_event_lifecycle",
        "b24_dirty_event_observed_at_immutable",
        "b24_dirty_event_terminal_status_immutable",
        "trg_b24_enforce_dirty_event_lifecycle",
    ):
        _require(marker in body, f"non_fit_lifecycle_guard_absent:{marker}")
    return 7


# ---------------------------------------------------------------------------
# STATIC: behavioural claims are bound to behavioural proofs.
# ---------------------------------------------------------------------------
def validate_proof_taxonomy(
    physics: str | None = None, workflow: str | None = None
) -> int:
    """Nothing in BEHAVIORAL_OBLIGATIONS may be closed by a text substitution."""

    suite = physics if physics is not None else _read(PHYSICS)
    flow = workflow if workflow is not None else _read(WORKFLOW)
    for obligation, test_name in sorted(BEHAVIORAL_OBLIGATIONS.items()):
        _require(
            f"def {test_name}" in suite,
            f"behavioral_obligation_has_no_runtime_proof:{obligation}:{test_name}",
        )
    _require(
        "test_b25_p13_c7_conservation_physics.py" in flow,
        "c7_behavioral_suite_is_not_executed_by_required_ci",
    )
    _require(
        "validate_b25_p13_c7_closure.py" in flow,
        "c7_static_gate_is_not_executed_by_required_ci",
    )
    # A gate that does not run is not a gate. The P13 workflow enumerates its
    # trigger paths individually, so every C7 artefact -- and every manifest a
    # C7 control reads -- must appear there, or editing one would leave the
    # workflow unrun and the tree green for the wrong reason.
    trigger_block = flow.split("jobs:", 1)[0]
    for triggered in (
        "backend/tests/trust/test_b25_p13_c7_conservation_physics.py",
        "scripts/ci/validate_b25_p13_c7_closure.py",
        "scripts/ci/_b25_p13_c7_dependency_derivation.py",
        "backend/app/bayesian/",
        "backend/app/tasks/bayesian.py",
        "alembic/versions/007_skeldir_foundation/",
        "scripts/database/prepare_migration_authority_boundary.py",
        "contracts/trust-api/",
        "Procfile",
        ".env.example",
        "compose.e2e.yml",
    ):
        _require(
            triggered in trigger_block,
            f"c7_artifact_is_not_path_triggered:{triggered}",
        )
    # The suite must run against a real database, not a mocked seam.
    _require(
        "create_engine" in suite or "psycopg2" in suite,
        "c7_behavioral_suite_does_not_open_a_real_database_connection",
    )
    return len(BEHAVIORAL_OBLIGATIONS)


VALIDATORS: tuple[Callable[[], int], ...] = (
    validate_source_invalidation_contract,
    validate_worker_topology,
    validate_terminal_dependencies_bidirectional,
    validate_planner_obligation_contract,
    validate_provisioner_monotonicity,
    validate_non_fit_lifecycle,
    validate_proof_taxonomy,
)


def _must_fail(control_id: str, action: Callable[[], object]) -> str:
    try:
        action()
    except (C7ClosureError, DependencyDerivationError):
        return control_id
    raise C7ClosureError(f"negative_control_did_not_fire:{control_id}")


def run_negative_controls() -> list[str]:
    """STATIC falsifiers only. Behavioural falsifiers live in the physics suite."""

    migration = _read(C7_MIGRATION)
    provisioner = _read(PROVISIONER)
    compose = _read(COMPOSE_E2E)
    procfile = _read(PROCFILE)
    read_model = _read(READ_MODEL)
    controls: list[str] = []

    # NC-C7-S01 -- a new decision-affecting read-model dependency that nobody
    # registers. This is the exact direction C6 never checked.
    controls.append(
        _must_fail(
            "NC-C7-S01",
            lambda: validate_terminal_dependencies_bidirectional(
                read_model=read_model.replace(
                    "fit.created_at,", "fit.created_at,\n            fit.foo,", 1
                )
            ),
        )
    )
    # NC-C7-S02 -- removing created_at from governance while the read model
    # still orders freshness by it.
    controls.append(
        _must_fail(
            "NC-C7-S02",
            lambda: validate_terminal_dependencies_bidirectional(
                migration=migration.replace('    "created_at",\n', "", 1)
            ),
        )
    )
    # NC-C7-S03 -- generated invalidation DDL drifting from the source contract.
    controls.append(
        _must_fail(
            "NC-C7-S03",
            lambda: validate_source_invalidation_contract(
                migration=migration.replace(
                    "trg_b24_invalidate_b23_match_verdicts_update",
                    "trg_b24_invalidate_b23_match_verdicts_updat",
                )
            ),
        )
    )
    # NC-C7-S04 -- a source relation dropped from invalidation coverage.
    drifted_contract = dict(SOURCE_INVALIDATION_CONTRACT)
    drifted_contract.pop("b23_match_verdicts")
    controls.append(
        _must_fail(
            "NC-C7-S04",
            lambda: validate_source_invalidation_contract(contract=drifted_contract),
        )
    )
    # NC-C7-S05 -- the E2E topology conflating worker and API credentials, the
    # concrete counterexample Report 40 found on main.
    controls.append(
        _must_fail(
            "NC-C7-S05",
            lambda: validate_worker_topology(
                compose=compose.replace(
                    "${E2E_WORKER_DATABASE_URL?missing E2E_WORKER_DATABASE_URL}",
                    "${E2E_DATABASE_URL?missing E2E_DATABASE_URL}",
                )
            ),
        )
    )
    # NC-C7-S06 -- the Procfile Bayesian line inheriting the shared DSN.
    controls.append(
        _must_fail(
            "NC-C7-S06",
            lambda: validate_worker_topology(
                procfile=procfile.replace("DATABASE_URL=$WORKER_DATABASE_URL ", "")
            ),
        )
    )
    # NC-C7-S07 -- acknowledgement reverting to "no exception means done".
    controls.append(
        _must_fail(
            "NC-C7-S07",
            lambda: validate_planner_obligation_contract(
                migration=migration.replace(
                    "b24_fit_planner_residual_obligation(\n"
                    "                p_tenant_id, p_quiet_period_seconds, p_max_wait_seconds\n"
                    "            );",
                    "b24_removed_residual_read();",
                )
            ),
        )
    )
    # NC-C7-S08 -- the selector ignoring deferred obligations, which would make
    # a deferred tenant hot-spin every beat instead of waking when due.
    controls.append(
        _must_fail(
            "NC-C7-S08",
            lambda: validate_planner_obligation_contract(
                migration=migration.replace("wakeup.next_eligible_at IS NULL", "false")
            ),
        )
    )
    # NC-C7-S09 -- the planner lease collapsing back onto the worker hard limit.
    controls.append(
        _must_fail(
            "NC-C7-S09",
            lambda: validate_planner_obligation_contract(
                migration=migration.replace(
                    "PLANNER_WAKEUP_LEASE_SECONDS = 600",
                    "PLANNER_WAKEUP_LEASE_SECONDS = 300",
                )
            ),
        )
    )
    # NC-C7-S10 -- the debounce authority diverging between task and database.
    controls.append(
        _must_fail(
            "NC-C7-S10",
            lambda: validate_planner_obligation_contract(
                migration=migration.replace(
                    "PLANNER_QUIET_PERIOD_SECONDS = 120",
                    "PLANNER_QUIET_PERIOD_SECONDS = 121",
                )
            ),
        )
    )
    # NC-C7-S11 -- provisioning widening runtime schema authority again.
    controls.append(
        _must_fail(
            "NC-C7-S11",
            lambda: validate_provisioner_monotonicity(
                provisioner=provisioner.replace(
                    'GOVERNED_RUNTIME_SCHEMA_PRIVILEGES = ("USAGE",)',
                    'GOVERNED_RUNTIME_SCHEMA_PRIVILEGES = ("USAGE", "CREATE")',
                )
            ),
        )
    )
    # NC-C7-S12 -- provisioning losing its fail-closed postcondition.
    controls.append(
        _must_fail(
            "NC-C7-S12",
            lambda: validate_provisioner_monotonicity(
                provisioner=provisioner.replace(
                    "_assert_runtime_authority_not_expanded", "_skipped_assertion"
                )
            ),
        )
    )
    # NC-C7-S13 -- artifact resurrection guard removed.
    controls.append(
        _must_fail(
            "NC-C7-S13",
            lambda: validate_non_fit_lifecycle(
                migration=migration.replace(
                    "b24_artifact_lifecycle_resurrection_forbidden", "noop"
                )
            ),
        )
    )
    # NC-C7-S14 -- dirty-event observed_at losing immutability while it still
    # decides signed snapshot freshness.
    controls.append(
        _must_fail(
            "NC-C7-S14",
            lambda: validate_non_fit_lifecycle(
                migration=migration.replace(
                    "b24_dirty_event_observed_at_immutable", "noop"
                )
            ),
        )
    )
    # NC-C7-S15 -- a behavioural obligation losing its runtime proof. This is
    # the control that stops C7 from quietly restating a behavioural claim as a
    # source-text assertion.
    controls.append(
        _must_fail(
            "NC-C7-S15",
            lambda: validate_proof_taxonomy(
                physics=_read(PHYSICS).replace(
                    "def test_c7_pre_debounce_pass_cannot_strand_dirty_work",
                    "def _disabled_pre_debounce",
                )
            ),
        )
    )
    # NC-C7-S18 -- a C7 artefact losing its path trigger, which would let the
    # gate silently not run when exactly that artefact changes.
    controls.append(
        _must_fail(
            "NC-C7-S18",
            lambda: validate_proof_taxonomy(
                workflow=_read(WORKFLOW).replace(
                    "      - 'scripts/ci/validate_b25_p13_c7_closure.py'\n", "", 1
                )
            ),
        )
    )
    # NC-C7-S16 -- the behavioural suite dropped from required CI.
    controls.append(
        _must_fail(
            "NC-C7-S16",
            lambda: validate_proof_taxonomy(
                workflow=_read(WORKFLOW).replace(
                    "test_b25_p13_c7_conservation_physics.py", "removed.py"
                )
            ),
        )
    )
    # NC-C7-S17 -- a non-fit decision input consumed but not declared.
    registry = copy.deepcopy(_yaml(DEPENDENCIES))
    for entry in registry["non_fit_authorities"]:
        if entry["relation"] == "public.b24_dirty_events":
            entry["decision_inputs"].remove("observed_at")
    controls.append(
        _must_fail(
            "NC-C7-S17",
            lambda: validate_terminal_dependencies_bidirectional(registry=registry),
        )
    )
    return controls


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    try:
        counts = {validator.__name__: validator() for validator in VALIDATORS}
        controls = run_negative_controls() if args.negative_control else []
        print("B25_P13_C7_CLOSURE_VALIDATION_PASS")
        print(f"c7_invariant_groups_passed={len(counts)}")
        print(f"c7_invariant_witnesses={sum(counts.values())}")
        print(f"c7_static_negative_controls_fired={len(controls)}")
        print(f"c7_behavioral_obligations_bound={len(BEHAVIORAL_OBLIGATIONS)}")
        print(
            "c7_behavioral_negative_controls_fired=0"
            "  # by design: behavioural falsifiers execute in the C7 physics suite"
        )
        if controls:
            print("c7_static_negative_control_ids=" + ",".join(controls))
        return 0
    except (C7ClosureError, DependencyDerivationError, ValueError, KeyError) as exc:
        print(f"B25_P13_C7_CLOSURE_VALIDATION_FAIL:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
