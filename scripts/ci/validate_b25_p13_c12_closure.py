#!/usr/bin/env python3
"""Validate C12 authority closure and merge-governing proof topology."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/"
    "202608261200_b25_p13_c12_authority_closure.py"
)
FIT_EXECUTION = Path("backend/app/bayesian/fit_execution.py")
DISPATCH_OUTBOX = Path("backend/app/bayesian/dispatch_outbox.py")
CANONICAL_SCHEMA = Path("db/schema/canonical_schema.sql")
WORKFLOW = Path(".github/workflows/b2_5-p13-e2e-trust-closure.yml")
C12_TESTS = Path("backend/tests/trust/test_b25_p13_c12_authority_closure.py")

PRIVILEGED_SETTINGS = {
    "app.b24_recovery_reconciler",
    "app.b24_dispatch_claim_access",
    "app.b24_worker_authority_access",
    "app.b24_claim_capability_digest",
    "app.b24_fit_resolution_id",
}
LOAD_BEARING_JOBS = {
    "b25-p13-e2e-trust-closure-core",
    "b2-5-p13-c9-positive-confidence",
    "b2-5-p13-c10-artifact-topology",
    "b2-5-p13-c13-semantic-history",
    "b2-5-p13-c14-semantic-authority",
    # B2.5-P13 Corrective XV: issuance-capability inescapability, durable
    # audit truth, and historical HTTP serviceability are merge-governing.
    "b2-5-p13-c15-issuance-truth",
    # Corrective XVI: physical signature history is conserved in both
    # directions and nullable CHECK semantics are surveyed exhaustively.
    "b2-5-p13-c16-bidirectional-truth",
    # Corrective XVII: completed issuance is an exact projection of durable
    # signer-produced attempt evidence, with reconstructable recovery.
    # Corrective XIX: the full production-topology composition proof
    # (external evidence to public verification) is merge-governing.
    "b2-5-p13-c19-context-robust-closure",
    "b2-5-p13-c17-consequence-lineage",
    # Corrective XX: verdict-authority conservation -- the API principal
    # may not author B2.3 truth -- is merge-governing.
    "b2-5-p13-c20-verdict-authority",
}


class ValidationError(RuntimeError):
    pass


def _read(path: Path) -> str:
    full = ROOT / path
    if not full.is_file():
        raise ValidationError(f"missing required file: {path.as_posix()}")
    return full.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _policy_blocks(schema: str) -> list[str]:
    return re.findall(r"CREATE POLICY\s+.*?;", schema, flags=re.IGNORECASE | re.DOTALL)


def validate_authority_closure(
    *,
    migration_text: str | None = None,
    fit_execution_text: str | None = None,
    outbox_text: str | None = None,
    canonical_text: str | None = None,
) -> None:
    migration = migration_text if migration_text is not None else _read(MIGRATION)
    fit_execution = (
        fit_execution_text if fit_execution_text is not None else _read(FIT_EXECUTION)
    )
    outbox = outbox_text if outbox_text is not None else _read(DISPATCH_OUTBOX)
    canonical = (
        canonical_text if canonical_text is not None else _read(CANONICAL_SCHEMA)
    )
    upgrade = migration.split("def downgrade()", 1)[0]

    for token in (
        "_replace_fit_policies(include_resolution_capability=False)",
        "c12_dispatch_internal_select",
        "c12_recovery_internal_select",
        "c12_worker_authority_internal_select",
        "current_user = 'migration_owner'",
        "session_user = 'app_worker'",
        "b24_lease_fit_recovery_rows",
        "b24_mark_fit_recovery_published",
        "b24_mark_fit_recovery_failed",
        "REVOKE ALL ON public.b24_worker_process_authority",
    ):
        _require(token in upgrade, f"authority closure missing: {token}")

    _require(
        "app.b24_fit_resolution_id" not in fit_execution,
        "fit-id remains caller-minted resolution authority",
    )
    fit_lookup = fit_execution.split("def _load_fit_for_execution", 1)[1].split(
        "\ndef ", 1
    )[0]
    _require(
        "WHERE tenant_id = :tenant_id" in fit_lookup
        and "AND id = :fit_id" in fit_lookup,
        "fit resolution is not tenant-and-fit bound",
    )
    for setting in (
        "app.b24_recovery_reconciler",
        "app.b24_dispatch_claim_access",
    ):
        _require(setting not in outbox, f"application still mints authority: {setting}")

    policies = _policy_blocks(canonical)
    _require(policies, "canonical policy inventory is empty")
    for policy in policies:
        for setting in PRIVILEGED_SETTINGS:
            _require(
                setting not in policy,
                f"caller_minted_policy:{setting}",
            )

    required_policies = {
        "c12_dispatch_internal_select",
        "c12_dispatch_internal_update",
        "c12_recovery_internal_select",
        "c12_recovery_internal_insert",
        "c12_recovery_internal_update",
        "c12_worker_authority_internal_select",
        "c12_worker_authority_internal_insert",
        "c12_worker_authority_internal_update",
    }
    for policy_name in required_policies:
        matching = [block for block in policies if policy_name in block]
        _require(matching, f"canonical authority policy missing:{policy_name}")
        expression = matching[0].lower()
        _require(
            "current_user" in expression and "session_user" in expression,
            f"authority policy lacks authenticated identity:{policy_name}",
        )


def validate_merge_governing_graph(workflow_text: str | None = None) -> None:
    source = workflow_text if workflow_text is not None else _read(WORKFLOW)
    workflow = yaml.safe_load(source)
    jobs = workflow.get("jobs", {}) if isinstance(workflow, dict) else {}
    gate = jobs.get("b25-p13-e2e-trust-closure")
    _require(isinstance(gate, dict), "merge-governing aggregator missing")
    _require(
        gate.get("name") == "B2.5-P13 E2E Trust Closure",
        "merge-governing context name drifted",
    )
    needs = gate.get("needs", [])
    if isinstance(needs, str):
        needs = [needs]
    _require(
        set(needs) == LOAD_BEARING_JOBS,
        "merge-governing aggregator lacks load-bearing dependencies",
    )
    _require(
        gate.get("if") == "always()", "aggregator must evaluate failed dependencies"
    )
    run = "\n".join(
        str(step.get("run", ""))
        for step in gate.get("steps", [])
        if isinstance(step, dict)
    )
    for job in LOAD_BEARING_JOBS:
        _require(job in run, f"aggregator does not assert dependency result:{job}")


def validate_test_surface(test_text: str | None = None) -> None:
    tests = test_text if test_text is not None else _read(C12_TESTS)
    for token in (
        "test_c12_catalog_has_no_self_issued_privileged_policy",
        "test_c12_arbitrary_session_state_has_no_cross_tenant_consequence",
        "test_c12_session_residue_is_inert_and_worker_engine_is_nonpooled",
        "test_c12_bounded_claim_and_recovery_operations_remain_live",
        "test_c12_ordinary_roles_cannot_reach_privilege_transitively",
        "test_c12_competing_workers_preserve_one_producing_regime",
    ):
        _require(token in tests, f"C12 falsifier missing:{token}")


def validate_all() -> None:
    for path in (
        MIGRATION,
        FIT_EXECUTION,
        DISPATCH_OUTBOX,
        CANONICAL_SCHEMA,
        WORKFLOW,
        C12_TESTS,
    ):
        _read(path)
    validate_authority_closure()
    validate_merge_governing_graph()
    validate_test_surface()


def run_negative_controls() -> None:
    canonical = _read(CANONICAL_SCHEMA)
    workflow = _read(WORKFLOW)
    migration = _read(MIGRATION)
    fit_execution = _read(FIT_EXECUTION)
    controls = (
        (
            "alternate_self_issued_policy",
            lambda: validate_authority_closure(
                canonical_text=canonical
                + "\nCREATE POLICY c12_hostile ON public.b24_fit_dispatch_outbox "
                + "USING (current_setting('app.b24_recovery_reconciler', true) = 'on');\n"
            ),
            "caller_minted_policy",
        ),
        (
            "ordinary_role_table_grant",
            lambda: validate_authority_closure(
                migration_text=migration.replace(
                    "REVOKE ALL ON public.b24_worker_process_authority",
                    "GRANT ALL ON public.b24_worker_process_authority",
                    1,
                )
            ),
            "REVOKE ALL",
        ),
        (
            "unbound_fit_lookup",
            lambda: validate_authority_closure(
                fit_execution_text=fit_execution.replace(
                    "WHERE tenant_id = :tenant_id", "WHERE TRUE", 1
                )
            ),
            "tenant-and-fit",
        ),
        (
            "positive_composition_detached",
            lambda: validate_merge_governing_graph(
                workflow.replace("      - b2-5-p13-c9-positive-confidence\n", "", 1)
            ),
            "load-bearing dependencies",
        ),
    )
    fired = 0
    for name, runner, expected in controls:
        try:
            runner()
        except ValidationError as exc:
            _require(
                expected.lower() in str(exc).lower(),
                f"{name} failed for wrong reason:{exc}",
            )
            fired += 1
        else:
            raise ValidationError(f"negative control did not fail:{name}")
    print(f"c12_semantic_negative_controls_fired={fired}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    try:
        validate_all()
        if args.negative_control:
            run_negative_controls()
    except (ValidationError, yaml.YAMLError) as exc:
        print(f"B25_P13_C12_CLOSURE_VALIDATION_FAIL: {exc}")
        return 1
    print("B25_P13_C12_CLOSURE_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
