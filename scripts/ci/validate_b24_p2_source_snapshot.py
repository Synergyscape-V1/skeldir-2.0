#!/usr/bin/env python3
"""Validate B2.4-P2 deterministic source snapshot implementation."""

from __future__ import annotations

import argparse
import ast
import hashlib
import re
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BAYESIAN_PACKAGE = Path("backend/app/bayesian")
INPUT_CONTRACT = BAYESIAN_PACKAGE / "input_contract.py"
ELIGIBILITY = BAYESIAN_PACKAGE / "eligibility.py"
SOURCE_SNAPSHOT = BAYESIAN_PACKAGE / "source_snapshot.py"
REPOSITORY = BAYESIAN_PACKAGE / "repository.py"
MODELS = BAYESIAN_PACKAGE / "models.py"
ENUMS = BAYESIAN_PACKAGE / "enums.py"
P2_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202605211430_b24_p2_sparse_fallback_reasons.py"
)
CANONICAL_SCHEMA = Path("db/schema/canonical_schema.sql")
COMPLETION_REPORT = Path(
    "docs/forensics/B2.4-P2_Deterministic_Input_Contract_Source_Snapshot_Completion_Report.md"
)

REQUIRED_FILES = {
    INPUT_CONTRACT,
    ELIGIBILITY,
    SOURCE_SNAPSHOT,
    P2_MIGRATION,
}

FORBIDDEN_SCOPE_TOKENS = {
    "dirty_marker",
    "fit_planner",
    "fit_claim",
    "pymc",
    "pytensor",
    "arviz",
    "pm.Model",
    "pm.sample",
    "diagnostics",
    "projection",
    "artifact_lifecycle",
    "APIRouter",
    "include_router",
    "app.llm",
    "openai",
    "anthropic",
    "Celery",
    "send_task",
    "delay(",
    "apply_async",
}

IDENTITY_TABLES = {
    "attribution_commerce_identities",
    "webhook_ingress_identities",
}

PII_TOKENS = {
    "email",
    "phone",
    "ip_address",
    "user_agent",
    "raw_payload",
    "oauth",
    "token",
    "secret",
}

SENTINEL_REASONS = {
    "source_window_empty",
    "insufficient_data",
    "insufficient_privacy_cohort",
}


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


def _literal_assignment(tree: ast.Module, name: str) -> object:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    value = node.value
                    if (
                        isinstance(value, ast.Call)
                        and isinstance(value.func, ast.Name)
                        and value.func.id == "MappingProxyType"
                        and value.args
                    ):
                        value = value.args[0]
                    return ast.literal_eval(value)
    raise ValidationError(f"missing literal assignment: {name}")


def validate_input_contract(root: Path, text: str | None = None) -> None:
    text = text if text is not None else _read(root, INPUT_CONTRACT)
    tree = _parse(text, INPUT_CONTRACT)
    _require("SOURCE_CONTRACT_VERSION" in text, "source contract version missing")
    _require("ELIGIBILITY_POLICY_VERSION" in text, "eligibility policy version missing")
    _require("SparsePrivacyThresholds" in text, "sparse privacy thresholds missing")
    _require(
        "REPEATABLE READ" in text and "READ ONLY" in text,
        "transaction requirements missing",
    )
    _require("app.current_tenant_id" in text, "tenant GUC requirement missing")
    _require(
        "VERIFICATION_COVERAGE_RULE" in text and "excluded_in_b24_source_v1" in text,
        "verification coverage rule missing",
    )

    allowed = _literal_assignment(tree, "ALLOWED_SOURCE_READ_MODELS")
    _require(
        isinstance(allowed, dict), "allowed source read models must be literal mapping"
    )
    for table in IDENTITY_TABLES:
        _require(
            table not in allowed,
            f"identity table is an allowed manifest source: {table}",
        )
    for required in (
        "attribution_events",
        "attribution_allocations",
        "b23_match_verdicts",
        "b23_revenue_events",
    ):
        _require(
            required in allowed,
            f"missing allowed sanitized source read model: {required}",
        )
    for source_name, fields in allowed.items():
        lowered_fields = " ".join(str(field).lower() for field in fields)
        for token in PII_TOKENS:
            _require(
                token not in lowered_fields,
                f"manifest field contains forbidden privacy token {token}: {source_name}",
            )
        _require(
            "native_event_reference" not in lowered_fields,
            f"provider native event ref forbidden: {source_name}",
        )
        _require(
            "native_commerce_reference" not in lowered_fields,
            f"provider native commerce ref forbidden: {source_name}",
        )
    _require("id ASC" in text, "total ordering must include immutable id tie-breaker")
    _require("NULLS" in text, "total ordering must include explicit NULL handling")
    for reason in SENTINEL_REASONS:
        _require(
            reason in text,
            f"sentinel fallback category missing from contract: {reason}",
        )


def _validate_no_forbidden_scope(text: str, rel: Path) -> None:
    lowered = text.lower()
    for token in FORBIDDEN_SCOPE_TOKENS:
        token_lower = token.lower()
        if token_lower in lowered:
            raise ValidationError(
                f"P2 scope containment violation in {rel.as_posix()}: {token}"
            )


