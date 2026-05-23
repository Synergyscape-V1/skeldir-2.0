#!/usr/bin/env python3
"""Validate B2.4-P3 fit planning, claim, and dispatch outbox safety."""

from __future__ import annotations

import argparse
import ast
import re
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BAYESIAN_PACKAGE = Path("backend/app/bayesian")
DIRTY_MARKER = BAYESIAN_PACKAGE / "dirty_marker.py"
FIT_PLANNER = BAYESIAN_PACKAGE / "fit_planner.py"
FIT_CLAIM = BAYESIAN_PACKAGE / "fit_claim.py"
DISPATCH_OUTBOX = BAYESIAN_PACKAGE / "dispatch_outbox.py"
SOURCE_SNAPSHOT = BAYESIAN_PACKAGE / "source_snapshot.py"
P3_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202605221430_b24_p3_fit_planning_outbox.py"
)
INGESTION = Path("backend/app/ingestion/event_service.py")
ATTRIBUTION_TASKS = Path("backend/app/tasks/attribution.py")
B23_BATCH = Path("backend/app/revenue_verification/batch_engine.py")
BAYESIAN_TASKS = Path("backend/app/tasks/bayesian.py")

REQUIRED_FILES = {
    DIRTY_MARKER,
    FIT_PLANNER,
    FIT_CLAIM,
    DISPATCH_OUTBOX,
    P3_MIGRATION,
}

REQUIRED_TABLES = {
    "b24_dirty_events",
    "b24_active_execution_leases",
    "b24_fit_dispatch_outbox",
}

FORBIDDEN_P3_TOKENS = {
    "pymc",
    "pytensor",
    "arviz",
    "pm.Model",
    "pm.sample",
    "design_matrix",
    "credible_interval",
    "artifact_lifecycle",
    "APIRouter",
    "include_router",
    "app.llm",
    "openai",
    "anthropic",
}

HOT_PATH_FORBIDDEN = {
    "compute_source_snapshot_hash",
    "claim_fit_for_snapshot",
    "dispatch_due_outbox_rows",
    "publish_fit_id_only",
    "celery_app.send_task",
    "app.tasks.bayesian.execute_fit_intent",
}

ACTIVE_KEY_COLUMNS = (
    "tenant_id",
    "model_type",
    "model_version",
    "source_window_start",
    "source_window_end",
)


class ValidationError(RuntimeError):
    pass


def _read(root: Path, path: Path) -> str:
    full = root / path
    if not full.exists():
        raise ValidationError(f"missing required file: {path.as_posix()}")
    return full.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _parse(text: str, rel: Path) -> ast.Module:
    return ast.parse(text, filename=rel.as_posix())


def validate_required_files(root: Path) -> None:
    for path in REQUIRED_FILES:
        _read(root, path)


def validate_dirty_marker(root: Path, text: str | None = None) -> None:
    text = text if text is not None else _read(root, DIRTY_MARKER)
    _require("DIRTY_EVENT_LOW_CONTENTION_POLICY" in text, "dirty contention policy missing")
    _require("append_only_single_insert_v1" in text, "dirty capture must be append-only")
    _require("INSERT INTO public.b24_dirty_events" in text, "dirty event insert missing")
    _require("ON CONFLICT" not in text, "dirty hot path must not compact with ON CONFLICT")
    for token in HOT_PATH_FORBIDDEN:
        _require(token not in text, f"dirty marker calls forbidden hot-path operation: {token}")
    for token in ("raw_payload", "email", "ip_address", "token", "secret"):
        _require(token not in text.lower(), f"dirty marker contains forbidden payload/PII token: {token}")


def validate_hot_paths(root: Path) -> None:
    for path in (INGESTION, ATTRIBUTION_TASKS, B23_BATCH):
        text = _read(root, path)
        _require("append_dirty_event" in text, f"hot path missing dirty append: {path.as_posix()}")
        for token in HOT_PATH_FORBIDDEN:
            _require(token not in text, f"hot path performs forbidden P3 work: {path.as_posix()}:{token}")