def _validate_no_identity_query(text: str, rel: Path) -> None:
    lowered = text.lower()
    for table in IDENTITY_TABLES:
        _require(
            table not in lowered,
            f"identity table must not be queried or serialized in {rel.as_posix()}: {table}",
        )
    for token in PII_TOKENS:
        _require(
            token not in lowered,
            f"PII/token field must not be queried or serialized in {rel.as_posix()}: {token}",
        )


def validate_eligibility(root: Path, text: str | None = None) -> None:
    text = text if text is not None else _read(root, ELIGIBILITY)
    _validate_no_forbidden_scope(text, ELIGIBILITY)
    _validate_no_identity_query(text, ELIGIBILITY)
    _require("COUNT" in text.upper(), "preflight must use aggregate counts")
    _require(
        "count(DISTINCT" in text or "count(distinct" in text.lower(),
        "preflight must count distinct source features/events",
    )
    _require("sum(" in text.lower(), "preflight must aggregate amount by currency")
    _require(
        "min(" in text.lower() and "max(" in text.lower(),
        "preflight must compute source window min/max timestamps",
    )
    _require(
        "run_eligibility_preflight" in text, "aggregate preflight function missing"
    )
    _require(
        "stream_source_chunks" not in text,
        "eligibility must not call manifest/source streaming",
    )
    _require(
        "fetchall" not in text and ".all()" not in text,
        "eligibility must not full-materialize source rows",
    )
    for reason in SENTINEL_REASONS:
        _require(reason in text, f"preflight missing fallback classification: {reason}")


def validate_source_snapshot(root: Path, text: str | None = None) -> None:
    text = text if text is not None else _read(root, SOURCE_SNAPSHOT)
    _validate_no_forbidden_scope(text, SOURCE_SNAPSHOT)
    _validate_no_identity_query(text, SOURCE_SNAPSHOT)
    _require(
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY" in text,
        "missing repeatable-read read-only transaction",
    )
    _require(
        "set_config" in text and "app.current_tenant_id" in text,
        "missing tenant GUC binding/check",
    )
    compute_pos = text.find("async def compute_source_snapshot_hash")
    _require(compute_pos >= 0, "source snapshot compute function missing")
    compute_text = text[compute_pos:]
    preflight_pos = compute_text.find("run_eligibility_preflight")
    stream_pos = compute_text.find("stream_source_chunks")
    _require(
        preflight_pos >= 0 and stream_pos >= 0 and preflight_pos < stream_pos,
        "preflight must precede source streaming",
    )
    _require("session.stream" in text, "source hashing must use streaming cursor API")
    _require(
        "hashlib.sha256" in text and ".update(" in text,
        "hashing must update SHA-256 incrementally",
    )
    _require(
        "json.dumps(" in text and "sort_keys=True" in text and "separators=(" in text,
        "canonical JSON row encoding missing",
    )
    _require(
        "full_manifest" not in text and "json.dumps(full" not in text,
        "full manifest JSON serialization forbidden",
    )
    _require(
        "list(rows)" not in text and "fetchall" not in text and ".all()" not in text,
        "full source materialization forbidden",
    )
    for order_fragment in (
        "ORDER BY tenant_id ASC, occurred_at ASC NULLS LAST, id ASC",
        "ORDER BY tenant_id ASC, created_at ASC NULLS LAST, id ASC",
        "ORDER BY tenant_id ASC, last_transition_at ASC NULLS LAST, id ASC",
        "ORDER BY tenant_id ASC, event_occurred_at ASC NULLS LAST, id ASC",
    ):
        _require(
            order_fragment in text,
            f"source stream missing total order: {order_fragment}",
        )
    _require(
        "sentinel_material_for(preflight.fallback_reason)" in text
        and "SENTINEL_PREFIX" in text,
        "sentinel hash protocol missing",
    )
    for reason in SENTINEL_REASONS:
        material = (
            "B24_SOURCE_SNAPSHOT_SENTINEL"
            "|source_contract_version=b24-source-v1"
            "|eligibility_policy_version=b24-eligibility-v1"
            f"|fallback_reason={reason}"
        )
        expected_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
        _require(
            re.fullmatch(r"[a-f0-9]{64}", expected_hash) is not None,
            f"invalid sentinel hash for {reason}",
        )


def validate_repository(root: Path, text: str | None = None) -> None:
    text = text if text is not None else _read(root, REPOSITORY)
    _require(
        "upsert_fallback_from_snapshot" in text,
        "fallback upsert repository method missing",
    )
    _require(
        "ON CONFLICT" in text and "DO UPDATE SET" in text,
        "fallback debounce must use ON CONFLICT DO UPDATE",
    )
    for marker in (
        "sampling_started_at = NULL",
        "last_fit_at = NULL",
        "runtime_seconds = NULL",
        "n_samples_actual = NULL",
        "artifact_ref = NULL",
        "artifact_hash = NULL",
    ):
        _require(
            marker in text,
            f"cold-start fallback must clear compute/artifact marker: {marker}",
        )
    _validate_no_forbidden_scope(text, REPOSITORY)