def validate_planner(root: Path, text: str | None = None) -> None:
    text = text if text is not None else _read(root, FIT_PLANNER)
    for token in (
        "DEBOUNCE_POLICY_VERSION",
        "QUIET_PERIOD_SECONDS",
        "MAX_WAIT_SECONDS",
        "FOR UPDATE OF dirty SKIP LOCKED",
        "compute_source_snapshot_hash",
        "claim_fit_for_snapshot",
        "upsert_fallback_from_snapshot",
    ):
        _require(token in text, f"planner missing required semantic: {token}")
    _require(
        text.find("lease_debounced_dirty_candidates") < text.find("compute_source_snapshot_hash"),
        "planner must lease/debounce before source snapshot computation",
    )
    _require("status = 'leased'" in text, "planner must lifecycle dirty events through leased")
    for status in ("claimed", "fallback_only", "superseded"):
        _require(status in text, f"planner missing dirty lifecycle status: {status}")


def validate_active_claim(root: Path, text: str | None = None, migration: str | None = None) -> None:
    text = text if text is not None else _read(root, FIT_CLAIM)
    migration = migration if migration is not None else _read(root, P3_MIGRATION)
    _require("b24_active_execution_leases" in text, "active lease table not used")
    _require("source_snapshot_hash" in text, "claim must use source snapshot hash for historical fit")
    _require("needs_refit_after_current" in text, "H2 supersession marker missing")
    _require("active_source_snapshot_hash IS DISTINCT FROM" in text, "new hash active suppression missing")
    _require("INSERT INTO public.b24_fit_dispatch_outbox" in text, "claim must write dispatch outbox")
    _require("ON CONFLICT" in text, "claim must be idempotent under retries")
    pk_match = re.search(
        r"CONSTRAINT\s+b24_active_execution_leases_pkey\s+PRIMARY\s+KEY\s*\((.*?)\)",
        migration,
        re.S,
    )
    _require(pk_match is not None, "active lease primary key missing")
    pk_cols = tuple(re.findall(r"\b[a-z_]+\b", pk_match.group(1)))
    for column in ACTIVE_KEY_COLUMNS:
        _require(column in pk_cols, f"active lease key missing column: {column}")
    _require("source_snapshot_hash" not in pk_cols, "active lease key must not include source_snapshot_hash")


def validate_dispatch_outbox(root: Path, text: str | None = None) -> None:
    text = text if text is not None else _read(root, DISPATCH_OUTBOX)
    for token in (
        "b24_fit_dispatch_outbox",
        "FOR UPDATE SKIP LOCKED",
        "recover_stale_dispatching",
        "dead_lettered",
        "failed_retryable",
        "publish_fit_id_only",
    ):
        _require(token in text, f"dispatch outbox missing semantic: {token}")
    _require('return {"fit_id": str(self.fit_id)}' in text, "queue payload must be fit_id-only")
    for forbidden in ("source_rows", "manifest", "raw_payload", "tenant source data"):
        _require(forbidden not in text.lower(), f"dispatch payload contains forbidden token: {forbidden}")