def validate_schema_surface(root: Path) -> None:
    migration = _read(root, P2_MIGRATION)
    canonical = _read(root, CANONICAL_SCHEMA)
    models = _read(root, MODELS)
    enums = _read(root, ENUMS)
    for reason in SENTINEL_REASONS:
        _require(reason in migration, f"P2 migration missing fallback reason: {reason}")
        _require(
            reason in canonical, f"canonical schema missing fallback reason: {reason}"
        )
        _require(reason in models, f"ORM model missing fallback reason: {reason}")
        _require(reason in enums, f"enum missing fallback reason: {reason}")


def validate_all(root: Path) -> None:
    for path in REQUIRED_FILES:
        _read(root, path)
    validate_input_contract(root)
    validate_eligibility(root)
    validate_source_snapshot(root)
    validate_repository(root)
    validate_schema_surface(root)


def run_negative_controls(root: Path) -> None:
    contract = _read(root, INPUT_CONTRACT)
    eligibility = _read(root, ELIGIBILITY)
    snapshot = _read(root, SOURCE_SNAPSHOT)
    repository = _read(root, REPOSITORY)
    controls = (
        (
            "B24_P2_NC_IDENTITY_TABLE_MANIFEST_SOURCE_PASS",
            lambda: validate_input_contract(
                root,
                contract.replace(
                    '"b23_revenue_events": (',
                    '"webhook_ingress_identities": ("id", "tenant_id"),\n        "b23_revenue_events": (',
                    1,
                ),
            ),
            "identity table",
        ),
        (
            "B24_P2_NC_MANIFEST_CONTAINS_EMAIL_OR_IP_PASS",
            lambda: validate_input_contract(
                root,
                contract.replace('"currency",', '"email",\n            "currency",', 1),
            ),
            "privacy token",
        ),
        (
            "B24_P2_NC_ELIGIBILITY_AFTER_MANIFEST_FETCH_PASS",
            lambda: validate_source_snapshot(
                root,
                snapshot.replace(
                    "preflight = await run_eligibility_preflight",
                    "pre_stream = stream_source_chunks\n        preflight = await run_eligibility_preflight",
                    1,
                ),
            ),
            "preflight must precede",
        ),
        (
            "B24_P2_NC_SPLIT_OR_READ_COMMITTED_SNAPSHOT_PASS",
            lambda: validate_source_snapshot(
                root,
                snapshot.replace(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
                    "SET TRANSACTION READ WRITE",
                    1,
                ),
            ),
            "repeatable-read",
        ),
        (
            "B24_P2_NC_TIMESTAMP_ONLY_ORDER_PASS",
            lambda: validate_source_snapshot(
                root,
                snapshot.replace(
                    "ORDER BY tenant_id ASC, occurred_at ASC NULLS LAST, id ASC",
                    "ORDER BY occurred_at ASC",
                    1,
                ),
            ),
            "total order",
        ),
        (
            "B24_P2_NC_SPARSE_PRIVACY_STREAMED_PASS",
            lambda: validate_eligibility(
                root,
                eligibility.replace(
                    "insufficient_privacy_cohort", "sparse_stream_allowed"
                ),
            ),
            "insufficient_privacy_cohort",
        ),
        (
            "B24_P2_NC_COLD_START_HASH_CHANGES_WITH_SPARSE_NOISE_PASS",
            lambda: validate_source_snapshot(
                root,
                snapshot.replace(
                    "sentinel_material_for(preflight.fallback_reason)",
                    "str(preflight.included_row_counts_by_source)",
                    1,
                ),
            ),
            "sentinel",
        ),
        (
            "B24_P2_NC_COLD_START_SETS_LAST_FIT_PASS",
            lambda: validate_repository(
                root,
                repository.replace("last_fit_at = NULL", "last_fit_at = now()", 1),
            ),
            "last_fit_at = NULL",
        ),
        (
            "B24_P2_NC_UNBOUNDED_JSON_DUMPS_PASS",
            lambda: validate_source_snapshot(
                root, snapshot + "\nfull_manifest = []\njson.dumps(full_manifest)\n"
            ),
            "full manifest",
        ),
        (
            "B24_P2_NC_IMPORTS_PYMC_OR_LLM_PASS",
            lambda: validate_source_snapshot(
                root,
                snapshot + "\nimport pymc\nfrom app.llm.provider_boundary import x\n",
            ),
            "scope containment",
        ),
    )
    for label, runner, expected in controls:
        try:
            runner()
        except ValidationError as exc:
            _require(
                expected.lower() in str(exc).lower(),
                f"{label} failed for wrong reason: {exc}",
            )
            print(label)
        else:
            raise ValidationError(f"negative control did not fail: {label}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    validate_all(ROOT)
    if args.negative_control:
        run_negative_controls(ROOT)
    print("B24_P2_SOURCE_SNAPSHOT_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