def validate_migration(root: Path, text: str | None = None) -> None:
    text = text if text is not None else _read(root, P3_MIGRATION)
    for table in REQUIRED_TABLES:
        _require(f"CREATE TABLE public.{table}" in text, f"migration missing table: {table}")
        _require(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in text, f"RLS missing: {table}")
        _require(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY" in text, f"FORCE RLS missing: {table}")
    _require("uq_b24_fit_dispatch_outbox_fit" in text, "outbox fit uniqueness missing")
    _require("uq_b24_fit_dispatch_outbox_dispatch_key" in text, "outbox dispatch key uniqueness missing")
    _require("ck_b24_fit_dispatch_outbox_status" in text, "outbox status check missing")
    _require("idx_b24_dirty_events_tenant_model_window_pending" in text, "dirty coalescing index missing")


def validate_source_query_plan_proof(root: Path) -> None:
    source = _read(root, SOURCE_SNAPSHOT)
    migration = _read(root, Path("alembic/versions/007_skeldir_foundation/202605221200_b24_p2_source_stream_safety_indexes.py"))
    p3_migration = _read(root, P3_MIGRATION)
    for table, index_name in {
        "attribution_events": "idx_b24_p2_attribution_events_source_stream",
        "attribution_allocations": "idx_b24_p2_attribution_allocations_source_stream",
        "b23_match_verdicts": "idx_b24_p2_match_verdicts_source_stream",
        "b23_revenue_events": "idx_b24_p2_revenue_events_source_stream",
    }.items():
        _require(table in source, f"source snapshot query missing table: {table}")
        _require(index_name in migration, f"P2 fallback source index missing: {index_name}")
    for fallback_index in (
        "idx_b24_p3_attribution_events_source_stream_fallback",
        "idx_b24_p3_attribution_allocations_source_stream_fallback",
        "idx_b24_p3_match_verdicts_source_stream_fallback",
        "idx_b24_p3_revenue_events_source_stream_fallback",
    ):
        _require(fallback_index in p3_migration, f"P3 non-partial fallback index missing: {fallback_index}")
    _require("ORDER BY tenant_id ASC" in source, "source queries must keep tenant-leading order")
    _require("id ASC" in source, "source queries must use immutable id tie-breaker")


def validate_scope(root: Path) -> None:
    for path in REQUIRED_FILES | {BAYESIAN_TASKS}:
        text = _read(root, path)
        lowered = text.lower()
        for token in FORBIDDEN_P3_TOKENS:
            _require(token.lower() not in lowered, f"P3 scope violation in {path.as_posix()}: {token}")
    tasks = _read(root, BAYESIAN_TASKS)
    _require("def execute_fit_intent" in tasks, "fit intent worker stub missing")
    _require("fit_id: str" in tasks, "worker stub must accept fit_id only")
    _require("compute_started" in tasks and "False" in tasks, "worker stub must not compute")


def run_all(root: Path) -> None:
    validate_required_files(root)
    validate_dirty_marker(root)
    validate_hot_paths(root)
    validate_planner(root)
    validate_active_claim(root)
    validate_dispatch_outbox(root)
    validate_migration(root)
    validate_source_query_plan_proof(root)
    validate_scope(root)


def run_negative_control(root: Path) -> None:
    def _active_key_regression(_root: Path, _payload: str) -> None:
        validate_active_claim(
            _root,
            claim,
            migration.replace(
                "source_window_end\n            )",
                "source_window_end,\n                source_snapshot_hash\n            )",
                1,
            ),
        )

    checks = []
    dirty = _read(root, DIRTY_MARKER)
    checks.append(("dirty_compaction", validate_dirty_marker, dirty + "\n# ON CONFLICT DO UPDATE\n"))
    planner = _read(root, FIT_PLANNER)
    checks.append(("planner_no_skip_locked", validate_planner, planner.replace("FOR UPDATE OF dirty SKIP LOCKED", "FOR UPDATE OF dirty")))
    claim = _read(root, FIT_CLAIM)
    migration = _read(root, P3_MIGRATION)
    checks.append(("active_key_hash_regression", _active_key_regression, ""))
    outbox = _read(root, DISPATCH_OUTBOX)
    checks.append(("payload_regression", validate_dispatch_outbox, outbox.replace('return {"fit_id": str(self.fit_id)}', 'return {"fit_id": str(self.fit_id), "source_rows": []}')))

    failures = 0
    for name, check, payload in checks:
        try:
            check(root, payload)
        except ValidationError:
            failures += 1
        else:
            raise ValidationError(f"negative control did not fail: {name}")
    _require(failures == len(checks), "not all negative controls failed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    try:
        if args.negative_control:
            run_negative_control(ROOT)
        else:
            run_all(ROOT)
    except ValidationError as exc:
        print(f"B24_P3_FIT_PLANNING_VALIDATION_FAIL: {exc}")
        return 1
    print("B24_P3_FIT_PLANNING_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
